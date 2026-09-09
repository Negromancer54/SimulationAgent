from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CancellationToken:
    """
    Cooperative cancellation signal.

    The token itself never stops execution.

    It only records that cancellation has been requested.
    Physical executors decide how and when to observe the signal.
    """

    _requested: bool = False

    @property
    def requested(self) -> bool:
        return self._requested

    def cancel(self) -> None:
        self._requested = True

    def reset(self) -> None:
        self._requested = False