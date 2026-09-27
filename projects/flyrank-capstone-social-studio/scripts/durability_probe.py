"""Restart/recovery acceptance probe using an isolated temporary SQLite DB."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

os.environ["PUBLISHER"] = "mock_x"
os.environ["POLL_SECONDS"] = "1"
os.environ["DEMO_SEED"] = "false"
_temp = tempfile.TemporaryDirectory(prefix="social-studio-recovery-")
os.environ["DATABASE_PATH"] = str(Path(_temp.name) / "studio.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as service


def check(name: str, condition: bool) -> None:
    if not condition:
        raise SystemExit(f"FAIL {name}")
    print(f"PASS {name}")


def stuck_schedule(platform: str, key: str, body: str = "Restart-safe example") -> int:
    with service.connect() as db:
        cur = db.execute(
            "INSERT INTO posts(source_type, source_url, source_markdown, created_at) VALUES ('markdown', NULL, ?, ?)",
            (body, service.utc_text()),
        )
        post_id = cur.lastrowid
        cur = db.execute(
            "INSERT INTO variants(post_id, platform, body, status, validation_json, created_at, updated_at) VALUES (?, ?, ?, 'approved', '[]', ?, ?)",
            (post_id, platform, body, service.utc_text(), service.utc_text()),
        )
        variant_id = cur.lastrowid
        due = service.utc_text(service.utc_now() - timedelta(seconds=2))
        cur = db.execute(
            "INSERT INTO schedules(variant_id, platform, scheduled_at, idempotency_key, status, created_at, updated_at) VALUES (?, ?, ?, ?, 'publishing', ?, ?)",
            (variant_id, platform, due, key, service.utc_text(), service.utc_text()),
        )
        schedule_id = cur.lastrowid
        db.execute(
            "INSERT INTO publish_attempts(schedule_id, started_at, status, adapter) VALUES (?, ?, 'dispatching', ?)",
            (schedule_id, service.utc_text(), platform),
        )
        return schedule_id


async def run_probe() -> None:
    async with service.lifespan(service.app):
        check("service starts against a fresh temporary database", service.health()["status"] == "ok")
        before_id = stuck_schedule("mock_x", "probe:before-delivery")
        after_id = stuck_schedule("mock_x", "probe:after-delivery")
        service.MockXPublisher().publish("Restart-safe example", "probe:after-delivery")
        discord_id = stuck_schedule("discord", "probe:discord-uncertain")
        print("Simulated worker stopping after it claimed one local job, after a mock side effect, and during an external send.")

    async with service.lifespan(service.app):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            with service.connect() as db:
                before = db.execute("SELECT status FROM schedules WHERE id = ?", (before_id,)).fetchone()["status"]
                after = db.execute("SELECT status FROM schedules WHERE id = ?", (after_id,)).fetchone()["status"]
                discord = db.execute("SELECT status FROM schedules WHERE id = ?", (discord_id,)).fetchone()["status"]
                count = db.execute("SELECT COUNT(*) FROM mock_publications WHERE idempotency_key = 'probe:after-delivery'").fetchone()[0]
                attempts = db.execute("SELECT COUNT(*) FROM publish_attempts WHERE schedule_id = ? AND status = 'published'", (before_id,)).fetchone()[0]
            if before == "published" and after == "published":
                break
            await asyncio.sleep(0.1)
        check("uncompleted mock job resumes after application restart", before == "published")
        check("completed mock side effect is recovered without a duplicate", after == "published" and count == 1)
        check("ambiguous Discord delivery is held for manual reconciliation", discord == "uncertain")
        check("restarted work appears once in publish history", attempts == 1)

    print("PASS recovery probe used a temporary database and sent no external messages")


asyncio.run(run_probe())
