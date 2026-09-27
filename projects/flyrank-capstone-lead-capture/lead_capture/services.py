from __future__ import annotations

import threading
import time
from collections import defaultdict

class TokenBucketLimiter:
    """A per-process token bucket for the supplied admission scope."""

    def __init__(self, capacity: int, refill_per_second: float):
        self.capacity = float(capacity)
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, keys: list[str]) -> tuple[bool, float]:
        now = time.monotonic()
        with self._lock:
            current: dict[str, tuple[float, float]] = {}
            retry_after = 0.0
            for key in keys:
                tokens, updated = self._buckets.get(key, (self.capacity, now))
                tokens = min(self.capacity, tokens + (now - updated) * self.refill_per_second)
                current[key] = (tokens, now)
                if tokens < 1.0:
                    retry_after = max(retry_after, (1.0 - tokens) / self.refill_per_second)
            if retry_after:
                self._buckets.update(current)
                return False, retry_after
            self._buckets.update({key: (tokens - 1.0, updated) for key, (tokens, updated) in current.items()})
            return True, 0.0


class DevSwitches:
    def __init__(self, *, geo_a_down: bool, geo_b_down: bool, notification_fail: bool):
        self._values = {
            "geo_a_down": geo_a_down,
            "geo_b_down": geo_b_down,
            "notification_fail": notification_fail,
        }
        self._lock = threading.Lock()

    def get(self) -> dict[str, bool]:
        with self._lock:
            return dict(self._values)

    def update(self, **values: bool) -> dict[str, bool]:
        with self._lock:
            self._values.update(values)
            return dict(self._values)


class GeoEnricher:
    def __init__(self, switches: DevSwitches):
        self.switches = switches

    def enrich(self, client_ip: str) -> dict[str, str] | None:
        state = self.switches.get()
        providers = [self._provider_a, self._provider_b]
        for index, provider in enumerate(providers):
            name = "provider_a" if index == 0 else "provider_b"
            try:
                result = provider(client_ip, state)
                if result:
                    return {**result, "provider": name}
            except Exception as exc:  # upstream outages must not break a valid submission
                print(f"WARN geo {name} unavailable ({type(exc).__name__}); trying fallback")
        return None

    def _provider_a(self, _client_ip: str, state: dict[str, bool]) -> dict[str, str] | None:
        if state["geo_a_down"]:
            raise RuntimeError("mock provider A unavailable")
        return {"country": "United States", "country_code": "US", "city": "Ashburn"}

    def _provider_b(self, _client_ip: str, state: dict[str, bool]) -> dict[str, str] | None:
        if state["geo_b_down"]:
            raise RuntimeError("mock provider B unavailable")
        return {"country": "Canada", "country_code": "CA", "city": "Toronto"}
