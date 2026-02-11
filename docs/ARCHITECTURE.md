# Titan Architecture (Scaffold)

Pipeline:
1) Data ingestion (provider adapters)
2) Feature generation (signals)
3) Strategy outputs order intents
4) Risk governor veto/resize
5) Portfolio allocator final sizing
6) Broker executes (paper or live)
7) Reporting + audit log

Key design: **order intent** is a pure data structure; execution is an adapter.
