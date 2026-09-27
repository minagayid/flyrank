from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import read_connection, transaction
from app.invoices import store_invoice_summary

logger = logging.getLogger("usage_metering.jobs")
LEASE_SECONDS = 30
IDLE_SECONDS = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_invoice_job(tenant_id: str, period: str) -> dict[str, Any]:
    now = _now().isoformat()
    job_id = f"job_{uuid.uuid4().hex}"
    with transaction() as connection:
        tenant = connection.execute("SELECT id FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        if tenant is None:
            raise LookupError("Tenant is not available.")
        connection.execute(
            """INSERT INTO jobs(
                 id, kind, tenant_id, period, status, attempts, max_attempts,
                 next_attempt_at, created_at, updated_at
               ) VALUES (?, 'invoice_summary', ?, ?, 'queued', 0, 3, ?, ?, ?)""",
            (job_id, tenant_id, period, now, now, now),
        )
    return {"job_id": job_id, "kind": "invoice_summary", "status": "queued", "period": period}


def get_invoice_job(tenant_id: str, job_id: str) -> dict[str, Any] | None:
    with read_connection() as connection:
        row = connection.execute(
            """SELECT id, kind, tenant_id, period, status, attempts, max_attempts,
                      next_attempt_at, last_error, created_at, updated_at
               FROM jobs WHERE id = ? AND tenant_id = ?""",
            (job_id, tenant_id),
        ).fetchone()
        if row is None:
            return None
        alert = connection.execute(
            "SELECT level, message, created_at FROM ops_alerts WHERE job_id = ? ORDER BY created_at DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    result = dict(row)
    result["alert"] = dict(alert) if alert else None
    return result


def _claim_job() -> dict[str, Any] | None:
    now = _now()
    timestamp = now.isoformat()
    lease_until = (now + timedelta(seconds=LEASE_SECONDS)).isoformat()
    with transaction() as connection:
        connection.execute(
            """UPDATE jobs SET status='retry', lease_until=NULL, next_attempt_at=?,
                      updated_at=?
               WHERE status='running' AND lease_until IS NOT NULL AND lease_until < ?""",
            (timestamp, timestamp, timestamp),
        )
        row = connection.execute(
            """SELECT id, tenant_id, period, attempts, max_attempts
               FROM jobs WHERE status IN ('queued', 'retry') AND next_attempt_at <= ?
               ORDER BY created_at LIMIT 1""",
            (timestamp,),
        ).fetchone()
        if row is None:
            return None
        attempts = int(row["attempts"]) + 1
        connection.execute(
            """UPDATE jobs SET status='running', attempts=?, lease_until=?, updated_at=?
               WHERE id = ?""",
            (attempts, lease_until, timestamp, row["id"]),
        )
        return {**dict(row), "attempts": attempts}


def _mark_completed(job_id: str) -> None:
    now = _now().isoformat()
    with transaction() as connection:
        connection.execute(
            "UPDATE jobs SET status='completed', lease_until=NULL, last_error=NULL, updated_at=? WHERE id=?",
            (now, job_id),
        )


def _mark_failed_attempt(job: dict[str, Any], error: Exception) -> None:
    now = _now()
    timestamp = now.isoformat()
    attempts = int(job["attempts"])
    message = f"Invoice summary worker failed with {type(error).__name__}."
    with transaction() as connection:
        if attempts >= int(job["max_attempts"]):
            connection.execute(
                """UPDATE jobs SET status='failed', lease_until=NULL, last_error=?, updated_at=? WHERE id=?""",
                (message, timestamp, job["id"]),
            )
            connection.execute(
                """INSERT INTO ops_alerts(id, job_id, level, message, created_at)
                   VALUES (?, ?, 'critical', ?, ?)""",
                (f"alert_{uuid.uuid4().hex}", job["id"], "Invoice summary job exhausted its retry budget.", timestamp),
            )
        else:
            retry_seconds = 2 ** attempts
            next_attempt = (now + timedelta(seconds=retry_seconds)).isoformat()
            connection.execute(
                """UPDATE jobs SET status='retry', lease_until=NULL, last_error=?,
                          next_attempt_at=?, updated_at=? WHERE id=?""",
                (message, next_attempt, timestamp, job["id"]),
            )
    logger.warning("Invoice summary job %s failed on attempt %d.", job["id"], attempts)


def process_one_job() -> bool:
    job = _claim_job()
    if job is None:
        return False
    try:
        store_invoice_summary(job["tenant_id"], job["period"])
        _mark_completed(job["id"])
    except Exception as exc:  # A durable retry handles transient database or calculation failures.
        _mark_failed_attempt(job, exc)
    return True


async def invoice_worker() -> None:
    while True:
        did_work = await asyncio.to_thread(process_one_job)
        if not did_work:
            await asyncio.sleep(IDLE_SECONDS)
