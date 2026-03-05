# Repository Structure

> ⚠️ Under active development — not production ready.

## Directory Layout

```
AgentKS/
├── docs/                                    # Documentation
│   ├── INDEX.md                             # Documentation index
│   ├── architecture/                        # Architecture docs
│   │   ├── STRUCTURE.md                     # This file
│   │   ├── CADDY_ROUTING.md                 # Caddy ingress & path rewriting
│   │   └── AGENT_FLOW.md                    # LangGraph agent execution flow
│   ├── services/                            # Per-service docs
│   │   ├── backend_app.md
│   │   ├── rag/
│   │   │   ├── rag_mcp.md
│   │   │   └── rag_injector.md
│   │   ├── mcp_services/
│   │   │   ├── basic_tools.md
│   │   │   └── hyperparam_advisor.md
│   │   └── agents/
│   │       └── rag_skill.md
│   └── guides/
│       ├── quick_start.md
│       └── llm_management.md
│
├── backend/                                 # All backend services
│   ├── backend_app/                         # Main application container
│   │   ├── agents/                          # LangGraph agent API (:4000)
│   │   │   ├── main.py                      # FastAPI + /v1/chat/completions
│   │   │   ├── agent_skill.py               # LangGraph orchestrator
│   │   │   ├── rag_skill.py                 # RAG retrieval skill
│   │   │   ├── tools_skill.py               # Dynamic tool execution skill
│   │   │   └── llms.py                      # LLM loader (DB config + Ollama)
│   │   ├── admin/                           # Admin UI (:8000)
│   │   │   ├── main.py                      # FastAPI admin app
│   │   │   ├── templates/                   # Jinja2 templates
│   │   │   └── static/                      # CSS, JS
│   │   ├── tools/                           # MCP tool integration
│   │   │   ├── __init__.py                  # run_mcp_tool_async()
│   │   │   ├── tool_discovery.py            # Semantic tool search
│   │   │   └── models.py
│   │   ├── urls/                            # URL ingestion daemons
│   │   ├── db/                              # SQLAlchemy models + session
│   │   ├── migrations/                      # Alembic migrations
│   │   ├── supervisord.conf                 # Runs agents + admin
│   │   ├── startup.sh                       # Runs migrations then supervisord
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── rag_mcp_service/                     # RAG MCP + Injector container
│   │   ├── rag_mcp.py                       # FastMCP SSE server (:5000)
│   │   ├── rag_injector.py                  # FastAPI REST injector (:5001)
│   │   ├── rag_common.py                    # Shared LangChain/PGVector helpers
│   │   ├── url_discovery.py                 # URL-to-document ingestion
│   │   ├── db/                              # DB layer (groups + documents)
│   │   ├── migrations/                      # Alembic migrations
│   │   ├── supervisord.conf                 # Runs rag_mcp + rag_injector
│   │   └── Dockerfile
│   │
│   ├── basic_tools_mcp_service/             # Search tools MCP container (:5010)
│   │   ├── main.py                          # FastMCP SSE server
│   │   ├── hep.py                           # INSPIRE/CDS/arXiv HEP tools
│   │   └── Dockerfile
│   │
│   ├── hyperparam_advisor_mcp_service/      # Hyperparameter MCP container (:5020)
│   │   ├── main.py                          # MCP stdio entry point
│   │   ├── rag_mcp.py                       # FastMCP tool definitions
│   │   ├── rag_common.py                    # HTTP client -> rag_mcp_service
│   │   ├── hyperparam_skill.py              # Optimisation logic
│   │   └── Dockerfile
│   │
│   ├── searxng/                             # SearXNG configuration
│   └── docker-compose.local.yml             # Backend-only compose
│
├── docker-compose.yml                       # Full stack orchestration
├── Caddyfile                                # HTTP ingress & auth routing
├── .env.example                             # Environment variable template
├── Makefile                                 # Build/run shortcuts
├── README.md                                # Project overview
└── REFACTORING_SUMMARY.md                   # Migration history
```

---

## Service Map

### Infrastructure

| Container | Image | Port(s) | Purpose |
|-----------|-------|---------|---------|
| `caddy` | `caddy:2.8` | 80, 443 | Reverse proxy, TLS, forward_auth |
| `postgres` | `pgvector/pgvector:pg16` | 5433 (host) | PostgreSQL + pgvector |
| `redis` | `redis:7-alpine` | — | Cache for Authentik |
| `authentik_server` | `goauthentik/server` | 9000 | SSO server |
| `authentik_worker` | `goauthentik/server` | — | Background worker |
| `authentik_proxy` | `goauthentik/proxy` | 9000 | Forward auth proxy |
| `ollama` | `ollama/ollama` | 11434 | LLM inference |
| `searxng` | `searxng/searxng` | 8081 | Meta search engine |

### Application

| Container | Directory | Port(s) | Description |
|-----------|-----------|---------|-------------|
| `openwebui` | Docker image | 8080 | Chat UI (Authentik SSO + PostgreSQL) |
| `backend` | `backend/backend_app/` | 8000, 4000 | Admin UI + Agent API |
| `rag_mcp_service` | `backend/rag_mcp_service/` | 5000, 5001 | RAG MCP (SSE) + Injector (REST) |
| `basic_tools_mcp_service` | `backend/basic_tools_mcp_service/` | 5010 | Search tools MCP (SSE) |
| `hyperparam_advisor_mcp_service` | `backend/hyperparam_advisor_mcp_service/` | 5020 | Hyperparameter MCP |

---

## Port Reference

| Port | Container | Access | Transport | Purpose |
|------|-----------|--------|-----------|---------|
| 80 / 443 | `caddy` | Public | HTTP/HTTPS | Reverse proxy + TLS |
| 4000 | `backend` | Via Caddy `/api` | HTTP | Agent API (OpenAI-compatible) |
| 5000 | `rag_mcp_service` | Internal | SSE | RAG MCP — document retrieval |
| 5001 | `rag_mcp_service` | Internal | HTTP REST | RAG Injector — document ingestion |
| 5010 | `basic_tools_mcp_service` | Internal | SSE | Search tools MCP |
| 5020 | `hyperparam_advisor_mcp_service` | Internal | stdio | Hyperparameter MCP |
| 8000 | `backend` | Via Caddy `/admin` | HTTP | Admin UI |
| 8080 | `openwebui` | Via Caddy `/webui` | HTTP | Chat interface |
| 9000 | `authentik_*` | Internal | HTTP | Authentik SSO |
| 11434 | `ollama` | Internal | HTTP | LLM inference |

---

## Architecture Diagram

```
+------------------------------------------------+
|              CADDY  :80 / :443                 |
|   forward_auth -> authentik_proxy:9000         |
+---+----------+----------+----------+-----------+
    | /webui   | /api     | /admin   | /rag
    v          v          v          v
openwebui  backend    backend   rag_mcp_service
  :8080      :4000      :8000       :5001
               |
     +---------+------------------+
     v         v                  v
 RAG MCP   Tools MCP      Hyperparam MCP
  :5000      :5010              :5020
     |
  postgres:5432
  ollama:11434
```

---

## Internal Docker Network DNS

```
postgres:5432                           — PostgreSQL + pgvector
redis:6379                              — Redis cache
authentik_server:9000                   — Authentik SSO
authentik_proxy:9000                    — Forward auth proxy
openwebui:8080                          — Chat UI
backend:4000                            — Agent API
backend:8000                            — Admin UI
rag_mcp_service:5000                    — RAG MCP SSE
rag_mcp_service:5001                    — RAG Injector REST
basic_tools_mcp_service:5010            — Tools MCP SSE
hyperparam_advisor_mcp_service:5020     — Hyperparam MCP
ollama:11434                            — LLM inference
searxng:8080                            — Meta search engine
```
