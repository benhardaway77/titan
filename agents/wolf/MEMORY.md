# Performance & State Memory

## Current State
- **Last run:** [Pending first execution]
- **Last run_id:** [YYYY-MM-DD_n8n001]
- **Active Bias:** Neutral (awaiting first signal)

## Trade Log
| Date | Market | Signal | Technical Score | Sentiment Score | Action | P&L |
|------|--------|--------|-----------------|-----------------|--------|-----|
| - | - | - | - | - | - | - |

## Sentiment History
| Date | Headline | Score | Logic | Source |
|------|----------|-------|-------|--------|
| - | - | - | - | - |

## n8n Workflow Versions
- **v1:** Daily Market Aggregation (EST) - 6:30 AM trigger
  - RSS feeds: Reuters, MarketWatch, CNBC, Investing.com, Seeking Alpha, Reddit (stocks/wsb)
  - Yahoo Finance: 60+ symbols
  - Deduplication: Workflow-scoped
  - Sentiment: Ollama llama3
  - Quality Gate: ≥5 news, ≥1 symbol

## Research Agent Connections
Wolf can escalate to research agents when findings warrant deeper analysis:
- **Trigger:** Unusual sentiment spikes, volume anomalies, or conflicting signals
- **Routing:** Mission Control → Research Agent → Wolf
- **Models:** Available Ollama models on Bbox

## Weekly PDF Reports
- **Destination:** `/mnt/user/appdata/clawdbot-quarantine/findings-report/`
- **Format:** PDF summary
- **Cadence:** Weekly (Sunday 23:59 EST)
- **Contents:**
  - Trade log
  - Sentiment trends
  - Technical patterns
  - n8n workflow changes
  - Next week thesis

## Directives
1. **Dual Confirmation:** Never trade without both technical + sentiment alignment
2. **Sentiment Floor:** 0.2 minimum for LONG positions
3. **Workflow Autonomy:** Build new n8n flows (max 5 without approval)
4. **Memory Efficiency:** Deduplicate headlines to save compute
5. **Research Escalation:** Connect to research agents when findings warrant robust analysis

---

*Update this file after each trade, sentiment run, or workflow change.*
