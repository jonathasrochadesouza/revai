"""A process-local limiter for expensive review runs.

The queue is deliberately independent from provider adapters. It bounds whole
reviews (including deterministic analysis) and accepts each review's configured
limit at acquisition time, so a config save affects the next queued run without a
server restart.
"""

from __future__ import annotations

import asyncio


class ReviewLimiter:
    def __init__(self) -> None:
        self._active = 0
        self._condition = asyncio.Condition()

    async def acquire(self, limit: int) -> None:
        async with self._condition:
            while self._active >= limit:
                await self._condition.wait()
            self._active += 1

    async def release(self) -> None:
        async with self._condition:
            self._active = max(0, self._active - 1)
            self._condition.notify_all()
