"""
utils/rate_limiter.py
In-memory sliding-window rate limiter. Используется антиспам-модулем:
если пользователь присылает больше N сообщений за T секунд — считаем
это спамом.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, max_events: int, window_seconds: int) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[int, deque[float]] = defaultdict(deque)

    def hit(self, key: int) -> bool:
        """Регистрирует событие и возвращает True, если лимит превышен."""
        now = time.monotonic()
        window = self._events[key]
        window.append(now)
        cutoff = now - self.window_seconds
        while window and window[0] < cutoff:
            window.popleft()
        return len(window) > self.max_events

    def reset(self, key: int) -> None:
        self._events.pop(key, None)
