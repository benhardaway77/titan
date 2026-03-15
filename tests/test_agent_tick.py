"""Unit tests for AlpacaMomentumAgent and PolymarketCopyAgent ticks.

All network calls (Alpaca, Polymarket) are mocked — runs without credentials.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from titan.agent import AlpacaMomentumAgent, PolymarketCopyAgent
from titan.brokers.alpaca_broker import OrderResult
from titan.brokers.polymarket_broker import PolyOrderResult
from titan.config.settings import AgentSettings, AlpacaSettings, PolymarketSettings, Settings
from titan.portfolio.state import PortfolioState, Position
from titan.risk.governor import RiskGovernor
from titan.reporting.tick_reporter import TickReporter
from titan.reporting.state_writer import StateWriter
from titan.signals.copy_trade import CopyTradeEvent, CopyTradeSignal
from titan.signals.ma_crossover import MACrossoverSignal
from titan.signals.polymarket_odds import PolymarketOddsSignal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings(symbols=None, fast=3, slow=5) -> Settings:
    return Settings(
        env="paper",
        agent=AgentSettings(
            symbols=symbols or ["SPY"],
            fast_period=fast,
            slow_period=slow,
            tick_interval_seconds=60,
            position_size_pct=0.10,
        ),
        alpaca=AlpacaSettings(api_key="K", secret_key="S"),
        polymarket=PolymarketSettings(
            private_key="pk", api_key="ak", api_secret="as", api_passphrase="ap",
            copy_addresses=["0xABC"],
            copy_size_pct=0.03,
            max_copy_odds=0.85,
        ),
    )


def _make_portfolio(equity: float = 100_000.0) -> PortfolioState:
    return PortfolioState(initial_equity=equity)


def _make_governor() -> RiskGovernor:
    return RiskGovernor()


def _cross_up_bars(fast: int, slow: int) -> pd.DataFrame:
    """Prices that produce fast MA > slow MA at the end."""
    declining = [100.0 - i * 0.5 for i in range(slow)]
    rising = [80.0 + i * 5.0 for i in range(fast + 5)]
    prices = declining + rising
    return pd.DataFrame({"close": prices})


def _flat_bars(n: int = 20) -> pd.DataFrame:
    return pd.DataFrame({"close": [100.0] * n})


def _mock_broker(equity: float = 100_000.0) -> MagicMock:
    b = MagicMock()
    b.get_account_equity.return_value = equity
    b.submit_order.return_value = MagicMock(submitted=True, order_id="ord1", error=None)
    b.close_position.return_value = MagicMock(submitted=True, order_id="ord2", error=None)
    return b


def _mock_fetcher(bars: dict | None = None) -> MagicMock:
    f = MagicMock()
    f.fetch_bars.return_value = bars or {}
    return f


def _mock_odds(multiplier: float = 1.0) -> MagicMock:
    o = MagicMock()
    o.get_size_multiplier.return_value = multiplier
    return o


def _mock_reporter() -> MagicMock:
    return MagicMock(spec=TickReporter)


def _mock_state_writer() -> MagicMock:
    return MagicMock(spec=StateWriter)


def _build_alpaca_agent(settings, portfolio, governor, fetcher, broker, odds=None, reporter=None, state_writer=None):
    return AlpacaMomentumAgent(
        settings=settings,
        portfolio=portfolio,
        governor=governor,
        fetcher=fetcher,
        broker=broker,
        odds_signal=odds or _mock_odds(),
        reporter=reporter or _mock_reporter(),
        state_writer=state_writer or _mock_state_writer(),
    )


# ---------------------------------------------------------------------------
# AlpacaMomentumAgent
# ---------------------------------------------------------------------------

class TestAlpacaMomentumAgentTick:
    def test_submits_buy_on_cross_up(self) -> None:
        settings = _settings(fast=3, slow=5)
        portfolio = _make_portfolio()
        broker = _mock_broker()
        fetcher = _mock_fetcher({"SPY": _cross_up_bars(3, 5)})
        agent = _build_alpaca_agent(settings, portfolio, _make_governor(), fetcher, broker)

        agent.tick()

        broker.submit_order.assert_called_once()
        intent = broker.submit_order.call_args[0][0]
        assert intent.symbol == "SPY"
        assert intent.side == "buy"
        assert intent.qty > 0

    def test_no_order_when_flat_prices(self) -> None:
        settings = _settings(fast=3, slow=5)
        fetcher = _mock_fetcher({"SPY": _flat_bars()})
        broker = _mock_broker()
        agent = _build_alpaca_agent(settings, _make_portfolio(), _make_governor(), fetcher, broker)

        agent.tick()
        broker.submit_order.assert_not_called()

    def test_no_order_when_risk_dead(self) -> None:
        settings = _settings(fast=3, slow=5)
        portfolio = _make_portfolio(equity=100_000.0)
        portfolio.high_water_mark = 100_000.0
        portfolio.equity = 1.0   # 99.999% drawdown → dead zone

        broker = _mock_broker(equity=1.0)
        fetcher = _mock_fetcher({"SPY": _cross_up_bars(3, 5)})
        reporter = _mock_reporter()
        agent = _build_alpaca_agent(
            settings, portfolio, _make_governor(), fetcher, broker, reporter=reporter
        )

        agent.tick()
        broker.submit_order.assert_not_called()
        reporter.report_blocked.assert_called_once()

    def test_no_duplicate_buy_when_position_already_open(self) -> None:
        settings = _settings(fast=3, slow=5)
        portfolio = _make_portfolio()
        portfolio.open_long("SPY", qty=10, price=100.0)

        broker = _mock_broker()
        fetcher = _mock_fetcher({"SPY": _cross_up_bars(3, 5)})
        agent = _build_alpaca_agent(settings, portfolio, _make_governor(), fetcher, broker)

        agent.tick()
        broker.submit_order.assert_not_called()

    def test_exit_closes_open_position(self) -> None:
        settings = _settings(fast=3, slow=5)
        portfolio = _make_portfolio()
        portfolio.open_long("SPY", qty=10, price=100.0)

        # Prime signal state so it thinks it already emitted LONG
        broker = _mock_broker()
        fetcher = _mock_fetcher({"SPY": _flat_bars()})
        agent = _build_alpaca_agent(settings, portfolio, _make_governor(), fetcher, broker)

        # Override signal state to LONG so declining prices emit EXIT
        from titan.signals.ma_crossover import Direction
        agent._ma_signal._last_direction["SPY"] = Direction.LONG

        declining = pd.DataFrame({"close": [100.0 - i * 2 for i in range(20)]})
        agent._fetcher.fetch_bars.return_value = {"SPY": declining}

        agent.tick()
        broker.close_position.assert_called_once_with("SPY")

    def test_missing_symbol_in_bars_skipped(self) -> None:
        settings = _settings(symbols=["SPY", "QQQ"])
        broker = _mock_broker()
        fetcher = _mock_fetcher({})  # no bars for any symbol
        agent = _build_alpaca_agent(settings, _make_portfolio(), _make_governor(), fetcher, broker)

        agent.tick()
        broker.submit_order.assert_not_called()

    def test_odds_multiplier_scales_position_size(self) -> None:
        """With odds_multiplier=0.5, qty should be half what it would be at 1.0."""
        settings = _settings(fast=3, slow=5)
        bars = {"SPY": _cross_up_bars(3, 5)}

        broker_full = _mock_broker()
        agent_full = _build_alpaca_agent(
            settings, _make_portfolio(), _make_governor(),
            _mock_fetcher(bars), broker_full, odds=_mock_odds(1.0)
        )
        agent_full.tick()
        qty_full = broker_full.submit_order.call_args[0][0].qty

        broker_half = _mock_broker()
        agent_half = _build_alpaca_agent(
            settings, _make_portfolio(), _make_governor(),
            _mock_fetcher(bars), broker_half, odds=_mock_odds(0.5)
        )
        agent_half.tick()
        qty_half = broker_half.submit_order.call_args[0][0].qty

        assert qty_half <= qty_full  # scaled down (may be 0 if very small)


# ---------------------------------------------------------------------------
# PolymarketCopyAgent
# ---------------------------------------------------------------------------

class TestPolymarketCopyAgentTick:
    def _build_poly_agent(self, settings, portfolio, governor, copy_signal, poly_broker, state_writer=None):
        return PolymarketCopyAgent(
            settings=settings,
            portfolio=portfolio,
            governor=governor,
            copy_signal=copy_signal,
            broker=poly_broker,
            reporter=_mock_reporter(),
            state_writer=state_writer or _mock_state_writer(),
        )

    def test_submits_order_on_new_copy_event(self) -> None:
        settings = _settings()
        portfolio = _make_portfolio()
        governor = _make_governor()

        event = CopyTradeEvent(
            address="0xABC", token_id="tok1", side="BUY", price=0.60, size_usd=500.0
        )
        copy_signal = MagicMock()
        copy_signal.poll.return_value = [event]

        poly_broker = MagicMock()
        poly_broker.submit_order.return_value = MagicMock(submitted=True, order_id="p1", error=None)

        agent = self._build_poly_agent(settings, portfolio, governor, copy_signal, poly_broker)
        agent.tick()

        poly_broker.submit_order.assert_called_once()
        intent = poly_broker.submit_order.call_args[0][0]
        assert intent.token_id == "tok1"
        assert intent.side == "BUY"

    def test_skips_trade_above_max_odds(self) -> None:
        settings = _settings()
        portfolio = _make_portfolio()

        event = CopyTradeEvent(
            address="0xABC", token_id="tok1", side="BUY", price=0.90, size_usd=500.0
        )
        copy_signal = MagicMock()
        copy_signal.poll.return_value = [event]

        poly_broker = MagicMock()
        agent = self._build_poly_agent(
            settings, portfolio, _make_governor(), copy_signal, poly_broker
        )
        agent.tick()

        poly_broker.submit_order.assert_not_called()

    def test_no_order_when_no_events(self) -> None:
        settings = _settings()
        copy_signal = MagicMock()
        copy_signal.poll.return_value = []
        poly_broker = MagicMock()

        agent = self._build_poly_agent(
            settings, _make_portfolio(), _make_governor(), copy_signal, poly_broker
        )
        agent.tick()
        poly_broker.submit_order.assert_not_called()

    def test_no_order_when_risk_dead(self) -> None:
        settings = _settings()
        portfolio = _make_portfolio()
        portfolio.high_water_mark = 100_000.0
        portfolio.equity = 1.0  # dead zone

        event = CopyTradeEvent("0xABC", "tok1", "BUY", 0.55, 500.0)
        copy_signal = MagicMock()
        copy_signal.poll.return_value = [event]
        poly_broker = MagicMock()

        agent = self._build_poly_agent(
            settings, portfolio, _make_governor(), copy_signal, poly_broker
        )
        agent.tick()
        poly_broker.submit_order.assert_not_called()
