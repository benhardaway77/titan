"""Polymarket odds signal — macro overlay for Alpaca position sizing.

Fetches the probability of configured macro markets (e.g. "Will the Fed
raise rates?") and returns a sizing multiplier applied to each Alpaca order.

If no macro_market_ids are configured, the multiplier is always 1.0.

Multiplier logic (simple threshold-based):
  price < 0.30  → regime is "risk-on"  → multiplier 1.0 (full size)
  price < 0.60  → regime is neutral    → multiplier 0.75
  price >= 0.60 → regime is "risk-off" → multiplier 0.50
  price >= 0.80 → strong risk-off      → multiplier 0.25
"""
from __future__ import annotations

import logging

from titan.data.polymarket_data import PolymarketDataClient

logger = logging.getLogger(__name__)

_THRESHOLDS = [
    (0.80, 0.25),
    (0.60, 0.50),
    (0.30, 0.75),
    (0.00, 1.00),
]


def _odds_to_multiplier(price: float) -> float:
    for threshold, multiplier in _THRESHOLDS:
        if price >= threshold:
            return multiplier
    return 1.0


class PolymarketOddsSignal:
    """Fetches macro market probabilities and derives a position-size multiplier.

    Call ``get_size_multiplier()`` each tick before sizing Alpaca orders.
    The multiplier is the *minimum* across all configured macro markets —
    conservative: if any macro signal says risk-off, we scale down everything.
    """

    def __init__(self, client: PolymarketDataClient, market_ids: list[str]) -> None:
        self._client = client
        self._market_ids = market_ids

    def get_size_multiplier(self) -> float:
        """Return a multiplier in (0, 1] based on configured macro markets.

        Returns 1.0 if no markets are configured or on any fetch error.
        """
        if not self._market_ids:
            return 1.0

        multipliers = []
        for token_id in self._market_ids:
            try:
                price = self._client.get_market_price(token_id)
                m = _odds_to_multiplier(price)
                multipliers.append(m)
                logger.debug("macro market %s price=%.2f multiplier=%.2f", token_id, price, m)
            except Exception as exc:
                logger.warning("Failed to fetch macro market %s: %s — using 1.0", token_id, exc)
                multipliers.append(1.0)

        return min(multipliers) if multipliers else 1.0
