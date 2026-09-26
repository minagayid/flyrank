from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.db import read_connection, transaction
from app.pricing import round_microcents_to_cents, token_cost_microcents


@dataclass(frozen=True)
class MeterResult:
    status_code: int
    body: dict[str, Any]
    replayed: bool = False


def _month_bounds(period: str) -> tuple[str, str]:
    start = datetime.strptime(period, "%Y-%m").replace(tzinfo=timezone.utc)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(), end.isoformat()


def _period_for(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m")


def _seconds_until_next_month(now: datetime) -> int:
    utc_now = now.astimezone(timezone.utc)
    if utc_now.month == 12:
        next_month = utc_now.replace(year=utc_now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        next_month = utc_now.replace(month=utc_now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((next_month - utc_now).total_seconds()))


def _billing_state(connection: sqlite3.Connection, tenant_id: str) -> tuple[sqlite3.Row | None, sqlite3.Row | None]:
    tenant = connection.execute("SELECT id, name FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    if tenant is None:
        return None, None
    subscription = connection.execute(
        """SELECT s.tenant_id, s.plan_id, s.status, s.stripe_customer_id,
                  s.stripe_subscription_id, p.name AS plan_name,
                  p.api_calls_limit, p.ai_tokens_limit, p.monthly_price_cents,
                  p.api_call_microcents, p.input_microcents_per_token,
                  p.cached_input_microcents_per_token, p.output_microcents_per_token,
                  p.reasoning_microcents_per_token
           FROM subscriptions s JOIN plans p ON p.id = s.plan_id
           WHERE s.tenant_id = ?""",
        (tenant_id,),
    ).fetchone()
    return tenant, subscription


def _usage_quantities(connection: sqlite3.Connection, tenant_id: str, period: str) -> dict[str, int]:
    row = connection.execute(
        """SELECT COALESCE(SUM(api_call_quantity), 0) AS api_calls,
                  COALESCE(SUM(CASE WHEN event_type IN ('ai_tokens', 'billable_action')
                                    THEN quantity ELSE 0 END), 0) AS ai_tokens
           FROM usage_events WHERE tenant_id = ? AND period = ?""",
        (tenant_id, period),
    ).fetchone()
    return {"api_calls": int(row["api_calls"]), "ai_tokens": int(row["ai_tokens"])}


def _error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, **extra}}


def record_usage(
    tenant_id: str,
    idempotency_key: str,
    request_hash: str,
    requested: list[dict[str, Any]],
) -> MeterResult:
    now = datetime.now(timezone.utc)
    period = _period_for(now)
    timestamp = now.isoformat()

    with transaction() as connection:
        cached = connection.execute(
            """SELECT request_hash, http_status, response_json FROM idempotency_records
               WHERE tenant_id = ? AND idempotency_key = ?""",
            (tenant_id, idempotency_key),
        ).fetchone()
        if cached:
            if cached["request_hash"] != request_hash:
                return MeterResult(
                    409,
                    _error_body("idempotency_key_reused", "This key was already used with a different request."),
                )
            return MeterResult(cached["http_status"], json.loads(cached["response_json"]), replayed=True)

        tenant, subscription = _billing_state(connection, tenant_id)
        if tenant is None or subscription is None:
            body = _error_body("tenant_not_ready", "This tenant is not available for metering.")
            connection.execute(
                "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, idempotency_key, request_hash, 404, json.dumps(body), timestamp),
            )
            return MeterResult(404, body)

        if subscription["status"] != "active":
            body = _error_body(
                "subscription_inactive",
                "This subscription is not active. Update billing or choose an active plan before using the service.",
                subscription_status=subscription["status"],
            )
            connection.execute(
                "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, idempotency_key, request_hash, 402, json.dumps(body), timestamp),
            )
            return MeterResult(402, body)

        current = _usage_quantities(connection, tenant_id, period)
        requested_totals = {"api_calls": 0, "ai_tokens": 0}
        for item in requested:
            event_type = item["event_type"]
            if event_type == "api_calls":
                requested_totals["api_calls"] += int(item["quantity"])
            elif event_type == "ai_tokens":
                requested_totals["ai_tokens"] += int(item["quantity"])
            elif event_type == "billable_action":
                requested_totals["api_calls"] += int(item.get("api_call_quantity", 1))
                requested_totals["ai_tokens"] += int(item["quantity"])
            else:
                raise ValueError("Unsupported usage event type.")

        for event_type, requested_quantity in requested_totals.items():
            if requested_quantity == 0:
                continue
            limit_column = "api_calls_limit" if event_type == "api_calls" else "ai_tokens_limit"
            limit = int(subscription[limit_column])
            projected = current[event_type] + requested_quantity
            if projected > limit:
                retry_after = _seconds_until_next_month(now)
                body = _error_body(
                    "usage_quota_exceeded",
                    f"The {event_type.replace('_', ' ')} quota would be exceeded: {current[event_type]} used + {requested_quantity} requested > {limit} allowed this month.",
                    usage_type=event_type,
                    used=current[event_type],
                    requested=requested_quantity,
                    limit=limit,
                    retry_after_seconds=retry_after,
                )
                connection.execute(
                    "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?)",
                    (tenant_id, idempotency_key, request_hash, 429, json.dumps(body), timestamp),
                )
                return MeterResult(429, body)

        inserted: list[dict[str, Any]] = []
        for item in requested:
            event_type = item["event_type"]
            quantity = int(item["quantity"])
            token_counts = item.get("tokens") or {}
            api_call_quantity = int(item.get("api_call_quantity", quantity if event_type == "api_calls" else 0))
            api_cost_microcents = api_call_quantity * int(subscription["api_call_microcents"])
            token_cost = (
                token_cost_microcents(token_counts, dict(subscription))
                if event_type in {"ai_tokens", "billable_action"}
                else 0
            )
            cost_microcents = api_cost_microcents + token_cost
            event_id = f"use_{uuid.uuid4().hex}"
            connection.execute(
                """INSERT INTO usage_events(
                       id, tenant_id, event_type, quantity, api_call_quantity, input_tokens,
                       cached_input_tokens, output_tokens, reasoning_tokens,
                       cost_microcents, api_call_cost_microcents, token_cost_microcents,
                       idempotency_key, period, occurred_at, metadata_json
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    tenant_id,
                    event_type,
                    quantity,
                    api_call_quantity,
                    token_counts.get("input_tokens", 0),
                    token_counts.get("cached_input_tokens", 0),
                    token_counts.get("output_tokens", 0),
                    token_counts.get("reasoning_tokens", 0),
                    cost_microcents,
                    api_cost_microcents,
                    token_cost,
                    idempotency_key,
                    period,
                    timestamp,
                    json.dumps({"source": "simulated" if event_type in {"ai_tokens", "billable_action"} else "billable_action"}),
                ),
            )
            inserted.append(
                {
                    "id": event_id,
                    "type": event_type,
                    "quantity": quantity,
                    "api_calls": api_call_quantity,
                    "ai_tokens": quantity if event_type in {"ai_tokens", "billable_action"} else 0,
                    "cost_microcents": cost_microcents,
                    "cost_cents_rounded": round_microcents_to_cents(cost_microcents),
                }
            )

        final_usage = {
            "api_calls": current["api_calls"] + requested_totals["api_calls"],
            "ai_tokens": current["ai_tokens"] + requested_totals["ai_tokens"],
        }
        response_body = {
            "accepted": True,
            "tenant_id": tenant_id,
            "period": period,
            "events": inserted,
            "usage": {
                "api_calls": {"used": final_usage["api_calls"], "limit": int(subscription["api_calls_limit"])},
                "ai_tokens": {"used": final_usage["ai_tokens"], "limit": int(subscription["ai_tokens_limit"])},
            },
        }
        connection.execute(
            "INSERT INTO idempotency_records VALUES (?, ?, ?, ?, ?, ?)",
            (tenant_id, idempotency_key, request_hash, 201, json.dumps(response_body), timestamp),
        )
        return MeterResult(201, response_body)


def get_usage(tenant_id: str, period: str | None = None) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    selected_period = period or _period_for(now)
    _month_bounds(selected_period)
    with read_connection() as connection:
        tenant, subscription = _billing_state(connection, tenant_id)
        if tenant is None or subscription is None:
            raise LookupError("Tenant is not available.")
        current = _usage_quantities(connection, tenant_id, selected_period)
        costs = connection.execute(
            """SELECT COALESCE(SUM(api_call_cost_microcents), 0) AS api_call_cost,
                      COALESCE(SUM(token_cost_microcents), 0) AS token_cost
               FROM usage_events WHERE tenant_id = ? AND period = ?""",
            (tenant_id, selected_period),
        ).fetchone()
    cost_by_type = {
        "api_calls": int(costs["api_call_cost"]),
        "ai_tokens": int(costs["token_cost"]),
    }
    calls_limit = int(subscription["api_calls_limit"])
    tokens_limit = int(subscription["ai_tokens_limit"])
    return {
        "tenant_id": tenant_id,
        "period": selected_period,
        "plan": {"id": subscription["plan_id"], "name": subscription["plan_name"], "status": subscription["status"]},
        "usage": {
            "api_calls": {"used": current["api_calls"], "limit": calls_limit, "remaining": max(0, calls_limit - current["api_calls"])},
            "ai_tokens": {"used": current["ai_tokens"], "limit": tokens_limit, "remaining": max(0, tokens_limit - current["ai_tokens"])},
        },
        "cost_estimate": {
            "currency": "USD",
            "api_calls_microcents": cost_by_type["api_calls"],
            "api_calls_cents_rounded": round_microcents_to_cents(cost_by_type["api_calls"]),
            "ai_tokens_microcents": cost_by_type["ai_tokens"],
            "ai_tokens_cents_rounded": round_microcents_to_cents(cost_by_type["ai_tokens"]),
            "total_cents_rounded": round_microcents_to_cents(sum(cost_by_type.values())),
        },
        "subscription_monthly_price_cents": int(subscription["monthly_price_cents"]),
    }
