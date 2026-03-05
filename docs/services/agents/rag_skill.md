# RAG Skill

The RAG skill is a LangGraph sub-workflow inside `backend_app/agents/rag_skill.py`. It retrieves relevant documents from the knowledge base via the RAG MCP service and synthesises an answer using the chat LLM.

## Flow

```
rag_skill.retrieve_documents(query, k=5)
      ↓
Connect via SSE:  RAG_MCP_URL/sse   (http://rag_mcp_service:5000/sse)
      ↓
Call MCP tool: rag_search
  { "query": "...", "rag_group": COLLECTION_DOCS, "k": k }
      ↓
Returns: list[{content, metadata, score}]
      ↓
LLM synthesises answer with retrieved context
```

## API Endpoints

The agent backend exposes these convenience endpoints on port 4000:

```bash
# Full RAG query (retrieve + synthesise)
POST /api/rag-skill/run
Content-Type: application/json
{
  "query": "What optimiser works best for transformers?",
  "k": 5,
  "user_id": "user@example.com"
}

# Raw retrieval only (no LLM synthesis)
POST /api/rag-skill/retrieve
Content-Type: application/json
{
  "query": "attention mechanism",
  "k": 5
}
```

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_MCP_URL` | `http://rag_mcp_service:5000` | RAG MCP SSE endpoint |
| `COLLECTION_DOCS` | `kb_docs` | Default RAG group to search |
| `OLLAMA_CHAT_MODEL` | `llama2:7b` | LLM for synthesis |

## Ingesting Documents

Use the RAG Injector REST API (port 5001):

```bash
# Quick inject
curl -X POST http://localhost:5001/quick-inject \
  -H "Content-Type: application/json" \
  -d '{"title": "My Doc", "content": "Full text...", "rag_group": "kb_docs"}'

# Via Caddy (authenticated)
curl -X POST https://your-domain.com/rag/quick-inject \
  -H "Content-Type: application/json" \
  -d '{"title": "My Doc", "content": "Full text...", "rag_group": "kb_docs"}'
```

See [rag_injector.md](../rag/rag_injector.md) for the full injection API.

## Testing

```bash
# Direct RAG retrieval
curl -X POST http://localhost:4000/api/rag-skill/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "k": 3}'

# Full RAG + synthesis
curl -X POST http://localhost:4000/api/rag-skill/run \
  -H "Content-Type: application/json" \
  -d '{"query": "What is pgvector?", "k": 5}'
```
