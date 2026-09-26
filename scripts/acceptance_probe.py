from __future__ import annotations

import json
import os
import secrets
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def request(base: str, method: str, path: str, body=None, token: str | None = None, headers=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    if token:
        request_headers["Authorization"] = f"Bearer {token}"
    request = Request(base + path, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=3) as response:
            return response.status, response.headers, response.read()
    except HTTPError as response:
        return response.code, response.headers, response.read()


def check(condition: bool, message: str, passed: list[str]) -> None:
    if not condition:
        raise AssertionError(message)
    passed.append(message)


def wait_for_job(base: str, job_id: str, token: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status, _, body = request(base, "GET", f"/jobs/{job_id}", token=token)
        if status == 200:
            job = json.loads(body)["job"]
            if job["status"] in {"succeeded", "failed"}:
                return job
        time.sleep(0.03)
    raise AssertionError(f"Job {job_id} did not finish within {timeout:.1f} seconds.")


def main() -> None:
    password = secrets.token_urlsafe(20)
    os.environ["SIGNAL_DESK_AI_MODE"] = "mock"
    os.environ["SIGNAL_DESK_DEMO_USER"] = "probe-demo"
    os.environ["SIGNAL_DESK_DEMO_PASSWORD"] = password

    with tempfile.TemporaryDirectory(prefix="signal-desk-probe-") as temp_dir:
        os.environ["SIGNAL_DESK_DB_PATH"] = str(Path(temp_dir) / "probe.sqlite3")

        from signal_desk.database import initialize, reader
        from signal_desk.leads import create_lead
        from signal_desk.security import create_user
        from signal_desk.seed import seed
        from signal_desk.triage import (
            OllamaProvider,
            ProviderFailure,
            enqueue,
            get_job,
            process_one,
            validate_assessment,
        )
        import signal_desk.triage as triage_module
        from signal_desk.api import make_server
        from signal_desk.worker import JobWorker

        passed: list[str] = []
        initialize()
        inserted = seed()
        check(inserted == 3, "Seed inserts three fictional example leads.", passed)

        worker = JobWorker()
        server = make_server("127.0.0.1", 0)
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        server_thread.start()

        try:
            status, _, body = request(base, "GET", "/health")
            health = json.loads(body)
            check(status == 200 and health["database"] == "ok" and health["migration"] == 1, "Health route reports initialized SQLite migration 1.", passed)

            status, _, _ = request(base, "GET", "/leads")
            check(status == 401, "Lead API rejects anonymous access with 401.", passed)
            status, _, _ = request(base, "POST", "/auth/login", {"username": "probe-demo", "password": "wrong"})
            check(status == 401, "Login rejects an incorrect password with 401.", passed)

            status, _, body = request(base, "POST", "/auth/login", {"username": "probe-demo", "password": password})
            login_data = json.loads(body)
            token = login_data["access_token"]
            check(status == 200 and login_data["token_type"] == "bearer", "PBKDF2-backed login creates a bearer session.", passed)

            status, _, _ = request(
                base,
                "POST",
                "/leads",
                {"full_name": "Bad Example", "email": "not-an-email", "project_description": "too short"},
                token=token,
            )
            check(status == 422, "Malformed lead input receives a field-validation 422.", passed)

            lead_payload = {
                "full_name": "Casey Example",
                "email": "casey@example.invalid",
                "company": "Good Day Cafe",
                "project_description": "Please create a brand identity and logo system for our cafe launch next month.",
                "budget_range": "$4,000 to $6,000",
                "timeline": "next month",
            }
            status, _, body = request(base, "POST", "/leads", lead_payload, token=token)
            lead_id = json.loads(body)["lead"]["id"]
            check(status == 201 and lead_id.startswith("lead_"), "Authenticated API creates a validated lead.", passed)

            status, _, body = request(
                base,
                "POST",
                f"/leads/{lead_id}/triage",
                token=token,
                headers={"Idempotency-Key": "probe-triage-1"},
            )
            job_id = json.loads(body)["job_id"]
            replay_status, replay_headers, replay_body = request(
                base,
                "POST",
                f"/leads/{lead_id}/triage",
                token=token,
                headers={"Idempotency-Key": "probe-triage-1"},
            )
            replay = json.loads(replay_body)
            check(status == replay_status == 202 and replay["job_id"] == job_id and replay["replayed"], "Background triage enqueue reuses the same job for the same idempotency key.", passed)

            job = wait_for_job(base, job_id, token)
            result = job["result"]
            check(
                job["status"] == "succeeded"
                and result["fit_score"] in range(101)
                and "brand" in result["evidence"]
                and job["attempts"] == 1,
                "Mock triage completes asynchronously with schema-valid, input-grounded evidence.",
                passed,
            )

            clone = dict(lead_payload, full_name="Morgan Example", email="morgan@example.invalid")
            status, _, body = request(base, "POST", "/leads", clone, token=token)
            clone_id = json.loads(body)["lead"]["id"]
            status, _, body = request(
                base,
                "POST",
                f"/leads/{clone_id}/triage",
                token=token,
                headers={"Idempotency-Key": "probe-cache-copy"},
            )
            clone_job = wait_for_job(base, json.loads(body)["job_id"], token)
            check(status == 202 and clone_job["status"] == "succeeded" and clone_job["cache_hit"], "Equivalent triage reuses the content-addressed result cache.", passed)
            with reader() as connection:
                mock_calls = connection.execute(
                    "SELECT COUNT(*) AS total FROM ai_call_ledger WHERE provider='local_mock'"
                ).fetchone()["total"]
            check(mock_calls == 1, "Cache reuse avoids a second model-ledger call.", passed)

            today = datetime.now(timezone.utc).date().isoformat()
            status, headers, pdf = request(
                base, "GET", f"/reports/daily.pdf?date={today}", token=token
            )
            xref_marker = pdf.rsplit(b"startxref\n", 1)
            xref_valid = (
                len(xref_marker) == 2
                and xref_marker[1].splitlines()
                and int(xref_marker[1].splitlines()[0]) == pdf.find(b"xref\n")
            )
            check(
                status == 200
                and headers.get_content_type() == "application/pdf"
                and pdf.startswith(b"%PDF-1.4")
                and xref_valid
                and b"Signal Desk" in pdf
                and b"casey@example.invalid" not in pdf,
                "Authenticated daily PDF has a valid cross-reference offset and omits lead contact details.",
                passed,
            )

            other_password = secrets.token_urlsafe(20)
            create_user("probe-other", other_password)
            from signal_desk.security import login as local_login

            other_session = local_login("probe-other", other_password)
            other_token = other_session["access_token"]
            status, _, _ = request(base, "GET", f"/leads/{lead_id}", token=other_token)
            check(status == 404, "A second authenticated account cannot fetch another user's lead.", passed)

            status, _, _ = request(base, "POST", "/auth/logout", token=token)
            revoked_status, _, _ = request(base, "GET", "/leads", token=token)
            check(status == 200 and revoked_status == 401, "Logout revokes the stored bearer session.", passed)

            # Stop the built-in mock worker so deterministic fake-provider/retry probes own the queue.
            worker.stop()
            demo_user_id = login_data["user"]["id"]

            ollama_lead = create_lead(
                demo_user_id,
                {
                    "full_name": "Taylor Local",
                    "email": "taylor@example.invalid",
                    "company": "Fixture Creative",
                    "project_description": "We need a brand identity for a new workshop.",
                    "budget_range": "under 2000",
                    "timeline": "next month",
                },
            )

            class FakeOllamaHandler(BaseHTTPRequestHandler):
                calls = 0
                omits_contact_fields = False

                def log_message(self, format, *args):
                    return

                def do_POST(self):
                    FakeOllamaHandler.calls += 1
                    size = int(self.headers.get("Content-Length", "0"))
                    incoming = json.loads(self.rfile.read(size))
                    user_message = next(
                        item["content"] for item in incoming["messages"] if item["role"] == "user"
                    )
                    FakeOllamaHandler.omits_contact_fields = (
                        "Taylor Local" not in user_message
                        and "taylor@example.invalid" not in user_message
                    )
                    content = {
                        "fit_score": 74,
                        "urgency": "normal",
                        "evidence": ["brand identity"],
                        "cautions": [],
                        "next_question": "What is the launch date?",
                        "summary": "The request mentions a brand identity project.",
                    }
                    response = json.dumps(
                        {
                            "message": {"content": json.dumps(content)},
                            "prompt_eval_count": 55,
                            "eval_count": 17,
                        }
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)

            fake_server = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllamaHandler)
            fake_thread = threading.Thread(target=fake_server.serve_forever, daemon=True)
            fake_thread.start()
            try:
                provider = OllamaProvider(
                    f"http://127.0.0.1:{fake_server.server_address[1]}", "fixture-model"
                )
                _, _ = enqueue(demo_user_id, ollama_lead["id"], "fixture-ollama")
                with reader() as connection:
                    ollama_job_id = connection.execute(
                        "SELECT id FROM triage_jobs WHERE lead_id=? ORDER BY created_at DESC LIMIT 1",
                        (ollama_lead["id"],),
                    ).fetchone()["id"]
                processed = process_one(provider)
                ollama_job = get_job(demo_user_id, ollama_job_id)
                check(
                    processed
                    and ollama_job["status"] == "succeeded"
                    and ollama_job["result"]["evidence"] == ["brand identity"]
                    and FakeOllamaHandler.calls == 1
                    and FakeOllamaHandler.omits_contact_fields,
                    "Ollama adapter validates grounded output and omits lead name/email from its prompt.",
                    passed,
                )
                with reader() as connection:
                    ledger = connection.execute(
                        """SELECT prompt_tokens, completion_tokens, cost_microusd, outcome
                           FROM ai_call_ledger WHERE provider='ollama' ORDER BY id DESC LIMIT 1"""
                    ).fetchone()
                check(
                    ledger["prompt_tokens"] == 55
                    and ledger["completion_tokens"] == 17
                    and ledger["cost_microusd"] == 0
                    and ledger["outcome"] == "success",
                    "Local model usage is attributed to the lead and recorded at zero provider cost.",
                    passed,
                )
                try:
                    OllamaProvider("https://example.com")
                    remote_refused = False
                except ValueError:
                    remote_refused = True
                check(remote_refused, "Ollama adapter refuses non-loopback or credential-bearing service URLs.", passed)

                # Reaching the test budget prevents another local model request.
                previous_limit = triage_module.DAILY_AI_CALL_LIMIT
                triage_module.DAILY_AI_CALL_LIMIT = 1
                try:
                    budget_lead = create_lead(
                        demo_user_id,
                        {
                            "full_name": "Budget Example",
                            "email": "budget@example.invalid",
                            "company": "Fixture Creative",
                            "project_description": "We need a fresh brand identity for a side project.",
                            "budget_range": "under 2000",
                            "timeline": "next month",
                        },
                    )
                    _, _ = enqueue(demo_user_id, budget_lead["id"], "fixture-budget")
                    with reader() as connection:
                        budget_job_id = connection.execute(
                            "SELECT id FROM triage_jobs WHERE lead_id=? ORDER BY created_at DESC LIMIT 1",
                            (budget_lead["id"],),
                        ).fetchone()["id"]
                    process_one(provider)
                    budget_job = get_job(demo_user_id, budget_job_id)
                    check(
                        budget_job["status"] == "failed"
                        and budget_job["error_code"] == "daily_budget_exceeded"
                        and FakeOllamaHandler.calls == 1,
                        "Daily model-call budget blocks work before a second provider request.",
                        passed,
                    )
                finally:
                    triage_module.DAILY_AI_CALL_LIMIT = previous_limit
            finally:
                fake_server.shutdown()
                fake_server.server_close()
                fake_thread.join(timeout=2)

            retry_lead = create_lead(
                demo_user_id,
                {
                    "full_name": "Retry Example",
                    "email": "retry@example.invalid",
                    "company": "Retry Studio",
                    "project_description": "A brand identity request with enough detail for a first review.",
                    "budget_range": "",
                    "timeline": "",
                },
            )
            retry_job, _ = enqueue(demo_user_id, retry_lead["id"], "retry-check")

            class FlakyProvider:
                name = "probe_flaky"
                model = "deterministic-fixture"

                def __init__(self):
                    self.calls = 0

                def assess(self, lead):
                    self.calls += 1
                    if self.calls < 3:
                        raise ProviderFailure("synthetic_transient_failure")
                    return (
                        {
                            "fit_score": 60,
                            "urgency": "normal",
                            "evidence": ["brand identity"],
                            "cautions": [],
                            "next_question": "What should the first review include?",
                            "summary": "A retry-fixture result for a human to review.",
                        },
                        0,
                        0,
                    )

            flaky = FlakyProvider()
            process_one(flaky)
            first_attempt = get_job(demo_user_id, retry_job["id"])
            check(
                first_attempt["status"] == "queued"
                and first_attempt["attempts"] == 1
                and first_attempt["error_code"] == "synthetic_transient_failure",
                "Transient provider failure returns the durable job to queued with a retry.",
                passed,
            )
            time.sleep(1.1)
            process_one(flaky)
            second_attempt = get_job(demo_user_id, retry_job["id"])
            check(
                second_attempt["status"] == "queued" and second_attempt["attempts"] == 2,
                "Second transient failure remains bounded and records attempt two.",
                passed,
            )
            time.sleep(2.1)
            process_one(flaky)
            final_attempt = get_job(demo_user_id, retry_job["id"])
            check(
                final_attempt["status"] == "succeeded"
                and final_attempt["attempts"] == 3
                and flaky.calls == 3,
                "Job succeeds on the final allowed retry attempt.",
                passed,
            )

            try:
                validate_assessment(
                    {
                        "fit_score": 99,
                        "urgency": "high",
                        "evidence": ["a fact absent from the request"],
                        "cautions": [],
                        "next_question": "Clarify scope?",
                        "summary": "Looks urgent.",
                    },
                    {"project_description": "A small identity request."},
                )
                grounded = False
            except ProviderFailure as exc:
                grounded = exc.code == "unsupported_evidence"
            check(grounded, "Evidence that is not a substring of the submitted brief is rejected.", passed)

            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)
            worker.stop()
            initialize()
            restarted = make_server("127.0.0.1", 0)
            restart_thread = threading.Thread(target=restarted.serve_forever, daemon=True)
            restarted_worker = JobWorker()
            restarted_worker.start()
            restart_thread.start()
            try:
                new_base = f"http://127.0.0.1:{restarted.server_address[1]}"
                status, _, body = request(
                    new_base,
                    "POST",
                    "/auth/login",
                    {"username": "probe-demo", "password": password},
                )
                new_token = json.loads(body)["access_token"]
                status_list, _, lead_bytes = request(
                    new_base, "GET", "/leads", token=new_token
                )
                persisted = json.loads(lead_bytes)["items"]
                status_job, _, job_bytes = request(
                    new_base, "GET", f"/jobs/{retry_job['id']}", token=new_token
                )
                persisted_job = json.loads(job_bytes)["job"]
                check(
                    status == 200
                    and status_list == 200
                    and len(persisted) >= 6
                    and status_job == 200
                    and persisted_job["status"] == "succeeded",
                    "After service restart, authentication, lead rows, and completed job state persist in SQLite.",
                    passed,
                )
            finally:
                restarted.shutdown()
                restarted.server_close()
                restart_thread.join(timeout=2)
                restarted_worker.stop()

        finally:
            worker.stop()
            if server_thread.is_alive():
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)

        print(f"Acceptance result: {len(passed)}/{len(passed)} checks passed.")
        for item in passed:
            print(f"PASS {item}")
        print("Provider boundary: deterministic mock + fake loopback Ollama protocol; no real model server or paid API was called.")
        print("Persistence boundary: temporary SQLite database; no repository data or credentials were used.")


if __name__ == "__main__":
    main()
