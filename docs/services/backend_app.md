# Backend App

The `backend` Docker container hosts two FastAPI services and two background daemons,
all managed by `supervisord`.

| Process | Port | Source | Description |
|---------|------|--------|-------------|
| `admin` | 8000 | `admin/main.py` | Admin UI — RAG groups, MCPs, LLMs, URLs |
| `agents` | 4000 | `agents/main.py` | Agent API — OpenAI-compatible chat endpoint |
| `url_watcher` | — | `urls/daemons/url_watcher.py` | Background URL ingestion daemon |
| `tools_watcher` | — | `tools/daemons/watcher.py` | MCP tool auto-discovery daemon |

---

## Directory Layout

```
backend_app/
├── agents/                 # LangGraph agent — OpenAI-compatible API (:4000)
│   ├── main.py             # FastAPI app + /v1/chat/completions
│   ├── agent_skill.py      # LangGraph orchestrator (multi-skill)
│   ├── rag_skill.py        # RAG retrieval skill
│   ├── tools_skill.py      # Dynamic tool execution skill
│   └── llms.py             # LLM loader (DB config + Ollama fallback)
│
├── admin/                  # Admin dashboard (:8000)
│   ├── main.py             # FastAPI app, gated by X-Authentik-Groups header
│   ├── templates/          # Jinja2 templates (HTML pages)
│   └── static/             # CSS, JS assets
│
├── tools/                  # MCP tool integration
│   ├── __init__.py         # run_mcp_tool_async()
│   ├── tool_discovery.py   # Semantic + hybrid tool search
│   ├── models.py           # Tool data models
│   ├── client/             # MCP client utilities
│   └── daemons/
│       └── watcher.py      # Auto-discovery daemon
│
├── urls/                   # URL ingestion
│   └── daemons/
│       └── url_watcher.py  # Polls DB for URLs to ingest via RAG Injector
│
├── db/                     # SQLAlchemy models + session
├── migrations/             # Alembic migrations
├── supervisord.conf        # Runs admin + agents + url_watcher + tools_watcher
├── startup.sh              # Runs Alembic migrations then supervisord
├── Dockerfile
└── requirements.txt
```

---

## Agent API (port 4000)

OpenAI-compatible chat completions endpoint consumed by OpenWebUI.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/models` | List available models |
| `POST` | `/v1/chat/completions` | Chat completion (streaming supported) |

### LangGraph flow

```
/v1/chat/completions
       │
       ▼
  agent_skill.py   (LangGraph orchestrator)
  ├── rag_skill.py      → POST rag_mcp_service:5000  (document retrieval)
  └── tools_skill.py    → MCP tool execution via tools/__init__.py
```

The model is loaded from the database (admin-configured), falling back to Ollama defaults defined in `llms.py`.

---

## Admin UI (port 8000)

Web dashboard for managing the knowledge stack. All routes require the
`X-Authentik-Groups: admin` header (injected by Caddy forward_auth).

### Page Routes

| Path | Description |
|------|-------------|
| `GET /admin` | Dashboard home |
| `GET /admin/urls` | URL source list |
| `GET /admin/urls/add` | Add URL form |
| `POST /admin/urls/add` | Submit new URL |
| `POST /admin/urls/bulk` | Bulk URL import |
| `GET /admin/mcps` | MCP server list |
| `GET /admin/mcps/add` | Add MCP form |
| `POST /admin/mcps/add` | Register MCP server |
| `POST /admin/mcps/discover` | Trigger tool discovery |
| `GET /admin/rags` | RAG group list |
| `POST /admin/rags/bulk` | Bulk RAG group import |
| `GET /admin/llms` | LLM configuration list |
| `GET /admin/llms/add` | Add LLM form |
| `POST /admin/llms/add` | Register LLM |
| `POST /admin/llms/{id}/set-default` | Set default LLM |
| `POST /admin/llms/{id}/toggle` | Enable/disable LLM |

### API Routes (JSON)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/api/health` | Health check |
| `GET` | `/admin/api/users` | List authenticated users |
| `POST` | `/api/tools-skill/query` | Run tools skill directly |
| `GET` | `/api/tools-skill/test` | Tools skill smoke test |
| `POST` | `/api/rag-skill/ask` | Run RAG skill directly |
| `GET` | `/api/rag-skill/test` | RAG skill smoke test |

### Identity / Auth

The admin UI reads identity from Authentik headers injected by Caddy:

```python
groups = request.headers.get("X-Authentik-Groups", "")
if "admin" not in groups.lower():
    raise HTTPException(status_code=403)
```

---

## Background Daemons

### `url_watcher`

Polls the database for pending URL sources and submits their content to the
RAG Injector (`rag_mcp_service:5001`) for chunking and embedding.

### `tools_watcher`

Periodically queries registered MCP servers, discovers available tools, and
updates the tool registry used by `tools_skill.py` for semantic matching.

---

## Configuration

Key environment variables (set in `docker-compose.yml` or `.env`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `OLLAMA_BASE_URL` | Ollama API base URL (default: `http://ollama:11434`) |
| `OLLAMA_CHAT_MODEL` | Fallback chat model |
| `OLLAMA_EMBED_MODEL` | Fallback embedding model |

---

## See Also

- [`rag/rag_mcp.md`](rag/rag_mcp.md) — retrieval MCP (port 5000)
- [`rag/rag_injector.md`](rag/rag_injector.md) — injection REST API (port 5001)
- [`agents/rag_skill.md`](agents/rag_skill.md) — RAG skill detail
- [`../architecture/CADDY_ROUTING.md`](../architecture/CADDY_ROUTING.md) — how traffic reaches this container
