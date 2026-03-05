# Quick Start Guide

> ⚠️ Under active development — not production ready.

## Prerequisites

- Docker + Docker Compose v2
- A domain with DNS pointing to your server (or use `localhost` for dev)
- Ports 80 and 443 available (or 8080 if using the default compose mapping)

## 1. Clone & Configure

```bash
git clone https://github.com/BNLNPPS/AgentKS.git
cd AgentKS
cp .env.example .env
```

Edit `.env` and fill in the required values:

| Variable | Description |
|----------|-------------|
| `DOMAIN` | Your public domain (e.g. `example.com`) — also used for Authentik |
| `AUTHENTIK_SECRET_KEY` | Random 50+ char string |
| `AUTHENTIK_OUTPOST_TOKEN` | From Authentik admin after first setup |
| `AK_POSTGRES_PASSWORD` | Strong password for PostgreSQL |
| `AK_REDIS_PASSWORD` | Strong password for Redis |
| `AUTHENTIK_TAG` | Authentik image tag (e.g. `latest`) |

Optional (override LLM defaults):

```bash
OLLAMA_CHAT_MODEL=llama2:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
```

## 2. Start the Stack

```bash
docker compose up --build -d
```

This starts: Caddy, Postgres, Redis, Authentik, OpenWebUI, Ollama, SearXNG, backend, rag_mcp_service, basic_tools_mcp_service, hyperparam_advisor_mcp_service.

Check all services:
```bash
docker compose ps
docker compose logs -f
```

## 3. First-Run: Authentik Setup

1. Visit `https://auth.your-domain.com` and complete the Authentik initial setup wizard.
2. Create a **Proxy Provider** for your domain with the forward auth flow.
3. Create an **Outpost** and copy the token into `AUTHENTIK_OUTPOST_TOKEN` in `.env`.
4. Restart: `docker compose restart authentik_proxy caddy`

## 4. Run Migrations

```bash
docker compose exec backend alembic upgrade head
docker compose exec rag_mcp_service alembic upgrade head
```

## 5. Pull Ollama Models

```bash
docker compose exec ollama ollama pull llama2:7b
docker compose exec ollama ollama pull nomic-embed-text
```

## 6. Verify Services

```bash
# Agent API
curl http://localhost:4000/v1/models

# Admin UI (simulate auth header)
curl -H "X-Authentik-Groups: admin" http://localhost:8000/api/health

# RAG Injector
curl http://localhost:5001/health

# Basic Tools MCP
curl http://localhost:5010/health
```

## 7. Access

| URL | Service |
|-----|---------|
| `https://your-domain.com/webui` | OpenWebUI chat interface |
| `https://your-domain.com/admin` | Admin dashboard |
| `https://your-domain.com/rag/health` | RAG Injector health |
| `https://auth.your-domain.com` | Authentik admin |

## Backend-Only (Dev, No Caddy/Authentik)

```bash
# Start only the core services
docker compose up -d postgres ollama searxng rag_mcp_service basic_tools_mcp_service backend

# Inject a test document
curl -X POST http://localhost:5001/quick-inject \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello", "content": "This is a test document.", "rag_group": "kb_docs"}'

# Query the agent
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "rag-agent", "messages": [{"role": "user", "content": "What documents do you have?"}]}'
```

## Troubleshooting

```bash
# Postgres not ready
docker compose logs postgres
docker compose exec postgres pg_isready

# Migration failures
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head

# Backend services
docker compose exec backend supervisorctl status

# RAG not returning results
curl http://localhost:5001/admin/stats
curl http://localhost:5001/groups
```
