from __future__ import annotations

from typing import Any

from app.config import MICROCENTS_PER_CENT


def token_cost_microcents(tokens: dict[str, int], plan: dict[str, Any]) -> int:
    """Price disjoint token categories without floating-point arithmetic."""
    return (
        tokens.get("input_tokens", 0) * plan["input_microcents_per_token"]
        + tokens.get("cached_input_tokens", 0)
        * plan["cached_input_microcents_per_token"]
        + tokens.get("output_tokens", 0) * plan["output_microcents_per_token"]
        + tokens.get("reasoning_tokens", 0) * plan["reasoning_microcents_per_token"]
    )


def round_microcents_to_cents(amount_microcents: int) -> int:
    """Round non-negative micro-cent totals half-up once at the invoice boundary."""
    if amount_microcents < 0:
        raise ValueError("Billing amounts cannot be negative.")
    return (amount_microcents + MICROCENTS_PER_CENT // 2) // MICROCENTS_PER_CENT


def format_cents(amount_cents: int) -> str:
    if amount_cents < 0:
        raise ValueError("Billing amounts cannot be negative.")
    return f"${amount_cents // 100}.{amount_cents % 100:02d}"
