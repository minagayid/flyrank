from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value in (None, "") else int(value)


def _path_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    path = Path(value) if value else default
    return path if path.is_absolute() else PROJECT_ROOT / path


DATABASE_PATH = _path_env("DATABASE_PATH", PROJECT_ROOT / "data" / "usage_metering.sqlite3")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = _int_env("PORT", 8000)
APP_BASE_URL = os.getenv("APP_BASE_URL", f"http://{HOST}:{PORT}").rstrip("/")
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "mock").strip().lower()
if PAYMENT_MODE not in {"mock", "stripe_test"}:
    raise ValueError("PAYMENT_MODE must be 'mock' or 'stripe_test'.")

MOCK_WEBHOOK_SECRET = os.getenv("MOCK_WEBHOOK_SECRET", "local-mock-only-secret-change-me")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
PRO_MONTHLY_PRICE_CENTS = _int_env("PRO_MONTHLY_PRICE_CENTS", 2999)

DEMO_KEYS = {
    "demo-free": os.getenv("DEMO_FREE_KEY", "local-free-demo-key"),
    "demo-pro": os.getenv("DEMO_PRO_KEY", "local-pro-demo-key"),
}

MICROCENTS_PER_CENT = 1_000_000
PLAN_CONFIG = {
    "free": {
        "name": "Free",
        "api_calls_limit": 1_000,
        "ai_tokens_limit": 100_000,
        "monthly_price_cents": 0,
    },
    "pro": {
        "name": "Pro",
        "api_calls_limit": 50_000,
        "ai_tokens_limit": 5_000_000,
        "monthly_price_cents": PRO_MONTHLY_PRICE_CENTS,
    },
}

# Example cost assumptions, stored as integer micro-cents per unit.
PRICING_CONFIG = {
    "api_call_microcents": MICROCENTS_PER_CENT,
    "input_microcents_per_token": 15,
    "cached_input_microcents_per_token": 5,
    "output_microcents_per_token": 60,
    "reasoning_microcents_per_token": 60,
}

MAX_METER_QUANTITY = 10_000_000
