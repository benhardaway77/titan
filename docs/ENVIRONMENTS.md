# Environments: Paper → Live

## Philosophy
- Paper is the default: fast iteration, safe experimentation.
- Live is a controlled release: identical code paths with stricter gates.

## Gates
1) `TITAN_ENABLE_LIVE=true` required for any live order submission.
2) Risk governor always on. If drawdown >= 60% from HWM → stop.
3) Provider credentials must be present for selected env.

## Promotion
- develop → main merges require:
  - unit tests pass
  - backtest regression suite pass
  - risk governor tests pass
