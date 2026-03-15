"""Polymarket public Data API client (no authentication required).

Used for:
  1. Fetching current market prices (YES probability) for macro overlay.
  2. Polling tracked wallet addresses for copy-trade signal detection.
"""
from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class PolyTrade:
    id: str
    address: str
    token_id: str
    side: str          # "BUY" | "SELL"
    price: float       # probability (0..1)
    size: float        # USD size
    timestamp: str     # ISO-8601


@dataclass(frozen=True)
class PolyPosition:
    token_id: str
    size: float
    avg_price: float


class PolymarketDataClient:
    """Thin wrapper around the public Polymarket Data API.

    Base URL: https://data-api.polymarket.com
    No authentication required for any endpoint.
    """

    def __init__(self, base_url: str = "https://data-api.polymarket.com", timeout: int = 10) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = "titan-agent/0.1"

    def get_recent_trades(self, address: str, limit: int = 50) -> list[PolyTrade]:
        """Return up to `limit` most recent trades for a wallet address."""
        resp = self._session.get(
            f"{self._base}/trades",
            params={"user": address, "limit": limit},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        trades = []
        for item in resp.json():
            trades.append(PolyTrade(
                id=str(item.get("id", "")),
                address=address,
                token_id=str(item.get("asset_id", item.get("token_id", ""))),
                side=str(item.get("side", "BUY")).upper(),
                price=float(item.get("price", 0.0)),
                size=float(item.get("size", 0.0)),
                timestamp=str(item.get("timestamp", "")),
            ))
        return trades

    def get_market_price(self, token_id: str) -> float:
        """Return the current YES price (probability 0..1) for a market token.

        Falls back to 0.5 (neutral) on any error so callers never crash.
        """
        try:
            resp = self._session.get(
                f"{self._base}/price",
                params={"token_id": token_id},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return float(data.get("price", 0.5))
        except Exception:
            return 0.5

    def get_positions(self, address: str) -> list[PolyPosition]:
        """Return all open positions for a wallet address."""
        resp = self._session.get(
            f"{self._base}/positions",
            params={"user": address},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        positions = []
        for item in resp.json():
            positions.append(PolyPosition(
                token_id=str(item.get("asset_id", item.get("token_id", ""))),
                size=float(item.get("size", 0.0)),
                avg_price=float(item.get("avg_price", 0.0)),
            ))
        return positions
