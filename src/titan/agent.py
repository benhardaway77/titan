"""Titan trading agents.

AlpacaMomentumAgent — MA crossover on Alpaca equities with Polymarket macro overlay.
PolymarketCopyAgent — mirrors tracked wallet trades on Polymarket.

Both agents share the same RiskGovernor and PortfolioState (one global drawdown gate).
``run_agents()`` is the single entry point called from cli.py.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from titan.brokers.alpaca_broker import AlpacaBroker, OrderIntent, build_broker
from titan.brokers.polymarket_broker import PolyOrderIntent, PolymarketBroker, build_poly_broker
from titan.config.settings import Settings
from titan.data.alpaca_bars import AlpacaBarFetcher, build_fetcher
from titan.data.polymarket_data import PolymarketDataClient
from titan.portfolio.state import PortfolioState
from titan.reporting.state_writer import StateWriter
from titan.reporting.tick_reporter import TickReporter
from titan.risk.governor import RiskGovernor
from titan.signals.copy_trade import CopyTradeSignal
from titan.signals.ma_crossover import Direction, MACrossoverSignal
from titan.signals.polymarket_odds import PolymarketOddsSignal

logger = logging.getLogger(__name__)


class AlpacaMomentumAgent:
    """MA crossover momentum agent for Alpaca equities.

    Uses Polymarket odds as a macro overlay to scale position sizes when
    macro risk markets signal elevated uncertainty.
    """

    def __init__(
        self,
        settings: Settings,
        portfolio: PortfolioState,
        governor: RiskGovernor,
        fetcher: AlpacaBarFetcher,
        broker: AlpacaBroker,
        odds_signal: PolymarketOddsSignal,
        reporter: TickReporter,
        state_writer: StateWriter,
    ) -> None:
        self._cfg = settings.agent
        self._risk_cfg = settings.risk
        self._env = settings.env
        self._portfolio = portfolio
        self._governor = governor
        self._fetcher = fetcher
        self._broker = broker
        self._odds_signal = odds_signal
        self._reporter = reporter
        self._state_writer = state_writer
        self._ma_signal = MACrossoverSignal(
            fast_period=self._cfg.fast_period,
            slow_period=self._cfg.slow_period,
        )

    def tick(self) -> None:
        """Single agent tick: fetch bars → signals → risk gate → orders → report."""
        equity = self._broker.get_account_equity()
        self._portfolio.update_equity(equity)
        risk_state = self._portfolio.to_risk_state()

        if not self._governor.allow_new_risk(risk_state):
            self._reporter.report_blocked(
                f"zone={self._governor.zone(risk_state)} "
                f"dd={risk_state.drawdown_pct:.1%}"
            )
            return

        # Macro overlay: scale position sizes when risk-off
        size_multiplier = self._odds_signal.get_size_multiplier()

        bars = self._fetcher.fetch_bars(
            self._cfg.symbols,
            lookback_bars=self._cfg.slow_period + 5,
        )

        signals_emitted = []
        order_results: list[dict] = []
        orders_submitted = 0

        for symbol in self._cfg.symbols:
            df = bars.get(symbol)
            if df is None or df.empty:
                continue

            signal = self._ma_signal.compute(symbol, df["close"])
            if signal is None:
                continue

            signals_emitted.append(signal)

            if signal.direction == Direction.LONG:
                n, results = self._handle_long(
                    symbol, float(df["close"].iloc[-1]), risk_state, size_multiplier
                )
                orders_submitted += n
                order_results.extend(results)
            elif signal.direction == Direction.EXIT:
                n, results = self._handle_exit(symbol)
                orders_submitted += n
                order_results.extend(results)

        tick_time = datetime.now(timezone.utc)
        self._reporter.report_alpaca_tick(
            tick_time=tick_time,
            state=self._portfolio,
            governor=self._governor,
            signals=signals_emitted,
            orders_submitted=orders_submitted,
            size_multiplier=size_multiplier,
        )
        self._state_writer.write_alpaca_tick(
            env=self._env,
            state=self._portfolio,
            governor=self._governor,
            signals=signals_emitted,
            orders_submitted=orders_submitted,
            size_multiplier=size_multiplier,
            order_results=order_results or None,
        )

    def _handle_long(
        self, symbol: str, last_price: float, risk_state, size_multiplier: float
    ) -> tuple[int, list[dict]]:
        if self._portfolio.has_position(symbol):
            return 0, []  # no pyramiding

        base_cap = self._risk_cfg.crypto_max_leverage
        eff_cap = self._governor.leverage_cap(base_cap, risk_state)
        effective_size_pct = self._cfg.position_size_pct * size_multiplier

        qty = self._portfolio.target_qty(
            symbol, last_price, effective_size_pct, eff_cap
        )
        if qty <= 0:
            return 0, []

        intent = OrderIntent(symbol=symbol, side="buy", qty=qty)
        result = self._broker.submit_order(intent)
        if result.submitted:
            self._portfolio.open_long(symbol, qty, last_price)
        else:
            self._reporter.report_error(symbol, result.error or "unknown error")
        r = {"symbol": symbol, "side": "buy", "qty": qty,
             "submitted": result.submitted, "order_id": result.order_id,
             "error": result.error}
        return (1 if result.submitted else 0), [r]

    def _handle_exit(self, symbol: str) -> tuple[int, list[dict]]:
        if not self._portfolio.has_position(symbol):
            return 0, []
        result = self._broker.close_position(symbol)
        if result.submitted:
            self._portfolio.close_position(symbol)
            self._ma_signal.reset(symbol)
        r = {"symbol": symbol, "side": "sell", "qty": 0,
             "submitted": result.submitted, "order_id": result.order_id,
             "error": result.error}
        return (1 if result.submitted else 0), [r]


class PolymarketCopyAgent:
    """Mirrors trades from tracked Polymarket wallet addresses.

    Each tick polls the Data API for new trades from watched wallets and
    submits proportionally sized orders via the CLOB broker.
    Skips trades where the odds price exceeds ``max_copy_odds`` (too crowded).
    """

    def __init__(
        self,
        settings: Settings,
        portfolio: PortfolioState,
        governor: RiskGovernor,
        copy_signal: CopyTradeSignal,
        broker: PolymarketBroker,
        reporter: TickReporter,
        state_writer: StateWriter,
    ) -> None:
        self._poly_cfg = settings.polymarket
        self._risk_cfg = settings.risk
        self._portfolio = portfolio
        self._governor = governor
        self._copy_signal = copy_signal
        self._broker = broker
        self._reporter = reporter
        self._state_writer = state_writer

    def tick(self) -> None:
        """Single copy-agent tick: poll wallets → filter → risk gate → orders."""
        risk_state = self._portfolio.to_risk_state()

        if not self._governor.allow_new_risk(risk_state):
            return  # already reported by Alpaca agent if both share the same tick

        events = self._copy_signal.poll()
        orders_submitted = 0
        order_results: list[dict] = []

        for event in events:
            # Skip if odds are already too high (crowded / low edge)
            if event.price > self._poly_cfg.max_copy_odds:
                logger.debug(
                    "Skipping copy trade: %s @ %.2f > max_copy_odds %.2f",
                    event.token_id, event.price, self._poly_cfg.max_copy_odds,
                )
                continue

            # Re-check risk gate per order
            if not self._governor.allow_new_risk(risk_state):
                break

            size_usd = self._portfolio.equity * self._poly_cfg.copy_size_pct
            if size_usd < 1.0:
                continue

            intent = PolyOrderIntent(
                token_id=event.token_id,
                side=event.side,
                size_usd=size_usd,
                price=event.price,
            )
            result = self._broker.submit_order(intent)
            if result.submitted:
                orders_submitted += 1
            else:
                self._reporter.report_error(
                    f"poly:{event.token_id[:12]}", result.error or "unknown"
                )
            order_results.append({
                "token_id": event.token_id,
                "side": event.side,
                "size_usd": round(size_usd, 2),
                "price": round(event.price, 4),
                "submitted": result.submitted,
                "order_id": result.order_id,
                "error": result.error,
            })

        self._reporter.report_poly_tick(
            tick_time=datetime.now(timezone.utc),
            events=events,
            orders_submitted=orders_submitted,
        )
        self._state_writer.write_poly_tick(
            events=events,
            order_results=order_results or None,
        )


def run_agents(settings: Settings) -> None:
    """Build both agents and run them in an interleaved blocking loop.

    Agents share RiskGovernor and PortfolioState (one global drawdown gate).
    Polymarket agents are only instantiated if credentials are present —
    running without Polymarket credentials only activates the Alpaca agent.
    """
    paper = settings.env != "live"

    # --- Shared state ---
    governor = RiskGovernor(
        max_drawdown_pct=settings.risk.max_drawdown_pct,
        green_dd=settings.risk.green_dd,
        yellow_dd=settings.risk.yellow_dd,
        red_dd=settings.risk.red_dd,
    )
    reporter = TickReporter()

    # --- Alpaca agent ---
    alpaca_broker = build_broker(settings.alpaca, paper=paper)
    initial_equity = alpaca_broker.get_account_equity()
    portfolio = PortfolioState(initial_equity=initial_equity)
    fetcher = build_fetcher(settings.alpaca, timeframe_str=settings.agent.bar_timeframe)
    poly_data = PolymarketDataClient(base_url=settings.polymarket.data_url)
    odds_signal = PolymarketOddsSignal(poly_data, settings.polymarket.macro_market_ids)

    alpaca_agent = AlpacaMomentumAgent(
        settings=settings,
        portfolio=portfolio,
        governor=governor,
        fetcher=fetcher,
        broker=alpaca_broker,
        odds_signal=odds_signal,
        reporter=reporter,
    )

    # --- Polymarket copy agent (optional) ---
    poly_agent: PolymarketCopyAgent | None = None
    if settings.polymarket.is_trading_configured() and settings.polymarket.copy_addresses:
        poly_broker = build_poly_broker(settings.polymarket)
        copy_signal = CopyTradeSignal(poly_data, settings.polymarket.copy_addresses)
        poly_agent = PolymarketCopyAgent(
            settings=settings,
            portfolio=portfolio,
            governor=governor,
            copy_signal=copy_signal,
            broker=poly_broker,
            reporter=reporter,
        )
        logger.info(
            "PolymarketCopyAgent active — watching %d address(es)",
            len(settings.polymarket.copy_addresses),
        )
    else:
        logger.info("Polymarket copy agent disabled (credentials or addresses not set)")

    interval = settings.agent.tick_interval_seconds
    logger.info(
        "Titan running. env=%s interval=%ds symbols=%s",
        settings.env, interval, settings.agent.symbols,
    )

    while True:
        try:
            alpaca_agent.tick()
        except Exception as exc:
            logger.exception("AlpacaMomentumAgent tick error: %s", exc)

        if poly_agent is not None:
            try:
                poly_agent.tick()
            except Exception as exc:
                logger.exception("PolymarketCopyAgent tick error: %s", exc)

        time.sleep(interval)
