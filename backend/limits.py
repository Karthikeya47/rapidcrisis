"""
limits.py — guards for a public demo: request rate limits that protect the
Token Factory credits. In-memory, so they apply per server instance.
"""
import threading
import time
from collections import deque


class RateLimiter:
    """Sliding window: at most `limit` hits per `window_s` seconds for each key."""

    def __init__(self, limit: int, window_s: float):
        self.limit, self.window_s = limit, window_s
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window_s:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            # forget idle keys so the map does not grow with every visitor
            if len(self._hits) > 10_000:
                self._hits = {k: v for k, v in self._hits.items() if v and now - v[-1] < self.window_s}
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()
