"""Course acceptance probes. Start the app with PUBLISHER=mock_x first."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx


BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "http://127.0.0.1:8000")


def check(name: str, condition: bool) -> None:
    if not condition:
        raise SystemExit(f"FAIL {name}")
    print(f"PASS {name}")


with httpx.Client(base_url=BASE, timeout=10) as client:
    health = client.get("/health")
    check("one-command service starts and health responds", health.status_code == 200 and health.json()["status"] == "ok")

    post = client.post("/posts", json={"source_markdown": "A clear API contract reduces integration errors for teams shipping software."})
    check("Markdown source is stored", post.status_code == 201)
    generated = client.post(f"/posts/{post.json()['id']}/generate")
    check("one stored post generates valid variants", generated.status_code == 201 and len(generated.json()) == 3)
    variants = generated.json()
    check("each variant passes its configured profile", all(json.loads(item["validation_json"]) == [] for item in variants))

    invalid = client.post(f"/posts/{post.json()['id']}/variants", json={"platform": "mock_x", "body": "x" * 300})
    check("invalid variant is blocked with a named length rule", invalid.status_code == 422 and "280" in str(invalid.json()))
    tone_failure = client.post(f"/posts/{post.json()['id']}/variants", json={"platform": "discord", "body": "A short statement without a question."})
    check("tone constraints are enforced before review", tone_failure.status_code == 422 and "conversational tone" in str(tone_failure.json()))

    target = next(item for item in variants if item["platform"] == "mock_x")
    rejected_schedule = client.post(f"/variants/{target['id']}/schedule", json={"scheduled_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()})
    check("unapproved variant cannot be scheduled", rejected_schedule.status_code == 409)

    approved = client.patch(f"/variants/{target['id']}", json={"decision": "approve"})
    check("human review approval changes status", approved.status_code == 200 and approved.json()["status"] == "approved")
    slot = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    scheduled = client.post(f"/variants/{target['id']}/schedule", json={"scheduled_at": slot})
    check("approved variant can be scheduled", scheduled.status_code == 201)
    schedule_id = scheduled.json()["id"]
    first = client.post(f"/schedules/{schedule_id}/publish")
    second = client.post(f"/schedules/{schedule_id}/publish")
    history = client.get("/history").json()
    same_key = [item for item in history if item["idempotency_key"] == scheduled.json()["idempotency_key"] and item["outcome"] == "published"]
    check("repeated publish is idempotent", first.status_code == 200 and second.status_code == 200 and second.json().get("idempotent_replay") and len(same_key) == 1)
    check("publish history records the result", any(item["schedule_id"] == schedule_id and item["outcome"] == "published" for item in history))

print("NOTE Discord was selected as the live adapter, but no webhook was configured; no real post was sent.")
