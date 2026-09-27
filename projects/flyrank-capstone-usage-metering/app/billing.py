from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.config import (
    APP_BASE_URL,
    MOCK_WEBHOOK_SECRET,
    PAYMENT_MODE,
    PRO_MONTHLY_PRICE_CENTS,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
)
from app.db import read_connection, transaction
from app.security import request_fingerprint


class WebhookVerificationError(Exception):
    """The supplied webhook signature is absent, stale, or invalid."""


class WebhookPayloadError(Exception):
    """The verified event does not match a known tenant or checkout session."""


@dataclass(frozen=True)
class CheckoutResult:
    status_code: int
    body: dict[str, Any]
    replayed: bool = False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stripe_test_configured() -> bool:
    return (
        STRIPE_SECRET_KEY.startswith("sk_test_")
        and STRIPE_SECRET_KEY != "sk_test_replace_me"
        and STRIPE_WEBHOOK_SECRET.startswith("whsec_")
        and STRIPE_WEBHOOK_SECRET != "whsec_replace_me"
    )


def create_checkout(
    tenant_id: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> CheckoutResult:
    request_hash = request_fingerprint("POST", "/billing/checkout", payload)
    with read_connection() as connection:
        cached = connection.execute(
            """SELECT request_hash, http_status, response_json FROM idempotency_records
               WHERE tenant_id = ? AND idempotency_key = ?""",
            (tenant_id, idempotency_key),
        ).fetchone()
        subscription = connection.execute(
            "SELECT plan_id, status FROM subscriptions WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
    if cached:
        if cached["request_hash"] != request_hash:
            return CheckoutResult(409, {"error": {"code": "idempotency_key_reused", "message": "This key was already used with a different request."}})
        return CheckoutResult(cached["http_status"], json.loads(cached["response_json"]), replayed=True)
    if subscription is None:
        return CheckoutResult(404, {"error": {"code": "tenant_not_ready", "message": "This tenant is not available for billing."}})
    if subscription["plan_id"] == "pro" and subscription["status"] == "active":
        return CheckoutResult(409, {"error": {"code": "already_on_pro", "message": "This tenant already has an active Pro plan."}})

    local_session_id = f"cs_{uuid.uuid4().hex}"
    provider = PAYMENT_MODE
    if PAYMENT_MODE == "mock":
        # Same tenant + key always reuses the same local session, even after a process retry.
        digest = hashlib.sha256(f"{tenant_id}:{idempotency_key}".encode("utf-8")).hexdigest()[:24]
        provider_session_id = f"cs_mock_{digest}"
        local_session_id = provider_session_id
        checkout_url = f"{APP_BASE_URL}/mock-checkout/{local_session_id}"
    else:
        if not _stripe_test_configured():
            return CheckoutResult(503, {"error": {"code": "stripe_test_not_configured", "message": "Stripe test mode requires sk_test_ and whsec_ credentials; mock mode works without credentials."}})
        try:
            import stripe

            stripe.api_key = STRIPE_SECRET_KEY
            stripe_key = hashlib.sha256(f"{tenant_id}:{idempotency_key}".encode("utf-8")).hexdigest()
            session = stripe.checkout.Session.create(
                mode="subscription",
                success_url=f"{APP_BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{APP_BASE_URL}/billing/cancel",
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": PRO_MONTHLY_PRICE_CENTS,
                            "product_data": {"name": "Usage Metering Pro"},
                            "recurring": {"interval": "month"},
                        },
                        "quantity": 1,
                    }
                ],
                metadata={"tenant_id": tenant_id, "plan": "pro"},
                subscription_data={"metadata": {"tenant_id": tenant_id, "plan": "pro"}},
                client_reference_id=tenant_id,
                idempotency_key=f"checkout-{stripe_key}",
            )
            if getattr(session, "livemode", False):
                raise RuntimeError("Stripe returned a live-mode session; refusing to store it.")
            provider_session_id = str(session.id)
            checkout_url = str(session.url)
            local_session_id = provider_session_id
        except Exception as exc:
            # Do not return provider response text; it can contain request details.
            return CheckoutResult(502, {"error": {"code": "stripe_checkout_failed", "message": f"Stripe test Checkout could not be created ({type(exc).__name__})."}})

    response_body = {
        "checkout_id": local_session_id,
        "provider_session_id": provider_session_id,
        "provider_mode": provider,
        "checkout_url": checkout_url,
        "subscription_amount_cents": PRO_MONTHLY_PRICE_CENTS,
        "note": "Creating this session does not charge a card. Only a verified subscription event updates the tenant plan.",
    }
    now = _now()
    with transaction() as connection:
        connection.execute(
            """INSERT OR IGNORE INTO checkout_sessions(
                   id, tenant_id, plan_id, provider, provider_session_id,
                   status, checkout_url, created_at
               ) VALUES (?, ?, 'pro', ?, ?, 'open', ?, ?)""",
            (local_session_id, tenant_id, provider, provider_session_id, checkout_url, now),
        )
        connection.execute(
            """INSERT INTO idempotency_records(
                 tenant_id, idempotency_key, request_hash, http_status, response_json, created_at
               ) VALUES (?, ?, ?, 201, ?, ?)""",
            (tenant_id, idempotency_key, request_hash, json.dumps(response_body), now),
        )
    return CheckoutResult(201, response_body)


def _verify_mock_signature(raw_body: bytes, header: str) -> dict[str, Any]:
    parts: dict[str, list[str]] = {}
    for component in header.split(","):
        key, separator, value = component.partition("=")
        if separator:
            parts.setdefault(key.strip(), []).append(value.strip())
    timestamp_values = parts.get("t", [])
    signatures = parts.get("v1", [])
    if not timestamp_values or not signatures:
        raise WebhookVerificationError("Missing signature fields.")
    timestamp = timestamp_values[0]
    try:
        signed_at = int(timestamp)
    except ValueError as exc:
        raise WebhookVerificationError("Invalid signature timestamp.") from exc
    if abs(int(time.time()) - signed_at) > 300:
        raise WebhookVerificationError("Signature timestamp is outside the accepted window.")
    signed_payload = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(MOCK_WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        raise WebhookVerificationError("Signature mismatch.")
    try:
        event = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WebhookPayloadError("The signed event body is not valid JSON.") from exc
    if not isinstance(event, dict):
        raise WebhookPayloadError("The event body must be a JSON object.")
    return event


def sign_mock_payload(raw_body: bytes) -> str:
    timestamp = str(int(time.time()))
    signed_payload = timestamp.encode("ascii") + b"." + raw_body
    signature = hmac.new(MOCK_WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _verified_event(raw_body: bytes, signature_header: str | None) -> dict[str, Any]:
    if not signature_header:
        raise WebhookVerificationError("Missing Stripe-Signature header.")
    if PAYMENT_MODE == "mock":
        return _verify_mock_signature(raw_body, signature_header)
    if not _stripe_test_configured():
        raise WebhookVerificationError("Stripe test webhook verification is not configured.")
    try:
        import stripe

        event = stripe.Webhook.construct_event(raw_body, signature_header, STRIPE_WEBHOOK_SECRET)
        if hasattr(event, "to_dict_recursive"):
            return event.to_dict_recursive()
        return dict(event)
    except Exception as exc:
        raise WebhookVerificationError("Stripe rejected the webhook signature or payload.") from exc


def _find_tenant_for_subscription(connection: sqlite3.Connection, subscription_id: str) -> str | None:
    row = connection.execute(
        "SELECT tenant_id FROM subscriptions WHERE stripe_subscription_id = ?", (subscription_id,)
    ).fetchone()
    return row["tenant_id"] if row else None


def _apply_subscription_event(
    connection: sqlite3.Connection,
    event_type: str,
    event_object: dict[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    metadata = event_object.get("metadata") or {}
    tenant_id = metadata.get("tenant_id") or event_object.get("client_reference_id")
    subscription_id = event_object.get("subscription") or event_object.get("id")
    if not tenant_id and subscription_id:
        tenant_id = _find_tenant_for_subscription(connection, str(subscription_id))

    if event_type == "checkout.session.completed":
        provider_session_id = str(event_object.get("id") or "")
        checkout = connection.execute(
            "SELECT id, tenant_id, provider FROM checkout_sessions WHERE provider_session_id = ?",
            (provider_session_id,),
        ).fetchone()
        if checkout is None or checkout["provider"] != PAYMENT_MODE:
            raise WebhookPayloadError("Checkout session is not one created by this service.")
        if tenant_id and tenant_id != checkout["tenant_id"]:
            raise WebhookPayloadError("Checkout tenant metadata does not match the stored session.")
        tenant_id = checkout["tenant_id"]
        if event_object.get("status") != "complete" or event_object.get("payment_status") not in {"paid", "no_payment_required"}:
            return tenant_id, {"applied": False, "reason": "checkout is not complete and paid"}
        stripe_subscription_id = event_object.get("subscription")
        if not stripe_subscription_id:
            raise WebhookPayloadError("Completed Pro Checkout did not include a subscription ID.")
        connection.execute(
            """UPDATE subscriptions SET plan_id='pro', status='active',
                      stripe_customer_id=?, stripe_subscription_id=?, updated_at=?
               WHERE tenant_id=?""",
            (event_object.get("customer"), str(stripe_subscription_id), _now(), tenant_id),
        )
        connection.execute(
            "UPDATE checkout_sessions SET status='completed', completed_at=? WHERE id=?",
            (_now(), checkout["id"]),
        )
        return tenant_id, {"applied": True, "plan_id": "pro", "subscription_status": "active"}

    if not tenant_id:
        raise WebhookPayloadError("Subscription event is not associated with a known tenant.")
    tenant_exists = connection.execute("SELECT 1 FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    if tenant_exists is None:
        raise WebhookPayloadError("Subscription event references an unknown tenant.")

    if event_type == "customer.subscription.deleted":
        plan_id, status = "free", "canceled"
    else:
        provider_status = str(event_object.get("status") or "incomplete")
        if provider_status in {"active", "trialing"}:
            plan_id, status = "pro", "active"
        elif provider_status in {"past_due", "unpaid"}:
            plan_id, status = "pro", "past_due"
        elif provider_status in {"canceled", "incomplete_expired", "paused"}:
            plan_id, status = "free", "canceled"
        else:
            plan_id, status = "pro", "incomplete"

    connection.execute(
        """UPDATE subscriptions SET plan_id=?, status=?,
                  stripe_customer_id=COALESCE(?, stripe_customer_id),
                  stripe_subscription_id=COALESCE(?, stripe_subscription_id), updated_at=?
           WHERE tenant_id=?""",
        (
            plan_id,
            status,
            event_object.get("customer"),
            str(subscription_id) if subscription_id else None,
            _now(),
            tenant_id,
        ),
    )
    return tenant_id, {"applied": True, "plan_id": plan_id, "subscription_status": status}


def apply_verified_event(event: dict[str, Any]) -> dict[str, Any]:
    event_id = event.get("id")
    event_type = event.get("type")
    data = event.get("data") or {}
    event_object = data.get("object") or {}
    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
        raise WebhookPayloadError("Event must include a string id and type.")
    if not isinstance(event_object, dict):
        raise WebhookPayloadError("Event data.object must be an object.")

    now = _now()
    with transaction() as connection:
        existing = connection.execute("SELECT 1 FROM stripe_events WHERE event_id = ?", (event_id,)).fetchone()
        if existing:
            return {"received": True, "duplicate": True, "applied": False, "event_id": event_id}

        result: dict[str, Any]
        tenant_id: str | None = None
        if event_type in {
            "checkout.session.completed",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        }:
            tenant_id, result = _apply_subscription_event(connection, event_type, event_object)
        else:
            result = {"applied": False, "ignored": True, "reason": "event type is not handled"}

        connection.execute(
            "INSERT INTO stripe_events(event_id, event_type, tenant_id, processed_at, result_json) VALUES (?, ?, ?, ?, ?)",
            (event_id, event_type, tenant_id, now, json.dumps(result)),
        )
    return {"received": True, "duplicate": False, "event_id": event_id, **result}


def receive_webhook(raw_body: bytes, signature_header: str | None) -> dict[str, Any]:
    event = _verified_event(raw_body, signature_header)
    return apply_verified_event(event)


def complete_mock_checkout(tenant_id: str, session_id: str) -> dict[str, Any]:
    if PAYMENT_MODE != "mock":
        raise LookupError("Mock checkout completion is disabled outside mock mode.")
    with read_connection() as connection:
        checkout = connection.execute(
            """SELECT id, tenant_id, provider, status FROM checkout_sessions
               WHERE id=? AND tenant_id=?""",
            (session_id, tenant_id),
        ).fetchone()
    if checkout is None or checkout["provider"] != "mock":
        raise LookupError("Mock checkout session is not available to this tenant.")

    event_id_hash = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
    event = {
        "id": f"evt_mock_{event_id_hash}",
        "object": "event",
        "created": int(time.time()),
        "livemode": False,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "mode": "subscription",
                "status": "complete",
                "payment_status": "paid",
                "subscription": f"sub_mock_{event_id_hash}",
                "customer": f"cus_mock_{event_id_hash}",
                "client_reference_id": tenant_id,
                "metadata": {"tenant_id": tenant_id, "plan": "pro"},
            }
        },
    }
    body = json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return receive_webhook(body, sign_mock_payload(body))
