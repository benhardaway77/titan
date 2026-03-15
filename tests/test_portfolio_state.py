"""Tests for PortfolioState equity tracking and position sizing."""
from __future__ import annotations

import pytest

from titan.portfolio.state import PortfolioState, Position
from titan.risk.governor import RiskState


class TestEquityTracking:
    def test_initial_equity_sets_hwm(self) -> None:
        ps = PortfolioState(initial_equity=50_000.0)
        assert ps.equity == 50_000.0
        assert ps.high_water_mark == 50_000.0

    def test_hwm_increases_with_equity(self) -> None:
        ps = PortfolioState(initial_equity=50_000.0)
        ps.update_equity(60_000.0)
        assert ps.high_water_mark == 60_000.0

    def test_hwm_does_not_decrease_on_drawdown(self) -> None:
        ps = PortfolioState(initial_equity=50_000.0)
        ps.update_equity(70_000.0)
        ps.update_equity(40_000.0)
        assert ps.high_water_mark == 70_000.0

    def test_to_risk_state(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        ps.update_equity(80_000.0)
        rs: RiskState = ps.to_risk_state()
        assert rs.equity == 80_000.0
        assert rs.high_water_mark == 100_000.0
        assert abs(rs.drawdown_pct - 0.20) < 1e-9


class TestTargetQty:
    def test_basic_sizing(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        # 10% of 100k at 1x leverage = $10k / $100/share = 100 shares
        qty = ps.target_qty("SPY", last_price=100.0, position_size_pct=0.10, leverage_cap=1.0)
        assert qty == 100

    def test_zero_leverage_cap_returns_zero(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        qty = ps.target_qty("SPY", last_price=100.0, position_size_pct=0.10, leverage_cap=0.0)
        assert qty == 0

    def test_zero_price_returns_zero(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        qty = ps.target_qty("SPY", last_price=0.0, position_size_pct=0.10, leverage_cap=1.0)
        assert qty == 0

    def test_leverage_multiplies_qty(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        qty_1x = ps.target_qty("SPY", last_price=100.0, position_size_pct=0.10, leverage_cap=1.0)
        qty_2x = ps.target_qty("SPY", last_price=100.0, position_size_pct=0.10, leverage_cap=2.0)
        assert qty_2x == qty_1x * 2

    def test_returns_int(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        qty = ps.target_qty("SPY", last_price=333.0, position_size_pct=0.10, leverage_cap=1.0)
        assert isinstance(qty, int)


class TestPositions:
    def test_open_and_has_position(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        assert not ps.has_position("SPY")
        ps.open_long("SPY", qty=10, price=400.0)
        assert ps.has_position("SPY")

    def test_close_position(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        ps.open_long("SPY", qty=10, price=400.0)
        ps.close_position("SPY")
        assert not ps.has_position("SPY")

    def test_close_nonexistent_is_noop(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        ps.close_position("MISSING")  # must not raise

    def test_position_fields(self) -> None:
        ps = PortfolioState(initial_equity=100_000.0)
        ps.open_long("AAPL", qty=5, price=200.0)
        pos = ps.positions["AAPL"]
        assert pos.qty == 5
        assert pos.avg_entry_price == 200.0
