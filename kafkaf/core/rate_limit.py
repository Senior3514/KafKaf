"""In-memory fixed-window rate limiter — no Redis, single process, matching
KafKaf's single-user/self-hosted deployment model (see docs/ARCHITECTURE.md).
Keyed by client IP; not meant for a multi-tenant public deployment."""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from kafkaf.core.config import settings

WINDOW_SECONDS = 60
_EXEMPT_PATHS = {"/health"}
_EXEMPT_PREFIXES = ("/static",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        # Read fresh on every request (not cached at __init__ time) so tests
        # can monkeypatch settings.rate_limit_per_minute and so a running
        # server picks up a config reload without restarting.
        limit = settings.rate_limit_per_minute
        path = request.url.path
        if limit <= 0 or path in _EXEMPT_PATHS or path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        key = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()

        if len(window) >= limit:
            return JSONResponse(
                {"detail": "rate limit exceeded — try again shortly"}, status_code=429
            )

        window.append(now)
        return await call_next(request)
