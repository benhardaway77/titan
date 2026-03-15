"""Per-tick console reporting using rich."""
from __future__ import annotations

import logging
from datetime import datetime

from rich.console import Console
from rich.table import Table

from titan.portfolio.state import PortfolioState
from titan.risk.governor import RiskGovernor
from titan.signals.copy_trade import CopyTradeEvent
from titan.signals.ma_crossover import CrossoverSignal

logger = logging.getLogger(__name__)

_ZONE_COLOR = {
    "green": "green",
    "yellow": "yellow",
    "red": "red",
    "critical": "bold red",
    "dead": "white on red",
}


class TickReporter:
    """Prints a per-tick summary: zone, equity, signals, and orders."""

    def __init__(self) -> None:
        self._console = Console()

    def report_alpaca_tick(
        self,
        tick_time: datetime,
        state: PortfolioState,
        governor: RiskGovernor,
        signals: list[CrossoverSignal],
        orders_submitted: int,
        size_multiplier: float = 1.0,
    ) -> None:
        risk_state = state.to_risk_state()
        zone = governor.zone(risk_state)
        color = _ZONE_COLOR.get(zone, "white")
        dd_pct = risk_state.drawdown_pct * 100

        self._console.print(
            f"[bold]{tick_time.strftime('%H:%M:%S')}[/bold] "
            f"zone=[{color}]{zone}[/{color}] "
            f"equity=${state.equity:,.0f} "
            f"dd={dd_pct:.1f}% "
            f"positions={len(state.positions)} "
            f"signals={len(signals)} "
            f"orders={orders_submitted} "
            f"macro_mult={size_multiplier:.2f}"
        )

        if signals:
            t = Table(show_header=False, box=None, padding=(0, 1))
            for sig in signals:
                direction_color = "green" if sig.direction.value == "long" else "yellow"
                t.add_row(
                    f"  [{direction_color}]{sig.direction.value.upper()}[/{direction_color}]",
                    sig.symbol,
                    f"fast={sig.fast_ma:.2f}",
                    f"slow={sig.slow_ma:.2f}",
                )
            self._console.print(t)

    def report_poly_tick(
        self,
        tick_time: datetime,
        events: list[CopyTradeEvent],
        orders_submitted: int,
    ) -> None:
        if not events and not orders_submitted:
            return
        self._console.print(
            f"[bold]{tick_time.strftime('%H:%M:%S')}[/bold] [cyan]POLY[/cyan] "
            f"copy_events={len(events)} orders={orders_submitted}"
        )
        for ev in events:
            self._console.print(
                f"  copy {ev.side} {ev.token_id[:12]}... "
                f"@ {ev.price:.0%} size=${ev.size_usd:.0f} from {ev.address[:8]}..."
            )

    def report_blocked(self, reason: str) -> None:
        self._console.print(f"[bold red]RISK BLOCK[/bold red] {reason}")

    def report_error(self, context: str, error: str) -> None:
        self._console.print(f"[yellow]WARN[/yellow] {context}: {error}")
        logger.warning("%s: %s", context, error)
