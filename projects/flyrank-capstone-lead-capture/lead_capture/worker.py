from __future__ import annotations

import threading
import time
import uuid

from .config import Settings
from .db import connect, utc_now
from .services import DevSwitches


class NotificationWorker:
    """Outbox worker for non-critical notifications, isolated from the submit response."""

    def __init__(self, settings: Settings, switches: DevSwitches):
        self.settings = settings
        self.switches = switches
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="notification-outbox", daemon=True)

    def start(self) -> None:
        with connect(self.settings) as connection:
            connection.execute(
                "UPDATE notification_jobs SET status='queued', available_at=? WHERE status='processing'",
                (time.time(),),
            )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            job = self._claim_one()
            if job is None:
                self._stop.wait(0.2)
                continue
            self._deliver(job)

    def _claim_one(self) -> dict | None:
        now = time.time()
        with connect(self.settings) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT id, submission_id, attempts FROM notification_jobs "
                "WHERE status='queued' AND available_at<=? ORDER BY created_at LIMIT 1",
                (now,),
            ).fetchone()
            if row is None:
                connection.execute("COMMIT")
                return None
            connection.execute(
                "UPDATE notification_jobs SET status='processing', attempts=attempts+1, updated_at=? WHERE id=?",
                (utc_now(), row["id"]),
            )
            connection.execute("COMMIT")
            return {"id": row["id"], "submission_id": row["submission_id"], "attempt": row["attempts"] + 1}

    def _deliver(self, job: dict) -> None:
        state = self.switches.get()
        try:
            if state["notification_fail"]:
                raise RuntimeError("simulated notification provider outage")
            # Local demo side effect: this is intentionally a log, never a real email.
            print(f"NOTIFY simulated confirmation queued for submission_id={job['submission_id']}")
            with connect(self.settings) as connection:
                connection.execute(
                    "UPDATE notification_jobs SET status='sent', last_error=NULL, updated_at=? WHERE id=?",
                    (utc_now(), job["id"]),
                )
        except Exception as exc:
            attempts = int(job["attempt"])
            now = utc_now()
            if attempts >= self.settings.notification_max_attempts:
                with connect(self.settings) as connection:
                    connection.execute(
                        "UPDATE notification_jobs SET status='dead', last_error=?, updated_at=? WHERE id=?",
                        (type(exc).__name__, now, job["id"]),
                    )
                print(f"ALERT notification job exhausted retries job_id={job['id']} attempts={attempts}; submission remains stored")
            else:
                delay = min(0.25 * (2 ** (attempts - 1)), 2.0)
                with connect(self.settings) as connection:
                    connection.execute(
                        "UPDATE notification_jobs SET status='queued', available_at=?, last_error=?, updated_at=? WHERE id=?",
                        (time.time() + delay, type(exc).__name__, now, job["id"]),
                    )
                print(f"WARN notification retry scheduled job_id={job['id']} attempt={attempts}")
