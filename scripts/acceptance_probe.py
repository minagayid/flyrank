"""Run the capstone's published local acceptance probes against a running service."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lead_capture.config import Settings


settings = Settings.from_env()
BASE = settings.public_base_url
ORIGIN = f"http://{settings.demo_host}:{settings.demo_port}"
TENANT_A = settings.tenant_a_token
TENANT_B = settings.tenant_b_token
WIDGET_ID = "widget_demo_signup"
RUN_ID = uuid.uuid4().hex[:8]


def request(method: str, path: str, *, body=None, raw: bytes | None = None, token: str | None = None,
            origin: str | None = None, headers: dict[str, str] | None = None):
    request_headers = dict(headers or {})
    if body is not None:
        raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    if raw is not None:
        request_headers.setdefault("Content-Type", "application/json")
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    if origin:
        request_headers["Origin"] = origin
    req = urllib.request.Request(BASE + path, data=raw, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = response.read()
            try:
                parsed = json.loads(payload) if payload else None
            except json.JSONDecodeError:
                parsed = {"non_json": payload[:120].decode("utf-8", "replace")}
            return response.status, dict(response.headers.items()), parsed
    except urllib.error.HTTPError as response:
        payload = response.read()
        try:
            parsed = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            parsed = {"non_json": payload[:120].decode("utf-8", "replace")}
        return response.code, dict(response.headers.items()), parsed


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def submit(*, key: str | None = None, email: str | None = None, name: str = "Acceptance Lead", honeypot: str = ""):
    body = {
        "widget_id": WIDGET_ID,
        "fields": {"name": name, "email": email or f"probe-{uuid.uuid4().hex[:8]}@example.test"},
        "company_website": honeypot,
    }
    key = key or f"probe-{uuid.uuid4().hex}"
    return request(
        "POST", "/api/public/submissions", body=body, origin=ORIGIN,
        headers={"Idempotency-Key": key},
    )


def main() -> None:
    report: dict[str, object] = {}
    status, _, health = request("GET", "/health")
    check(status == 200 and health["status"] == "ok", "health")
    report["health"] = status

    status, _, _ = request("GET", "/api/widgets")
    check(status == 401, "owner route must reject missing auth")
    status, _, _ = request("GET", f"/api/widgets/{WIDGET_ID}", token=TENANT_B)
    check(status == 404, "tenant B must not read tenant A widget")
    report["owner_auth_and_tenant_read"] = {"missing_token": 401, "cross_tenant_widget": 404}

    create_body = {
        "type": "contact", "title": "Probe contact form", "description": "Created by local acceptance probe.",
        "fields": [{"name": "email", "label": "Email", "type": "email", "required": True, "max_length": 254}],
        "button_text": "Contact me", "display": {"theme": "light", "position": "inline"},
    }
    status, _, created = request("POST", "/api/widgets", body=create_body, token=TENANT_A)
    check(status == 201, "owner can create widget")
    probe_widget_id = created["widget"]["id"]
    status, _, _ = request("GET", f"/api/widgets/{probe_widget_id}", token=TENANT_A)
    check(status == 200, "owner can read widget")
    status, _, _ = request("GET", f"/api/widgets/{probe_widget_id}", token=TENANT_B)
    check(status == 404, "other tenant cannot read created widget")
    create_body["title"] = "Probe contact form revised"
    status, _, updated = request("PUT", f"/api/widgets/{probe_widget_id}", body=create_body, token=TENANT_A)
    check(status == 200 and updated["widget"]["version"] == 2, "owner can update widget and version increments")
    status, _, _ = request("PUT", f"/api/widgets/{probe_widget_id}", body=create_body, token=TENANT_B)
    check(status == 404, "other tenant cannot update widget")
    status, _, tenant_b_created = request("POST", "/api/widgets", body=create_body, token=TENANT_B)
    check(status == 201, "tenant B can create its own widget")
    tenant_b_widget = tenant_b_created["widget"]["id"]
    status, _, _ = request("GET", f"/api/widgets/{tenant_b_widget}", token=TENANT_A)
    check(status == 404, "tenant A cannot read tenant B widget")
    status, _, _ = request("PUT", f"/api/widgets/{tenant_b_widget}", body=create_body, token=TENANT_A)
    check(status == 404, "tenant A cannot update tenant B widget")
    b_submission_status, _, b_submission = request(
        "POST", "/api/public/submissions",
        body={"widget_id": tenant_b_widget, "fields": {"email": f"tenant-b-{RUN_ID}@example.test"}, "company_website": ""},
        origin=ORIGIN, headers={"Idempotency-Key": f"probe-{RUN_ID}-tenant-b-0001"},
    )
    check(b_submission_status == 201, "tenant B widget accepts a lead")
    status, _, b_owner_rows = request("GET", f"/api/widgets/{tenant_b_widget}/submissions", token=TENANT_B)
    check(status == 200 and any(row["id"] == b_submission["submission_id"] for row in b_owner_rows["submissions"]),
          "tenant B can read its own lead")
    status, _, _ = request("GET", f"/api/widgets/{tenant_b_widget}/submissions", token=TENANT_A)
    check(status == 404, "tenant A cannot read tenant B submissions")
    status, _, deleted = request("DELETE", f"/api/widgets/{probe_widget_id}", token=TENANT_A)
    check(status == 200 and deleted["data_retained"] is True, "owner can soft-delete widget")
    status, _, _ = request("GET", f"/api/widgets/{probe_widget_id}", token=TENANT_A)
    check(status == 404, "soft-deleted widget is hidden")
    status, _, _ = request("DELETE", f"/api/widgets/{tenant_b_widget}", token=TENANT_B)
    check(status == 200, "tenant B can delete its own widget")
    status, _, retained_rows = request("GET", f"/api/widgets/{tenant_b_widget}/submissions", token=TENANT_B)
    check(status == 200 and any(row["id"] == b_submission["submission_id"] for row in retained_rows["submissions"]),
          "soft-deleted widget lead history remains available to its owner")
    report["widget_crud"] = {"create": 201, "read": 200, "update": 200, "delete": 200,
                             "cross_tenant_read_update_submissions": 404,
                             "tenant_b_own_submission": b_submission_status}

    status, _, embed = request("GET", f"/api/widgets/{WIDGET_ID}/embed", token=TENANT_A)
    check(status == 200 and "\n" not in embed["snippet"], "one-line embed snippet")
    config_status, config_headers, config = request("GET", f"/api/public/widgets/{WIDGET_ID}/config", origin=ORIGIN)
    check(config_status == 200 and "max-age=60" in config_headers.get("Cache-Control", "") and
          int(config_headers.get("Content-Length", "999999")) < 4096, "config short cache and small payload")
    etag = config_headers.get("ETag")
    not_modified, _, _ = request("GET", f"/api/public/widgets/{WIDGET_ID}/config", origin=ORIGIN, headers={"If-None-Match": etag})
    check(not_modified == 304, "config ETag")
    script_status, script_headers, _ = request("GET", f"/widget.{settings.widget_bundle_version}.js?widget_id={WIDGET_ID}", origin=ORIGIN)
    check(script_status == 200 and "immutable" in script_headers.get("Cache-Control", ""), "versioned bundle cache")
    report["delivery"] = {"snippet": embed["snippet"], "config": config_status, "config_bytes": int(config_headers["Content-Length"]), "config_etag": not_modified,
                           "config_cache": config_headers.get("Cache-Control"), "bundle": script_status,
                           "bundle_cache": script_headers.get("Cache-Control")}

    preflight_status, preflight_headers, _ = request(
        "OPTIONS", "/api/public/submissions", origin=ORIGIN,
        headers={"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,idempotency-key"},
    )
    allow_headers = preflight_headers.get("Access-Control-Allow-Headers", "").lower()
    check(preflight_status == 204 and preflight_headers.get("Access-Control-Allow-Origin") == "*" and
          "post" in preflight_headers.get("Access-Control-Allow-Methods", "").lower() and
          "content-type" in allow_headers and "idempotency-key" in allow_headers, "preflight CORS")
    valid_status, valid_headers, valid = submit(key=f"probe-{RUN_ID}-valid-0001", email="valid@example.test")
    check(valid_status == 201 and valid["accepted"] is True, "valid cross-origin submission")
    check(valid_headers.get("Access-Control-Allow-Origin") == "*", "POST CORS header")
    replay_status, _, replay = submit(key=f"probe-{RUN_ID}-valid-0001", email="valid@example.test")
    check(replay_status == 200 and replay["submission_id"] == valid["submission_id"], "idempotent replay")
    conflict_status, _, _ = submit(key=f"probe-{RUN_ID}-valid-0001", email="different@example.test")
    check(conflict_status == 409, "idempotency conflict")
    status, _, owner_submissions = request("GET", f"/api/widgets/{WIDGET_ID}/submissions", token=TENANT_A)
    check(status == 200 and any(row["id"] == valid["submission_id"] for row in owner_submissions["submissions"]), "stored owner-visible row")
    status, _, _ = request("GET", f"/api/widgets/{WIDGET_ID}/submissions", token=TENANT_B)
    check(status == 404, "tenant B cannot read tenant A submissions")
    report["public_submit"] = {"preflight": preflight_status, "origin": preflight_headers.get("Access-Control-Allow-Origin"),
                               "post": valid_status, "stored": True, "idempotent_replay": replay_status,
                               "conflicting_replay": conflict_status, "cross_tenant_submissions": 404}

    invalid_status, _, invalid = request(
        "POST", "/api/public/submissions",
        body={"widget_id": WIDGET_ID, "fields": {"name": "Missing email"}, "company_website": ""},
        origin=ORIGIN, headers={"Idempotency-Key": f"probe-{RUN_ID}-invalid-0001"},
    )
    check(invalid_status == 422 and invalid["error"]["code"] == "required_field", "malformed field gets clean 4xx")
    syntax_status, _, syntax_error = request("POST", "/api/public/submissions", raw=b"{not-json", origin=ORIGIN,
                                              headers={"Idempotency-Key": f"probe-{RUN_ID}-syntax-0001"})
    check(syntax_status == 400 and syntax_error["error"]["code"] == "invalid_json", "malformed JSON gets clean 400")
    large_body = b'{"widget_id":"' + WIDGET_ID.encode() + b'","fields":{"name":"' + b"x" * (settings.max_request_bytes + 100) + b'"},"company_website":""}'
    oversized_status, _, oversized = request("POST", "/api/public/submissions", raw=large_body, origin=ORIGIN,
                                              headers={"Idempotency-Key": f"probe-{RUN_ID}-oversize-001"})
    check(oversized_status == 413 and oversized["error"]["code"] == "payload_too_large", "oversized body gets JSON 413")
    report["validation"] = {"malformed_json": {"status": syntax_status, "error": syntax_error["error"]["code"]},
                            "missing_required": {"status": invalid_status, "error": invalid["error"]["code"]},
                            "oversized": {"status": oversized_status, "error": oversized["error"]["code"]}}

    time.sleep(1.6)
    burst_results = [submit(key=f"probe-{RUN_ID}-burst-{index:04d}") for index in range(1, 7)]
    burst = [item[0] for item in burst_results]
    check(429 in burst, "burst produces a rate limit response")
    retry_after_values = [headers.get("Retry-After") for status, headers, _ in burst_results if status == 429]
    check(all(int(value or "0") >= 1 for value in retry_after_values),
          "rate limited requests include Retry-After")
    time.sleep(0.75)
    recovery_status, _, _ = submit(key=f"probe-{RUN_ID}-recovery-0001")
    check(recovery_status == 201, "normal request succeeds after token refill")
    report["rate_limit"] = {"burst_statuses": burst, "retry_after_seconds": retry_after_values,
                            "recovery_after_750ms": recovery_status}

    status, _, stats_before_spam = request("GET", "/api/dashboard/summary", token=TENANT_A)
    total_before_spam = int(stats_before_spam["total_submissions"])
    time.sleep(0.8)
    spam_status, _, spam = submit(key=f"probe-{RUN_ID}-honeypot-0001", honeypot="https://bot.example.test")
    # Distinct idempotency keys prove honeypot requests never create stored rows.
    spam_status_again, _, spam_again = submit(key=f"probe-{RUN_ID}-honeypot-0002", honeypot="https://bot.example.test")
    status, _, stats_after_spam_again = request("GET", "/api/dashboard/summary", token=TENANT_A)
    check(spam_status == 201 and spam["accepted"] is True and spam_status_again == 201 and
          stats_after_spam_again["total_submissions"] == total_before_spam, "honeypot is suppressed without storage")
    report["honeypot"] = {"first": spam_status, "second": spam_status_again, "stored": False}

    request("POST", "/api/dev/geo", token=TENANT_A, body={"provider_a_down": True, "provider_b_down": False})
    time.sleep(0.6)
    fallback_status, _, fallback = submit(key=f"probe-{RUN_ID}-geo-fallback-0001")
    check(fallback_status == 201 and fallback["geo"]["provider"] == "provider_b", "provider B fallback")
    status, _, fallback_rows = request("GET", f"/api/widgets/{WIDGET_ID}/submissions", token=TENANT_A)
    check(status == 200 and any(row["id"] == fallback["submission_id"] for row in fallback_rows["submissions"]),
          "fallback-enriched submission is stored")
    request("POST", "/api/dev/geo", token=TENANT_A, body={"provider_a_down": True, "provider_b_down": True})
    time.sleep(0.6)
    degraded_status, _, degraded = submit(key=f"probe-{RUN_ID}-geo-degraded-0001")
    check(degraded_status == 201 and degraded["geo"] is None, "all geo providers down still stores")
    status, _, degraded_rows = request("GET", f"/api/widgets/{WIDGET_ID}/submissions", token=TENANT_A)
    check(status == 200 and any(row["id"] == degraded["submission_id"] for row in degraded_rows["submissions"]),
          "unenriched lead is stored")
    request("POST", "/api/dev/geo", token=TENANT_A, body={"provider_a_down": False, "provider_b_down": False})
    report["geo"] = {"provider_a_down": {"status": fallback_status, "provider": fallback["geo"]["provider"],
                                         "country": fallback["geo"]["country"]},
                      "all_down": {"status": degraded_status, "geo": degraded["geo"]}}

    request("POST", "/api/dev/notification", token=TENANT_A, body={"fail": True})
    time.sleep(0.6)
    notification_status, _, notification = submit(key=f"probe-{RUN_ID}-notification-failure-0001")
    check(notification_status == 201 and notification["notification"] == "queued", "side effect failure does not fail submission")
    job_state = None
    deadline = time.time() + 5
    while time.time() < deadline:
        status, _, jobs = request("GET", "/api/dashboard/jobs", token=TENANT_A)
        job_state = next((job for job in jobs["jobs"] if job["submission_id"] == notification["submission_id"]), None)
        if job_state and job_state["status"] == "dead":
            break
        time.sleep(0.15)
    request("POST", "/api/dev/notification", token=TENANT_A, body={"fail": False})
    status, _, owner_rows = request("GET", f"/api/widgets/{WIDGET_ID}/submissions", token=TENANT_A)
    check(job_state and job_state["status"] == "dead" and job_state["attempts"] == settings.notification_max_attempts,
          "worker retries, records dead job, and alerts")
    check(any(row["id"] == notification["submission_id"] for row in owner_rows["submissions"]), "failed notification lead remains stored")
    report["notification"] = {"submission_response": notification_status, "stored": True,
                               "job_status": job_state["status"], "attempts": job_state["attempts"]}

    status, _, summary = request("GET", "/api/dashboard/summary", token=TENANT_A)
    check(status == 200 and summary["total_submissions"] >= 1 and summary["by_widget"], "owner stats available")
    report["dashboard"] = {"status": status, "total_submissions": summary["total_submissions"],
                           "widget_rows": len(summary["by_widget"]), "geo_rows": len(summary["by_country"])}

    required_files = ["README.md", "capstone.yaml", "EVIDENCE.md", "BUILDLOG.md", ".env.example", ".gitignore", "docs/DESIGN.md"]
    missing_files = [name for name in required_files if not (settings.root / name).is_file()]
    check(not missing_files, "required submission-pack files exist")
    report["submission_pack"] = {"required_files": len(required_files), "missing": missing_files}

    print(json.dumps({"acceptance_probes": "PASS", "results": report}, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"acceptance_probes": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, indent=2), file=sys.stderr)
        raise SystemExit(1)
