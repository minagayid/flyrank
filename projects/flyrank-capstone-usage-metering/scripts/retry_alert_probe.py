"""Deterministically prove invoice-job retries end in one persisted alert.

The probe sets a temporary SQLite location and disables python-dotenv before
importing app modules. It never reads a .env file or uses payment credentials.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    os.environ["PAYMENT_MODE"] = "mock"
    os.environ["DEMO_FREE_KEY"] = "retry-probe-free-demo-key"
    os.environ["DEMO_PRO_KEY"] = "retry-probe-pro-demo-key"
    os.environ["MOCK_WEBHOOK_SECRET"] = "retry-probe-local-mock-only"
    os.environ.pop("STRIPE_SECRET_KEY", None)
    os.environ.pop("STRIPE_WEBHOOK_SECRET", None)

    with tempfile.TemporaryDirectory(prefix="metering-retry-probe-") as temp_dir:
        os.environ["DATABASE_PATH"] = str(Path(temp_dir) / "retry-probe.sqlite3")

        from app.db import initialize_database, read_connection
        from app.jobs import enqueue_invoice_job
        import app.jobs as jobs
        from app.seed import seed_demo_data

        initialize_database()
        seed_demo_data()
        queued = enqueue_invoice_job("demo-free", "2026-09")
        job_id = queued["job_id"]

        calls = 0

        def deterministic_failure(_tenant_id: str, _period: str) -> dict:
            nonlocal calls
            calls += 1
            raise RuntimeError("synthetic failure used only by this probe")

        original_store = jobs.store_invoice_summary
        original_now = jobs._now
        original_logger_disabled = jobs.logger.disabled
        clock = [datetime.now(timezone.utc) + timedelta(seconds=60)]
        jobs.store_invoice_summary = deterministic_failure
        jobs._now = lambda: clock[0]
        jobs.logger.disabled = True

        def snapshot() -> dict:
            with read_connection() as connection:
                row = connection.execute(
                    "SELECT status, attempts, max_attempts, last_error FROM jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
                alerts = connection.execute(
                    "SELECT level, message FROM ops_alerts WHERE job_id=? ORDER BY created_at",
                    (job_id,),
                ).fetchall()
            return {
                "status": row["status"],
                "attempts": row["attempts"],
                "max_attempts": row["max_attempts"],
                "last_error": row["last_error"],
                "alerts": [dict(alert) for alert in alerts],
            }

        try:
            assert jobs.process_one_job() is True
            attempt_one = snapshot()
            assert (
                attempt_one["status"] == "retry"
                and attempt_one["attempts"] == 1
                and attempt_one["max_attempts"] == 3
                and attempt_one["alerts"] == []
            ), attempt_one
            print(
                "PASS attempt 1: status=retry, attempts=1/3, alerts=0"
            )

            clock[0] += timedelta(seconds=3)
            assert jobs.process_one_job() is True
            attempt_two = snapshot()
            assert (
                attempt_two["status"] == "retry"
                and attempt_two["attempts"] == 2
                and attempt_two["alerts"] == []
            ), attempt_two
            print(
                "PASS attempt 2: status=retry, attempts=2/3, alerts=0"
            )

            clock[0] += timedelta(seconds=5)
            assert jobs.process_one_job() is True
            attempt_three = snapshot()
            assert (
                attempt_three["status"] == "failed"
                and attempt_three["attempts"] == 3
                and attempt_three["max_attempts"] == 3
                and attempt_three["last_error"]
                == "Invoice summary worker failed with RuntimeError."
                and attempt_three["alerts"]
                == [
                    {
                        "level": "critical",
                        "message": "Invoice summary job exhausted its retry budget.",
                    }
                ]
                and calls == 3
            ), attempt_three
            print(
                "PASS attempt 3: status=failed, attempts=3/3, one critical alert persisted"
            )

            # Reinitialize and open a fresh connection to prove the terminal state is durable.
            initialize_database()
            persisted = snapshot()
            assert persisted == attempt_three, persisted
            print(
                "PASS reopened SQLite: failed job and critical alert match the committed state"
            )
            print("PASS retry-exhaustion probe: 4/4 checks passed; no payment/provider call made")
        finally:
            jobs.store_invoice_summary = original_store
            jobs._now = original_now
            jobs.logger.disabled = original_logger_disabled


if __name__ == "__main__":
    main()
