from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import socket
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl, model_validator


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(ROOT / "data" / "studio.db")))
POLL_SECONDS = max(1, int(os.environ.get("POLL_SECONDS", "2")))
ACTIVE_PUBLISHER = os.environ.get("PUBLISHER", "mock_x").lower()


PROFILES = {
    "discord": {"max_length": 2000, "max_hashtags": 3, "tone": "conversational"},
    "mock_x": {"max_length": 280, "max_hashtags": 2, "tone": "concise"},
    "mock_linkedin": {"max_length": 3000, "max_hashtags": 5, "tone": "professional"},
}
PLATFORM_NAMES = {
    "discord": "Discord",
    "mock_x": "Mock X",
    "mock_linkedin": "Mock LinkedIn",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime | None = None) -> str:
    return (value or utc_now()).astimezone(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    try:
        yield db
    finally:
        db.close()


def initialize_database() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY,
                source_type TEXT NOT NULL CHECK (source_type IN ('markdown', 'url')),
                source_url TEXT,
                source_markdown TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS variants (
                id INTEGER PRIMARY KEY,
                post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                body TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft', 'approved', 'rejected', 'published')),
                validation_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY,
                variant_id INTEGER NOT NULL REFERENCES variants(id),
                platform TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'publishing', 'published', 'failed', 'uncertain')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (variant_id, scheduled_at)
            );
            CREATE TABLE IF NOT EXISTS publish_attempts (
                id INTEGER PRIMARY KEY,
                schedule_id INTEGER NOT NULL REFERENCES schedules(id),
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                adapter TEXT NOT NULL,
                message_ref TEXT,
                error_summary TEXT
            );
            CREATE TABLE IF NOT EXISTS mock_publications (
                id INTEGER PRIMARY KEY,
                idempotency_key TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL,
                message_ref TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_schedules_due ON schedules(status, scheduled_at);
            CREATE INDEX IF NOT EXISTS idx_attempts_schedule ON publish_attempts(schedule_id, id);
            """
        )


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "br"} and not self.hidden_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def extract_html_text(payload: bytes) -> str:
    parser = _VisibleText()
    parser.feed(payload.decode("utf-8", errors="replace"))
    return re.sub(r"\n{3,}", "\n\n", " ".join(parser.parts)).strip()


def fetch_public_article(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise HTTPException(400, "source_url must be a public HTTP(S) URL")
    if host.lower() in {"localhost", "metadata.google.internal"} or host.lower().endswith((".local", ".internal")):
        raise HTTPException(400, "source_url host is not public")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))}
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise HTTPException(400, "source_url must resolve only to public IP addresses")
    except HTTPException:
        raise
    except (OSError, ValueError) as exc:
        raise HTTPException(400, "source_url host could not be resolved safely") from exc

    try:
        with httpx.Client(timeout=8, follow_redirects=False, headers={"User-Agent": "FlyRankSocialStudio/1.0"}) as client:
            with client.stream("GET", url) as response:
                if 300 <= response.status_code < 400:
                    raise HTTPException(400, "redirects are not followed for source URLs")
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if not any(kind in content_type for kind in ("text/", "application/xhtml+xml")):
                    raise HTTPException(415, "source URL must return text or HTML")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 1_000_000:
                        raise HTTPException(413, "source URL exceeds the 1 MB limit")
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(400, "source URL could not be fetched") from exc

    text = extract_html_text(bytes(data)) if "html" in content_type else bytes(data).decode("utf-8", errors="replace")
    if not text.strip():
        raise HTTPException(400, "source URL did not contain readable text")
    return text[:20_000]


def clean_source(markdown: str) -> str:
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", markdown)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_>#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def validate_variant(platform: str, body: str) -> list[str]:
    if platform not in PROFILES:
        return [f"platform must be one of: {', '.join(PROFILES)}"]
    profile = PROFILES[platform]
    errors: list[str] = []
    if not body.strip():
        errors.append("body must not be empty")
    if len(body) > profile["max_length"]:
        errors.append(f"length must be at most {profile['max_length']} characters (got {len(body)})")
    hashtags = re.findall(r"(?<!\w)#[\w]+", body)
    if len(hashtags) > profile["max_hashtags"]:
        errors.append(f"hashtag count must be at most {profile['max_hashtags']} (got {len(hashtags)})")
    if profile["tone"] == "conversational" and "?" not in body:
        errors.append("conversational tone must invite a response with a question")
    if profile["tone"] == "concise":
        sentence_count = len(re.findall(r"[.!?](?:\s|$)", body))
        if sentence_count > 2:
            errors.append(f"concise tone must use at most 2 sentences (got {sentence_count})")
    if profile["tone"] == "professional" and (re.search(r"[A-Z]{4,}", body) or re.search(r"[!?]{2,}", body)):
        errors.append("professional tone must avoid all-caps words and repeated punctuation")
    if re.search(r"@everyone|@here", body, re.IGNORECASE):
        errors.append("mass mentions are not allowed")
    if re.search(r"(?:guaranteed|risk[- ]free|100% certain)", body, re.IGNORECASE):
        errors.append("unsupported certainty language is not allowed")
    return errors


def make_variant(source: str, platform: str, source_url: str | None = None) -> str:
    excerpt = clean_source(source)
    if platform == "discord":
        body = f"New from the blog:\n{excerpt}\n\nWhat would you add?"
    elif platform == "mock_x":
        short_excerpt = re.split(r"(?<=[.!?])\s+", excerpt, maxsplit=2)[0]
        body = f"A useful idea from our latest post: {short_excerpt}"
    else:
        body = f"A practical idea from the latest post:\n\n{excerpt}\n\nWhat has worked for your team?"
    if source_url:
        body += f"\n\nRead more: {source_url}"
    limit = int(PROFILES[platform]["max_length"])
    if len(body) > limit:
        suffix = "…"
        body = body[: limit - len(suffix)].rstrip() + suffix
    return body


class PostCreate(BaseModel):
    source_markdown: str | None = Field(default=None, max_length=20_000)
    source_url: HttpUrl | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "PostCreate":
        if bool(self.source_markdown and self.source_markdown.strip()) == bool(self.source_url):
            raise ValueError("provide exactly one of source_markdown or source_url")
        return self


class VariantCreate(BaseModel):
    platform: Literal["discord", "mock_x", "mock_linkedin"]
    body: str = Field(min_length=1, max_length=20_000)


class VariantUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=20_000)
    decision: Literal["approve", "reject"] | None = None


class ScheduleCreate(BaseModel):
    scheduled_at: datetime


class PublishResult(BaseModel):
    message_ref: str
    url: str | None = None


class SocialPublisher(Protocol):
    name: str

    def publish(self, body: str, idempotency_key: str) -> PublishResult: ...


class MockPublisher:
    def __init__(self, platform: str) -> None:
        self.platform = platform
        self.name = f"mock:{platform}"

    def publish(self, body: str, idempotency_key: str) -> PublishResult:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT OR IGNORE INTO mock_publications(idempotency_key, platform, body, created_at, message_ref) VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, self.platform, body, utc_text(), f"mock-{idempotency_key}"),
            )
            row = db.execute("SELECT message_ref FROM mock_publications WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            db.commit()
        return PublishResult(message_ref=row["message_ref"])


class MockXPublisher(MockPublisher):
    def __init__(self) -> None:
        super().__init__("mock_x")


class MockLinkedInPublisher(MockPublisher):
    def __init__(self) -> None:
        super().__init__("mock_linkedin")


class DiscordPublisher:
    name = "discord-webhook"

    def publish(self, body: str, idempotency_key: str) -> PublishResult:
        webhook = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
        parsed = urlparse(webhook)
        if parsed.scheme != "https" or parsed.hostname not in {"discord.com", "discordapp.com"} or not parsed.path.startswith("/api/webhooks/"):
            raise RuntimeError("Discord webhook is not configured with a valid discord.com URL")
        try:
            response = httpx.post(
                webhook + ("&" if "?" in webhook else "?") + "wait=true",
                json={"content": body, "allowed_mentions": {"parse": []}},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise TimeoutError("Discord delivery result is uncertain; inspect the channel before retrying") from exc
        if response.status_code >= 500:
            raise TimeoutError("Discord returned a server error; delivery result is uncertain")
        if response.status_code >= 400:
            raise ValueError(f"Discord rejected the post with HTTP {response.status_code}")
        result = response.json()
        message_id = str(result.get("id", ""))
        if not message_id:
            raise TimeoutError("Discord response did not include a message ID; delivery result is uncertain")
        channel_id = str(result.get("channel_id", ""))
        message_url = f"https://discord.com/channels/@me/{channel_id}/{message_id}" if channel_id else None
        return PublishResult(message_ref=message_id, url=message_url)


def publisher_for(platform: str) -> SocialPublisher:
    if platform == "discord":
        return DiscordPublisher()
    if platform == "mock_x":
        return MockXPublisher()
    if platform == "mock_linkedin":
        return MockLinkedInPublisher()
    raise ValueError(f"unknown platform: {platform}")


def record_attempt(schedule_id: int, outcome: str, adapter: str, message_ref: str | None = None, error_summary: str | None = None) -> None:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        attempt = db.execute(
            "SELECT id FROM publish_attempts WHERE schedule_id = ? AND status = 'dispatching' ORDER BY id DESC LIMIT 1",
            (schedule_id,),
        ).fetchone()
        if attempt:
            db.execute(
                "UPDATE publish_attempts SET finished_at = ?, status = ?, message_ref = ?, error_summary = ? WHERE id = ?",
                (utc_text(), outcome, message_ref, error_summary, attempt["id"]),
            )
        else:
            db.execute(
                "INSERT INTO publish_attempts(schedule_id, started_at, finished_at, status, adapter, message_ref, error_summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (schedule_id, utc_text(), utc_text(), outcome, adapter, message_ref, error_summary),
            )
        db.commit()


def publish_schedule(schedule_id: int, force: bool = False) -> dict:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT s.*, v.body, v.status AS variant_status FROM schedules s JOIN variants v ON v.id = s.variant_id WHERE s.id = ?",
            (schedule_id,),
        ).fetchone()
        if not row:
            db.rollback()
            raise HTTPException(404, "schedule not found")
        if row["status"] == "published":
            db.commit()
            return {"status": "published", "idempotent_replay": True}
        if row["status"] != "pending":
            db.commit()
            raise HTTPException(409, f"schedule is {row['status']} and cannot be sent again automatically")
        due = datetime.fromisoformat(row["scheduled_at"])
        if not force and due > utc_now():
            db.commit()
            raise HTTPException(409, "schedule is not due yet")
        if row["variant_status"] != "approved":
            db.rollback()
            raise HTTPException(409, "only approved variants can be published")
        adapter = publisher_for(row["platform"])
        db.execute("UPDATE schedules SET status = 'publishing', updated_at = ? WHERE id = ?", (utc_text(), schedule_id))
        db.execute(
            "INSERT INTO publish_attempts(schedule_id, started_at, status, adapter) VALUES (?, ?, 'dispatching', ?)",
            (schedule_id, utc_text(), adapter.name),
        )
        db.commit()

    try:
        result = adapter.publish(row["body"], row["idempotency_key"])
    except TimeoutError as exc:
        with connect() as db:
            db.execute("UPDATE schedules SET status = 'uncertain', updated_at = ? WHERE id = ?", (utc_text(), schedule_id))
        record_attempt(schedule_id, "uncertain", adapter.name, error_summary=str(exc))
        raise HTTPException(502, "publish outcome is uncertain; automatic retry is disabled to prevent duplicates") from exc
    except (RuntimeError, ValueError) as exc:
        with connect() as db:
            db.execute("UPDATE schedules SET status = 'failed', updated_at = ? WHERE id = ?", (utc_text(), schedule_id))
        record_attempt(schedule_id, "failed", adapter.name, error_summary=str(exc))
        raise HTTPException(502, str(exc)) from exc

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE schedules SET status = 'published', updated_at = ? WHERE id = ?", (utc_text(), schedule_id))
        db.execute("UPDATE variants SET status = 'published', updated_at = ? WHERE id = ?", (utc_text(), row["variant_id"]))
        db.commit()
    record_attempt(schedule_id, "published", adapter.name, message_ref=result.message_ref)
    return {"status": "published", "message_ref": result.message_ref, "url": result.url, "adapter": adapter.name}


def recover_interrupted_sends() -> None:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute("SELECT * FROM schedules WHERE status = 'publishing'").fetchall()
        for row in rows:
            attempt = db.execute(
                "SELECT id FROM publish_attempts WHERE schedule_id = ? AND status = 'dispatching' ORDER BY id DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
            if row["platform"] in {"mock_x", "mock_linkedin"}:
                posted = db.execute(
                    "SELECT message_ref FROM mock_publications WHERE idempotency_key = ?",
                    (row["idempotency_key"],),
                ).fetchone()
                if posted:
                    db.execute("UPDATE schedules SET status = 'published', updated_at = ? WHERE id = ?", (utc_text(), row["id"]))
                    db.execute("UPDATE variants SET status = 'published', updated_at = ? WHERE id = ?", (utc_text(), row["variant_id"]))
                    outcome, summary, message_ref = "published", None, posted["message_ref"]
                else:
                    # Mock delivery is a local transaction with a unique key, so it is safe to resume.
                    db.execute("UPDATE schedules SET status = 'pending', updated_at = ? WHERE id = ?", (utc_text(), row["id"]))
                    outcome, summary, message_ref = "interrupted", "worker restarted before mock delivery; queued safely", None
            else:
                db.execute("UPDATE schedules SET status = 'uncertain', updated_at = ? WHERE id = ?", (utc_text(), row["id"]))
                outcome, summary, message_ref = "uncertain", "worker restarted during external delivery; reconcile before retry", None
            if attempt:
                db.execute(
                    "UPDATE publish_attempts SET finished_at = ?, status = ?, message_ref = ?, error_summary = ? WHERE id = ?",
                    (utc_text(), outcome, message_ref, summary, attempt["id"]),
                )
        db.commit()


async def scheduler_loop() -> None:
    while True:
        with connect() as db:
            rows = db.execute(
                "SELECT id FROM schedules WHERE status = 'pending' AND scheduled_at <= ? ORDER BY scheduled_at LIMIT 10",
                (utc_text(),),
            ).fetchall()
        for row in rows:
            try:
                await asyncio.to_thread(publish_schedule, row["id"])
            except HTTPException:
                continue
        await asyncio.sleep(POLL_SECONDS)


def seed_demo_if_empty() -> None:
    if os.environ.get("DEMO_SEED", "true").lower() not in {"1", "true", "yes"}:
        return
    with connect() as db:
        if db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]:
            return
        cur = db.execute(
            "INSERT INTO posts(source_type, source_url, source_markdown, created_at) VALUES ('markdown', NULL, ?, ?)",
            ("A small API is easier to maintain when each feature has a clear boundary. Start with one useful workflow, measure it, and improve it from evidence.", utc_text()),
        )
        post_id = cur.lastrowid
        source = db.execute("SELECT source_markdown FROM posts WHERE id = ?", (post_id,)).fetchone()[0]
        for platform in PROFILES:
            body = make_variant(source, platform)
            errors = validate_variant(platform, body)
            db.execute(
                "INSERT INTO variants(post_id, platform, body, status, validation_json, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?, ?)",
                (post_id, platform, body, json.dumps(errors), utc_text(), utc_text()),
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    recover_interrupted_sends()
    seed_demo_if_empty()
    worker = asyncio.create_task(scheduler_loop())
    yield
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Social Media Studio", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/health")
def health() -> dict:
    with connect() as db:
        db.execute("SELECT 1").fetchone()
    return {"status": "ok", "publisher": ACTIVE_PUBLISHER}


@app.get("/profiles")
def profiles() -> dict:
    return {key: {**value, "name": PLATFORM_NAMES[key]} for key, value in PROFILES.items()}


@app.post("/posts", status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreate) -> dict:
    source_url = str(payload.source_url) if payload.source_url else None
    source = payload.source_markdown.strip() if payload.source_markdown else fetch_public_article(source_url or "")
    with connect() as db:
        cur = db.execute(
            "INSERT INTO posts(source_type, source_url, source_markdown, created_at) VALUES (?, ?, ?, ?)",
            ("url" if source_url else "markdown", source_url, source, utc_text()),
        )
        post_id = cur.lastrowid
        row = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return dict(row)


@app.get("/posts")
def list_posts() -> list[dict]:
    with connect() as db:
        return [dict(row) for row in db.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()]


@app.post("/posts/{post_id}/generate", status_code=status.HTTP_201_CREATED)
def generate_variants(post_id: int) -> list[dict]:
    with connect() as db:
        post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(404, "post not found")
        result = []
        for platform in PROFILES:
            body = make_variant(post["source_markdown"], platform, post["source_url"])
            errors = validate_variant(platform, body)
            if errors:
                raise HTTPException(422, {"platform": platform, "errors": errors})
            now = utc_text()
            cur = db.execute(
                "INSERT INTO variants(post_id, platform, body, status, validation_json, created_at, updated_at) VALUES (?, ?, ?, 'draft', ?, ?, ?)",
                (post_id, platform, body, json.dumps(errors), now, now),
            )
            result.append(dict(db.execute("SELECT * FROM variants WHERE id = ?", (cur.lastrowid,)).fetchone()))
    return result


@app.post("/posts/{post_id}/variants", status_code=status.HTTP_201_CREATED)
def create_variant(post_id: int, payload: VariantCreate) -> dict:
    errors = validate_variant(payload.platform, payload.body)
    if errors:
        raise HTTPException(422, {"errors": errors})
    with connect() as db:
        if not db.execute("SELECT 1 FROM posts WHERE id = ?", (post_id,)).fetchone():
            raise HTTPException(404, "post not found")
        now = utc_text()
        cur = db.execute(
            "INSERT INTO variants(post_id, platform, body, status, validation_json, created_at, updated_at) VALUES (?, ?, ?, 'draft', '[]', ?, ?)",
            (post_id, payload.platform, payload.body, now, now),
        )
        return dict(db.execute("SELECT * FROM variants WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.get("/variants")
def list_variants(post_id: int | None = None) -> list[dict]:
    with connect() as db:
        if post_id is None:
            rows = db.execute("SELECT * FROM variants ORDER BY id DESC").fetchall()
        else:
            rows = db.execute("SELECT * FROM variants WHERE post_id = ? ORDER BY id DESC", (post_id,)).fetchall()
    return [{**dict(row), "validation": json.loads(row["validation_json"])} for row in rows]


@app.patch("/variants/{variant_id}")
def update_variant(variant_id: int, payload: VariantUpdate) -> dict:
    if payload.body is None and payload.decision is None:
        raise HTTPException(400, "provide body and/or decision")
    with connect() as db:
        row = db.execute("SELECT * FROM variants WHERE id = ?", (variant_id,)).fetchone()
        if not row:
            raise HTTPException(404, "variant not found")
        if row["status"] in {"published"}:
            raise HTTPException(409, "published variants cannot be changed")
        body = payload.body if payload.body is not None else row["body"]
        errors = validate_variant(row["platform"], body)
        if errors:
            raise HTTPException(422, {"errors": errors})
        new_status = "draft" if payload.body is not None else row["status"]
        if payload.decision == "approve":
            new_status = "approved"
        elif payload.decision == "reject":
            new_status = "rejected"
        db.execute(
            "UPDATE variants SET body = ?, status = ?, validation_json = '[]', updated_at = ? WHERE id = ?",
            (body, new_status, utc_text(), variant_id),
        )
        return dict(db.execute("SELECT * FROM variants WHERE id = ?", (variant_id,)).fetchone())


@app.post("/variants/{variant_id}/schedule", status_code=status.HTTP_201_CREATED)
def schedule_variant(variant_id: int, payload: ScheduleCreate) -> dict:
    if payload.scheduled_at.tzinfo is None or payload.scheduled_at.utcoffset() is None:
        raise HTTPException(400, "scheduled_at must include a timezone")
    slot = utc_text(payload.scheduled_at)
    with connect() as db:
        variant = db.execute("SELECT * FROM variants WHERE id = ?", (variant_id,)).fetchone()
        if not variant:
            raise HTTPException(404, "variant not found")
        if variant["status"] != "approved":
            raise HTTPException(409, "only approved variants can be scheduled")
        adapter = ACTIVE_PUBLISHER
        if adapter not in {"discord", "mock_x", "mock_linkedin"}:
            raise HTTPException(500, "PUBLISHER must be discord, mock_x, or mock_linkedin")
        key = f"variant:{variant_id}:slot:{slot}"
        try:
            cur = db.execute(
                "INSERT INTO schedules(variant_id, platform, scheduled_at, idempotency_key, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (variant_id, adapter, slot, key, utc_text(), utc_text()),
            )
        except sqlite3.IntegrityError:
            existing = db.execute("SELECT * FROM schedules WHERE variant_id = ? AND scheduled_at = ?", (variant_id, slot)).fetchone()
            return {**dict(existing), "idempotent_replay": True}
        return dict(db.execute("SELECT * FROM schedules WHERE id = ?", (cur.lastrowid,)).fetchone())


@app.post("/schedules/{schedule_id}/publish")
def publish_now(schedule_id: int) -> dict:
    return publish_schedule(schedule_id, force=True)


@app.get("/schedules")
def list_schedules() -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT s.*, v.body, v.status AS variant_status FROM schedules s JOIN variants v ON v.id = s.variant_id ORDER BY s.scheduled_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]

@app.get("/history")
def history() -> list[dict]:
    with connect() as db:
        rows = db.execute(
            "SELECT a.id AS attempt_id, a.started_at, a.finished_at, a.status AS outcome, a.adapter, a.message_ref, a.error_summary, s.id AS schedule_id, s.variant_id, s.platform, s.scheduled_at, s.idempotency_key, v.body FROM publish_attempts a JOIN schedules s ON s.id = a.schedule_id JOIN variants v ON v.id = s.variant_id ORDER BY a.id DESC"
        ).fetchall()
    return [dict(row) for row in rows]
