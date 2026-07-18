"""Small, shared HTTP helpers for skills that call third-party APIs —
retry-with-backoff for transient failures, and a tiny TTL cache for
slow/rate-limited endpoints. Deliberately minimal: no new dependency, no
speculative generality beyond what the skills actually need. See the
"Backend DNA" checklist in CONTRIBUTING.md — this exists so every
network-calling skill gets fault tolerance and caching without
reimplementing it per skill.
"""

import asyncio
import time

import httpx

_RETRY_DELAYS = (0.5, 1.5)  # seconds — a couple of quick retries, not a long hang


async def get_with_retry(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float = 15.0,
    retries: int = len(_RETRY_DELAYS),
) -> httpx.Response:
    """GET with retry-with-backoff on transient failures only — connection
    errors, timeouts, and 5xx responses. Never retries a 4xx (a bad
    request stays bad no matter how many times it's repeated); that
    response is returned as-is so the caller's own `raise_for_status()`
    behaves exactly as before. If every attempt fails, the final
    exception propagates — `core/skills/loop.py`'s broad `except
    Exception` already turns that into a clean "error: ..." observation
    instead of crashing the conversation, so callers don't need their own
    try/except for this."""
    delays = _RETRY_DELAYS[:retries]
    for attempt in range(len(delays) + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, params=params, headers=headers)
        except httpx.TransportError:
            if attempt < len(delays):
                await asyncio.sleep(delays[attempt])
                continue
            raise
        else:
            if response.status_code >= 500 and attempt < len(delays):
                await asyncio.sleep(delays[attempt])
                continue
            return response


class TTLCache:
    """A tiny in-memory cache with per-entry expiry, so repeat queries
    within a short window don't hit a slow/rate-limited third-party API
    again. Not shared across processes — fine for KafKaf's single-process,
    single-user deployment model (same reasoning as core/rate_limit.py)."""

    def __init__(self, ttl_seconds: float):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self.ttl_seconds:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value) -> None:
        self._store[key] = (time.monotonic(), value)
