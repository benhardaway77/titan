from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskState:
    equity: float
    high_water_mark: float

    @property
    def drawdown_pct(self) -> float:
        if self.high_water_mark <= 0:
            return 0.0
        dd = (self.high_water_mark - self.equity) / self.high_water_mark
        return max(0.0, dd)


class RiskGovernor:
    """Enforces global portfolio safety rules (incl. -60% hard stop).

    Zones (ascending risk):
        green    : dd < green_dd           — full risk allowed
        yellow   : green_dd  <= dd < yellow_dd — leverage capped at 2x
        red      : yellow_dd <= dd < red_dd    — leverage capped at 1x
        critical : red_dd    <= dd < max_dd    — no new risk (1% before kill-switch)
        dead     : dd >= max_dd               — kill-switch; no trading
    """

    def __init__(
        self,
        max_drawdown_pct: float = 0.60,
        green_dd: float = 0.15,
        yellow_dd: float = 0.40,
        red_dd: float = 0.59,
    ):
        self.max_drawdown_pct = max_drawdown_pct
        self.green_dd = green_dd
        self.yellow_dd = yellow_dd
        self.red_dd = red_dd

    def zone(self, state: RiskState) -> str:
        dd = state.drawdown_pct
        if dd >= self.max_drawdown_pct:
            return "dead"
        if dd >= self.red_dd:
            return "critical"
        if dd >= self.yellow_dd:
            return "red"
        if dd >= self.green_dd:
            return "yellow"
        return "green"

    def allow_new_risk(self, state: RiskState) -> bool:
        return self.zone(state) in ("green", "yellow", "red")

    def leverage_cap(self, base_cap: float, state: RiskState) -> float:
        z = self.zone(state)
        if z == "green":
            return base_cap
        if z == "yellow":
            return min(base_cap, 2.0)
        if z == "red":
            return 1.0
        # critical or dead: no new leverage
        return 0.0
