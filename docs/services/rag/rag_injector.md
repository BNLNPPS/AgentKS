# RAG Injector REST API

FastAPI REST service for ingesting documents into the RAG knowledge base.  
Lives in the `rag_mcp_service` container on **port 5001**.

---

## Overview

```
rag_mcp_service container
├── rag_mcp.py       ← FastMCP SSE server  :5000  (retrieval)
└── rag_injector.py  ← FastAPI REST server :5001  (ingestion)
```

Both processes share the same PostgreSQL + pgvector database and run under `supervisord`.

### Workflow

1. **Injection (5001)** — clients submit documents via REST
2. **Storage** — document record saved to `rag_documents` table
3. **Embedding** — content chunked with `RecursiveCharacterTextSplitter`, embedded using the group's model
4. **Vector storage** — embeddings stored in PGVector
5. **Retrieval (5000)** — `rag_mcp.py` queries the same store using the same embedding model

---

## Endpoint Reference

### Health & Info

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |

### RAG Groups

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/groups` | List groups (`?scope=global&owner=`) |
| `POST` | `/groups` | Create a new RAG group |
| `GET` | `/groups/{name}` | Get group by name |
| `PATCH` | `/groups/{name}` | Update group metadata |
| `DELETE` | `/groups/{name}` | Delete group + all documents |

### Document Injection

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/inject/{group}` | Inject a single document |
| `POST` | `/inject/{group}/batch` | Inject multiple documents |
| `POST` | `/quick-inject` | Inject with auto group creation |

### Document Retrieval / Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/documents/{group}` | List documents in a group |
| `GET` | `/documents/by-id/{uuid}` | Fetch document by UUID |
| `DELETE` | `/documents/{uuid}` | Delete a document |
| `DELETE` | `/documents/by-url/{url_id}` | Delete docs by source URL |

### Search & Query

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/search/{group}` | Vector similarity search |
| `GET` | `/query` | Structured DB filter |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/groups` | All groups with stats |
| `GET` | `/admin/stats` | DB-level statistics |
| `POST` | `/admin/groups/bulk` | Bulk group creation |

---

## Usage Examples

### Quick Inject (auto-creates group)

```bash
curl -X POST http://localhost:5001/quick-inject \
  -H "Content-Type: application/json" \
  -d '{
    "group_name": "research_papers",
    "title": "Attention Is All You Need",
    "content": "The dominant sequence transduction models...",
    "scope": "global",
    "embed_model": "nomic-embed-text"
  }'
```

### Create Group + Inject

```bash
# 1. Create group
curl -X POST http://localhost:5001/groups \
  -H "Content-Type: application/json" \
  -d '{"name": "my_kb", "scope": "global", "embed_model": "nomic-embed-text"}'

# 2. Inject document
curl -X POST http://localhost:5001/inject/my_kb \
  -H "Content-Type: application/json" \
  -d '{"title": "My Doc", "content": "Full text content here..."}'
```

### Vector Search

```bash
curl -X POST http://localhost:5001/search/my_kb \
  -H "Content-Type: application/json" \
  -d '{"query": "transformer attention mechanism", "k": 5}'
```

### List Groups

```bash
curl "http://localhost:5001/groups?scope=global"
```

### Fetch Document by ID

```bash
curl http://localhost:5001/documents/by-id/<uuid>
```

---

## Key Pydantic Models

### `RAGGroupCreate`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | — | Unique group name |
| `scope` | `str` | `"global"` | Visibility scope |
| `owner` | `str?` | `null` | Owner identifier |
| `description` | `str?` | `null` | Human-readable description |
| `embed_model` | `str` | — | Ollama embedding model name |

### `DocumentInject`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | `str` | — | Document title |
| `content` | `str` | — | Full text content |
| `url_id` | `str?` | `null` | Source URL reference |
| `metadata` | `dict` | `{}` | Arbitrary key-value metadata |
| `chunk_size` | `int` | `1000` | Token chunk size |
| `chunk_overlap` | `int` | `200` | Overlap between chunks |

### `QuickInjectRequest`

Combines group creation and document injection in one call. If the group already exists it is reused.

| Field | Type | Default |
|-------|------|---------|
| `group_name` | `str` | — |
| `scope` | `str?` | `"global"` |
| `embed_model` | `str` | `"nomic-embed-text"` |
| `title` | `str` | — |
| `content` | `str` | — |
| `metadata` | `dict` | `{}` |
| `chunk_size` | `int` | `1000` |
| `chunk_overlap` | `int` | `200` |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | from env | PostgreSQL connection string |
| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Default embedding model |
| `COLLECTION_DOCS` | `rag_documents` | PGVector collection name |

---

## See Also

- [`rag_mcp.md`](rag_mcp.md) — retrieval side (port 5000)
- [`backend_app.md`](../backend_app.md) — agent API that calls this service
