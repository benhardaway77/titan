"""Alpaca bar fetcher — wraps alpaca-py REST for OHLCV data.

The fetcher is the *only* module that imports alpaca-py's data client.
All other modules receive plain ``dict[str, pd.DataFrame]`` — no alpaca-py
types leak beyond this file, keeping the signal and agent layers mockable.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from titan.config.settings import AlpacaSettings

logger = logging.getLogger(__name__)


def _resolve_timeframe(timeframe_str: str) -> TimeFrame:
    mapping = {
        "1Min": TimeFrame(1, TimeFrameUnit.Minute),
        "5Min": TimeFrame(5, TimeFrameUnit.Minute),
        "15Min": TimeFrame(15, TimeFrameUnit.Minute),
        "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
        "1Day": TimeFrame(1, TimeFrameUnit.Day),
    }
    return mapping.get(timeframe_str, TimeFrame(1, TimeFrameUnit.Minute))


class AlpacaBarFetcher:
    """Fetches OHLCV bars for a list of symbols from Alpaca.

    Returns a dict of symbol -> DataFrame(open, high, low, close, volume),
    indexed by UTC timestamp, sorted ascending.
    """

    def __init__(self, settings: AlpacaSettings, timeframe_str: str = "1Min") -> None:
        self._client = StockHistoricalDataClient(
            api_key=settings.api_key,
            secret_key=settings.secret_key,
        )
        self._timeframe = _resolve_timeframe(timeframe_str)

    def fetch_bars(self, symbols: list[str], lookback_bars: int) -> dict[str, pd.DataFrame]:
        """Return up to `lookback_bars` bars per symbol.

        Fetches a window of (lookback_bars * 2) minutes from now to ensure
        enough data is returned even accounting for market closures / gaps.
        Returns an empty dict entry for any symbol with no data.
        """
        now = datetime.now(timezone.utc)
        # Generous lookback window: 2x bars + 1 day padding for weekends
        lookback_minutes = lookback_bars * 2 + 1440
        start = now - timedelta(minutes=lookback_minutes)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=self._timeframe,
                start=start,
                end=now,
                limit=lookback_bars,
            )
            bars_resp = self._client.get_stock_bars(request)
        except Exception as exc:
            logger.error("Alpaca bar fetch failed: %s", exc)
            return {}

        result: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            try:
                df = bars_resp.df.loc[symbol].copy() if symbol in bars_resp.df.index else pd.DataFrame()
                if df.empty:
                    logger.debug("No bars returned for %s", symbol)
                    result[symbol] = df
                    continue
                df = df[["open", "high", "low", "close", "volume"]].sort_index()
                # Trim to the requested lookback
                result[symbol] = df.iloc[-lookback_bars:]
            except Exception as exc:
                logger.warning("Error processing bars for %s: %s", symbol, exc)
                result[symbol] = pd.DataFrame()

        return result


def build_fetcher(settings: AlpacaSettings, timeframe_str: str = "1Min") -> AlpacaBarFetcher:
    """Factory — raises ValueError if credentials are not set."""
    if not settings.is_configured():
        raise ValueError(
            "Alpaca credentials not configured. "
            "Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env.paper"
        )
    return AlpacaBarFetcher(settings, timeframe_str=timeframe_str)
