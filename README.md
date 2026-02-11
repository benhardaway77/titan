# Titan

Paper-first → Live trading system scaffold for the Titan simulation.

## Goals
- Paper environment for continuous improvement (signals/strategies/data)
- Live environment gated by explicit promotion checks
- Shared codebase: only config + credentials differ between paper/live

## Core safety constraints
- Portfolio hard stop: **-60% drawdown from high-water mark** triggers kill-switch / stop-new-trades.
- Max leverage (crypto): **5x** (risk governor may force lower)

## Layout
- `src/titan/` core library
- `tests/` unit tests (risk governor + sizing + adapters)
- `docs/` design notes

## Quick start (dev)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

# Paper run (no live orders)
titan run --env paper
```

## Environments
- `paper`: research + paper execution only
- `live`: requires explicit enable flag + credentials present

