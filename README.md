# Titan — Paper-First Trading System

Titan is a paper-first → live trading scaffold that runs two agents in tandem:

1. **AlpacaMomentumAgent** — MA crossover momentum on equity markets via Alpaca paper/live trading
2. **PolymarketCopyAgent** — Mirror high-signal Polymarket wallets in real-time

Both agents share a single `RiskGovernor` and `PortfolioState`, so one global drawdown gate protects the entire portfolio across all venues.

---

## Architecture

```
titan run
     │
     ├── AlpacaMomentumAgent.tick()
     │       AlpacaBarFetcher       → Alpaca REST OHLCV bars
     │       MACrossoverSignal      → fast/slow MA crossover per symbol
     │       PolymarketOddsSignal   → macro overlay (scales position size)
     │       RiskGovernor           → 5-zone drawdown gate + leverage cap
     │       PortfolioState         → equity, HWM, open positions
     │       AlpacaBroker           → submit/close equity orders
     │       TickReporter           → rich console output per tick
     │
     └── PolymarketCopyAgent.tick()
             PolymarketDataClient   → public Data API (no auth)
             CopyTradeSignal        → polls watched wallets, emits new trades
             RiskGovernor           → shared global risk gate
             PortfolioState         → shared state
             PolymarketBroker       → py-clob-client order submission
             TickReporter           → rich console output per tick
```

---

## Risk Governor — 5 Zones

| Zone | Drawdown | New Trades | Leverage Cap |
|---|---|---|---|
| `green` | < 15% | Yes | full |
| `yellow` | 15–40% | Yes | ≤ 2× |
| `red` | 40–59% | Yes | 1× |
| `critical` | 59–60% | No | 0 |
| `dead` | ≥ 60% | No | 0 (kill-switch) |

Hard stop at **−60% drawdown from high-water mark**.

---

## Quick Start

```bash
# 1. Create a virtual environment and install
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Copy env template and fill in credentials
cp .env.paper.example .env.paper
# Edit .env.paper with your Alpaca + Polymarket keys

# 3. Check your promotion gate passes (no API keys needed)
titan promote

# 4. Run in paper mode
titan run --env paper
```

---

## Configuration

All settings are driven by environment variables (`.env.paper` or `.env.live`).

### Alpaca (equity trading)

| Variable | Default | Description |
|---|---|---|
| `ALPACA_API_KEY` | — | Paper/live API key |
| `ALPACA_SECRET_KEY` | — | Paper/live secret |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Switch to live URL for live env |
| `TITAN_AGENT_SYMBOLS` | `SPY,QQQ,AAPL` | Comma-separated symbol list |
| `TITAN_AGENT_FAST_PERIOD` | `10` | Fast MA period (bars) |
| `TITAN_AGENT_SLOW_PERIOD` | `30` | Slow MA period (bars) |
| `TITAN_AGENT_TICK_INTERVAL_SECONDS` | `60` | Seconds between ticks |
| `TITAN_AGENT_POSITION_SIZE_PCT` | `0.05` | Fraction of equity per position |

### Polymarket (prediction market trading + copy trades)

| Variable | Default | Description |
|---|---|---|
| `POLY_PRIVATE_KEY` | — | Wallet private key (EIP-712 signing) |
| `POLY_API_KEY` | — | L2 API key (from py-clob-client or Polymarket UI) |
| `POLY_API_SECRET` | — | L2 API secret |
| `POLY_API_PASSPHRASE` | — | L2 API passphrase |
| `POLY_COPY_ADDRESSES` | — | Comma-separated wallet addresses to mirror |
| `POLY_MACRO_MARKET_IDS` | — | Condition IDs for macro overlay (scales Alpaca sizes) |

> Polymarket trading is optional. The Alpaca agent runs standalone without any Polymarket credentials.

---

## Strategy Details

### MA Crossover (Alpaca)

- Stateful per-symbol direction tracker — only fires on direction *change*, preventing re-entry signals
- `LONG` when `fast_ma > slow_ma`, `EXIT` when reversed (1-bar lag to avoid look-ahead bias)
- Position size = `equity × position_size_pct × odds_multiplier × leverage_cap`

### Macro Overlay (Polymarket → Alpaca)

- Fetches configured `POLY_MACRO_MARKET_IDS` probability prices
- Returns a multiplier applied to Alpaca position sizes:
  - ≥ 80% probability → 0.25× (risk-off)
  - ≥ 60% → 0.50×
  - ≥ 30% → 0.75×
  - otherwise → 1.0× (no effect)

### Copy Trading (Polymarket)

- Polls `data-api.polymarket.com/trades` per watched address every tick
- First poll establishes a baseline (no trades emitted) to avoid replaying history on startup
- Skips trades at price > `max_copy_odds` (default 0.85) — avoids crowded probability positions
- Size = `equity × copy_size_pct`

---

## Promotion Gate

`titan promote` runs three checks before paper → live:

1. **Live gate** — `enable_live=true` in live settings
2. **Unit tests** — full `pytest` suite must pass (currently 78 tests)
3. **Backtest regression** — `MomentumMABacktest` (synthetic, seeded RNG, no API keys):
   - Sharpe ratio ≥ 0.5
   - Max drawdown ≤ 30%
   - Positive total return

```
$ titan promote
[PASS] Live gate check
[PASS] Unit tests (78 passed)
[PASS] Backtest: momentum_ma_crossover
       return=+14.3%  max_dd=11.2%  sharpe=1.84  trades=47
All promotion checks passed.
```

---

## Project Layout

```
titan/
├── src/titan/
│   ├── agent.py                   # AlpacaMomentumAgent, PolymarketCopyAgent, run_agents()
│   ├── cli.py                     # `titan run` and `titan promote` commands
│   ├── promote.py                 # Promotion check runner
│   ├── config/
│   │   └── settings.py            # AlpacaSettings, AgentSettings, PolymarketSettings, Settings
│   ├── risk/
│   │   └── governor.py            # RiskGovernor — 5-zone drawdown system
│   ├── portfolio/
│   │   └── state.py               # PortfolioState, Position, target_qty sizing
│   ├── data/
│   │   ├── alpaca_bars.py         # AlpacaBarFetcher — OHLCV bars from Alpaca REST
│   │   └── polymarket_data.py     # PolymarketDataClient — public Data API (no auth)
│   ├── signals/
│   │   ├── ma_crossover.py        # MACrossoverSignal — stateful per-symbol crossover
│   │   ├── polymarket_odds.py     # PolymarketOddsSignal — macro sizing multiplier
│   │   └── copy_trade.py          # CopyTradeSignal — wallet polling + dedup
│   ├── brokers/
│   │   ├── alpaca_broker.py       # AlpacaBroker — alpaca-py TradingClient wrapper
│   │   └── polymarket_broker.py   # PolymarketBroker — py-clob-client wrapper (Polygon)
│   ├── reporting/
│   │   └── tick_reporter.py       # TickReporter — rich console per-tick output
│   └── backtest/
│       ├── runner.py              # BacktestRunner base, @register decorator, promotion gate
│       └── momentum_backtest.py   # MomentumMABacktest — synthetic seeded price series
├── tests/                         # 78 unit tests (all pass without API keys)
├── docs/                          # Design notes
├── .env.paper.example             # Environment variable template
├── Dockerfile                     # python:3.14-slim
└── pyproject.toml                 # alpaca-py, py-clob-client, pydantic v2, ruff, mypy
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `alpaca-py>=0.26` | Alpaca data + trading v2 REST SDK |
| `py-clob-client>=0.7` | Polymarket CLOB API (order placement) |
| `pydantic>=2.6` | Settings validation + env var parsing |
| `pandas>=2.2` | Price series and bar data |
| `numpy>=1.26` | MA computation + backtest engine |
| `rich>=13.7` | Console tick output |
| `typer>=0.12` | CLI (`titan run`, `titan promote`) |
| `requests>=2.31` | Polymarket public Data API |

---

## Development

```bash
# Run all tests
pytest tests/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Full promotion gate (what CI runs)
titan promote
```

---

## Environments

| Env | Purpose |
|---|---|
| `paper` | Research + paper execution. Safe for any API key (no real money). |
| `live` | Real money. Requires `enable_live=true` AND passing `titan promote`. |

Live trading is intentionally double-gated: the `enable_live` flag must be set explicitly AND `titan promote` must pass. There is no auto-promote.
