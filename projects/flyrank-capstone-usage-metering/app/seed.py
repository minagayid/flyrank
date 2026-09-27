from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.config import DEMO_KEYS, PLAN_CONFIG, PRICING_CONFIG
from app.db import initialize_database, transaction


def _key_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def seed_demo_data() -> None:
    initialize_database()
    now = datetime.now(timezone.utc).isoformat()
    with transaction() as connection:
        for plan_id, plan in PLAN_CONFIG.items():
            connection.execute(
                """INSERT INTO plans(
                       id, name, api_calls_limit, ai_tokens_limit, monthly_price_cents,
                       api_call_microcents, input_microcents_per_token,
                       cached_input_microcents_per_token, output_microcents_per_token,
                       reasoning_microcents_per_token, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       name=excluded.name,
                       api_calls_limit=excluded.api_calls_limit,
                       ai_tokens_limit=excluded.ai_tokens_limit,
                       monthly_price_cents=excluded.monthly_price_cents,
                       api_call_microcents=excluded.api_call_microcents,
                       input_microcents_per_token=excluded.input_microcents_per_token,
                       cached_input_microcents_per_token=excluded.cached_input_microcents_per_token,
                       output_microcents_per_token=excluded.output_microcents_per_token,
                       reasoning_microcents_per_token=excluded.reasoning_microcents_per_token,
                       updated_at=excluded.updated_at""",
                (
                    plan_id,
                    plan["name"],
                    plan["api_calls_limit"],
                    plan["ai_tokens_limit"],
                    plan["monthly_price_cents"],
                    PRICING_CONFIG["api_call_microcents"],
                    PRICING_CONFIG["input_microcents_per_token"],
                    PRICING_CONFIG["cached_input_microcents_per_token"],
                    PRICING_CONFIG["output_microcents_per_token"],
                    PRICING_CONFIG["reasoning_microcents_per_token"],
                    now,
                ),
            )

        tenants = [
            ("demo-free", "Free demo tenant", "free"),
            ("demo-pro", "Pro demo tenant", "pro"),
        ]
        for tenant_id, name, plan_id in tenants:
            connection.execute(
                """INSERT INTO tenants(id, name, api_key_hash, created_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       name=excluded.name, api_key_hash=excluded.api_key_hash""",
                (tenant_id, name, _key_hash(DEMO_KEYS[tenant_id]), now),
            )
            connection.execute(
                """INSERT INTO subscriptions(tenant_id, plan_id, status, updated_at)
                   VALUES (?, ?, 'active', ?)
                   ON CONFLICT(tenant_id) DO NOTHING""",
                (tenant_id, plan_id, now),
            )


def main() -> None:
    seed_demo_data()
    print("Seeded demo-free (Free) and demo-pro (Pro); demo keys were not printed.")


if __name__ == "__main__":
    main()
