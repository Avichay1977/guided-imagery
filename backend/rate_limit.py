"""
In-process rate limiting.

Deliberately not Redis-backed: this app runs as a single web service, and adding
a datastore to throttle three endpoints would cost more than it protects. The
tradeoff is that limits are per-process, so they reset on deploy and do not add
up across replicas. If the service is ever scaled out, this is the piece to
replace.

Client identity comes from X-Forwarded-For counted from the *right*, because
only the hops appended by our own proxies are trustworthy — anything further
left is attacker-supplied. `MAX_CONCURRENT_GENERATIONS` in main.py is the
backstop for when that identity is wrong anyway.
"""

import re
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from config import TRUSTED_PROXY_HOPS

_PERIODS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
_SPEC = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour|day)\s*$", re.I)


def parse_spec(spec: str) -> tuple[int, int]:
    """'5/hour' -> (5, 3600). Raises ValueError on anything else."""
    match = _SPEC.match(spec)
    if not match:
        raise ValueError(f"invalid rate limit spec: {spec!r}")
    return int(match.group(1)), _PERIODS[match.group(2).lower()]


def client_key(request: Request) -> str:
    """Best-available client identity, resistant to header spoofing."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and TRUSTED_PROXY_HOPS > 0:
        hops = [h.strip() for h in forwarded.split(",") if h.strip()]
        if hops:
            # Count from the right: hop -1 was added by the nearest proxy.
            index = max(0, len(hops) - TRUSTED_PROXY_HOPS)
            return hops[index]
    return request.client.host if request.client else "unknown"


class SlidingWindow:
    """
    Sliding-window counter with lazy eviction.

    Timestamps are kept per key in a deque and expired entries are dropped on
    read, so idle keys cost nothing until they are touched again. `sweep()`
    drops keys that have gone fully cold, which is what keeps the dict from
    growing without bound under a spray of one-shot clients.
    """

    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """(allowed, retry_after_seconds). Records the hit when allowed."""
        now = time.monotonic() if now is None else now
        bucket = self._hits[key]
        cutoff = now - self.window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.limit:
            retry_after = max(1, int(bucket[0] + self.window - now) + 1)
            return False, retry_after

        bucket.append(now)
        return True, 0

    def sweep(self, now: float | None = None) -> int:
        """Drop fully-expired keys. Returns how many were removed."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window
        stale = [k for k, b in self._hits.items() if not b or b[-1] <= cutoff]
        for key in stale:
            del self._hits[key]
        return len(stale)


_registry: list[SlidingWindow] = []


def sweep_all() -> int:
    return sum(window.sweep() for window in _registry)


def rate_limit(spec: str):
    """
    FastAPI dependency enforcing `spec` (e.g. '5/hour') per client.

    Raises 429 with a Retry-After header when the window is full.
    """
    limit, window_seconds = parse_spec(spec)
    counter = SlidingWindow(limit, window_seconds)
    _registry.append(counter)

    async def dependency(request: Request) -> None:
        allowed, retry_after = counter.check(client_key(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait before trying again.",
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
