"""In-memory portfolio state — no persistence, Alpaca is the source of truth."""
from __future__ import annotations

from dataclasses import dataclass, field

from titan.risk.governor import RiskState


@dataclass
class Position:
    symbol: str
    qty: float            # positive = long, negative = short
    avg_entry_price: float


@dataclass
class PortfolioState:
    """Tracks equity, high-water mark, and open positions.

    Equity is refreshed each tick from the Alpaca account endpoint.
    This class is purely in-memory; it does not persist across restarts.
    On restart the HWM resets to the current equity — conservative but safe.
    """

    initial_equity: float
    equity: float = 0.0
    high_water_mark: float = 0.0
    positions: dict[str, Position] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.equity == 0.0:
            self.equity = self.initial_equity
        self.high_water_mark = max(self.high_water_mark, self.equity)

    def update_equity(self, new_equity: float) -> None:
        """Refresh equity from broker; update high-water mark if new peak."""
        self.equity = new_equity
        self.high_water_mark = max(self.high_water_mark, new_equity)

    def to_risk_state(self) -> RiskState:
        return RiskState(equity=self.equity, high_water_mark=self.high_water_mark)

    def target_qty(
        self,
        symbol: str,
        last_price: float,
        position_size_pct: float,
        leverage_cap: float,
    ) -> int:
        """Compute integer share count for a new position.

        notional = equity * position_size_pct * leverage_cap
        qty = floor(notional / last_price)

        Returns 0 if last_price <= 0, leverage_cap == 0, or notional is tiny.
        """
        if last_price <= 0 or leverage_cap <= 0:
            return 0
        notional = self.equity * position_size_pct * leverage_cap
        qty = int(notional / last_price)
        return max(0, qty)

    def open_long(self, symbol: str, qty: float, price: float) -> None:
        self.positions[symbol] = Position(symbol=symbol, qty=qty, avg_entry_price=price)

    def close_position(self, symbol: str) -> None:
        self.positions.pop(symbol, None)

    def has_position(self, symbol: str) -> bool:
        return symbol in self.positions
