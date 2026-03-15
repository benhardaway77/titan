"""Backtest framework for Titan.

Usage
-----
Implement a strategy by subclassing BacktestRunner and registering it:

    @register
    class MyStrategy(BacktestRunner):
        name = "my_strategy"

        def run(self, config: BacktestConfig) -> BacktestResult:
            ...
            return BacktestResult(
                strategy=self.name,
                total_return=...,
                max_drawdown=...,
                sharpe_ratio=...,
                num_trades=...,
            )

The promotion check (`run_regression_suite`) will call every registered
runner and verify the result passes the minimum thresholds in BacktestConfig.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import ClassVar


# ---------------------------------------------------------------------------
# Config / thresholds
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BacktestConfig:
    """Parameters and minimum pass thresholds for a backtest run."""

    # Evaluation window
    lookback_years: int = 2
    end_date: date = field(default_factory=date.today)

    # Pass/fail thresholds
    min_sharpe: float = 0.5         # annualised Sharpe
    max_drawdown_limit: float = 0.30  # max allowable peak-to-trough drawdown
    min_total_return: float = 0.0   # strategy must not be net negative

    @property
    def start_date(self) -> date:
        return self.end_date.replace(year=self.end_date.year - self.lookback_years)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    strategy: str
    total_return: float    # e.g. 0.42 = 42%
    max_drawdown: float    # e.g. 0.18 = 18% peak-to-trough
    sharpe_ratio: float    # annualised
    num_trades: int

    def passed(self, cfg: BacktestConfig) -> bool:
        return (
            self.sharpe_ratio >= cfg.min_sharpe
            and self.max_drawdown <= cfg.max_drawdown_limit
            and self.total_return >= cfg.min_total_return
        )

    def failure_reasons(self, cfg: BacktestConfig) -> list[str]:
        reasons = []
        if self.sharpe_ratio < cfg.min_sharpe:
            reasons.append(
                f"Sharpe {self.sharpe_ratio:.2f} < min {cfg.min_sharpe:.2f}"
            )
        if self.max_drawdown > cfg.max_drawdown_limit:
            reasons.append(
                f"Max drawdown {self.max_drawdown:.1%} > limit {cfg.max_drawdown_limit:.1%}"
            )
        if self.total_return < cfg.min_total_return:
            reasons.append(
                f"Total return {self.total_return:.1%} < min {cfg.min_total_return:.1%}"
            )
        return reasons


# ---------------------------------------------------------------------------
# Runner base + registry
# ---------------------------------------------------------------------------

_REGISTRY: list[BacktestRunner] = []


def register(cls: type[BacktestRunner]) -> type[BacktestRunner]:
    """Class decorator to register a BacktestRunner for the regression suite."""
    _REGISTRY.append(cls())
    return cls


def registered_runners() -> list[BacktestRunner]:
    return list(_REGISTRY)


class BacktestRunner:
    """Base class for strategy backtests.

    Subclass, set ``name``, implement ``run``, then decorate with ``@register``.
    """

    name: ClassVar[str] = "unnamed"

    def run(self, config: BacktestConfig) -> BacktestResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Regression suite (called by promotion checks)
# ---------------------------------------------------------------------------

@dataclass
class RegressionReport:
    config: BacktestConfig
    results: list[tuple[BacktestResult, list[str]]]   # (result, failure_reasons)

    @property
    def passed(self) -> bool:
        return all(not reasons for _, reasons in self.results)

    @property
    def summary(self) -> str:
        lines = [
            f"Backtest regression ({self.config.start_date} → {self.config.end_date})",
            f"Strategies: {len(self.results)}",
        ]
        for result, reasons in self.results:
            status = "PASS" if not reasons else "FAIL"
            lines.append(f"  [{status}] {result.strategy}")
            for r in reasons:
                lines.append(f"         {r}")
        return "\n".join(lines)


def run_regression_suite(config: BacktestConfig | None = None) -> RegressionReport:
    """Run all registered strategy backtests and return a RegressionReport."""
    cfg = config or BacktestConfig()
    runners = registered_runners()
    results = []
    for runner in runners:
        result = runner.run(cfg)
        results.append((result, result.failure_reasons(cfg)))
    return RegressionReport(config=cfg, results=results)
