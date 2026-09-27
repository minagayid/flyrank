"""Start the service with another adapter selected only by environment config."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[1]


def check(name: str, condition: bool) -> None:
    if not condition:
        raise SystemExit(f"FAIL {name}")
    print(f"PASS {name}")


with tempfile.TemporaryDirectory(prefix="social-studio-adapter-") as temp_dir:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({"PUBLISHER": "mock_linkedin", "DATABASE_PATH": str(Path(temp_dir) / "studio.db"), "DEMO_SEED": "false", "POLL_SECONDS": "1"})
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        client = httpx.Client(base_url=base, timeout=3)
        deadline = time.monotonic() + 15
        ready = False
        while time.monotonic() < deadline:
            try:
                response = client.get("/health")
                if response.status_code == 200:
                    ready = True
                    break
            except httpx.HTTPError:
                time.sleep(0.2)
        check("service starts with a different configured adapter", ready and response.json()["publisher"] == "mock_linkedin")
        post = client.post("/posts", json={"source_markdown": "Teams improve products by reviewing evidence and learning from results."}).json()
        variants = client.post(f"/posts/{post['id']}/generate").json()
        variant = next(item for item in variants if item["platform"] == "mock_x")
        approved = client.patch(f"/variants/{variant['id']}", json={"decision": "approve"})
        slot = "2026-01-01T00:00:00+00:00"
        schedule = client.post(f"/variants/{variant['id']}/schedule", json={"scheduled_at": slot}).json()
        published = client.post(f"/schedules/{schedule['id']}/publish")
        history = client.get("/history").json()
        entry = next((item for item in history if item["schedule_id"] == schedule["id"]), None)
        check("adapter changes through configuration with no workflow code change", approved.status_code == 200 and published.status_code == 200 and entry and entry["adapter"] == "mock:mock_linkedin")
        client.close()
    finally:
        process.terminate()
        process.wait(timeout=10)

print("PASS adapter swap probe used an isolated temporary database and sent no external messages")
