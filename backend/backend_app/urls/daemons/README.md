# URL Watcher Daemon

Background daemon that monitors the `source_urls` / `discovered_urls` tables
and automatically ingests web content into the RAG knowledge base via the
RAG Injector API.

Runs as the `url_watcher` process under `supervisord` in the `backend` container.

---

## Files

```
urls/daemons/
├── url_watcher.py    # Main daemon loop
├── url_discovery.py  # URL crawling / link discovery helpers
└── README.md         # This file
```

---

## Workflow

```
Admin registers a source URL via Admin UI
              ↓
       [source_urls table]
         status='queued'
              ↓
    url_watcher: Step 1 — Discovery
    Crawl source URL, find child links
              ↓
      [discovered_urls table]
         status='queued'
              ↓
    url_watcher: Step 2 — Ingestion
    Fetch content → POST /quick-inject
              ↓
    rag_mcp_service:5001
    (chunk + embed + store in PGVector)
              ↓
      [discovered_urls table]
         status='ingested'
              ↓
    url_watcher: Step 3 — Staleness check
    Periodically re-fetch ingested URLs;
    schedule 'refresh' if content changed
```

---

## Loop Steps

Each iteration of the daemon loop runs three stages in order:

| Step | Table | Action |
|------|-------|--------|
| 1 — Discovery | `source_urls` (status=`queued`) | Crawl source, create `discovered_urls` rows |
| 2 — Ingestion | `discovered_urls` (status=`queued`\|`refresh`) | Fetch content, call RAG Injector `/quick-inject` |
| 3 — Staleness | `discovered_urls` (status=`ingested`, stale) | Re-fetch, schedule `refresh` if hash changed |

Step 3 only runs when steps 1 and 2 produce no work (idle).

---

## Configuration

All settings are read from environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_INJECTOR_URL` | `http://rag_mcp_service:5001` | RAG Injector base URL |
| `SLEEP_SECONDS` | `5` | Idle poll interval (seconds) |
| `BATCH_SIZE` | `10` | URLs processed per loop iteration |
| `CHECK_INTERVAL_SECONDS` | `3600` | Staleness check interval (seconds) |
| `STALE_AFTER_SECONDS` | `21600` | Age before an ingested URL is re-checked (seconds) |
| `DEFAULT_RAG_GROUP` | `web_content` | RAG group for ingested documents |
| `DEFAULT_EMBED_MODEL` | `nomic-embed-text` | Ollama embedding model |
| `CHUNK_SIZE` | `1000` | Text chunk size (tokens) |
| `CHUNK_OVERLAP` | `200` | Chunk overlap (tokens) |
| `FETCH_TIMEOUT_SECONDS` | `30` | HTTP fetch timeout |
| `DATABASE_URL` | — | PostgreSQL connection string (required) |

---

## RAG Injector Integration

The daemon calls the RAG Injector REST API (port 5001) — it has no direct
LangChain or vector-store dependency.

| Operation | Endpoint | Description |
|-----------|----------|-------------|
| Ingest document | `POST /quick-inject` | Create group if needed, chunk, embed, store |
| Delete old docs | `DELETE /documents/by-url/{url_id}` | Used before re-ingesting on `refresh` |

---

## Running Manually

```bash
# From inside the backend container or backend_app directory:
cd backend/backend_app
python -m urls.daemons.url_watcher
```

The daemon is already started automatically by `supervisord` as the
`url_watcher` program — no manual start needed in production.

---

## See Also

- [`rag_injector.md`](../../../../docs/services/rag/rag_injector.md) — RAG Injector API reference
- [`tools/README.md`](../../tools/README.md) — MCP tools watcher (separate daemon)
