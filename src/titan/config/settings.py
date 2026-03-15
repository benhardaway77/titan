from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field


class LiveSettings(BaseModel):
    enable_live: bool = Field(default=False, description="Hard gate for live trading")


class RiskSettings(BaseModel):
    max_drawdown_pct: float = Field(default=0.60, description="Hard stop at 60% drawdown")
    green_dd: float = 0.15
    yellow_dd: float = 0.40
    red_dd: float = 0.59
    crypto_max_leverage: float = 5.0


class DataSettings(BaseModel):
    equities_provider: str = Field(default="alpaca", description="alpaca|polygon")
    crypto_primary: str = Field(default="binance", description="binance|kraken")
    crypto_fallback: str = Field(default="coingecko")


class AlpacaSettings(BaseModel):
    """Alpaca credentials and endpoints, read from environment variables."""

    model_config = ConfigDict(populate_by_name=True)

    api_key: str = Field(default="", validation_alias="ALPACA_API_KEY")
    secret_key: str = Field(default="", validation_alias="ALPACA_SECRET_KEY")
    base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        validation_alias="ALPACA_BASE_URL",
    )

    def is_configured(self) -> bool:
        return bool(self.api_key and self.secret_key)


class AgentSettings(BaseModel):
    """Momentum agent configuration."""

    symbols: list[str] = Field(
        default=["SPY", "QQQ", "AAPL"],
        description="Tradeable symbols (equity tickers for Alpaca paper)",
    )
    fast_period: int = Field(default=10, description="Fast MA window in bars")
    slow_period: int = Field(default=30, description="Slow MA window in bars")
    bar_timeframe: str = Field(default="1Min", description="Alpaca bar timeframe")
    tick_interval_seconds: int = Field(default=60, description="Agent loop cadence in seconds")
    position_size_pct: float = Field(
        default=0.05,
        description="Fraction of equity per position (before leverage cap)",
    )
    allow_short: bool = Field(default=False, description="Allow short orders on EXIT signal")


class PolymarketSettings(BaseModel):
    """Polymarket credentials and copy-trade configuration."""

    model_config = ConfigDict(populate_by_name=True)

    private_key: str = Field(default="", validation_alias="POLY_PRIVATE_KEY")
    api_key: str = Field(default="", validation_alias="POLY_API_KEY")
    api_secret: str = Field(default="", validation_alias="POLY_API_SECRET")
    api_passphrase: str = Field(default="", validation_alias="POLY_API_PASSPHRASE")
    clob_url: str = "https://clob.polymarket.com"
    data_url: str = "https://data-api.polymarket.com"
    # Comma-separated wallet addresses in env var, split to list on load
    copy_addresses: list[str] = Field(
        default_factory=list,
        description="Wallet addresses to mirror (set via POLY_COPY_ADDRESSES=0xA,0xB)",
    )
    copy_size_pct: float = Field(
        default=0.03,
        description="Fraction of portfolio per copied Polymarket bet",
    )
    max_copy_odds: float = Field(
        default=0.85,
        description="Skip copying trades already priced above this probability",
    )
    macro_market_ids: list[str] = Field(
        default_factory=list,
        description="Polymarket condition IDs used as macro overlay for Alpaca sizing",
    )

    def is_trading_configured(self) -> bool:
        return bool(self.private_key and self.api_key and self.api_secret and self.api_passphrase)


class Settings(BaseModel):
    env: str = "paper"
    live: LiveSettings = LiveSettings()
    risk: RiskSettings = RiskSettings()
    data: DataSettings = DataSettings()
    alpaca: AlpacaSettings = AlpacaSettings()
    agent: AgentSettings = AgentSettings()
    polymarket: PolymarketSettings = PolymarketSettings()

    @staticmethod
    def load(env: str) -> "Settings":
        # Load .env files (no secrets committed; user supplies locally)
        root = Path(__file__).resolve().parents[3]
        load_dotenv(root / f".env.{env}")
        load_dotenv(root / ".env", override=False)

        # Parse comma-separated POLY_COPY_ADDRESSES into a list
        copy_addresses_raw = os.getenv("POLY_COPY_ADDRESSES", "")
        copy_addresses = [a.strip() for a in copy_addresses_raw.split(",") if a.strip()]

        settings = Settings(env=env)
        if copy_addresses:
            settings = settings.model_copy(
                update={"polymarket": settings.polymarket.model_copy(
                    update={"copy_addresses": copy_addresses}
                )}
            )
        return settings
