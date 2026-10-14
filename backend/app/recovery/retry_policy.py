from __future__ import annotations

import time
from dataclasses import dataclass

from backend.app.config import settings


@dataclass
class RetryDecision:
    should_retry: bool
    delay_s: float
    attempt_number: int
    reason: str


class RetryPolicy:
    def __init__(
        self,
        max_attempts: int | None = None,
        base_delay_s: float | None = None,
        max_delay_s: float | None = None,
    ) -> None:
        self.max_attempts = max_attempts or settings.recovery_max_attempts
        self.base_delay_s = base_delay_s or settings.recovery_retry_base_delay_s
        self.max_delay_s = max_delay_s or settings.recovery_retry_max_delay_s

    def evaluate(self, retry_count: int, failure_reason: str) -> RetryDecision:
        next_attempt = retry_count + 1
        if next_attempt >= self.max_attempts:
            return RetryDecision(False, 0.0, next_attempt, f"retry exhausted: {failure_reason}")
        delay = min(self.max_delay_s, self.base_delay_s * (2**retry_count))
        return RetryDecision(True, delay, next_attempt, failure_reason)

    @staticmethod
    def ready(last_retry_timestamp: float | None, delay_s: float) -> bool:
        if last_retry_timestamp is None:
            return True
        return time.time() >= last_retry_timestamp + delay_s
