from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db import read_connection, transaction
from app.metering import get_usage
from app.pricing import format_cents


def build_invoice_summary(tenant_id: str, period: str) -> dict[str, Any]:
    usage = get_usage(tenant_id, period)
    plan = usage["plan"]
    amount_due = usage["subscription_monthly_price_cents"]
    calls = usage["usage"]["api_calls"]["used"]
    tokens = usage["usage"]["ai_tokens"]["used"]
    call_cost = usage["cost_estimate"]["api_calls_cents_rounded"]
    token_cost = usage["cost_estimate"]["ai_tokens_cents_rounded"]
    summary = {
        "invoice_id": f"preview_{tenant_id}_{period}",
        "tenant_id": tenant_id,
        "period": period,
        "currency": "USD",
        "plan": plan,
        "lines": [
            {
                "kind": "subscription",
                "description": f"{plan['name']} monthly plan",
                "quantity": 1,
                "amount_cents": amount_due,
                "amount": format_cents(amount_due),
            },
            {
                "kind": "included_api_calls",
                "description": "Included API calls (cost estimate, not billed)",
                "quantity": calls,
                "amount_cents": 0,
                "estimated_cost_cents": call_cost,
                "estimated_cost": format_cents(call_cost),
            },
            {
                "kind": "included_ai_tokens",
                "description": "Included AI tokens (cost estimate, not billed)",
                "quantity": tokens,
                "amount_cents": 0,
                "estimated_cost_cents": token_cost,
                "estimated_cost": format_cents(token_cost),
            },
        ],
        "usage_cost_estimate_cents": call_cost + token_cost,
        "subscription_amount_due_cents": amount_due,
        "amount_due_cents": amount_due,
        "amount_due": format_cents(amount_due),
        "note": "Preview only. Included usage is not charged again; over-quota usage is rejected.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return summary


def store_invoice_summary(tenant_id: str, period: str) -> dict[str, Any]:
    summary = build_invoice_summary(tenant_id, period)
    now = datetime.now(timezone.utc).isoformat()
    with transaction() as connection:
        connection.execute(
            """INSERT INTO invoice_summaries(id, tenant_id, period, summary_json, created_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, period) DO UPDATE SET
                 summary_json=excluded.summary_json, created_at=excluded.created_at""",
            (f"inv_{uuid.uuid4().hex}", tenant_id, period, json.dumps(summary), now),
        )
    return summary


def get_stored_invoice(tenant_id: str, period: str) -> dict[str, Any] | None:
    with read_connection() as connection:
        row = connection.execute(
            "SELECT summary_json FROM invoice_summaries WHERE tenant_id = ? AND period = ?",
            (tenant_id, period),
        ).fetchone()
    return json.loads(row["summary_json"]) if row else None
