from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field


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


class Settings(BaseModel):
    env: str = "paper"
    live: LiveSettings = LiveSettings()
    risk: RiskSettings = RiskSettings()
    data: DataSettings = DataSettings()

    @staticmethod
    def load(env: str) -> "Settings":
        # Load .env files (no secrets committed; user supplies locally)
        root = Path(__file__).resolve().parents[3]
        load_dotenv(root / f".env.{env}")
        load_dotenv(root / ".env", override=False)
        return Settings(env=env)
