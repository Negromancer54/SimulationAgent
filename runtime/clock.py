from __future__ import annotations

from typing import Protocol


class Clock(Protocol):
    def monotonic(self) -> float:
        ...


class MonotonicClock:
    """
    Production clock based on a monotonic timer.

    The value is suitable for measuring elapsed execution time
    and is not affected by wall-clock changes.
    """

    def monotonic(self) -> float:
        import time

        return time.monotonic()


class ManualClock:
    """
    Deterministic test clock.

    Tests control time explicitly with advance().
    """

    def __init__(self, initial: float = 0.0) -> None:
        self._time = float(initial)

    def monotonic(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        if seconds < 0:
            raise ValueError(
                "ManualClock cannot move backwards."
            )

        self._time += float(seconds)