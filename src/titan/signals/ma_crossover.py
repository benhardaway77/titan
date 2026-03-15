"""Simple moving-average crossover signal logic.

Signal is computed purely from a price Series — no external I/O.
This keeps the math unit-testable without mocking any network calls.

Direction semantics
-------------------
- LONG : fast MA just crossed above slow MA → enter (or hold) long
- EXIT : fast MA just crossed below slow MA → flatten long position
- Signals are only emitted on direction *change*, not every tick while
  fast > slow, so callers never re-enter an already-open position.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar

import pandas as pd


class Direction(str, Enum):
    LONG = "long"
    EXIT = "exit"


@dataclass(frozen=True)
class CrossoverSignal:
    symbol: str
    direction: Direction
    fast_ma: float
    slow_ma: float
    timestamp: pd.Timestamp


class MACrossoverSignal:
    """Stateful MA crossover calculator (one instance per agent lifetime).

    Tracks the last emitted direction per symbol so it only fires when
    the crossover *changes*. Call ``reset(symbol)`` to clear state after
    a force-close so the next cross is treated as fresh.
    """

    name: ClassVar[str] = "ma_crossover"

    def __init__(self, fast_period: int, slow_period: int) -> None:
        if fast_period >= slow_period:
            raise ValueError(
                f"fast_period ({fast_period}) must be < slow_period ({slow_period})"
            )
        self.fast_period = fast_period
        self.slow_period = slow_period
        # symbol -> last Direction emitted; None means "no signal yet"
        self._last_direction: dict[str, Direction | None] = {}

    def compute(self, symbol: str, close: pd.Series) -> CrossoverSignal | None:
        """Return a CrossoverSignal if a new actionable cross just occurred.

        Returns None when:
        - Not enough bars to compute both MAs
        - Either MA is NaN
        - The crossover direction has not changed since the last call
        """
        fast_ma = self._rolling_mean(close, self.fast_period)
        slow_ma = self._rolling_mean(close, self.slow_period)

        if math.isnan(fast_ma) or math.isnan(slow_ma):
            return None

        current_direction = Direction.LONG if fast_ma > slow_ma else Direction.EXIT
        last = self._last_direction.get(symbol)

        if current_direction == last:
            return None  # same state as before — no new signal

        self._last_direction[symbol] = current_direction
        timestamp = close.index[-1] if hasattr(close.index[-1], "timestamp") else pd.Timestamp.now()
        return CrossoverSignal(
            symbol=symbol,
            direction=current_direction,
            fast_ma=fast_ma,
            slow_ma=slow_ma,
            timestamp=timestamp,
        )

    def _rolling_mean(self, series: pd.Series, window: int) -> float:
        """Return the most recent rolling mean; NaN if not enough data."""
        if len(series) < window:
            return float("nan")
        return float(series.iloc[-window:].mean())

    def reset(self, symbol: str) -> None:
        """Clear per-symbol state (call after a position is force-closed)."""
        self._last_direction.pop(symbol, None)
