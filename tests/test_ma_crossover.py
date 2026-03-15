"""Unit tests for MACrossoverSignal — no network calls, no mocks."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from titan.signals.ma_crossover import CrossoverSignal, Direction, MACrossoverSignal


def _sig(fast: int = 3, slow: int = 5) -> MACrossoverSignal:
    return MACrossoverSignal(fast_period=fast, slow_period=slow)


def _prices(values: list[float]) -> pd.Series:
    return pd.Series(values, dtype=float)


# ---------------------------------------------------------------------------
# Construction validation
# ---------------------------------------------------------------------------

def test_raises_when_fast_equals_slow() -> None:
    with pytest.raises(ValueError, match="fast_period"):
        MACrossoverSignal(fast_period=5, slow_period=5)


def test_raises_when_fast_greater_than_slow() -> None:
    with pytest.raises(ValueError):
        MACrossoverSignal(fast_period=10, slow_period=5)


# ---------------------------------------------------------------------------
# Not enough data
# ---------------------------------------------------------------------------

def test_returns_none_with_fewer_bars_than_slow_period() -> None:
    sig = _sig(fast=3, slow=10)
    assert sig.compute("SPY", _prices([100.0] * 8)) is None


def test_returns_none_with_exactly_slow_minus_one_bars() -> None:
    sig = _sig(fast=3, slow=5)
    assert sig.compute("SPY", _prices([100.0] * 4)) is None


# ---------------------------------------------------------------------------
# LONG signal
# ---------------------------------------------------------------------------

def _cross_up_prices() -> pd.Series:
    """Series where fast(3) crosses above slow(5) at the end."""
    # Declining → fast < slow; then sharp rise → fast > slow
    return _prices([100, 99, 98, 97, 96, 97, 100, 105, 110, 120])


def test_emits_long_on_cross_up() -> None:
    sig = _sig(fast=3, slow=5)
    result = sig.compute("SPY", _cross_up_prices())
    assert result is not None
    assert result.direction == Direction.LONG
    assert result.symbol == "SPY"
    assert result.fast_ma > result.slow_ma


def test_no_duplicate_long_on_second_call() -> None:
    """Second call with the same prices should return None (no re-signal)."""
    sig = _sig(fast=3, slow=5)
    prices = _cross_up_prices()
    first = sig.compute("SPY", prices)
    second = sig.compute("SPY", prices)
    assert first is not None and first.direction == Direction.LONG
    assert second is None


def test_different_symbols_independent() -> None:
    """State is per-symbol; one symbol's cross doesn't affect another."""
    sig = _sig(fast=3, slow=5)
    prices = _cross_up_prices()
    r_spy = sig.compute("SPY", prices)
    r_qqq = sig.compute("QQQ", prices)
    assert r_spy is not None and r_spy.direction == Direction.LONG
    assert r_qqq is not None and r_qqq.direction == Direction.LONG


# ---------------------------------------------------------------------------
# EXIT signal
# ---------------------------------------------------------------------------

def _cross_down_prices() -> pd.Series:
    return _prices([100, 99, 98, 97, 96, 95, 94, 93, 92, 91])


def test_first_signal_on_declining_prices_is_exit() -> None:
    """If fast starts below slow (no prior LONG), first signal is EXIT."""
    sig = _sig(fast=3, slow=5)
    result = sig.compute("SPY", _cross_down_prices())
    assert result is not None
    assert result.direction == Direction.EXIT


def test_exit_after_long() -> None:
    """After a LONG, a declining series should emit EXIT."""
    sig = _sig(fast=3, slow=5)
    sig.compute("SPY", _cross_up_prices())  # consume LONG
    result = sig.compute("SPY", _cross_down_prices())
    assert result is not None
    assert result.direction == Direction.EXIT


# ---------------------------------------------------------------------------
# reset()
# ---------------------------------------------------------------------------

def test_reset_clears_state() -> None:
    """After reset, the same cross-up prices can emit LONG again."""
    sig = _sig(fast=3, slow=5)
    prices = _cross_up_prices()
    sig.compute("SPY", prices)   # consume LONG
    sig.reset("SPY")
    result = sig.compute("SPY", prices)
    assert result is not None
    assert result.direction == Direction.LONG


def test_reset_only_affects_named_symbol() -> None:
    sig = _sig(fast=3, slow=5)
    prices = _cross_up_prices()
    sig.compute("SPY", prices)
    sig.compute("QQQ", prices)
    sig.reset("SPY")
    # SPY state cleared → can re-emit
    assert sig.compute("SPY", prices) is not None
    # QQQ state untouched → still blocked
    assert sig.compute("QQQ", prices) is None


# ---------------------------------------------------------------------------
# _rolling_mean helper
# ---------------------------------------------------------------------------

def test_rolling_mean_correct() -> None:
    sig = _sig()
    series = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    assert sig._rolling_mean(series, 3) == pytest.approx(4.0)  # last 3: [3,4,5]


def test_rolling_mean_nan_insufficient_data() -> None:
    sig = _sig()
    assert math.isnan(sig._rolling_mean(pd.Series([1.0, 2.0]), 5))
