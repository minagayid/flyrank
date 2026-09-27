from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
DB_PATH = Path(os.environ.get("SIGNAL_DESK_DB_PATH", ROOT / "data" / "signal_desk.sqlite3"))
HOST = os.environ.get("SIGNAL_DESK_HOST", "127.0.0.1")
PORT = int(os.environ.get("SIGNAL_DESK_PORT", "8080"))
DEMO_USER = os.environ.get("SIGNAL_DESK_DEMO_USER", "demo").strip()
DEMO_PASSWORD = os.environ.get("SIGNAL_DESK_DEMO_PASSWORD", "")
AI_MODE = os.environ.get("SIGNAL_DESK_AI_MODE", "mock").strip().lower()
OLLAMA_URL = os.environ.get("SIGNAL_DESK_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("SIGNAL_DESK_OLLAMA_MODEL", "qwen2.5:3b").strip()
DAILY_AI_CALL_LIMIT = int(os.environ.get("SIGNAL_DESK_DAILY_AI_CALL_LIMIT", "25"))
SESSION_TTL_SECONDS = int(os.environ.get("SIGNAL_DESK_SESSION_TTL_SECONDS", "28800"))
CACHE_TTL_SECONDS = int(os.environ.get("SIGNAL_DESK_CACHE_TTL_SECONDS", "86400"))
MAX_BODY_BYTES = 24_000
MAX_JOB_ATTEMPTS = 3

if AI_MODE not in {"mock", "ollama"}:
    raise ValueError("SIGNAL_DESK_AI_MODE must be 'mock' or 'ollama'.")
if not 1 <= PORT <= 65535:
    raise ValueError("SIGNAL_DESK_PORT must be between 1 and 65535.")
if DAILY_AI_CALL_LIMIT < 1:
    raise ValueError("SIGNAL_DESK_DAILY_AI_CALL_LIMIT must be positive.")
