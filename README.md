# AgentKS — Agentic RAG Knowledge Stack

> **⚠️ DEVELOPMENT STATUS**  
> This system is currently under active development and bug fixes.  
> This is a **DRAFT VERSION** - features, APIs, and configurations may change without notice.  
> Not recommended for production use at this time.

AgentKS is an agentic RAG (Retrieval-Augmented Generation) knowledge stack under active development, orchestrated with Docker Compose and featuring LangGraph-based multi-skill agent execution, MCP (Model Context Protocol) services, and enterprise authentication. **Not production-ready.**

## 🎯 Key Features

- **🤖 LangGraph Agent** - Multi-skill execution with intelligent routing (RAG + Tools + Synthesis)
- **📚 RAG System** - Vector search with pgvector, document management via MCP
- **🔧 Dynamic Tools** - Semantic tool discovery, auto-registration via mcp_watcher
- **🔐 Enterprise Auth** - Authentik SSO with forward_auth pattern
- **🌐 Reverse Proxy** - Caddy with automatic HTTPS
- **💬 Chat Interface** - OpenWebUI for user interactions
- **🔍 Multi-Source Search** - arXiv, CDS, INSPIRE-HEP, SearXNG integration
- **📊 Admin Dashboard** - Web UI for system management

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CADDY (Reverse Proxy)                    │
│              80/443 - TLS + Forward Auth                    │
└────┬─────────────────┬────────────────--────────────────────┘
     │                 │                
     │ /webui          │ /admin
     ↓                 ↓
┌──────────┐    ┌──────────┐
│OpenWebUI │    │Admin UI  │
│  :8080   │    │  :8000   │
└────┬─────┘    └────┬─────┘
     │               │               
     │               |
     │               │
     │   ┌───────────▼─────────────────────────┐
     │   │   Agent Backend (:4000)             │
     │   │  ┌───────────────────────────────┐  │
     │   │  │  LangGraph Agent              │  │
     │   │  │  - agent_skill.py (routing)   │  │
     │   │  │  - rag_skill.py (retrieval)   │  │
     │   │  │  - tools_skill.py (tools)     │  │
     │   │  └───────────────────────────────┘  │
     │   └─────┬──────────────────┬────────────┘
     │         │                  │
     │    ┌────▼─────┐      ┌────-▼──────────┐
     │    │ RAG MCP  │      │  Tools MCP     │
     │    │  :5000   │      │   :5010        │
     │    │          │      │  - arXiv       │
     │    │PGVector  │      │  - CDS         │
     │    │Search    │      │  - INSPIRE     │
     │    └──────────┘      │  - SearXNG     │
     │                      └────────────────┘
     │                      ┌────────────────┐
     │                      │ Hyperparam MCP │
     │                      │   :5020        │
     │                      │  - RAG-based   │
     │                      │  - Optimization│
     │                      └────────────────┘
     │
     │    ┌─────────────┐   ┌──────────┐   ┌──────────┐
     └────│ Authentik   │   │ Postgres │   │  Ollama  │
          │  (SSO)      │   │(pgvector)│   │  :11434  │
          └─────────────┘   └──────────┘   └──────────┘
```

## 📁 Repository Structure

```
AgentKS/
├── docs/                       # Documentation (see docs/INDEX.md)
│   ├── INDEX.md               # Documentation index
│   ├── architecture/          # Architecture documentation
│   ├── services/              # Service-specific docs
│   ├── guides/                # How-to guides
│   └── api/                   # API references
│
├── backend/                    # Backend services
│   ├── backend_app/           # Main application
│   │   ├── agents/            # Agent backend (:4000)
│   │   ├── admin/             # Admin UI (:8000)
│   │   ├── rag/               # RAG services (now in rag_mcp_service)
│   │   ├── tools/             # MCP tool integration
│   │   ├── migrations/        # Alembic DB migrations
│   │   └── supervisord.conf   # Multi-service orchestration
│   │
│   ├── basic_tools_mcp_service/      # Search tools MCP (:5010)
│   ├── hyperparam_advisor_mcp_service/ # Hyperparameter optimization MCP (:5020)
│   ├── rag_mcp_service/              # RAG MCP + Injector (:5000, :5001)
│   └── searxng/               # SearXNG configuration
│
├── docker-compose.yml         # Full stack orchestration
├── Caddyfile                  # HTTP routing & auth
├── .env.example               # Environment template
└── README.md                  # This file
```

**See [`docs/INDEX.md`](docs/INDEX.md) for complete documentation index and [`docs/architecture/STRUCTURE.md`](docs/architecture/STRUCTURE.md) for directory tree**

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- `.env` file (copy from `.env.example` and configure)

### Start Full Stack

```bash
# Clone repository
git clone https://github.com/BNLNPPS/AgentKS.git
cd AgentKS

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start all services
docker compose up --build -d

# View logs
docker compose logs -f

# Check status
docker compose ps
```

### Access Services

- **OpenWebUI**: http://localhost/webui (Chat interface, authenticated via Authentik)
- **Agent API**: http://localhost/api (OpenAI-compatible API, used by OpenWebUI)
- **Admin Dashboard**: http://localhost/admin (System management, requires admin group)
- **Hyperparameter Advisor**: http://localhost/hyperparam (AI-powered optimization suggestions)
- **Authentik**: http://localhost:9000 (Authentication admin)

**Authentication Flow:**
1. All requests go through Caddy reverse proxy
2. Caddy uses forward_auth to Authentik for authentication
3. Authentik validates session and injects identity headers
4. OpenWebUI trusts `X-Authentik-Email`, `X-Authentik-Name`, `X-Authentik-Groups` headers
5. Users are automatically logged into OpenWebUI with their Authentik identity
6. OpenWebUI calls the Agent API at `/api/v1/*` for chat completions

### Backend-Only Development

For faster backend iteration without full stack:

```bash
cd backend
docker compose -f docker-compose.local.yml up --build
```

This starts: Backend + Postgres + Ollama + SearXNG (no Caddy/Authentik)

**Direct Access:**
- Admin UI: http://localhost:8000/admin
- Agent API: http://localhost:4000/v1/models
- RAG Injector: http://localhost:5001/health

## 🤖 Agent Capabilities

### Multi-Skill Execution Patterns

The LangGraph-based agent supports 5 execution patterns:

1. **Calculator** - Direct math evaluation (fast path)
   ```
   Query: "12 * (3 + 4)"
   Flow:  analyze → calculator → answer
   ```

2. **RAG Only** - Knowledge base search
   ```
   Query: "What do you know about quantum computing?"
   Flow:  analyze → rag_skill → answer
   ```

3. **Tools Only** - External API/search
   ```
   Query: "Search arXiv for transformer papers"
   Flow:  analyze → tools_skill → answer
   ```

4. **RAG + Tools** - Multi-skill with synthesis ⭐
   ```
   Query: "Compare our research with recent arXiv papers"
   Flow:  analyze → rag_skill → tools_skill → synthesize → answer
   ```

5. **Direct** - Conversational response
   ```
   Query: "Hello, how are you?"
   Flow:  analyze → direct → answer
   ```

**See [`docs/architecture/AGENT_FLOW.md`](docs/architecture/AGENT_FLOW.md) for detailed architecture**

### Available Tools (via MCP)

- **arXiv Search** - Scientific paper search
- **CDS Search** - CERN Document Server
- **INSPIRE-HEP** - High energy physics literature
- **SearXNG** - Meta search engine (web)
- **Calculator** - Math expression evaluation
- **RAG Search** - Internal knowledge base
- **Hyperparameter Advisor** - ML hyperparameter optimization suggestions based on historical results

Tools are auto-discovered and dynamically bound to the LLM based on semantic relevance.

## 🔌 API Endpoints

### Agent Backend (port 4000, exposed as /api)

**OpenAI-Compatible API** (used by OpenWebUI):
```bash
# List models
GET /api/v1/models

# Chat completions (streaming/non-streaming)
POST /api/v1/chat/completions
{
  "model": "rag-agent",
  "messages": [{"role": "user", "content": "Hello!"}],
  "stream": false
}
```

**Skills API** (internal use):
```bash
# RAG Skill - Run RAG with LLM generation
POST /api/rag-skill/ask

# RAG Skill - List available RAG groups
GET /api/rag-skill/groups

# RAG Skill - Smoke test
GET /api/rag-skill/test

# Tools Skill - Run tools with dynamic discovery
POST /api/tools-skill/query

# Tools Skill - Smoke test
GET /api/tools-skill/test
```

### RAG Injector (via /rag prefix)

**Note:** Caddy strips `/rag` prefix before forwarding to rag_mcp_service:5001

```bash
# Health check
# Client: GET /rag/health -> Backend: GET /health
GET /rag/health

# Upload document
# Client: POST /rag/upload -> Backend: POST /upload
POST /rag/upload

# List documents
# Client: GET /rag/documents -> Backend: GET /documents
GET /rag/documents
```

### Hyperparameter Advisor (port 5020, exposed as /hyperparam)

```bash
# Inject optimization results
POST /hyperparam/inject
{
  "experiment_id": "cnn_opt_v1",
  "results": [
    {
      "hyperparameters": {"lr": 0.001, "batch_size": 32},
      "result": 0.92,
      "result_type": "maximize"
    }
  ]
}

# Get suggestions
POST /hyperparam/suggest
{
  "target_params": ["lr", "batch_size", "dropout"],
  "result_type": "maximize",
  "n_suggestions": 3
}
```

### Admin UI (port 8000)

```bash
# Health check
GET /admin/api/health
# Response: {"ok": true}

# Dashboard (browser)
GET /admin
```

### Authentication Headers (Production)

When behind Caddy + Authentik:

```bash
curl -H "X-Authentik-Groups: admin" \
     -H "X-Authentik-Email: user@example.com" \
     -H "X-Authentik-Name: John Doe" \
     http://localhost/admin/api/health
```

## ⚙️ Configuration

### Required Environment Variables

```bash
# Domain configuration
DOMAIN=your-domain.com
# Note: AUTH_DOMAIN is the same as DOMAIN — Authentik is served under the same domain

# Authentik
AUTHENTIK_TAG=2024.2.0
AUTHENTIK_SECRET_KEY=<generate-random-50-char-key>
AUTHENTIK_OUTPOST_TOKEN=<from-authentik-admin-panel>

# Database
AK_POSTGRES_DB=authentik
AK_POSTGRES_USER=authentik
AK_POSTGRES_PASSWORD=<secure-password>
AK_REDIS_PASSWORD=<secure-password>

# OpenWebUI
WEBUI_AUTH=true  # Authentik-based authentication via trusted headers
OPENWEBUI_POSTGRES_DB=openwebui  # Optional, defaults to 'openwebui'

# Backend
DATABASE_URL=postgresql+psycopg://${AK_POSTGRES_USER}:${AK_POSTGRES_PASSWORD}@postgres:5432/${AK_POSTGRES_DB}
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_CHAT_MODEL=llama2:7b
OLLAMA_EMBED_MODEL=nomic-embed-text

# Collections
COLLECTION_DOCS=kb_docs
COLLECTION_TOOLS=tool_catalog
```

**See `.env.example` for complete configuration**

### Port Reference

| Port | Service | Access | Purpose |
|------|---------|--------|---------|
| 80/443 | Caddy | Public | HTTP/HTTPS ingress |
| 8000 | Admin UI | Via Caddy | Dashboard |
| 4000 | Agent API | Via Caddy | OpenAI-compatible API |
| 5000 | RAG MCP | Internal | Document retrieval (SSE) |
| 5001 | RAG Injector | Internal | Document ingestion (REST) |
| 5010 | Tools MCP | Internal | Search tools (SSE) |
| 5020 | Hyperparam MCP | Internal | Hyperparameter optimization (SSE) |
| 8080 | OpenWebUI | Via Caddy | Chat interface |
| 11434 | Ollama | Internal | LLM inference |

## 🛠️ Development

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend

# Within backend container (supervisord)
docker compose exec backend supervisorctl tail -f app
docker compose exec backend supervisorctl tail -f mcp_watcher
```

### Run Migrations

```bash
docker compose exec backend alembic upgrade head
```

### Local Python Development

```bash
cd backend/backend_app

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run services individually
uvicorn agents.main:app --reload --port 4000
uvicorn admin.main:app --reload --port 8000
python -m urls.daemons.url_watcher
python -m tools.daemons.watcher
```

### Testing Agent Skills

```bash
# Test RAG skill
curl -X POST http://localhost:8000/api/rag-skill/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is quantum computing?", "k": 5}'

# Test Tools skill
curl -X POST http://localhost:8000/api/tools-skill/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search arXiv for transformer papers",
    "user_id": "test@example.com",
    "role": "user"
  }'

# Test chat completions
curl -X POST http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-agent",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### Useful Scripts

```bash
docker compose up -d
docker compose ps
docker compose logs -f
```

## 📚 Documentation

- **[`README.md`](README.md)** - This file: Project overview and quick start
- **[`docs/INDEX.md`](docs/INDEX.md)** - Complete documentation index
- **[`docs/architecture/STRUCTURE.md`](docs/architecture/STRUCTURE.md)** - Repository structure and architecture
- **[`docs/architecture/AGENT_FLOW.md`](docs/architecture/AGENT_FLOW.md)** - Multi-skill agent execution patterns
- **[`docs/architecture/CADDY_ROUTING.md`](docs/architecture/CADDY_ROUTING.md)** - Caddy routing and path rewriting
- **[`docs/services/backend_app.md`](docs/services/backend_app.md)** - Backend services guide
- **[`docs/guides/llm_management.md`](docs/guides/llm_management.md)** - LLM configuration
- **[`docs/services/agents/rag_skill.md`](docs/services/agents/rag_skill.md)** - RAG skill usage
- **[`docs/services/mcp_services/hyperparam_advisor.md`](docs/services/mcp_services/hyperparam_advisor.md)** - Hyperparameter optimization tool

## 🔐 Authentication Flow

```
User Request
     ↓
  Caddy
     ↓
Forward Auth → Authentik Proxy
     ↓
Is Authenticated?
     ↓
  ┌──┴──┐
 YES    NO
  ↓      ↓
Add Headers  Redirect to Login
  ↓           ↓
Backend    Login Success
Services      ↓
           Redirect Back
```

**Identity Headers:**
- `X-Authentik-Email` - User email (canonical user ID)
- `X-Authentik-Name` - Display name
- `X-Authentik-Groups` - User groups (comma-separated)

Services treat these headers as the authoritative identity source.

## 🏗️ Technology Stack

| Category | Technology |
|----------|-----------|
| **Orchestration** | Docker Compose, Supervisord |
| **Web Framework** | FastAPI |
| **Agent Framework** | LangGraph |
| **LLM** | Ollama (llama2, nomic-embed-text) |
| **Vector DB** | PostgreSQL with pgvector |
| **Authentication** | Authentik |
| **Reverse Proxy** | Caddy 2.8 |
| **MCP Protocol** | SSE/HTTP transport |
| **Search** | SearXNG, arXiv API, CDS, INSPIRE-HEP |
| **Migrations** | Alembic |
| **UI** | OpenWebUI, Flowbite (admin) |

## 🐛 Troubleshooting

### Services won't start

```bash
# Check postgres is ready
docker compose exec postgres pg_isready

# Check logs
docker compose logs backend

# Run migrations manually
docker compose exec backend alembic upgrade head
```

### MCP tools not discovered

```bash
# Check mcp_watcher logs
docker compose exec backend supervisorctl tail -f mcp_watcher

# Verify basic_tools_mcp_service
curl http://localhost:5010/health

# Check database for registered tools
docker compose exec postgres psql -U authentik -d authentik \
  -c "SELECT name, enabled FROM tool_catalog;"
```

### Agent not using tools

```bash
# Test tool discovery
curl -X POST http://localhost:8000/api/tools-skill/query \
  -H "Content-Type: application/json" \
  -d '{"query": "search for papers", "user_id": "test", "role": "user"}'

# Check TOOL_SELECT_TOPK environment variable
docker compose exec backend env | grep TOOL_SELECT_TOPK
```

### RAG returns no results

```bash
# Check RAG MCP service is up
curl http://localhost:5000/health

# Verify injector
curl http://localhost:5001/health

# Test retrieval directly
curl -X POST http://localhost:8000/api/rag-skill/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "k": 5}'
```

## 🚢 Production Deployment

### Pre-Deployment Checklist

- [ ] Configure `.env` with production values
- [ ] Set strong passwords for `AK_POSTGRES_PASSWORD`, `AK_REDIS_PASSWORD`
- [ ] Generate secure `AUTHENTIK_SECRET_KEY` (50+ characters)
- [ ] Configure `DOMAIN` (Authentik uses the same domain)
- [ ] Set up DNS records pointing to your server
- [ ] Configure Authentik via admin panel
- [ ] Create outpost in Authentik, get token for `AUTHENTIK_OUTPOST_TOKEN`

### Deploy

```bash
# Start services
docker compose up -d

# Check all services are healthy
docker compose ps

# View logs
docker compose logs -f
```

### Access

- **Main Application**: https://your-domain.com/webui
- **Admin Dashboard**: https://your-domain.com/admin
- **Authentik Admin**: https://your-domain.com/if/admin/

### Monitoring

```bash
# Check service status
docker compose ps

# View resource usage
docker stats

# Check backend services
docker compose exec backend supervisorctl status
```

## 📊 Service Map

| Docker Service | Directory | Ports | Purpose |
|----------------|-----------|-------|---------|
| `caddy` | N/A (image) | 80, 443 | Reverse proxy + TLS |
| `postgres` | N/A (image) | 5432 | PostgreSQL + pgvector |
| `redis` | N/A (image) | 6379 | Redis cache |
| `authentik_server` | N/A (image) | 9000 | Auth server |
| `authentik_worker` | N/A (image) | - | Background worker |
| `authentik_proxy` | N/A (image) | 9000 | Forward auth proxy |
| `openwebui` | N/A (image) | 8080 | Chat interface (uses Authentik + PostgreSQL) |
| `backend` | `backend/backend_app/` | 8000, 4000 | Multi-service backend |
| `rag_mcp_service` | `backend/rag_mcp_service/` | 5000, 5001 | RAG MCP (SSE) + Injector (REST) |
| `basic_tools_mcp_service` | `backend/basic_tools_mcp_service/` | 5010 | Search tools MCP |
| `hyperparam_advisor_mcp_service` | `backend/hyperparam_advisor_mcp_service/` | 5020 | Hyperparameter optimization MCP |
| `ollama` | N/A (image) | 11434 | LLM inference |
| `searxng` | N/A (image) | 8081 | Meta search engine |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- **LangChain** - Agent framework
- **LangGraph** - Graph-based agent orchestration
- **Authentik** - Identity provider
- **Caddy** - Modern web server
- **Ollama** - Local LLM inference
- **pgvector** - Vector similarity search

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/BNLNPPS/AgentKS/issues)
- **Documentation**: See `docs/` directory
- **Copilot Context**: `.github/copilot-instructions.md`

---

**Made with ❤️ by BNLNPPS**



