"""State writer — persists Titan tick data as JSON for Mission Control dashboard.

Writes to ~/.openclaw/workspace/state/titan/ after every tick so the
Mission Control Next.js app can poll and display real-time data without
needing a live connection to the agent process.

Files written:
  snapshot.json       — portfolio + risk summary (overwritten each tick)
  positions.json      — all open positions (overwritten each tick)
  orders.json         — ring buffer of last ORDERS_LIMIT orders (all venues)
  signals.json        — ring buffer of last SIGNALS_LIMIT MA crossover signals
  copy_trades.json    — ring buffer of last COPY_LIMIT Polymarket copy events
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from titan.portfolio.state import PortfolioState
from titan.risk.governor import RiskGovernor
from titan.signals.copy_trade import CopyTradeEvent
from titan.signals.ma_crossover import CrossoverSignal

logger = logging.getLogger(__name__)

ORDERS_LIMIT = 50
SIGNALS_LIMIT = 30
COPY_LIMIT = 30

_DEFAULT_WORKSPACE = Path.home() / ".openclaw" / "workspace"


def _workspace() -> Path:
    raw = os.environ.get("WORKSPACE_ROOT", "")
    if raw:
        p = Path(raw)
        return p.expanduser() if str(p).startswith("~") else p
    return _DEFAULT_WORKSPACE


def _state_dir() -> Path:
    d = _workspace() / "state" / "titan"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(path: Path, data: object) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as exc:
        logger.warning("state_writer: failed to write %s — %s", path.name, exc)


def _read_ring(path: Path) -> list:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


class StateWriter:
    """Persists agent state to the Mission Control workspace after every tick."""

    def write_alpaca_tick(
        self,
        *,
        env: str,
        state: PortfolioState,
        governor: RiskGovernor,
        signals: list[CrossoverSignal],
        orders_submitted: int,
        size_multiplier: float,
        order_results: list[dict] | None = None,
    ) -> None:
        """Write snapshot + positions + signals + orders for an Alpaca tick."""
        d = _state_dir()
        now = datetime.now(timezone.utc).isoformat()
        risk_state = state.to_risk_state()
        zone = governor.zone(risk_state)

        # ── snapshot.json ────────────────────────────────────────────────
        _write(d / "snapshot.json", {
            "ts": now,
            "env": env,
            "equity": round(state.equity, 2),
            "hwm": round(state.high_water_mark, 2),
            "drawdown_pct": round(risk_state.drawdown_pct * 100, 3),
            "zone": zone,
            "leverage_cap": governor.leverage_cap(1.0, risk_state),
            "allow_new_risk": governor.allow_new_risk(risk_state),
            "macro_multiplier": round(size_multiplier, 4),
            "position_count": len(state.positions),
            "orders_submitted": orders_submitted,
        })

        # ── positions.json ───────────────────────────────────────────────
        positions = [
            {
                "symbol": sym,
                "qty": pos.qty,
                "avg_entry_price": round(pos.avg_entry_price, 4),
            }
            for sym, pos in state.positions.items()
        ]
        _write(d / "positions.json", {"ts": now, "positions": positions})

        # ── signals.json (ring buffer) ───────────────────────────────────
        if signals:
            ring = _read_ring(d / "signals.json")
            for sig in signals:
                ring.append({
                    "ts": now,
                    "symbol": sig.symbol,
                    "direction": sig.direction.value,
                    "fast_ma": round(sig.fast_ma, 4),
                    "slow_ma": round(sig.slow_ma, 4),
                })
            _write(d / "signals.json", ring[-SIGNALS_LIMIT:])

        # ── orders.json (ring buffer) ────────────────────────────────────
        if order_results:
            ring = _read_ring(d / "orders.json")
            for r in order_results:
                ring.append({"ts": now, "venue": "alpaca", **r})
            _write(d / "orders.json", ring[-ORDERS_LIMIT:])

    def write_poly_tick(
        self,
        *,
        events: list[CopyTradeEvent],
        order_results: list[dict] | None = None,
    ) -> None:
        """Append Polymarket copy-trade events + orders to their ring buffers."""
        if not events and not order_results:
            return

        d = _state_dir()
        now = datetime.now(timezone.utc).isoformat()

        # ── copy_trades.json (ring buffer) ───────────────────────────────
        if events:
            ring = _read_ring(d / "copy_trades.json")
            for ev in events:
                ring.append({
                    "ts": now,
                    "address": ev.address,
                    "token_id": ev.token_id,
                    "side": ev.side,
                    "price": round(ev.price, 4),
                    "size_usd": round(ev.size_usd, 2),
                })
            _write(d / "copy_trades.json", ring[-COPY_LIMIT:])

        # ── orders.json (ring buffer, shared with Alpaca) ────────────────
        if order_results:
            ring = _read_ring(d / "orders.json")
            for r in order_results:
                ring.append({"ts": now, "venue": "polymarket", **r})
            _write(d / "orders.json", ring[-ORDERS_LIMIT:])

    def seed_empty(self, env: str = "paper") -> None:
        """Write blank state files so the dashboard renders without errors."""
        d = _state_dir()
        now = datetime.now(timezone.utc).isoformat()

        snapshot_path = d / "snapshot.json"
        if not snapshot_path.exists():
            _write(snapshot_path, {
                "ts": now,
                "env": env,
                "equity": 0.0,
                "hwm": 0.0,
                "drawdown_pct": 0.0,
                "zone": "green",
                "leverage_cap": 1.0,
                "allow_new_risk": True,
                "macro_multiplier": 1.0,
                "position_count": 0,
                "orders_submitted": 0,
            })

        for fname in ("positions.json", "signals.json", "orders.json", "copy_trades.json"):
            path = d / fname
            if not path.exists():
                _write(path, [] if fname != "positions.json" else {"ts": now, "positions": []})
