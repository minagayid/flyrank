from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit

from .config import Settings
from .db import connect, digest, json_dump, load_json, migrate, utc_now
from .seed import WIDGET_ID
from .services import DevSwitches, GeoEnricher, TokenBucketLimiter
from .validation import (
    ApiError,
    require_object,
    text,
    validate_idempotency_key,
    validate_submission_envelope,
    validate_submission_values,
    validate_widget,
)
from .worker import NotificationWorker


_WIDGET_ID = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


class Application:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.limiter = TokenBucketLimiter(settings.rate_bucket_capacity, settings.rate_refill_per_second)
        self.ip_admission_limiter = TokenBucketLimiter(
            settings.ip_admission_bucket_capacity,
            settings.ip_admission_refill_per_second,
        )
        self.switches = DevSwitches(
            geo_a_down=settings.mock_geo_a_down,
            geo_b_down=settings.mock_geo_b_down,
            notification_fail=settings.mock_notification_fail,
        )
        self.geo = GeoEnricher(self.switches)
        self.worker = NotificationWorker(settings, self.switches)
        self.server: ThreadingHTTPServer | None = None

    def cors_headers(self) -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Idempotency-Key",
            "Access-Control-Max-Age": "600",
            "Vary": "Origin",
        }


class ApiHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "LeadCapture/1.0"
    sys_version = ""

    @property
    def app(self) -> Application:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, format_string: str, *args) -> None:
        # Do not log request bodies, paths, email addresses, IPs, or auth tokens.
        return

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_OPTIONS(self) -> None:
        self._dispatch("OPTIONS")

    def _dispatch(self, method: str) -> None:
        try:
            path = urlsplit(self.path).path
            if method == "OPTIONS":
                self._options(path)
                return
            if method == "GET":
                self._get(path)
                return
            if method == "POST":
                self._post(path)
                return
            if method == "PUT":
                self._put(path)
                return
            if method == "DELETE":
                self._delete(path)
                return
            self._send_error(405, "method_not_allowed", "Method is not allowed")
        except ApiError as exc:
            if exc.close:
                self.close_connection = True
            self._send_error(exc.status, exc.code, exc.message)
        except Exception as exc:
            print(f"ERROR request failed route={urlsplit(self.path).path} type={type(exc).__name__}")
            self._send_error(500, "internal_error", "The request could not be completed")

    def _public_request(self) -> bool:
        path = urlsplit(self.path).path
        return path.startswith("/api/public/") or bool(re.fullmatch(r"/widget\.v[1-9][0-9]*\.js", path))

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "no-store",
        }
        if self._public_request():
            headers.update(self.app.cors_headers())
        if extra:
            headers.update(extra)
        return headers

    def _send_bytes(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        for key, value in self._headers(extra).items():
            self.send_header(key, value)
        if self.close_connection:
            self.send_header("Connection", "close")
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _send_json(self, status: int, value: object, extra: dict[str, str] | None = None) -> None:
        self._send_bytes(status, json_dump(value).encode("utf-8"), "application/json; charset=utf-8", extra)

    def _send_error(self, status: int, code: str, message: str) -> None:
        self._send_json(status, {"error": {"code": code, "message": message}})

    def _read_json(self) -> dict:
        if self.headers.get("Transfer-Encoding"):
            raise ApiError(400, "unsupported_transfer_encoding", "Chunked request bodies are not supported")
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise ApiError(415, "content_type_required", "Content-Type must be application/json")
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ApiError(411, "content_length_required", "Content-Length is required")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ApiError(400, "invalid_content_length", "Content-Length is invalid", close=True) from exc
        if length < 0:
            raise ApiError(400, "invalid_content_length", "Content-Length is invalid", close=True)
        if length > self.app.settings.max_request_bytes:
            raise ApiError(413, "payload_too_large", f"Request body must be at most {self.app.settings.max_request_bytes} bytes", close=True)
        data = self.rfile.read(length)
        if len(data) != length:
            raise ApiError(400, "incomplete_body", "Request body ended before Content-Length", close=True)
        try:
            value = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
            raise ApiError(400, "invalid_json", "Request body must be valid UTF-8 JSON") from exc
        return require_object(value, "request body")

    def _owner(self) -> str:
        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            raise ApiError(401, "unauthorized", "A valid owner bearer token is required")
        token = authorization[len(prefix):]
        if not 16 <= len(token) <= 200:
            raise ApiError(401, "unauthorized", "A valid owner bearer token is required")
        token_hash = digest(token)
        with connect(self.app.settings) as connection:
            row = connection.execute("SELECT token_hash, tenant_id FROM api_tokens WHERE token_hash=?", (token_hash,)).fetchone()
        if row is None or not hmac.compare_digest(row["token_hash"], token_hash):
            raise ApiError(401, "unauthorized", "A valid owner bearer token is required")
        return str(row["tenant_id"])

    def _get_widget(self, tenant_id: str, widget_id: str, *, include_deleted: bool = False):
        deleted_clause = "" if include_deleted else " AND deleted_at IS NULL"
        with connect(self.app.settings) as connection:
            row = connection.execute(
                f"SELECT * FROM widgets WHERE id=? AND tenant_id=?{deleted_clause}",
                (widget_id, tenant_id),
            ).fetchone()
        if row is None:
            raise ApiError(404, "not_found", "Widget was not found")
        return row

    @staticmethod
    def _widget_public(row) -> dict:
        return {
            "id": row["id"],
            "type": row["type"],
            "title": row["title"],
            "description": row["description"],
            "fields": load_json(row["fields_json"]),
            "button_text": row["button_text"],
            "display": load_json(row["display_json"]),
            "enabled": bool(row["enabled"]),
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def _options(self, path: str) -> None:
        if path.startswith("/api/public/") or path == f"/widget.{self.app.settings.widget_bundle_version}.js":
            self._send_bytes(204, b"", "text/plain; charset=utf-8", self.app.cors_headers())
            return
        self._send_error(405, "method_not_allowed", "CORS preflight is available only on public widget routes")

    def _get(self, path: str) -> None:
        if path == "/health":
            self._send_json(200, {"status": "ok", "service": "lead-capture", "version": "1.0.0"})
            return
        if path == "/dashboard":
            data = (self.app.settings.root / "static" / "dashboard.html").read_bytes()
            self._send_bytes(200, data, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
            return
        if path == f"/widget.{self.app.settings.widget_bundle_version}.js":
            query = parse_qs(urlsplit(self.path).query)
            widget_id = query.get("widget_id", [""])[0]
            if not _WIDGET_ID.fullmatch(widget_id):
                raise ApiError(400, "widget_id_required", "A valid widget_id query parameter is required")
            with connect(self.app.settings) as connection:
                row = connection.execute("SELECT id FROM widgets WHERE id=? AND enabled=1 AND deleted_at IS NULL", (widget_id,)).fetchone()
            if row is None:
                raise ApiError(404, "not_found", "Widget was not found")
            data = (self.app.settings.root / "static" / "widget.js").read_bytes()
            self._send_bytes(
                200,
                data,
                "application/javascript; charset=utf-8",
                {"Cache-Control": "public, max-age=31536000, immutable", "Cross-Origin-Resource-Policy": "cross-origin"},
            )
            return
        public_config = re.fullmatch(r"/api/public/widgets/([A-Za-z0-9_-]{3,64})/config", path)
        if public_config:
            widget_id = public_config.group(1)
            with connect(self.app.settings) as connection:
                row = connection.execute(
                    "SELECT * FROM widgets WHERE id=? AND enabled=1 AND deleted_at IS NULL",
                    (widget_id,),
                ).fetchone()
            if row is None:
                raise ApiError(404, "not_found", "Widget was not found")
            config = {
                "id": row["id"],
                "type": row["type"],
                "title": row["title"],
                "description": row["description"],
                "fields": load_json(row["fields_json"]),
                "button_text": row["button_text"],
                "display": load_json(row["display_json"]),
            }
            body = json_dump(config).encode("utf-8")
            etag = '"' + hashlib.sha256(body).hexdigest()[:24] + '"'
            headers = {"Cache-Control": "public, max-age=60, stale-while-revalidate=30", "ETag": etag}
            if self.headers.get("If-None-Match") == etag:
                self._send_bytes(304, b"", "application/json; charset=utf-8", headers)
            else:
                self._send_bytes(200, body, "application/json; charset=utf-8", headers)
            return
        if path == "/api/widgets":
            tenant_id = self._owner()
            with connect(self.app.settings) as connection:
                rows = connection.execute(
                    "SELECT * FROM widgets WHERE tenant_id=? AND deleted_at IS NULL ORDER BY updated_at DESC",
                    (tenant_id,),
                ).fetchall()
            self._send_json(200, {"widgets": [self._widget_public(row) for row in rows]})
            return
        if path == "/api/dashboard/summary":
            tenant_id = self._owner()
            since = (datetime.now(timezone.utc) - timedelta(days=6)).date().isoformat()
            with connect(self.app.settings) as connection:
                total = connection.execute("SELECT COUNT(*) AS n FROM submissions WHERE tenant_id=?", (tenant_id,)).fetchone()["n"]
                daily = connection.execute(
                    "SELECT substr(created_at,1,10) AS day, COUNT(*) AS count FROM submissions "
                    "WHERE tenant_id=? AND substr(created_at,1,10)>=? GROUP BY day ORDER BY day",
                    (tenant_id, since),
                ).fetchall()
                by_widget = connection.execute(
                    "SELECT w.id AS widget_id, w.title, COUNT(s.id) AS count FROM widgets w "
                    "LEFT JOIN submissions s ON s.widget_id=w.id AND s.tenant_id=w.tenant_id "
                    "WHERE w.tenant_id=? AND w.deleted_at IS NULL GROUP BY w.id,w.title ORDER BY count DESC,w.title",
                    (tenant_id,),
                ).fetchall()
                by_country = connection.execute(
                    "SELECT COALESCE(country,'Unenriched') AS country, COUNT(*) AS count FROM submissions "
                    "WHERE tenant_id=? GROUP BY country ORDER BY count DESC,country LIMIT 12",
                    (tenant_id,),
                ).fetchall()
            self._send_json(200, {
                "total_submissions": total,
                "daily": [dict(row) for row in daily],
                "by_widget": [dict(row) for row in by_widget],
                "by_country": [dict(row) for row in by_country],
            })
            return
        if path == "/api/dashboard/jobs":
            tenant_id = self._owner()
            with connect(self.app.settings) as connection:
                rows = connection.execute(
                    "SELECT id, submission_id, status, attempts, last_error, created_at, updated_at "
                    "FROM notification_jobs WHERE tenant_id=? ORDER BY created_at DESC LIMIT 30",
                    (tenant_id,),
                ).fetchall()
            self._send_json(200, {"jobs": [dict(row) for row in rows]})
            return
        if path == "/api/dev/geo" or path == "/api/dev/notification":
            tenant_id = self._owner()
            if not self.app.settings.allow_dev_controls:
                raise ApiError(404, "not_found", "Developer controls are disabled")
            self._send_json(200, {"tenant_id": tenant_id, "switches": self.app.switches.get()})
            return
        if path.startswith("/api/widgets/"):
            tenant_id = self._owner()
            parts = path.strip("/").split("/")
            if len(parts) < 3 or not _WIDGET_ID.fullmatch(parts[2]):
                raise ApiError(404, "not_found", "Route was not found")
            widget_id = parts[2]
            include_deleted = len(parts) == 4 and parts[3] == "submissions"
            row = self._get_widget(tenant_id, widget_id, include_deleted=include_deleted)
            if len(parts) == 3:
                self._send_json(200, {"widget": self._widget_public(row)})
                return
            if len(parts) == 4 and parts[3] == "embed":
                snippet = (
                    f'<script defer src="{self.app.settings.public_base_url}/widget.'
                    f'{self.app.settings.widget_bundle_version}.js?widget_id={widget_id}"></script>'
                )
                self._send_json(200, {"widget_id": widget_id, "snippet": snippet})
                return
            if len(parts) == 4 and parts[3] == "submissions":
                query = parse_qs(urlsplit(self.path).query)
                try:
                    limit = int(query.get("limit", ["50"])[0])
                except ValueError as exc:
                    raise ApiError(400, "invalid_limit", "limit must be an integer from 1 to 100") from exc
                if not 1 <= limit <= 100:
                    raise ApiError(400, "invalid_limit", "limit must be an integer from 1 to 100")
                with connect(self.app.settings) as connection:
                    rows = connection.execute(
                        "SELECT id, widget_id, fields_json, origin, country, country_code, city, geo_provider, created_at "
                        "FROM submissions WHERE tenant_id=? AND widget_id=? ORDER BY created_at DESC LIMIT ?",
                        (tenant_id, widget_id, limit),
                    ).fetchall()
                self._send_json(200, {"submissions": [self._submission_public(row) for row in rows]})
                return
        raise ApiError(404, "not_found", "Route was not found")

    @staticmethod
    def _submission_public(row) -> dict:
        return {
            "id": row["id"],
            "widget_id": row["widget_id"],
            "fields": load_json(row["fields_json"]),
            "origin": row["origin"],
            "geo": {
                "country": row["country"],
                "country_code": row["country_code"],
                "city": row["city"],
                "provider": row["geo_provider"],
            } if row["country"] else None,
            "created_at": row["created_at"],
        }

    def _post(self, path: str) -> None:
        if path == "/api/public/submissions":
            self._submit_public()
            return
        if path == "/api/widgets":
            tenant_id = self._owner()
            payload = validate_widget(self._read_json())
            widget_id = "w_" + secrets.token_urlsafe(12).replace("-", "").replace("_", "")
            now = utc_now()
            with connect(self.app.settings) as connection:
                connection.execute(
                    "INSERT INTO widgets(id,tenant_id,type,title,description,fields_json,button_text,display_json,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (widget_id, tenant_id, payload["type"], payload["title"], payload["description"], json_dump(payload["fields"]), payload["button_text"], json_dump(payload["display"]), now, now),
                )
                row = connection.execute("SELECT * FROM widgets WHERE id=? AND tenant_id=?", (widget_id, tenant_id)).fetchone()
            self._send_json(201, {"widget": self._widget_public(row)})
            return
        if path == "/api/dev/geo":
            self._owner()
            if not self.app.settings.allow_dev_controls:
                raise ApiError(404, "not_found", "Developer controls are disabled")
            payload = require_object(self._read_json(), "developer controls")
            allowed = {"provider_a_down", "provider_b_down"}
            if not payload or set(payload) - allowed or any(not isinstance(value, bool) for value in payload.values()):
                raise ApiError(422, "invalid_controls", "Set provider_a_down and/or provider_b_down to boolean values")
            current = self.app.switches.get()
            updates = dict(current)
            if "provider_a_down" in payload:
                updates["geo_a_down"] = payload["provider_a_down"]
            if "provider_b_down" in payload:
                updates["geo_b_down"] = payload["provider_b_down"]
            state = self.app.switches.update(**updates)
            self._send_json(200, {"switches": state})
            return
        if path == "/api/dev/notification":
            self._owner()
            if not self.app.settings.allow_dev_controls:
                raise ApiError(404, "not_found", "Developer controls are disabled")
            payload = require_object(self._read_json(), "developer controls")
            if set(payload) != {"fail"} or not isinstance(payload["fail"], bool):
                raise ApiError(422, "invalid_controls", "Set fail to a boolean value")
            state = self.app.switches.update(notification_fail=payload["fail"])
            self._send_json(200, {"switches": state})
            return
        raise ApiError(404, "not_found", "Route was not found")

    def _put(self, path: str) -> None:
        match = re.fullmatch(r"/api/widgets/([A-Za-z0-9_-]{3,64})", path)
        if not match:
            raise ApiError(404, "not_found", "Route was not found")
        tenant_id = self._owner()
        widget_id = match.group(1)
        payload = validate_widget(self._read_json())
        now = utc_now()
        with connect(self.app.settings) as connection:
            cursor = connection.execute(
                "UPDATE widgets SET type=?,title=?,description=?,fields_json=?,button_text=?,display_json=?,version=version+1,updated_at=? "
                "WHERE id=? AND tenant_id=? AND deleted_at IS NULL",
                (payload["type"], payload["title"], payload["description"], json_dump(payload["fields"]), payload["button_text"], json_dump(payload["display"]), now, widget_id, tenant_id),
            )
            if cursor.rowcount != 1:
                raise ApiError(404, "not_found", "Widget was not found")
            row = connection.execute("SELECT * FROM widgets WHERE id=? AND tenant_id=?", (widget_id, tenant_id)).fetchone()
        self._send_json(200, {"widget": self._widget_public(row)})

    def _delete(self, path: str) -> None:
        match = re.fullmatch(r"/api/widgets/([A-Za-z0-9_-]{3,64})", path)
        if not match:
            raise ApiError(404, "not_found", "Route was not found")
        tenant_id = self._owner()
        now = utc_now()
        with connect(self.app.settings) as connection:
            cursor = connection.execute(
                "UPDATE widgets SET enabled=0,deleted_at=?,updated_at=? WHERE id=? AND tenant_id=? AND deleted_at IS NULL",
                (now, now, match.group(1), tenant_id),
            )
        if cursor.rowcount != 1:
            raise ApiError(404, "not_found", "Widget was not found")
        self._send_json(200, {"deleted": True, "widget_id": match.group(1), "data_retained": True})

    def _submit_public(self) -> None:
        remote_ip = self.client_address[0]
        allowed, retry_after = self.app.ip_admission_limiter.allow([f"ip-admission:{remote_ip}"])
        if not allowed:
            seconds = max(1, int(retry_after + 0.999))
            self._send_json(429, {"error": {"code": "rate_limited", "message": "Please slow down and try again"}}, {"Retry-After": str(seconds)})
            return
        payload = validate_submission_envelope(self._read_json())
        idem_key = validate_idempotency_key(self.headers.get("Idempotency-Key"))
        with connect(self.app.settings) as connection:
            widget = connection.execute(
                "SELECT * FROM widgets WHERE id=? AND enabled=1 AND deleted_at IS NULL",
                (payload["widget_id"],),
            ).fetchone()
        if widget is None:
            raise ApiError(404, "not_found", "Widget was not found")
        fields = validate_submission_values(load_json(widget["fields_json"]), payload["fields"])
        normalized = json_dump({"widget_id": payload["widget_id"], "fields": fields})
        fingerprint = digest(normalized)
        existing = self._existing_submission(widget["tenant_id"], widget["id"], idem_key)
        if existing is not None:
            if not hmac.compare_digest(existing["request_fingerprint"], fingerprint):
                raise ApiError(409, "idempotency_conflict", "Idempotency-Key was already used with a different submission")
            self._send_json(200, {"accepted": True, "submission_id": existing["id"], "idempotent_replay": True})
            return
        allowed, retry_after = self.app.limiter.allow([f"widget:{widget['id']}"])
        if not allowed:
            seconds = max(1, int(retry_after + 0.999))
            self._send_json(429, {"error": {"code": "rate_limited", "message": "Please slow down and try again"}}, {"Retry-After": str(seconds)})
            return
        if payload["company_website"]:
            self._send_json(201, {
                "accepted": True,
                "submission_id": "sub_" + uuid.uuid4().hex,
                "idempotent_replay": False,
                "geo": None,
                "notification": "queued",
            })
            return
        origin = self.headers.get("Origin", "")[:300] or None
        geo = self.app.geo.enrich(remote_ip)
        submission_id = "sub_" + uuid.uuid4().hex
        job_id = "job_" + uuid.uuid4().hex
        now = utc_now()
        ip_digest = hmac.new(self.app.settings.ip_hash_salt.encode("utf-8"), remote_ip.encode("utf-8"), hashlib.sha256).hexdigest()
        with connect(self.app.settings) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT id,request_fingerprint FROM submissions WHERE tenant_id=? AND widget_id=? AND idempotency_key=?",
                (widget["tenant_id"], widget["id"], idem_key),
            ).fetchone()
            if existing:
                connection.execute("COMMIT")
                if not hmac.compare_digest(existing["request_fingerprint"], fingerprint):
                    raise ApiError(409, "idempotency_conflict", "Idempotency-Key was already used with a different submission")
                self._send_json(200, {"accepted": True, "submission_id": existing["id"], "idempotent_replay": True})
                return
            connection.execute(
                "INSERT INTO submissions(id,tenant_id,widget_id,idempotency_key,request_fingerprint,fields_json,origin,ip_digest,country,country_code,city,geo_provider,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (submission_id, widget["tenant_id"], widget["id"], idem_key, fingerprint, json_dump(fields), origin, ip_digest,
                 geo.get("country") if geo else None, geo.get("country_code") if geo else None,
                 geo.get("city") if geo else None, geo.get("provider") if geo else None, now),
            )
            connection.execute(
                "INSERT INTO notification_jobs(id,tenant_id,submission_id,dedupe_key,status,attempts,available_at,created_at,updated_at) "
                "VALUES (?,?,?,?,'queued',0,?,?,?)",
                (job_id, widget["tenant_id"], submission_id, f"confirmation:{submission_id}", time.time(), now, now),
            )
            connection.execute("COMMIT")
        self._send_json(201, {
            "accepted": True,
            "submission_id": submission_id,
            "idempotent_replay": False,
            "geo": geo,
            "notification": "queued",
        })

    def _existing_submission(self, tenant_id: str, widget_id: str, key: str):
        with connect(self.app.settings) as connection:
            return connection.execute(
                "SELECT id,request_fingerprint FROM submissions WHERE tenant_id=? AND widget_id=? AND idempotency_key=?",
                (tenant_id, widget_id, key),
            ).fetchone()


class DemoHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory: str, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format_string: str, *args) -> None:
        return


def run() -> None:
    settings = Settings.from_env()
    migrate(settings)
    app = Application(settings)
    worker = app.worker
    worker.start()
    handler = ApiHandler
    api_server = ThreadingHTTPServer((settings.api_host, settings.api_port), handler)
    api_server.daemon_threads = True
    api_server.app = app  # type: ignore[attr-defined]
    app.server = api_server
    demo_handler = lambda *args, **kwargs: DemoHandler(*args, directory=str(settings.root / "demo"), **kwargs)
    demo_server = ThreadingHTTPServer((settings.demo_host, settings.demo_port), demo_handler)
    demo_server.daemon_threads = True
    demo_thread = Thread(target=demo_server.serve_forever, name="demo-site", daemon=True)
    demo_thread.start()
    print(f"API ready at http://{settings.api_host}:{settings.api_port}")
    print(f"Second-origin demo at http://{settings.demo_host}:{settings.demo_port}/")
    print(f"Owner dashboard at {settings.public_base_url}/dashboard")
    try:
        api_server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping local demo service")
    finally:
        api_server.shutdown()
        demo_server.shutdown()
        worker.stop()
        api_server.server_close()
        demo_server.server_close()


if __name__ == "__main__":
    run()
