"""Retry policies for messaging."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class ExponentialBackoff:
    """Exponential backoff with jitter and a maximum attempt count."""

    max_attempts: int = 5
    base_delay_seconds: float = 0.1
    max_delay_seconds: float = 30.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be positive")

    def next_delay(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be positive")
        delay = min(self.base_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)
        if self.jitter:
            delay = delay * (0.5 + random.random() / 2)
        return float(delay)
