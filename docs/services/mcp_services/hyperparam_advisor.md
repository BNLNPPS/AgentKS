# Hyperparameter Advisor MCP Service

MCP service for ML hyperparameter optimization using RAG-backed history.  
Runs in the `hyperparam_advisor_mcp_service` container on **port 5020** (stdio transport).

## Architecture

```
hyperparam_advisor_mcp_service
├── main.py         # MCP stdio server (hyperparam_inject, hyperparam_suggest)
├── rag_mcp.py      # FastMCP SSE variant (rag_search, rag_query, rag_list_groups …)
└── rag_common.py   # HTTP client → rag_mcp_service:5001
```

This service has **no direct database access**. All RAG operations go through HTTP calls to `rag_mcp_service`.

## Tools

### `hyperparam_inject`

Store a hyperparameter experiment result in the RAG knowledge base.

```json
{
  "experiment_id": "cnn_opt_v2",
  "hyperparameters": {"lr": 0.001, "batch_size": 32, "dropout": 0.3},
  "result": 0.924,
  "result_type": "maximize",
  "metadata": {"dataset": "MNIST", "epochs": 50}
}
```

### `hyperparam_suggest`

Get tuning suggestions based on historical experiment data stored in RAG.

```json
{
  "experiment_id": "cnn_opt_v2",
  "current_params": {"lr": 0.01, "batch_size": 64},
  "objective": "maximize validation accuracy",
  "n_suggestions": 3
}
```

## RAG Integration

The service calls `rag_mcp_service` via HTTP:

```
hyperparam_suggest
      ↓
rag_common.rag_search(query, rag_group="hyperparameter-optimization")
      ↓
POST rag_mcp_service:5001/search/{group}
      ↓
Returns similar past experiments
      ↓
LLM synthesises suggestions
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_INJECTOR_URL` | `http://rag_mcp_service:5001` | RAG Injector REST endpoint |
| `RAG_MCP_URL` | `http://rag_mcp_service:5000` | RAG MCP SSE endpoint |
| `HYPERPARAM_RAG_GROUP` | `hyperparameter-optimization` | RAG group for experiment data |
| `RAG_EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `USE_LLM_ANALYSIS` | `true` | Enable LLM-based suggestion analysis |
| `LLM_API_URL` | `http://backend:4000/v1/chat/completions` | Chat LLM endpoint |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama server |
| `COLLECTION_DOCS` | `kb_docs` | PGVector collection |

## Migration Note

This service was migrated from direct PostgreSQL + LangChain access to an HTTP client pattern delegating all RAG operations to `rag_mcp_service`. See `MIGRATION.md` in the service directory for details.

## Testing

```bash
# Container health
docker compose ps hyperparam_advisor_mcp_service

# Logs
docker compose logs -f hyperparam_advisor_mcp_service

# Inject a test experiment (via RAG Injector directly)
curl -X POST http://localhost:5001/quick-inject \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Experiment cnn_v1",
    "content": "lr=0.001, batch_size=32, accuracy=0.92",
    "rag_group": "hyperparameter-optimization",
    "scope": "global"
  }'
```

## Protocol Details

- **Transport**: stdio (invoked by agent via MCP client)
- **Port**: 5020 (SSE variant of `rag_mcp.py`)
- **Container**: `hyperparam_advisor_mcp_service`
