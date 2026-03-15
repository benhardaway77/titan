"""Copy-trade signal — detects new trades from watched Polymarket wallets.

Polling strategy:
  - Each call to ``poll()`` fetches recent trades for every tracked address.
  - A per-address "last seen trade ID" is maintained in memory so only
    *new* trades since the last poll are emitted as events.
  - The first poll populates the baseline (no events emitted) so we don't
    replay historical trades on startup.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from titan.data.polymarket_data import PolymarketDataClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CopyTradeEvent:
    address: str     # source wallet that made the trade
    token_id: str    # Polymarket market token ID
    side: str        # "BUY" | "SELL"
    price: float     # probability at which they traded (0..1)
    size_usd: float  # their notional trade size in USD


class CopyTradeSignal:
    """Polls tracked wallet addresses and emits new trade events.

    Usage::

        signal = CopyTradeSignal(client, addresses=["0xABC...", "0xDEF..."])
        # First call: baseline — no events returned
        signal.poll()
        # Subsequent calls: only trades newer than last poll
        events = signal.poll()
    """

    def __init__(self, client: PolymarketDataClient, addresses: list[str]) -> None:
        self._client = client
        self._addresses = list(addresses)
        # address -> set of trade IDs already seen
        self._seen: dict[str, set[str]] = {addr: set() for addr in addresses}
        self._initialized: dict[str, bool] = {addr: False for addr in addresses}

    def poll(self) -> list[CopyTradeEvent]:
        """Return list of new trade events since the last poll.

        On the first call per address the baseline is set and no events
        are emitted (prevents replaying old trades on startup).
        """
        events: list[CopyTradeEvent] = []

        for address in self._addresses:
            try:
                trades = self._client.get_recent_trades(address, limit=20)
            except Exception as exc:
                logger.warning("Failed to fetch trades for %s: %s", address, exc)
                continue

            if not self._initialized[address]:
                # First call: populate baseline, emit nothing
                self._seen[address] = {t.id for t in trades}
                self._initialized[address] = True
                continue

            for trade in trades:
                if trade.id in self._seen[address]:
                    continue
                self._seen[address].add(trade.id)
                events.append(CopyTradeEvent(
                    address=address,
                    token_id=trade.token_id,
                    side=trade.side,
                    price=trade.price,
                    size_usd=trade.size,
                ))

        return events

    def add_address(self, address: str) -> None:
        """Dynamically add a new address to watch (initialized on next poll)."""
        if address not in self._addresses:
            self._addresses.append(address)
            self._seen[address] = set()
            self._initialized[address] = False
