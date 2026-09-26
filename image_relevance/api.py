"""Dependency-free JSON HTTP API built on the Python standard library."""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .config import (
    CONFIDENCE_THRESHOLD,
    COST_BUDGET_USD,
    DATABASE_PATH,
    HOST,
    MAX_JOB_RETRIES,
    EMBEDDING_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_EMBEDDING_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    PORT,
    SIMILARITY_THRESHOLD,
)
from .database import Database
from .jobs import JobManager
from .repository import Repository
from .service import MatchingService, ServiceError


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class Application:
    def __init__(
        self,
        database_path: str,
        similarity_threshold: float,
        confidence_threshold: float,
        cost_budget: float,
        max_retries: int,
        embedding_provider: str,
        ollama_base_url: str,
        ollama_model: str,
        ollama_timeout_seconds: float,
    ) -> None:
        self.database = Database(database_path)
        self.database.initialize()
        self.repository = Repository(self.database)
        self.repository.ensure_tenant("demo")
        self.service = MatchingService(self.repository, similarity_threshold, confidence_threshold)
        self.jobs = JobManager(
            self.repository,
            confidence_threshold,
            cost_budget,
            max_retries,
            embedding_provider=embedding_provider,
            ollama_base_url=ollama_base_url,
            ollama_model=ollama_model,
            ollama_timeout_seconds=ollama_timeout_seconds,
        )


def make_handler(app: Application) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ImageRelevance/0.1"

        def log_message(self, format: str, *args: object) -> None:
            # Keep server logs small and avoid echoing request bodies or arbitrary headers.
            sys.stderr.write("%s %s\n" % (self.log_date_time_string(), format % args))

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _error(self, error: ApiError | ServiceError) -> None:
            self._send(error.status, {"error": {"code": error.code, "message": str(error)}})

        def _tenant(self) -> str:
            tenant = self.headers.get("X-Tenant-ID", "demo")
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant):
                raise ApiError(400, "invalid_tenant", "X-Tenant-ID must use 1-64 letters, digits, underscores, or hyphens")
            self.server.app.repository.ensure_tenant(tenant)  # type: ignore[attr-defined]
            return tenant

        def _body(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                raise ApiError(411, "length_required", "Content-Length is required")
            try:
                length = int(raw_length)
            except ValueError as exc:
                raise ApiError(400, "invalid_content_length", "Content-Length must be an integer") from exc
            if length <= 0 or length > 1_000_000:
                raise ApiError(413, "invalid_body_size", "JSON body must be between 1 byte and 1 MB")
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise ApiError(415, "unsupported_media_type", "Content-Type must be application/json")
            try:
                value = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ApiError(400, "invalid_json", "Request body is not valid UTF-8 JSON") from exc
            if not isinstance(value, dict):
                raise ApiError(400, "invalid_body", "JSON request body must be an object")
            return value

        def _idempotency_key(self) -> str:
            key = self.headers.get("Idempotency-Key", "")
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key):
                raise ApiError(400, "idempotency_key_required", "Provide an Idempotency-Key header (1-128 safe characters)")
            return key

        def _segments(self) -> tuple[list[str], dict[str, list[str]]]:
            parsed = urlsplit(self.path)
            segments = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
            return segments, parse_qs(parsed.query, keep_blank_values=False)

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name
            try:
                tenant = self._tenant()
                segments, query = self._segments()
                repo = self.server.app.repository  # type: ignore[attr-defined]
                if segments == ["health"]:
                    self._send(200, {"status": "ok", "service": "image-relevance", "tenant_scope": "header"})
                    return
                if segments == ["openapi.json"]:
                    self._send(200, openapi_document())
                    return
                if segments == ["images"]:
                    images = repo.list_images(tenant)
                    self._send(200, {"tenant_id": tenant, "count": len(images), "images": [public_image(item) for item in images]})
                    return
                if len(segments) == 2 and segments[0] == "images":
                    image = repo.get_image(tenant, segments[1])
                    if image is None:
                        raise ApiError(404, "image_not_found", "Image was not found for this tenant")
                    self._send(200, public_image(image))
                    return
                if segments == ["posts"]:
                    posts = repo.list_posts(tenant)
                    self._send(200, {"tenant_id": tenant, "count": len(posts), "posts": [public_post(item) for item in posts]})
                    return
                if len(segments) == 3 and segments[0] == "posts" and segments[2] == "images":
                    candidate_id = query.get("candidate_id", [None])[0]
                    self._send(200, self.server.app.service.recommendations(tenant, segments[1], candidate_id))  # type: ignore[attr-defined]
                    return
                if len(segments) == 3 and segments[0] == "posts" and segments[2] == "suggestions":
                    post = repo.get_post(tenant, segments[1])
                    if post is None:
                        raise ApiError(404, "post_not_found", "Post was not found for this tenant")
                    self._send(200, {"post_id": segments[1], "suggestions": repo.list_suggestions(tenant, segments[1])})
                    return
                if segments == ["jobs"]:
                    self._send(200, {"tenant_id": tenant, "jobs": repo.list_jobs(tenant)})
                    return
                if len(segments) == 2 and segments[0] == "jobs":
                    job = repo.get_job(tenant, segments[1])
                    if job is None:
                        raise ApiError(404, "job_not_found", "Job was not found for this tenant")
                    self._send(200, job)
                    return
                if segments == ["costs"]:
                    try:
                        limit = int(query.get("limit", ["200"])[0])
                    except ValueError as exc:
                        raise ApiError(400, "invalid_limit", "limit must be an integer") from exc
                    if not 1 <= limit <= 1000:
                        raise ApiError(400, "invalid_limit", "limit must be between 1 and 1000")
                    self._send(200, repo.list_costs(tenant, limit))
                    return
                if len(segments) == 2 and segments[0] == "suggestions":
                    self._send(200, self.server.app.service.get_suggestion(tenant, segments[1]))  # type: ignore[attr-defined]
                    return
                raise ApiError(404, "route_not_found", "No API route matches this path")
            except (ApiError, ServiceError) as exc:
                self._error(exc)
            except Exception as exc:
                self._send(500, {"error": {"code": "internal_error", "message": "The request could not be completed"}})
                sys.stderr.write(f"request failed: {type(exc).__name__}\n")

        def do_POST(self) -> None:  # noqa: N802
            try:
                tenant = self._tenant()
                segments, _ = self._segments()
                repo = self.server.app.repository  # type: ignore[attr-defined]
                if segments == ["jobs"]:
                    body = self._body()
                    if set(body) != {"kind"} or body.get("kind") != "process-corpus":
                        raise ApiError(400, "invalid_job_request", 'Body must be exactly {"kind":"process-corpus"}')
                    key = self._idempotency_key()
                    job, created = self.server.app.jobs.submit(tenant, key)  # type: ignore[attr-defined]
                    self._send(202 if created else 200, {"created": created, "job": job})
                    return
                if len(segments) == 3 and segments[0] == "posts" and segments[2] == "suggestions":
                    key = self._idempotency_key()
                    payload, created = self.server.app.service.create_suggestions(tenant, segments[1], key)  # type: ignore[attr-defined]
                    self._send(201 if created else 200, {"created": created, **payload})
                    return
                if len(segments) == 3 and segments[0] == "suggestions" and segments[2] == "review":
                    body = self._body()
                    action = body.get("action")
                    if set(body) - {"action", "note"} or not isinstance(action, str) or action not in {"approve", "reject"}:
                        raise ApiError(400, "invalid_review", 'Body must contain action "approve" or "reject" and optional note')
                    note = body.get("note", "")
                    if not isinstance(note, str) or len(note) > 500:
                        raise ApiError(400, "invalid_review_note", "note must be a string of at most 500 characters")
                    key = self._idempotency_key()
                    suggestion = self.server.app.service.get_suggestion(tenant, segments[1])  # type: ignore[attr-defined]
                    if body["action"] == "approve" and not suggestion["accepted"]:
                        raise ApiError(409, "guard_rejected", "A suggestion rejected by the mismatch guard cannot be approved")
                    try:
                        review, created = repo.create_review(tenant, segments[1], body["action"], note, key)
                    except ValueError as exc:
                        raise ApiError(409, "idempotency_conflict", str(exc)) from exc
                    self._send(201 if created else 200, {"created": created, "review": {k: review[k] for k in ("review_id", "suggestion_id", "action", "note", "created_at")}})
                    return
                raise ApiError(404, "route_not_found", "No API route matches this path")
            except (ApiError, ServiceError) as exc:
                self._error(exc)
            except Exception as exc:
                self._send(500, {"error": {"code": "internal_error", "message": "The request could not be completed"}})
                sys.stderr.write(f"request failed: {type(exc).__name__}\n")

    return Handler


def public_image(image: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_id": image["image_id"],
        "reference": image["reference"],
        "tag_status": image["tag_status"],
        "tags": image["tags"],
        "review_required": image["review_required"],
        "confidence": image["confidence"],
        "embedding_model": image["model_id"],
    }


def public_post(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "post_id": post["post_id"],
        "title": post["title"],
        "body": post["body"],
        "embedded": isinstance(post["embedding"], list),
        "embedding_model": post["model_id"],
    }


def openapi_document() -> dict[str, Any]:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Image Relevance API",
            "version": "0.1.0",
            "description": "X-Tenant-ID selects a local data partition; it is not authentication or authorization. Keep this demo bound to loopback.",
        },
        "servers": [{"url": "http://127.0.0.1:8000"}],
        "paths": {
            "/health": {"get": {"summary": "Liveness check"}},
            "/images": {"get": {"summary": "List tenant-scoped images"}},
            "/posts": {"get": {"summary": "List tenant-scoped posts"}},
            "/jobs": {"get": {"summary": "List jobs"}, "post": {"summary": "Start an idempotent async corpus batch"}},
            "/jobs/{job_id}": {"get": {"summary": "Inspect progress, retries, failures, and cost"}},
            "/costs": {"get": {"summary": "List per-call cost ledger entries"}},
            "/posts/{post_id}/images": {"get": {"summary": "Rank images or inspect a forced candidate"}},
            "/posts/{post_id}/suggestions": {"get": {"summary": "List persisted suggestion reviews"}, "post": {"summary": "Persist an idempotent ranked suggestion run"}},
            "/suggestions/{suggestion_id}": {"get": {"summary": "Inspect a suggestion and its review history"}},
            "/suggestions/{suggestion_id}/review": {"post": {"summary": "Approve or reject a suggestion"}},
        },
    }


def create_server(
    database_path: str = str(DATABASE_PATH),
    host: str = HOST,
    port: int = PORT,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
    cost_budget: float = COST_BUDGET_USD,
    max_retries: int = MAX_JOB_RETRIES,
    embedding_provider: str = EMBEDDING_PROVIDER,
    ollama_base_url: str = OLLAMA_BASE_URL,
    ollama_model: str = OLLAMA_EMBEDDING_MODEL,
    ollama_timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
) -> ThreadingHTTPServer:
    app = Application(
        database_path,
        similarity_threshold,
        confidence_threshold,
        cost_budget,
        max_retries,
        embedding_provider,
        ollama_base_url,
        ollama_model,
        ollama_timeout_seconds,
    )
    server = ThreadingHTTPServer((host, port), make_handler(app))
    server.daemon_threads = True
    server.app = app  # type: ignore[attr-defined]
    app.jobs.resume_incomplete_jobs()
    return server


def main() -> None:
    server = create_server()
    app = server.app  # type: ignore[attr-defined]
    print(f"Image Relevance API listening on http://{server.server_address[0]}:{server.server_address[1]}")
    print(f"SQLite database: {app.database.path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
