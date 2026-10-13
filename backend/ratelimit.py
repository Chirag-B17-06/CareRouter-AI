"""Small in-process sliding-window rate limiter keyed by client address.

Adequate for a single-process deployment.  Behind several workers/instances, enforce the
limit at the reverse proxy or API gateway instead (counters here are per process).
Set RATE_LIMIT_PER_MINUTE=0 to disable.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import Request
from fastapi.responses import JSONResponse

from config import get_settings

_WINDOW_SECONDS = 60.0
_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)

# Authentication endpoints get a tighter budget than the general API.
_LOGIN_PATH = "/api/auth/login"
_LOGIN_LIMIT = 20


def reset() -> None:
    with _lock:
        _hits.clear()


def _allow(key: str, limit: int, now: float) -> bool:
    with _lock:
        window = _hits[key]
        while window and now - window[0] > _WINDOW_SECONDS:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True


async def rate_limit_middleware(request: Request, call_next):
    limit = get_settings().rate_limit_per_minute
    if limit <= 0 or not request.url.path.startswith("/api/") or request.url.path == "/api/health":
        return await call_next(request)

    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if request.url.path == _LOGIN_PATH:
        allowed = _allow(f"login:{client}", min(_LOGIN_LIMIT, limit), now)
    else:
        allowed = _allow(f"api:{client}", limit, now)
    if not allowed:
        return JSONResponse(
            status_code=429, content={"detail": "Too many requests. Please slow down and retry shortly."},
            headers={"Retry-After": "30"},
        )
    return await call_next(request)
