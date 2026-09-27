"""Offline hash embeddings and an optional loopback-only Ollama adapter."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .concepts import normalize_text


MODEL_ID = "local-token-hash-512-v1"
DIMENSIONS = 512
DEFAULT_OLLAMA_MODEL = "nomic-embed-text"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in", "is", "its",
    "of", "on", "or", "the", "this", "to", "with", "their", "about", "guide", "article",
}


def features(text: str) -> Counter[str]:
    tokens = [token for token in re.findall(r"[a-z0-9]+", normalize_text(text)) if token not in STOP_WORDS]
    counts: Counter[str] = Counter()
    for token in tokens:
        counts[f"word:{token}"] += 1.0
    for left, right in zip(tokens, tokens[1:]):
        counts[f"bigram:{left}_{right}"] += 0.65
    # A phrase feature preserves subject identity even if other description terms overlap.
    phrases = ("red fox", "gray wolf", "domestic dog", "barn owl", "sourdough bread", "oak tree", "eiffel tower")
    normalized = normalize_text(text)
    for phrase in phrases:
        if phrase in normalized:
            counts[f"concept:{phrase}"] += 2.5
    return counts


def embed(text: str) -> list[float]:
    vector = [0.0] * DIMENSIONS
    for feature, weight in features(text).items():
        digest = hashlib.blake2s(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % DIMENSIONS
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]
    return vector


class EmbeddingAdapter(Protocol):
    provider: str
    model_id: str

    def embed(self, text: str) -> list[float]: ...


class HashEmbedder:
    provider = "local"
    model_id = MODEL_ID

    def embed(self, text: str) -> list[float]:
        return embed(text)


class OllamaEmbedder:
    """Call Ollama's embeddings endpoint without permitting remote providers."""

    provider = "ollama"

    def __init__(
        self,
        model_id: str = DEFAULT_OLLAMA_MODEL,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        timeout_seconds: float = 30.0,
    ) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama base URL must be a plain HTTP loopback URL")
        if not model_id or len(model_id) > 128:
            raise ValueError("Ollama model name must be 1-128 characters")
        if timeout_seconds <= 0:
            raise ValueError("Ollama timeout must be positive")
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text or len(text) > 50_000:
            raise ValueError("embedding text must contain 1-50000 characters")
        body = json.dumps({"model": self.model_id, "input": text}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with build_opener(_NoRedirect).open(request, timeout=self.timeout_seconds) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError("local Ollama embedding request failed") from exc
        if len(raw) > 2 * 1024 * 1024:
            raise RuntimeError("local Ollama response exceeded the 2 MiB limit")
        try:
            payload = json.loads(raw.decode("utf-8"))
            vectors = payload["embeddings"]
            vector = vectors[0]
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("local Ollama returned an invalid embedding response") from exc
        if not isinstance(vector, list) or not vector:
            raise RuntimeError("local Ollama returned an empty embedding")
        clean: list[float] = []
        for value in vector:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise RuntimeError("local Ollama returned a non-numeric embedding value")
            clean.append(float(value))
        return clean


def create_embedder(
    provider: str = "hash",
    model_id: str = DEFAULT_OLLAMA_MODEL,
    base_url: str = DEFAULT_OLLAMA_BASE_URL,
    timeout_seconds: float = 30.0,
) -> EmbeddingAdapter:
    if provider == "hash":
        return HashEmbedder()
    if provider == "ollama":
        return OllamaEmbedder(model_id, base_url, timeout_seconds)
    raise ValueError("embedding provider must be 'hash' or 'ollama'")


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must be non-empty and have equal dimensions")
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right))))


def image_embedding_text(tags: dict[str, object]) -> str:
    attributes = tags.get("attributes", [])
    pieces = [str(tags.get("subject", "")), str(tags.get("category", "")), str(tags.get("caption", ""))]
    if isinstance(attributes, list):
        pieces.extend(str(item) for item in attributes)
    return " ".join(pieces)
