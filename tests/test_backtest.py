from titan.backtest.runner import (
    BacktestConfig,
    BacktestResult,
    BacktestRunner,
    RegressionReport,
    _REGISTRY,
    run_regression_suite,
)
from titan.checks import run_backtest_regression


# ---------------------------------------------------------------------------
# BacktestResult
# ---------------------------------------------------------------------------

def _make_result(strategy="test", total_return=0.20, max_drawdown=0.10, sharpe=1.2, trades=100):
    return BacktestResult(
        strategy=strategy,
        total_return=total_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        num_trades=trades,
    )


def test_result_passes_defaults():
    cfg = BacktestConfig()
    r = _make_result()
    assert r.passed(cfg) is True
    assert r.failure_reasons(cfg) == []


def test_result_fails_low_sharpe():
    cfg = BacktestConfig(min_sharpe=1.0)
    r = _make_result(sharpe=0.3)
    assert r.passed(cfg) is False
    reasons = r.failure_reasons(cfg)
    assert any("Sharpe" in s for s in reasons)


def test_result_fails_high_drawdown():
    cfg = BacktestConfig(max_drawdown_limit=0.20)
    r = _make_result(max_drawdown=0.35)
    assert r.passed(cfg) is False
    reasons = r.failure_reasons(cfg)
    assert any("drawdown" in s for s in reasons)


def test_result_fails_negative_return():
    cfg = BacktestConfig(min_total_return=0.0)
    r = _make_result(total_return=-0.05)
    assert r.passed(cfg) is False
    reasons = r.failure_reasons(cfg)
    assert any("return" in s for s in reasons)


def test_result_multiple_failures():
    cfg = BacktestConfig(min_sharpe=1.0, max_drawdown_limit=0.20, min_total_return=0.0)
    r = _make_result(sharpe=0.1, max_drawdown=0.50, total_return=-0.10)
    assert len(r.failure_reasons(cfg)) == 3


# ---------------------------------------------------------------------------
# BacktestConfig
# ---------------------------------------------------------------------------

def test_config_start_date():
    from datetime import date
    cfg = BacktestConfig(lookback_years=2, end_date=date(2026, 1, 1))
    assert cfg.start_date == date(2024, 1, 1)


# ---------------------------------------------------------------------------
# Regression suite with a stub runner
# ---------------------------------------------------------------------------

class _PassingRunner(BacktestRunner):
    name = "_test_passing"

    def run(self, config: BacktestConfig) -> BacktestResult:
        return _make_result(strategy=self.name)


class _FailingRunner(BacktestRunner):
    name = "_test_failing"

    def run(self, config: BacktestConfig) -> BacktestResult:
        return _make_result(strategy=self.name, sharpe=-1.0, total_return=-0.5)


def test_regression_suite_all_pass():
    cfg = BacktestConfig()
    runners = [_PassingRunner()]
    results = [(r.run(cfg), r.run(cfg).failure_reasons(cfg)) for r in runners]
    report = RegressionReport(config=cfg, results=results)
    assert report.passed is True


def test_regression_suite_one_fail():
    cfg = BacktestConfig()
    runners = [_PassingRunner(), _FailingRunner()]
    results = [(r.run(cfg), r.run(cfg).failure_reasons(cfg)) for r in runners]
    report = RegressionReport(config=cfg, results=results)
    assert report.passed is False


def test_regression_suite_empty_registry():
    """No registered strategies should not block promotion at scaffold stage."""
    cfg = BacktestConfig()
    # run_regression_suite uses the global registry; if it's empty, passed=True
    orig = _REGISTRY.copy()
    _REGISTRY.clear()
    try:
        report = run_regression_suite(cfg)
        assert report.passed is True
        assert report.results == []
    finally:
        _REGISTRY.extend(orig)


# ---------------------------------------------------------------------------
# CheckResult integration
# ---------------------------------------------------------------------------

def test_check_no_strategies_passes():
    orig = _REGISTRY.copy()
    _REGISTRY.clear()
    try:
        result = run_backtest_regression()
        assert result.ok is True
        assert "No strategies" in result.details
    finally:
        _REGISTRY.extend(orig)
