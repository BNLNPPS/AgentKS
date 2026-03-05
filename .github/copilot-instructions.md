## Quick context for AI code agents

This repository is an agentic RAG knowledge-stack composed of multiple services wired by Docker Compose and Caddy. Key pieces:

- **Orchestration:** `docker-compose.yml` — services: `caddy`, `postgres`, `redis`, `authentik_*`, `openwebui`, `ollama`, `searxng`, `rag_mcp_service`, `basic_tools_mcp_service`, `hyperparam_advisor_mcp_service`, `backend`.
- **HTTP ingress & auth:** `Caddyfile` — Caddy uses `forward_auth` (Authentik proxy) and injects headers `X-Authentik-Email`, `X-Authentik-Name`, `X-Authentik-Groups` into every proxied request.
- **Agent API + Admin UI:** `backend/backend_app/` — two FastAPI apps run via `supervisord` (agent API on port 4000, admin UI on port 8000).
- **RAG service:** `backend/rag_mcp_service/` — FastMCP SSE server on port 5000 (retrieval) + FastAPI REST injector on port 5001 (ingestion).
- **Tools MCP:** `backend/basic_tools_mcp_service/` — FastMCP SSE server on port 5010.
- **Hyperparam MCP:** `backend/hyperparam_advisor_mcp_service/` — MCP stdio server on port 5020; calls `rag_mcp_service` over HTTP.

Read these files first for accurate context: `README.md`, `docker-compose.yml`, `Caddyfile`, `backend/backend_app/agents/main.py`, `backend/backend_app/admin/main.py`.

## Big-picture architecture

- **Caddy** is the public router. All paths (`/api*`, `/admin*`, `/webui*`, `/rag*`, `/hyperparam*`) are gated by `forward_auth` before being proxied to the appropriate backend container.
- **Authentication metadata is delivered via headers** — treat `X-Authentik-*` headers as the canonical identity source; never trust user-supplied identity data.
- **`DOMAIN`** is the single public domain. Authentik is served under the same domain (no separate `AUTH_DOMAIN`).
- **Persistence:** the `backend` services use PostgreSQL (via SQLAlchemy + Alembic). There is no in-memory-only storage in production code.

## Port reference

| Container | Port | Purpose |
|-----------|------|---------|
| `backend` | 4000 | Agent API (OpenAI-compatible `/v1/chat/completions`) |
| `backend` | 8000 | Admin UI |
| `rag_mcp_service` | 5000 | RAG MCP SSE (retrieval) |
| `rag_mcp_service` | 5001 | RAG Injector REST (ingestion) |
| `basic_tools_mcp_service` | 5010 | Tools MCP SSE |
| `hyperparam_advisor_mcp_service` | 5020 | Hyperparam MCP |
| `openwebui` | 8080 | Chat UI |
| `ollama` | 11434 | LLM inference |

## Developer workflows and useful commands

Bring up the full stack:

```bash
docker compose up --build
```

Run the backend locally (fast check):

```bash
cd backend/backend_app
docker build -t agentks-backend .
docker run --rm -p 4000:4000 -p 8000:8000 agentks-backend
```

Health check (simulate authenticated admin request):

```bash
curl -H "X-Authentik-Groups: admin" http://localhost:8000/admin/api/health
```

## Important code patterns and conventions

- **Header-based identity** — see `backend/backend_app/admin/main.py`:
  ```python
  groups = request.headers.get("X-Authentik-Groups", "")
  if "admin" not in groups.lower():
      raise HTTPException(status_code=403)
  ```

- **LangGraph agent flow** — `agents/agent_skill.py` orchestrates `rag_skill.py` (calls `rag_mcp_service:5000`) and `tools_skill.py` (calls registered MCP servers).

- **RAG group model** — documents belong to a named RAG group with a specific `embed_model`. Always specify `embed_model` when creating groups; it must match the model used at query time.

- **Template rendering** — Admin UI uses Jinja2 templates in `backend/backend_app/admin/templates/` and static assets in `backend/backend_app/admin/static/`.

- **Migrations** — run `alembic upgrade head` (via `startup.sh`) before starting services. Never modify DB schema outside of Alembic migrations.

## Where to make changes

| What | Where |
|------|-------|
| Agent logic / chat endpoint | `backend/backend_app/agents/main.py` |
| LangGraph orchestration | `backend/backend_app/agents/agent_skill.py` |
| RAG retrieval skill | `backend/backend_app/agents/rag_skill.py` |
| Tool execution skill | `backend/backend_app/agents/tools_skill.py` |
| Admin UI pages & API | `backend/backend_app/admin/main.py` + `templates/` + `static/` |
| RAG MCP (retrieval) | `backend/rag_mcp_service/rag_mcp.py` |
| RAG Injector (ingestion) | `backend/rag_mcp_service/rag_injector.py` |
| Tools MCP | `backend/basic_tools_mcp_service/main.py` |
| Hyperparam MCP | `backend/hyperparam_advisor_mcp_service/main.py` |
| HTTP routing & auth | `Caddyfile` |
| Service orchestration | `docker-compose.yml` |
