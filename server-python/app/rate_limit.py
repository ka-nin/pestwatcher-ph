"""In-memory sliding-window rate limiter for public, unauthenticated
endpoints. The mobile app has no farmer accounts (see
app/routers/locations.py) so the only identity a spam submission carries is
the requesting IP — this is not a substitute for a shared store (Redis,
etc) behind a multi-worker/multi-instance deployment, but is enough for
this thesis-scope single-process backend.

Used by app/routers/reports.py to throttle report submissions.
"""

import time
from collections import defaultdict, deque


class RateLimitExceeded(Exception):
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"Rate limit exceeded, retry after {retry_after_seconds:.0f}s")


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()
        if len(hits) >= self.max_requests:
            retry_after = self.window_seconds - (now - hits[0])
            raise RateLimitExceeded(retry_after)
        hits.append(now)
