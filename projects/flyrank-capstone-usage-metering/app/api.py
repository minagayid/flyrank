from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.billing import (
    WebhookPayloadError,
    WebhookVerificationError,
    complete_mock_checkout,
    create_checkout,
    receive_webhook,
)
from app.config import PAYMENT_MODE
from app.db import read_connection
from app.invoices import build_invoice_summary
from app.jobs import enqueue_invoice_job, get_invoice_job
from app.metering import get_usage, record_usage
from app.schemas import CheckoutRequest, GenerateRequest, MeterEventRequest
from app.security import authenticate_tenant, request_fingerprint

router = APIRouter()
PERIOD_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def tenant_context(
    tenant_id: str = Header(..., alias="X-Tenant-ID", description="Tenant identity from the local seed."),
    tenant_key: str = Header(..., alias="X-Tenant-Key", description="Demo key for this tenant; never use these sample keys in production."),
) -> dict[str, Any]:
    return authenticate_tenant(tenant_id, tenant_key)


def required_idempotency_key(value: str | None) -> str:
    if value is None or not value.strip():
        raise HTTPException(status_code=400, detail={"code": "idempotency_key_required", "message": "Provide a non-empty Idempotency-Key header."})
    cleaned = value.strip()
    if len(cleaned) > 200:
        raise HTTPException(status_code=400, detail={"code": "idempotency_key_too_long", "message": "Idempotency-Key must be at most 200 characters."})
    return cleaned


def checked_period(period: str | None) -> str:
    if period is None:
        return datetime.now(timezone.utc).strftime("%Y-%m")
    if not PERIOD_PATTERN.fullmatch(period):
        raise HTTPException(status_code=422, detail={"code": "invalid_period", "message": "period must use YYYY-MM with a valid month."})
    return period


def _meter_response(result: Any) -> JSONResponse:
    headers = {"Idempotent-Replayed": str(result.replayed).lower()}
    retry_after = result.body.get("error", {}).get("retry_after_seconds")
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(status_code=result.status_code, content=result.body, headers=headers)


@router.get("/health", tags=["system"], summary="Check service and database readiness")
def health() -> dict[str, Any]:
    with read_connection() as connection:
        connection.execute("SELECT 1").fetchone()
        migration = connection.execute("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations").fetchone()
    return {"status": "ok", "service": "usage-metering", "database": "sqlite", "migration_version": migration["version"]}


@router.get("/plans", tags=["plans"], summary="List pinned plans and example rates")
def list_plans() -> dict[str, Any]:
    with read_connection() as connection:
        rows = connection.execute(
            """SELECT id, name, api_calls_limit, ai_tokens_limit, monthly_price_cents,
                      api_call_microcents, input_microcents_per_token,
                      cached_input_microcents_per_token, output_microcents_per_token,
                      reasoning_microcents_per_token
               FROM plans ORDER BY monthly_price_cents"""
        ).fetchall()
    return {
        "currency": "USD",
        "microcents_per_cent": 1_000_000,
        "plans": [dict(row) for row in rows],
    }


@router.post("/generate", tags=["metering"], summary="Simulate one billable AI response")
def generate(
    payload: GenerateRequest,
    tenant: dict[str, Any] = Depends(tenant_context),
    idempotency_header: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
) -> JSONResponse:
    idempotency_key = required_idempotency_key(idempotency_header)
    body = payload.model_dump()
    token_counts = body["tokens"]
    requested = [{
        "event_type": "billable_action",
        "api_call_quantity": 1,
        "quantity": payload.tokens.total_tokens,
        "tokens": token_counts,
    }]
    fingerprint = request_fingerprint("POST", "/generate", body)
    result = record_usage(tenant["id"], idempotency_key, fingerprint, requested)
    return _meter_response(result)


@router.post("/usage/events", tags=["metering"], summary="Record explicit usage for quota demonstrations")
def meter_event(
    payload: MeterEventRequest,
    tenant: dict[str, Any] = Depends(tenant_context),
    idempotency_header: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
) -> JSONResponse:
    idempotency_key = required_idempotency_key(idempotency_header)
    body = payload.model_dump()
    requested = [{
        "event_type": payload.usage_type,
        "quantity": payload.quantity,
        "tokens": body.get("tokens"),
    }]
    fingerprint = request_fingerprint("POST", "/usage/events", body)
    result = record_usage(tenant["id"], idempotency_key, fingerprint, requested)
    return _meter_response(result)


@router.get("/usage", tags=["usage"], summary="Read tenant-scoped monthly usage and cost")
def usage(
    period: str | None = Query(default=None, description="UTC billing month in YYYY-MM format"),
    tenant: dict[str, Any] = Depends(tenant_context),
) -> dict[str, Any]:
    try:
        return get_usage(tenant["id"], checked_period(period))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "tenant_not_found", "message": str(exc)}) from exc


@router.get("/invoices/preview", tags=["invoices"], summary="Preview a no-charge monthly invoice summary")
def invoice_preview(
    period: str | None = Query(default=None, description="UTC billing month in YYYY-MM format"),
    tenant: dict[str, Any] = Depends(tenant_context),
) -> dict[str, Any]:
    try:
        return build_invoice_summary(tenant["id"], checked_period(period))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "tenant_not_found", "message": str(exc)}) from exc


@router.post("/invoice-jobs", status_code=202, tags=["invoices"], summary="Queue a durable invoice-summary job")
def create_invoice_job(
    period: str | None = Query(default=None, description="UTC billing month in YYYY-MM format"),
    tenant: dict[str, Any] = Depends(tenant_context),
) -> dict[str, Any]:
    try:
        return enqueue_invoice_job(tenant["id"], checked_period(period))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "tenant_not_found", "message": str(exc)}) from exc


@router.get("/invoice-jobs/{job_id}", tags=["invoices"], summary="Read a tenant-scoped invoice job")
def invoice_job(job_id: str, tenant: dict[str, Any] = Depends(tenant_context)) -> dict[str, Any]:
    result = get_invoice_job(tenant["id"], job_id)
    if result is None:
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "No invoice job exists for this tenant and ID."})
    return result


@router.post("/billing/checkout", tags=["billing"], summary="Create a Pro subscription Checkout session")
def checkout(
    payload: CheckoutRequest,
    tenant: dict[str, Any] = Depends(tenant_context),
    idempotency_header: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
) -> JSONResponse:
    idempotency_key = required_idempotency_key(idempotency_header)
    result = create_checkout(tenant["id"], idempotency_key, payload.model_dump())
    return _meter_response(result)


@router.get("/billing/success", tags=["billing"], summary="Return from Checkout without trusting the redirect")
def billing_success(session_id: str = Query(..., alias="session_id")) -> dict[str, Any]:
    return {
        "status": "checkout_returned",
        "session_id": session_id,
        "note": "This redirect is not proof of payment. The tenant plan changes only after a verified webhook.",
    }


@router.get("/billing/cancel", tags=["billing"], summary="Return from a canceled Checkout session")
def billing_cancel() -> dict[str, str]:
    return {"status": "checkout_canceled", "note": "No plan change was made."}


@router.get("/mock-checkout/{session_id}", tags=["billing"], summary="Inspect local mock Checkout instructions")
def mock_checkout_instructions(
    session_id: str,
    tenant: dict[str, Any] = Depends(tenant_context),
) -> dict[str, Any]:
    if PAYMENT_MODE != "mock":
        raise HTTPException(status_code=404, detail={"code": "mock_disabled", "message": "Mock Checkout is disabled."})
    with read_connection() as connection:
        row = connection.execute(
            "SELECT id, tenant_id, status FROM checkout_sessions WHERE id=? AND tenant_id=? AND provider='mock'",
            (session_id, tenant["id"]),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "checkout_not_found", "message": "No local mock Checkout session exists."})
    return {
        "checkout_id": row["id"],
        "status": row["status"],
        "note": "Offline simulation only; no card data or payment is collected.",
        "complete_with": f"POST /mock-checkout/{row['id']}/complete using this tenant's demo headers.",
    }


@router.post("/mock-checkout/{session_id}/complete", tags=["billing"], summary="Complete local mock Checkout")
def finish_mock_checkout(
    session_id: str,
    tenant: dict[str, Any] = Depends(tenant_context),
) -> dict[str, Any]:
    try:
        return complete_mock_checkout(tenant["id"], session_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"code": "checkout_not_found", "message": str(exc)}) from exc


@router.post("/webhooks/stripe", tags=["billing"], summary="Verify and process Stripe webhook events")
async def stripe_webhook(request: Request, signature: str | None = Header(default=None, alias="Stripe-Signature", description="Required signature; verification uses the unmodified raw request body.")) -> dict[str, Any]:
    raw_body = await request.body()
    try:
        return receive_webhook(raw_body, signature)
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_webhook_signature", "message": "Webhook signature verification failed."}) from exc
    except WebhookPayloadError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_webhook_event", "message": str(exc)}) from exc
