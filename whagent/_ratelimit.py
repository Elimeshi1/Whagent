"""A small client-side limiter that keeps requests under the documented caps.

Each endpoint has its own counter over a rolling 60-second window, per agent,
so the limiter tracks one sliding window per key.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable, Deque

__all__ = ["SlidingWindowLimiter"]


class SlidingWindowLimiter:
    """Blocks just long enough to stay inside ``limit`` calls per ``window``."""

    def __init__(
        self,
        limits: dict[str, int],
        *,
        window: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = dict(limits)
        self._window = window
        self._sleep = sleep
        self._monotonic = monotonic
        self._calls: dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def acquire(self, key: str) -> float:
        """Reserve a slot for ``key``, sleeping if the window is full.

        Returns how long it slept, in seconds.
        """
        limit = self._limits.get(key)
        if not limit:
            return 0.0

        waited = 0.0
        while True:
            with self._lock:
                now = self._monotonic()
                calls = self._calls[key]
                cutoff = now - self._window
                while calls and calls[0] <= cutoff:
                    calls.popleft()
                if len(calls) < limit:
                    calls.append(now)
                    return waited
                delay = calls[0] + self._window - now
            delay = max(delay, 0.001)
            self._sleep(delay)
            waited += delay
