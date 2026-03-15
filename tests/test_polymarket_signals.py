"""Unit tests for Polymarket odds signal and copy-trade signal (all mocked)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from titan.data.polymarket_data import PolyTrade
from titan.signals.copy_trade import CopyTradeEvent, CopyTradeSignal
from titan.signals.polymarket_odds import PolymarketOddsSignal, _odds_to_multiplier


# ---------------------------------------------------------------------------
# PolymarketOddsSignal
# ---------------------------------------------------------------------------

class TestOddsToMultiplier:
    def test_low_probability_full_size(self) -> None:
        assert _odds_to_multiplier(0.10) == 1.0
        assert _odds_to_multiplier(0.29) == 1.0

    def test_neutral_probability_reduced(self) -> None:
        assert _odds_to_multiplier(0.30) == 0.75
        assert _odds_to_multiplier(0.59) == 0.75

    def test_high_probability_risk_off(self) -> None:
        assert _odds_to_multiplier(0.60) == 0.50
        assert _odds_to_multiplier(0.79) == 0.50

    def test_very_high_probability_strong_risk_off(self) -> None:
        assert _odds_to_multiplier(0.80) == 0.25
        assert _odds_to_multiplier(0.99) == 0.25


class TestPolymarketOddsSignal:
    def _client(self, price: float = 0.5) -> MagicMock:
        c = MagicMock()
        c.get_market_price.return_value = price
        return c

    def test_no_markets_returns_1(self) -> None:
        sig = PolymarketOddsSignal(self._client(), market_ids=[])
        assert sig.get_size_multiplier() == 1.0

    def test_single_low_odds_market(self) -> None:
        sig = PolymarketOddsSignal(self._client(price=0.10), market_ids=["tok1"])
        assert sig.get_size_multiplier() == 1.0

    def test_single_high_odds_market(self) -> None:
        sig = PolymarketOddsSignal(self._client(price=0.85), market_ids=["tok1"])
        assert sig.get_size_multiplier() == 0.25

    def test_minimum_across_multiple_markets(self) -> None:
        client = MagicMock()
        client.get_market_price.side_effect = [0.10, 0.85]  # low, high
        sig = PolymarketOddsSignal(client, market_ids=["tok1", "tok2"])
        # min(1.0, 0.25) = 0.25
        assert sig.get_size_multiplier() == 0.25

    def test_fetch_error_returns_1_for_that_market(self) -> None:
        client = MagicMock()
        client.get_market_price.side_effect = RuntimeError("timeout")
        sig = PolymarketOddsSignal(client, market_ids=["tok1"])
        assert sig.get_size_multiplier() == 1.0


# ---------------------------------------------------------------------------
# CopyTradeSignal
# ---------------------------------------------------------------------------

def _make_trade(id: str, token_id: str = "tok1", side: str = "BUY",
                price: float = 0.55, size: float = 100.0) -> PolyTrade:
    return PolyTrade(
        id=id, address="0xABC", token_id=token_id,
        side=side, price=price, size=size, timestamp="2026-01-01T00:00:00Z",
    )


class TestCopyTradeSignal:
    def _client(self, trades: list[PolyTrade] | None = None) -> MagicMock:
        c = MagicMock()
        c.get_recent_trades.return_value = trades or []
        return c

    def test_first_poll_returns_no_events(self) -> None:
        client = self._client([_make_trade("id1")])
        sig = CopyTradeSignal(client, addresses=["0xABC"])
        events = sig.poll()
        assert events == []

    def test_second_poll_with_new_trade_returns_event(self) -> None:
        client = MagicMock()
        # First poll: baseline
        client.get_recent_trades.return_value = [_make_trade("id1")]
        sig = CopyTradeSignal(client, addresses=["0xABC"])
        sig.poll()  # baseline

        # Second poll: new trade appears
        client.get_recent_trades.return_value = [_make_trade("id2"), _make_trade("id1")]
        events = sig.poll()
        assert len(events) == 1
        assert events[0].token_id == "tok1"
        assert events[0].side == "BUY"

    def test_known_trade_not_re_emitted(self) -> None:
        client = self._client([_make_trade("id1")])
        sig = CopyTradeSignal(client, addresses=["0xABC"])
        sig.poll()  # baseline
        events = sig.poll()  # same trade, no new
        assert events == []

    def test_multiple_addresses_independent(self) -> None:
        client = MagicMock()
        client.get_recent_trades.return_value = [_make_trade("id1")]
        sig = CopyTradeSignal(client, addresses=["0xABC", "0xDEF"])
        sig.poll()  # baseline for both

        client.get_recent_trades.return_value = [_make_trade("id2"), _make_trade("id1")]
        events = sig.poll()
        # id2 is new for both addresses → 2 events
        assert len(events) == 2

    def test_fetch_error_skips_address(self) -> None:
        client = MagicMock()
        client.get_recent_trades.side_effect = RuntimeError("network error")
        sig = CopyTradeSignal(client, addresses=["0xABC"])
        sig.poll()  # should not crash
        events = sig.poll()
        assert events == []

    def test_add_address_dynamically(self) -> None:
        client = self._client([])
        sig = CopyTradeSignal(client, addresses=[])
        sig.add_address("0xNEW")
        assert "0xNEW" in sig._addresses
