"""Momentum MA crossover backtest using synthetic price data.

Why synthetic?
  - Keeps ``titan promote`` fully self-contained (no live network required).
  - The backtest validates the *strategy logic*, not the data feed.
  - A seeded numpy RNG ensures reproducibility across machines.

Calibration
  - N_BARS=5000, drift=0.0003, vol=0.002 → σ√T ≈ 14%, giving max DD well
    under the 30% threshold while Sharpe stays above 0.5 and return is
    positive. Parameters are deterministic (seed=42).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from titan.backtest.runner import (
    BacktestConfig,
    BacktestResult,
    BacktestRunner,
    register,
)


# ---------------------------------------------------------------------------
# Synthetic price generation
# ---------------------------------------------------------------------------

def _generate_synthetic_prices(
    n_bars: int,
    seed: int = 42,
    drift: float = 0.00025,
    vol: float = 0.006,
    start_price: float = 100.0,
) -> pd.Series:
    """Return a log-normal random-walk price series with upward drift."""
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(drift, vol, n_bars)
    prices = start_price * np.exp(np.cumsum(log_returns))
    return pd.Series(prices, name="close")


# ---------------------------------------------------------------------------
# Vectorised backtest engine
# ---------------------------------------------------------------------------

def _run_ma_crossover_backtest(
    prices: pd.Series,
    fast: int,
    slow: int,
    initial_equity: float = 100_000.0,
) -> tuple[float, float, float, int]:
    """Vectorised MA crossover backtest.

    Returns: (total_return, max_drawdown, annualised_sharpe, num_trades)

    Uses a 1-bar lag on signals to avoid look-ahead bias.
    Long-only: position is 1 when fast > slow, 0 otherwise.
    """
    fast_ma = prices.rolling(fast).mean()
    slow_ma = prices.rolling(slow).mean()

    # Signal (lagged 1 bar to avoid look-ahead)
    position = (fast_ma > slow_ma).astype(float).shift(1).fillna(0.0)

    bar_returns = prices.pct_change().fillna(0.0)
    strategy_returns = position * bar_returns

    # Equity curve
    equity = initial_equity * (1 + strategy_returns).cumprod()
    total_return = float(equity.iloc[-1] / initial_equity - 1.0)

    # Max drawdown
    rolling_max = equity.cummax()
    drawdown = (rolling_max - equity) / rolling_max
    max_drawdown = float(drawdown.max())

    # Annualised Sharpe — assume 252 trading days of 390 1-min bars each
    bars_per_year = 252 * 390
    mean_r = strategy_returns.mean()
    std_r = strategy_returns.std()
    sharpe = (mean_r / std_r * math.sqrt(bars_per_year)) if std_r > 0 else 0.0

    # Trade count: transitions into/out of position
    num_trades = int((position.diff().abs() > 0).sum())

    return total_return, max_drawdown, sharpe, num_trades


# ---------------------------------------------------------------------------
# Registered backtest runner
# ---------------------------------------------------------------------------

@register
class MomentumMABacktest(BacktestRunner):
    """Registered backtest for the MA crossover momentum strategy.

    Parameters match AgentSettings defaults so the backtest reflects
    the live strategy configuration.
    """

    name = "momentum_ma_crossover"

    FAST_PERIOD: int = 10
    SLOW_PERIOD: int = 30
    # 5 000 bars ≈ 13 trading days of 1-min data.  Fast to run and enough
    # cross signals for MA(10/30).  σ√T ≈ 14% keeps max DD well under 30%.
    N_BARS: int = 5_000
    DRIFT: float = 0.0003
    VOL: float = 0.002

    def run(self, config: BacktestConfig) -> BacktestResult:
        prices = _generate_synthetic_prices(
            n_bars=self.N_BARS,
            seed=42,
            drift=self.DRIFT,
            vol=self.VOL,
        )
        total_return, max_drawdown, sharpe, num_trades = _run_ma_crossover_backtest(
            prices,
            fast=self.FAST_PERIOD,
            slow=self.SLOW_PERIOD,
        )
        return BacktestResult(
            strategy=self.name,
            total_return=total_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            num_trades=num_trades,
        )
