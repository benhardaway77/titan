"""Polymarket order submission via py-clob-client.

The broker is the *only* module that calls the Polymarket CLOB API for trading.
It requires: private_key (for EIP-712 order signing) + L2 API credentials.
All methods return ``OrderResult`` and never raise — callers log and continue.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType as ClobOrderType
from py_clob_client.order_builder.constants import BUY, SELL

from titan.config.settings import PolymarketSettings

logger = logging.getLogger(__name__)

# Polygon mainnet chain ID
_CHAIN_ID = 137


@dataclass(frozen=True)
class PolyOrderIntent:
    token_id: str
    side: str       # "BUY" | "SELL"  (YES = BUY token, NO = SELL token)
    size_usd: float
    price: float    # limit price in probability (0..1)


@dataclass
class PolyOrderResult:
    intent: PolyOrderIntent
    submitted: bool
    order_id: str | None = None
    error: str | None = None


class PolymarketBroker:
    """Thin wrapper around py-clob-client ClobClient for order submission."""

    def __init__(self, settings: PolymarketSettings) -> None:
        self._client = ClobClient(
            host=settings.clob_url,
            key=settings.private_key,
            chain_id=_CHAIN_ID,
            signature_type=0,  # 0 = EOA (standard wallet private key)
        )
        self._client.set_api_creds(
            self._client.create_or_derive_api_creds()
            if not settings.api_key
            else type("Creds", (), {  # type: ignore[arg-type]
                "api_key": settings.api_key,
                "api_secret": settings.api_secret,
                "api_passphrase": settings.api_passphrase,
            })()
        )

    def submit_order(self, intent: PolyOrderIntent) -> PolyOrderResult:
        """Place a GTC limit order on Polymarket. Never raises."""
        try:
            side_const = BUY if intent.side == "BUY" else SELL
            order_args = OrderArgs(
                token_id=intent.token_id,
                price=intent.price,
                size=intent.size_usd,
                side=side_const,
            )
            signed = self._client.create_order(order_args)
            resp = self._client.post_order(signed, ClobOrderType.GTC)
            order_id = resp.get("orderID", "")
            logger.info(
                "Poly order submitted: %s %s @ %.2f size=$%.2f id=%s",
                intent.side, intent.token_id, intent.price, intent.size_usd, order_id,
            )
            return PolyOrderResult(intent=intent, submitted=True, order_id=order_id)
        except Exception as exc:
            logger.error("Poly order failed %s %s: %s", intent.side, intent.token_id, exc)
            return PolyOrderResult(intent=intent, submitted=False, error=str(exc))

    def get_open_orders(self) -> list[dict]:
        """Return raw list of open orders from CLOB."""
        try:
            return self._client.get_orders() or []
        except Exception as exc:
            logger.error("Failed to fetch Poly open orders: %s", exc)
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a single order by ID. Returns True on success."""
        try:
            self._client.cancel(order_id)
            return True
        except Exception as exc:
            logger.error("Failed to cancel Poly order %s: %s", order_id, exc)
            return False


def build_poly_broker(settings: PolymarketSettings) -> PolymarketBroker:
    """Factory — raises ValueError if trading credentials are not set."""
    if not settings.is_trading_configured():
        raise ValueError(
            "Polymarket trading credentials not configured. "
            "Set POLY_PRIVATE_KEY, POLY_API_KEY, POLY_API_SECRET, POLY_API_PASSPHRASE in .env.paper"
        )
    return PolymarketBroker(settings)
