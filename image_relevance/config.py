"""Environment configuration with safe, free local defaults."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "var/image_relevance.sqlite3"))
HOST = os.getenv("HOST", "127.0.0.1")
PORT = _int_env("PORT", 8000)
SIMILARITY_THRESHOLD = _float_env("SIMILARITY_THRESHOLD", 0.22)
CONFIDENCE_THRESHOLD = _float_env("CONFIDENCE_THRESHOLD", 0.70)
COST_BUDGET_USD = _float_env("COST_BUDGET_USD", 0.10)
MAX_JOB_RETRIES = _int_env("MAX_JOB_RETRIES", 2)

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower()
if EMBEDDING_PROVIDER not in {"hash", "ollama"}:
    raise ValueError("EMBEDDING_PROVIDER must be 'hash' or 'ollama'")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text").strip()
OLLAMA_TIMEOUT_SECONDS = _float_env("OLLAMA_TIMEOUT_SECONDS", 30.0)
if OLLAMA_TIMEOUT_SECONDS <= 0:
    raise ValueError("OLLAMA_TIMEOUT_SECONDS must be positive")
if not OLLAMA_EMBEDDING_MODEL or len(OLLAMA_EMBEDDING_MODEL) > 128:
    raise ValueError("OLLAMA_EMBEDDING_MODEL must be 1-128 characters")

_ollama_url = urlsplit(OLLAMA_BASE_URL)
if (
    _ollama_url.scheme != "http"
    or _ollama_url.hostname not in {"127.0.0.1", "localhost", "::1"}
    or _ollama_url.username is not None
    or _ollama_url.password is not None
    or _ollama_url.path not in {"", "/"}
    or _ollama_url.query
    or _ollama_url.fragment
):
    raise ValueError("OLLAMA_BASE_URL must be a plain HTTP loopback URL")
