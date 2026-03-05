# AgentKS Documentation Index# AgentKS Documentation Index



> ⚠️ **Under active development — not production ready.**Welcome to the comprehensive documentation for AgentKS - an agentic RAG knowledge stack.



## Navigation## 📚 Documentation Structure



### Architecture### 🏗️ Architecture

| Document | Description |- [AGENT_FLOW.md](architecture/AGENT_FLOW.md) - Multi-skill agent execution flow

|----------|-------------|- [STRUCTURE.md](architecture/STRUCTURE.md) - Complete repository structure

| [STRUCTURE.md](architecture/STRUCTURE.md) | Repository layout, service map, port reference |- [CADDY_ROUTING.md](architecture/CADDY_ROUTING.md) - Reverse proxy and routing

| [CADDY_ROUTING.md](architecture/CADDY_ROUTING.md) | Caddy ingress, path rewriting, forward_auth |- [OPENWEBUI_AUTHENTIK.md](architecture/OPENWEBUI_AUTHENTIK.md) - Authentication integration

| [AGENT_FLOW.md](architecture/AGENT_FLOW.md) | LangGraph agent execution and skill routing |

### 🔧 Services

### Services

| Document | Description |#### Backend Application

|----------|-------------|- [backend_app.md](services/backend_app.md) - Main backend service overview

| [backend_app.md](services/backend_app.md) | Main backend (agents API + admin UI) |

| [rag/rag_mcp.md](services/rag/rag_mcp.md) | RAG MCP server — document retrieval over SSE |#### Agents

| [rag/rag_injector.md](services/rag/rag_injector.md) | RAG Injector REST API — document ingestion |- [rag_skill.md](services/agents/rag_skill.md) - RAG retrieval skill

| [mcp_services/basic_tools.md](services/mcp_services/basic_tools.md) | Basic Tools MCP — search tools |- [tools_skill.md](services/agents/tools_skill.md) - Dynamic tool discovery skill

| [mcp_services/hyperparam_advisor.md](services/mcp_services/hyperparam_advisor.md) | Hyperparam Advisor MCP |

| [agents/rag_skill.md](services/agents/rag_skill.md) | RAG skill usage guide |#### RAG Services

- [rag_mcp.md](services/rag/rag_mcp.md) - RAG MCP server

### Guides- [rag_injector.md](services/rag/rag_injector.md) - Document injection API

| Document | Description |- [embedding_models.md](services/rag/embedding_models.md) - Embedding model configuration

|----------|-------------|- [url_watcher.md](services/rag/url_watcher.md) - URL monitoring daemon

| [guides/quick_start.md](guides/quick_start.md) | Get the stack running locally |

| [guides/llm_management.md](guides/llm_management.md) | Ollama model configuration |#### Tools

- [tools_overview.md](services/tools/tools_overview.md) - Tools module overview

## Port Reference- [tool_discovery.md](services/tools/tool_discovery.md) - Semantic tool discovery

- [tool_mcp_combination.md](services/tools/tool_mcp_combination.md) - MCP integration patterns

| Port | Service | Container | Transport |- [mcp_watcher_architecture.md](services/tools/mcp_watcher_architecture.md) - MCP watcher design

|------|---------|-----------|-----------|- [mcp_watcher_summary.md](services/tools/mcp_watcher_summary.md) - MCP watcher summary

| 80 / 443 | Caddy | `caddy` | HTTP/HTTPS public |- [mcp_watcher_migration.md](services/tools/mcp_watcher_migration.md) - MCP watcher migration guide

| 4000 | Agent API | `backend` | HTTP (OpenAI-compat) |- [mcp_watcher_quickref.md](services/tools/mcp_watcher_quickref.md) - MCP watcher quick reference

| 5000 | RAG MCP | `rag_mcp_service` | SSE |

| 5001 | RAG Injector | `rag_mcp_service` | HTTP REST |#### MCP Services

| 5010 | Basic Tools MCP | `basic_tools_mcp_service` | SSE |- [basic_tools.md](services/mcp_services/basic_tools.md) - Basic tools MCP service (search, arXiv, etc.)

| 5020 | Hyperparam MCP | `hyperparam_advisor_mcp_service` | stdio |- [hyperparam_advisor.md](services/mcp_services/hyperparam_advisor.md) - Hyperparameter optimization service

| 8000 | Admin UI | `backend` | HTTP |- [hyperparam_categorical.md](services/mcp_services/hyperparam_categorical.md) - Categorical parameter support

| 8080 | OpenWebUI | `openwebui` | HTTP |- [hyperparam_migration.md](services/mcp_services/hyperparam_migration.md) - Hyperparameter service migration notes

| 9000 | Authentik | `authentik_server` / `authentik_proxy` | HTTP |

| 11434 | Ollama | `ollama` | HTTP |### 📖 Guides

- [llm_management.md](guides/llm_management.md) - LLM configuration and management
- [using_llms.md](guides/using_llms.md) - Using LLMs in the application
- [url_hierarchy.md](guides/url_hierarchy.md) - URL hierarchy implementation

### 🔌 API Reference
- [database.md](api/database.md) - Database schema and operations

## 🚀 Quick Start

1. **Getting Started**: Start with [../README.md](../README.md) for overview and setup
2. **Architecture**: Review [architecture/AGENT_FLOW.md](architecture/AGENT_FLOW.md) to understand the system
3. **Services**: Explore specific services in the [services/](services/) directory
4. **Guides**: Check [guides/](guides/) for operational guidance

## 📁 Documentation Layers

```
docs/
├── INDEX.md                          # This file
├── architecture/                     # High-level architecture docs
│   ├── AGENT_FLOW.md                # Multi-skill execution
│   ├── STRUCTURE.md                 # Repository structure
│   ├── CADDY_ROUTING.md             # HTTP routing
│   └── OPENWEBUI_AUTHENTIK.md       # Authentication
│
├── services/                         # Service-specific documentation
│   ├── backend_app.md               # Backend overview
│   ├── agents/                      # Agent skills
│   │   ├── rag_skill.md
│   │   └── tools_skill.md
│   ├── rag/                         # RAG services
│   │   ├── rag_mcp.md
│   │   ├── rag_injector.md
│   │   ├── embedding_models.md
│   │   └── url_watcher.md
│   ├── tools/                       # Tools and MCP integration
│   │   ├── tools_overview.md
│   │   ├── tool_discovery.md
│   │   ├── tool_mcp_combination.md
│   │   ├── mcp_watcher_architecture.md
│   │   ├── mcp_watcher_summary.md
│   │   ├── mcp_watcher_migration.md
│   │   └── mcp_watcher_quickref.md
│   └── mcp_services/                # Standalone MCP services
│       ├── basic_tools.md
│       ├── hyperparam_advisor.md
│       ├── hyperparam_categorical.md
│       └── hyperparam_migration.md
│
├── guides/                           # How-to guides
│   ├── llm_management.md
│   ├── using_llms.md
│   └── url_hierarchy.md
│
├── api/                              # API references
│   └── database.md
│
└── deployment/                       # Deployment docs (TBD)
```

## 🔍 Finding Documentation

- **By Feature**: Start with guides/
- **By Service**: Browse services/
- **By Architecture**: Check architecture/
- **By API**: See api/

## 📝 Contributing

When adding new documentation:
1. Place it in the appropriate layer
2. Update this INDEX.md
3. Use relative links for cross-references
4. Follow the naming convention: lowercase with underscores

## 🔗 External References

- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent framework
- [Authentik](https://goauthentik.io/) - Identity provider
