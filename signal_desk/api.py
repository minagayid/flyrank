from __future__ import annotations

import json
import re
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from signal_desk.config import MAX_BODY_BYTES
from signal_desk.database import reader
from signal_desk.leads import ValidationError, create_lead, get_lead, list_leads
from signal_desk.reports import daily_report
from signal_desk.security import authenticate, login, revoke
from signal_desk.triage import enqueue, get_job, queue_depth

KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict[str, str] | None = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.fields = fields


class SignalDeskHandler(BaseHTTPRequestHandler):
    server_version = "SignalDesk/0.1"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:
        # Default logs include paths and can accidentally retain query data.
        return

    def _send_json(self, status: int, payload: dict[str, Any], extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, error: ApiError) -> None:
        body: dict[str, Any] = {"error": {"code": error.code, "message": str(error)}}
        if error.fields:
            body["error"]["fields"] = error.fields
        self._send_json(error.status, body)

    def _read_json(self) -> Any:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ApiError(411, "content_length_required", "Provide a Content-Length header.")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ApiError(400, "invalid_content_length", "Content-Length must be an integer.") from exc
        if length < 0:
            raise ApiError(400, "invalid_content_length", "Content-Length cannot be negative.")
        if length > MAX_BODY_BYTES:
            raise ApiError(413, "body_too_large", "The JSON request is too large.")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(400, "invalid_json", "Request body must be valid UTF-8 JSON.") from exc

    def _current_user(self) -> tuple[dict[str, Any], str]:
        header = self.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.casefold() != "bearer" or not token:
            raise ApiError(401, "authentication_required", "Sign in and provide a Bearer token.")
        user = authenticate(token)
        if user is None:
            raise ApiError(401, "invalid_session", "The session is invalid or expired.")
        return user, token

    def _dispatch(self, method: str) -> None:
        try:
            parsed = urlsplit(self.path)
            path = parsed.path
            segments = [unquote(part) for part in path.split("/") if part]

            if method == "GET" and path == "/health":
                with reader() as connection:
                    version = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()["version"]
                self._send_json(200, {"status": "ok", "database": "ok", "migration": version, "queue_depth": queue_depth()})
                return

            if method == "POST" and path == "/auth/login":
                payload = self._read_json()
                if not isinstance(payload, dict) or set(payload) != {"username", "password"}:
                    raise ApiError(422, "invalid_login", "Provide only username and password.")
                username, password = payload["username"], payload["password"]
                if not isinstance(username, str) or not isinstance(password, str):
                    raise ApiError(422, "invalid_login", "Username and password must be text.")
                if not 1 <= len(username) <= 80 or not 1 <= len(password) <= 256:
                    raise ApiError(422, "invalid_login", "Username or password length is outside the accepted range.")
                result = login(username, password)
                if result is None:
                    raise ApiError(401, "invalid_credentials", "Username or password was not accepted.")
                self._send_json(200, result)
                return

            if method == "GET" and path == "/reports/daily.pdf":
                user, _ = self._current_user()
                query = parse_qs(parsed.query)
                date_value = query.get("date", [None])[0]
                try:
                    day = date.fromisoformat(date_value) if date_value else None
                except ValueError as exc:
                    raise ApiError(422, "invalid_date", "Use a calendar date in YYYY-MM-DD format.") from exc
                body = daily_report(user["id"], day)
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Disposition", 'attachment; filename="signal-desk-daily.pdf"')
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return

            user, token = self._current_user()
            if method == "GET" and path == "/auth/me":
                self._send_json(200, {"user": user})
                return
            if method == "POST" and path == "/auth/logout":
                revoke(token)
                self._send_json(200, {"status": "signed_out"})
                return
            if method == "GET" and path == "/leads":
                self._send_json(200, {"items": list_leads(user["id"])})
                return
            if method == "POST" and path == "/leads":
                payload = self._read_json()
                self._send_json(201, {"lead": create_lead(user["id"], payload)})
                return
            if len(segments) == 2 and segments[0] == "leads" and method == "GET":
                lead = get_lead(user["id"], segments[1])
                if lead is None:
                    raise ApiError(404, "lead_not_found", "No lead exists for this account and ID.")
                self._send_json(200, {"lead": lead})
                return
            if len(segments) == 3 and segments[0] == "leads" and segments[2] == "triage" and method == "POST":
                key = self.headers.get("Idempotency-Key", "")
                if not KEY_PATTERN.fullmatch(key):
                    raise ApiError(400, "idempotency_key_required", "Provide a 1–200 character Idempotency-Key using letters, numbers, . _ : or -.")
                job, replayed = enqueue(user["id"], segments[1], key)
                if job is None:
                    raise ApiError(404, "lead_not_found", "No lead exists for this account and ID.")
                if "error" in job:
                    raise ApiError(409, "idempotency_key_reused", "This key was already used for a different request.")
                self._send_json(
                    202,
                    {"job_id": job["id"], "status": job["status"], "replayed": replayed},
                    {"Location": f"/jobs/{job['id']}"},
                )
                return
            if len(segments) == 2 and segments[0] == "jobs" and method == "GET":
                job = get_job(user["id"], segments[1])
                if job is None:
                    raise ApiError(404, "job_not_found", "No job exists for this account and ID.")
                self._send_json(200, {"job": job})
                return
            raise ApiError(404, "route_not_found", f"No {method} route matches this path.")
        except ApiError as error:
            self._send_error(error)
        except ValidationError as error:
            self._send_error(ApiError(422, "validation_error", str(error), error.fields))
        except BrokenPipeError:
            return
        except Exception:
            # Do not return exception text that could contain personal data or credentials.
            self._send_error(ApiError(500, "internal_error", "The request could not be completed."))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")


class SignalDeskHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(host: str, port: int) -> SignalDeskHTTPServer:
    return SignalDeskHTTPServer((host, port), SignalDeskHandler)
