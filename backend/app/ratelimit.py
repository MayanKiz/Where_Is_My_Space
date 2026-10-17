"""Small in-memory sliding-window rate limiter.

Deliberately process-local: it protects the public API from naive abuse and
accidental loops. For multi-instance deployments put a shared limiter (Redis or
an edge gateway) in front — this module keeps the same interface either way.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, window_seconds: float = 60.0, max_events: int = 120, clock=time.monotonic) -> None:
        self.window_seconds = window_seconds
        self.max_events = max_events
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_events:
                return False
            bucket.append(now)
            # Opportunistic cleanup so idle keys do not accumulate.
            if len(self._events) > 10_000:
                for stale in [k for k, v in self._events.items() if not v or v[-1] <= cutoff]:
                    self._events.pop(stale, None)
            return True

    def remaining(self, key: str) -> int:
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            return max(0, self.max_events - len(bucket))