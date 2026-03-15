"""Alpaca order submission — paper and live.

The broker is the *only* module that submits Alpaca orders.
All callers must ensure risk checks have passed before calling any submit_*().
Every method returns an ``OrderResult`` and never raises — the agent loop can
log and continue rather than crashing on a transient API error.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from alpaca.trading import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import ClosePositionRequest, MarketOrderRequest

from titan.config.settings import AlpacaSettings

logger = logging.getLogger(__name__)


class OrderType(str, Enum):
    MARKET = "market"


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    side: str    # "buy" | "sell"
    qty: int
    order_type: OrderType = OrderType.MARKET
    time_in_force: str = "day"


@dataclass
class OrderResult:
    intent: OrderIntent | None
    submitted: bool
    order_id: str | None = None
    error: str | None = None


class AlpacaBroker:
    """Thin wrapper around alpaca-py TradingClient."""

    def __init__(self, settings: AlpacaSettings, paper: bool = True) -> None:
        self._client = TradingClient(
            api_key=settings.api_key,
            secret_key=settings.secret_key,
            paper=paper,
        )

    def get_account_equity(self) -> float:
        """Fetch current portfolio equity from Alpaca."""
        account = self._client.get_account()
        return float(account.equity)

    def submit_order(self, intent: OrderIntent) -> OrderResult:
        """Submit a market order. Returns OrderResult — never raises."""
        try:
            side = OrderSide.BUY if intent.side == "buy" else OrderSide.SELL
            tif = TimeInForce.DAY if intent.time_in_force == "day" else TimeInForce.GTC
            req = MarketOrderRequest(
                symbol=intent.symbol,
                qty=intent.qty,
                side=side,
                time_in_force=tif,
            )
            order = self._client.submit_order(req)
            logger.info("Order submitted: %s %d %s id=%s", intent.side, intent.qty, intent.symbol, order.id)
            return OrderResult(intent=intent, submitted=True, order_id=str(order.id))
        except Exception as exc:
            logger.error("Order failed %s %d %s: %s", intent.side, intent.qty, intent.symbol, exc)
            return OrderResult(intent=intent, submitted=False, error=str(exc))

    def close_position(self, symbol: str) -> OrderResult:
        """Submit a market close for all shares of ``symbol``."""
        try:
            self._client.close_position(symbol)
            logger.info("Position closed: %s", symbol)
            dummy_intent = OrderIntent(symbol=symbol, side="sell", qty=0)
            return OrderResult(intent=dummy_intent, submitted=True)
        except Exception as exc:
            logger.error("Failed to close %s: %s", symbol, exc)
            dummy_intent = OrderIntent(symbol=symbol, side="sell", qty=0)
            return OrderResult(intent=dummy_intent, submitted=False, error=str(exc))

    def get_open_positions(self) -> dict[str, float]:
        """Return {symbol: qty} for all open positions from Alpaca."""
        try:
            positions = self._client.get_all_positions()
            return {p.symbol: float(p.qty) for p in positions}
        except Exception as exc:
            logger.error("Failed to fetch positions: %s", exc)
            return {}


def build_broker(settings: AlpacaSettings, paper: bool = True) -> AlpacaBroker:
    """Factory — raises ValueError if credentials are not configured."""
    if not settings.is_configured():
        raise ValueError(
            "Alpaca credentials not configured. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env.paper"
        )
    return AlpacaBroker(settings, paper=paper)
