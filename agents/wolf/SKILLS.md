# Agent Skills

## Market Data
- **Source:** CCXT library for OHLCV data
- **Coverage:** Crypto exchanges (Binance, Coinbase, Kraken, etc.)
- **Timeframes:** 1m, 5m, 15m, 1h, 4h, 1d
- **Indicators:** RSI, MACD, Bollinger Bands, EMA/SMA

## Sentiment Logic
- **Pipeline:** n8n workflow with Ollama integration
- **Model:** llama3 or mistral (local on Bbox)
- **Input:** RSS headlines (Reuters, MarketWatch, CNBC, Seeking Alpha, Reddit)
- **Output:** JSON `{ score: -1.0 to 1.0, logic: "1-sentence explanation" }`
- **Threshold:** 0.2 minimum for LONG signals

## Memory
- **Deduplication:** n8n workflow-scoped memory
- **Key:** `{{ $json.link || $json.guid }}` (RSS feed identifiers)
- **Persistence:** Across daily cron runs (6:30 AM EST)
- **Purpose:** Avoid re-analyzing same headlines, save compute

## Technical Analysis
- **Library:** Python (pandas, ta-lib, ccxt)
- **Execution:** Titan trade engine
- **Validation:** Dual confirmation (technical + sentiment)

## Workflow Creation
- **Autonomy:** Can create new n8n flows for market discovery
- **Limit:** 5 new implementations without approval
- **Scope:** RSS feeds, API integrations, data transformations

## Ollama Models (Bbox)
- Available: llama3, mistral, qwen3.5:cloud
- Endpoint: `http://host.docker.internal:11434`
- Usage: Sentiment analysis, research queries, trade justification
