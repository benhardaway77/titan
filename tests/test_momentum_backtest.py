"""Tests for the momentum backtest: synthetic data, math, and registration."""
from __future__ import annotations

import pytest

from titan.backtest.momentum_backtest import (
    MomentumMABacktest,
    _generate_synthetic_prices,
    _run_ma_crossover_backtest,
)
from titan.backtest.runner import BacktestConfig, registered_runners


# ---------------------------------------------------------------------------
# Synthetic price generation
# ---------------------------------------------------------------------------

class TestSyntheticPrices:
    def test_correct_length(self) -> None:
        assert len(_generate_synthetic_prices(n_bars=500)) == 500

    def test_all_positive(self) -> None:
        prices = _generate_synthetic_prices(n_bars=500)
        assert (prices > 0).all()

    def test_deterministic_with_same_seed(self) -> None:
        p1 = _generate_synthetic_prices(n_bars=100, seed=7)
        p2 = _generate_synthetic_prices(n_bars=100, seed=7)
        assert (p1 == p2).all()

    def test_different_seeds_differ(self) -> None:
        p1 = _generate_synthetic_prices(n_bars=100, seed=1)
        p2 = _generate_synthetic_prices(n_bars=100, seed=2)
        assert not (p1 == p2).all()


# ---------------------------------------------------------------------------
# Backtest math
# ---------------------------------------------------------------------------

class TestBacktestMath:
    def test_positive_drift_produces_positive_return(self) -> None:
        prices = _generate_synthetic_prices(n_bars=5000, drift=0.001, vol=0.001)
        ret, dd, sharpe, trades = _run_ma_crossover_backtest(prices, fast=5, slow=20)
        assert ret > 0

    def test_drawdown_bounded(self) -> None:
        prices = _generate_synthetic_prices(n_bars=5000)
        _, dd, _, _ = _run_ma_crossover_backtest(prices, fast=10, slow=30)
        assert 0.0 <= dd <= 1.0

    def test_num_trades_positive(self) -> None:
        prices = _generate_synthetic_prices(n_bars=5000)
        _, _, _, trades = _run_ma_crossover_backtest(prices, fast=10, slow=30)
        assert trades > 0

    def test_returns_four_values(self) -> None:
        prices = _generate_synthetic_prices(n_bars=1000)
        result = _run_ma_crossover_backtest(prices, fast=5, slow=15)
        assert len(result) == 4


# ---------------------------------------------------------------------------
# MomentumMABacktest runner
# ---------------------------------------------------------------------------

class TestMomentumMABacktest:
    def test_passes_default_thresholds(self) -> None:
        """The registered backtest must pass BacktestConfig default thresholds."""
        runner = MomentumMABacktest()
        cfg = BacktestConfig()  # min_sharpe=0.5, max_dd=0.30, min_return=0.0
        result = runner.run(cfg)
        assert result.passed(cfg), (
            f"Backtest failed thresholds: {result.failure_reasons(cfg)}"
        )

    def test_correct_strategy_name(self) -> None:
        runner = MomentumMABacktest()
        result = runner.run(BacktestConfig())
        assert result.strategy == "momentum_ma_crossover"

    def test_result_has_positive_trades(self) -> None:
        runner = MomentumMABacktest()
        result = runner.run(BacktestConfig())
        assert result.num_trades > 0

    def test_registered_in_global_registry(self) -> None:
        names = [r.name for r in registered_runners()]
        assert "momentum_ma_crossover" in names
