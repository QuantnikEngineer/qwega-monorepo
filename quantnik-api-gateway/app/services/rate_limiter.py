"""In-memory login rate limiter."""

from collections import defaultdict, deque
from collections.abc import Callable
from math import ceil
from time import time


class LoginRateLimiter:
    """Track login attempts by source IP within a rolling window."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        window_seconds: int = 60,
        clock: Callable[[], float] = time,
    ) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[str, deque[float]] = defaultdict(deque)

    def check_and_record(self, source_ip: str) -> tuple[bool, int]:
        """Return allowance status and retry-after seconds."""
        now = self._clock()
        timestamps = self._attempts[source_ip]

        while timestamps and (now - timestamps[0]) >= self.window_seconds:
            timestamps.popleft()

        if len(timestamps) >= self.max_attempts:
            retry_after = max(1, ceil(self.window_seconds - (now - timestamps[0])))
            return False, retry_after

        timestamps.append(now)
        return True, 0
