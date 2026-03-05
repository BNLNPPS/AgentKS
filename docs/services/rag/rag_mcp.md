# RAG MCP Server# RAG MCP Server



FastMCP SSE server for document retrieval from the PGVector knowledge base.  A Model Context Protocol (MCP) server for RAG (Retrieval-Augmented Generation) operations.

Lives in the `rag_mcp_service` container on **port 5000**.Provides tools to search and retrieve documents from the knowledge base using vector similarity

and database queries.

## Overview

## ⚠️ Important: Embedding Model Compatibility

```

rag_mcp_service container**Different embedding models are NOT compatible with each other!**

├── rag_mcp.py       ← FastMCP SSE server  :5000

└── rag_injector.py  ← FastAPI REST server :5001- Each RAG group tracks which embedding model was used to create its embeddings

```- You MUST use the same model for both document ingestion and query search

- Changing models requires re-embedding ALL documents in that group

Both processes run under `supervisord`. The MCP server handles retrieval; the Injector handles ingestion. See [rag_injector.md](rag_injector.md) for the ingestion API.- **Always specify `rag_group` in searches** to ensure model consistency



## ToolsSee [EMBEDDING_MODELS.md](./EMBEDDING_MODELS.md) for detailed information about managing embedding models.



| Tool | Description |## Features

|------|-------------|

| `rag_search` | Vector similarity search across a RAG group |- **Protocol Compliant**: Uses FastMCP for proper MCP JSON-RPC 2.0 protocol

| `rag_query` | Structured DB filter (title/content pattern, limit) |- **HTTP/SSE Transport**: Accessible via HTTP with streaming support (port 5000)

| `rag_get_document` | Fetch a single document by UUID |- **Vector Similarity Search**: Semantic search using embeddings and pgvector

| `rag_list_groups` | List all RAG groups (optionally filter by scope/owner) |- **Embedding Model Tracking**: Each RAG group uses a specific embedding model

| `rag_get_group_documents` | List documents in a group |- **Database Queries**: Direct SQL queries for precise filtering

- **Group Management**: Organize documents into named collections (RAG groups)

## Resources- **Metadata Resources**: Expose knowledge base statistics and group information



| Resource URI | Description |## Tools

|---|---|

| `rag://metadata` | Server stats + group list |### 1. `rag_search` - Vector Similarity Search

| `rag://groups` | All RAG groups as JSON |

Performs semantic search across the knowledge base using embeddings.

## Connecting (SSE)

**⚠️ IMPORTANT:** Always specify `rag_group` to ensure the correct embedding model is used.

```pythonSearching without a group may mix results from incompatible embedding models.

from mcp import ClientSession

from mcp.client.sse import sse_client**Parameters:**

- `query` (string, required): Search query or question

async with sse_client("http://rag_mcp_service:5000/sse") as (read, write):- `k` (int, optional): Number of results to return (default: 5, max: 20)

    async with ClientSession(read, write) as session:- `rag_group` (string, **RECOMMENDED**): Filter by RAG group name - ensures model consistency

        await session.initialize()- `score_threshold` (float, optional): Minimum similarity score 0.0-1.0

        result = await session.call_tool("rag_search", {

            "query": "transformer attention mechanism",**Example:**

            "rag_group": "research_papers",```json

            "k": 5{

        })  "query": "What is machine learning?",

```  "k": 5,

  "rag_group": "ml-docs"

From inside the `backend` container (via `rag_skill.py`):}

``````

RAG_MCP_URL=http://rag_mcp_service:5000

```**Response includes:**

- Search results with content and metadata

## Tool Reference- `embedding_model`: Which model was used (confirms compatibility)

- `similarity_score`: Relevance score for each result

### `rag_search`

### 2. `rag_query` - Database Query

Vector similarity search.

Structured queries on rag_documents table with pattern matching.

```json

{**Parameters:**

  "query": "hyperparameter tuning for neural networks",- `rag_group` (string, optional): Filter by RAG group name

  "rag_group": "kb_docs",- `title_pattern` (string, optional): SQL LIKE pattern for title

  "k": 5,- `content_pattern` (string, optional): SQL LIKE pattern for content

  "score_threshold": 0.0- `limit` (int, optional): Maximum results (default: 10, max: 50)

}

```**Example:**

```json

Returns:{

```json  "rag_group": "python-docs",

{  "title_pattern": "%async%",

  "query": "...",  "limit": 10

  "rag_group": "kb_docs",}

  "num_results": 3,```

  "results": [

    {"content": "...", "metadata": {...}, "score": 0.87}### 3. `rag_get_document` - Get Document by ID

  ]

}Retrieves full document content and metadata.

```

**Parameters:**

### `rag_query`- `document_id` (string, required): Document ID



Structured DB filter — no embedding required.**Example:**

```json

```json{

{  "document_id": "d1"

  "rag_group": "kb_docs",}

  "title_pattern": "%transformer%",```

  "content_pattern": null,

  "limit": 10### 4. `rag_list_groups` - List RAG Groups

}

```Lists all RAG groups (document collections) with statistics.



### `rag_get_document`**Parameters:**

- `scope` (string, optional): Filter by scope (default: "global")

```json- `owner` (string, optional): Filter by owner

{"document_id": "550e8400-e29b-41d4-a716-446655440000"}

```**Example:**

```json

### `rag_list_groups`{

  "scope": "global"

```json}

{"scope": "global", "owner": null}```

```

### 5. `rag_get_group_documents` - Get Documents in Group

## Environment Variables

Retrieves all documents in a specific RAG group.

| Variable | Default | Purpose |

|----------|---------|---------|**Parameters:**

| `DATABASE_URL` | — | PostgreSQL + pgvector (required) |- `rag_group_name` (string, required): RAG group name

| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama embedding server |- `limit` (int, optional): Maximum documents (default: 20, max: 100)

| `OLLAMA_EMBED_MODEL` | `nomic-embed-text` | Embedding model |

| `COLLECTION_DOCS` | `kb_docs` | PGVector collection name |**Example:**

```json

## Local Testing{

  "rag_group_name": "api-reference",

```bash  "limit": 50

# Server health (via injector — same container)}

curl http://localhost:5001/health```



# SSE endpoint## Resources

curl -N http://localhost:5000/sse

### `rag://metadata`

# List tools via MCP protocol

curl http://localhost:5000/sse/tools/listReturns metadata about the RAG knowledge base including:

```- Total groups and documents

- Embedding model configuration
- Top groups by document count

### `rag://groups`

Returns complete list of all RAG groups with details.

## Running the Server

### Via Supervisord (Integrated with Backend)

The RAG MCP service runs as a daemon managed by supervisord within the backend container.

**Deployment:**
```bash
# Build and start the backend (includes RAG MCP)
docker compose up -d backend

# Check logs for all services
docker compose logs -f backend

# Check RAG MCP specifically
docker compose exec backend supervisorctl status rag_mcp
docker compose exec backend supervisorctl tail -f rag_mcp

# Server will be available at http://localhost:5000
```

**Supervisord Configuration:**

The service is configured in `/app/supervisord.conf`:
```ini
[program:rag_mcp]
command=python -u rag_mcp/main.py
directory=/app
autostart=true
autorestart=true
stdout_logfile=/dev/stdout
stderr_logfile=/dev/stderr
startretries=3
environment=PYTHONUNBUFFERED="1"
```

**Manage the service:**
```bash
# Stop RAG MCP
docker compose exec backend supervisorctl stop rag_mcp

# Start RAG MCP
docker compose exec backend supervisorctl start rag_mcp

# Restart RAG MCP
docker compose exec backend supervisorctl restart rag_mcp

# View status of all services
docker compose exec backend supervisorctl status
```

### Local Development

```bash
cd backend/backend_app/rag_mcp

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/dbname"
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_EMBED_MODEL="nomic-embed-text"
export COLLECTION_DOCS="document_embeddings"

# Run server
python main.py
```

Server runs at http://localhost:5000

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | - | PostgreSQL connection string with psycopg |
| `OLLAMA_BASE_URL` | No | `http://ollama:11434` | Ollama service URL |
| `OLLAMA_EMBED_MODEL` | No | `nomic-embed-text` | Embedding model name |
| `COLLECTION_DOCS` | No | `document_embeddings` | PGVector collection name |

### Database Schema

The service uses these tables:

**rag_groups** - Document collections
- `id`: Primary key
- `name`: Group name (unique per scope)
- `scope`: Scope for multi-tenancy (default: "global")
- `owner`: Optional owner identifier
- `description`: Group description
- `embed_model`: Embedding model used
- `doc_count`: Number of documents

**rag_documents** - Individual documents
- `id`: Primary key
- `rag_group_id`: Foreign key to rag_groups
- `url_id`: Optional foreign key to source URL
- `title`: Document title
- `content`: Full text content
- `content_hash`: Hash for deduplication
- `metadata`: JSONB for flexible metadata
- `created_at`, `updated_at`: Timestamps

**PGVector collection** - Vector embeddings
- Stores document embeddings for similarity search
- Indexed with HNSW for fast retrieval

## Usage with MCP Clients

### Python Client Example

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async with stdio_client(
    StdioServerParameters(
        command="python",
        args=["main.py"],
        env={
            "DATABASE_URL": "postgresql+psycopg://...",
            "OLLAMA_BASE_URL": "http://localhost:11434"
        }
    )
) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        
        # Vector search
        result = await session.call_tool("rag_search", {
            "query": "machine learning concepts",
            "k": 5
        })
        print(result)
        
        # Get group documents
        result = await session.call_tool("rag_get_group_documents", {
            "rag_group_name": "ml-docs",
            "limit": 10
        })
        print(result)
```

### HTTP/SSE Client Example

```python
import httpx
import json

async with httpx.AsyncClient() as client:
    # Call tool via HTTP
    response = await client.post(
        "http://localhost:5000/sse",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "rag_search",
                "arguments": {
                    "query": "Python async programming",
                    "k": 5
                }
            },
            "id": 1
        }
    )
    result = response.json()
    print(result)
```

### OpenWebUI Integration

In OpenWebUI admin settings:

1. Navigate to Admin → Settings → Tools
2. Click "Add MCP Server"
3. Configure:
   - Name: `RAG Knowledge Base`
   - Type: `HTTP/SSE`
   - Endpoint: `http://rag_mcp_service:5000/sse` (or `http://localhost:5000/sse`)
4. Save and test connection

The RAG tools will appear in the chat interface for knowledge retrieval.

## Discovery Endpoint

The server exposes metadata at `/.well-known/mcp`:

```bash
curl http://localhost:5000/.well-known/mcp
```

Returns:
```json
{
  "name": "rag-mcp",
  "version": "1.0.0",
  "description": "RAG knowledge base retrieval service",
  "capabilities": {
    "tools": [...],
    "resources": [...],
    "prompts": [...]
  },
  "configuration": {...},
  "environment": {...}
}
```

## Architecture

### Vector Search Flow

1. User query → Embedding generation (Ollama)
2. Vector similarity search in PGVector
3. Results ranked by cosine similarity
4. Return top-k documents with scores

### Database Query Flow

1. Build SQL query with filters
2. Execute on rag_documents table
3. Join with rag_groups for metadata
4. Return structured results

### Group Organization

Documents are organized into RAG groups (collections):
- Each group has a unique name per scope
- Groups track document counts and embed model
- Supports multi-tenancy via scope field
- Optional owner association

## Performance

- **Vector Search**: O(log n) with HNSW index
- **Database Queries**: Indexed on rag_group_id
- **Concurrent Requests**: Async/await support
- **Connection Pooling**: psycopg built-in

## Monitoring

Check server health:
```bash
curl http://localhost:5000/
```

View knowledge base stats:
```bash
curl http://localhost:5000/mcp/resources/rag://metadata
```

## Troubleshooting

### "Vector search not available"

- Ensure LangChain dependencies are installed
- Check Ollama service is running and accessible
- Verify DATABASE_URL has pgvector extension enabled

### "Document not found"

- Check document ID exists in rag_documents table
- Verify RAG group scope matches query

### Connection errors

- Verify DATABASE_URL format: `postgresql+psycopg://user:pass@host:5432/db`
- Check PostgreSQL is running and accessible
- Ensure database has required tables (run migrations)

## Development

### Adding New Tools

```python
@mcp.tool()
def my_new_tool(param: str) -> str:
    """Tool description."""
    # Implementation
    return json.dumps(result)
```

### Adding Resources

```python
@mcp.resource("rag://custom")
def custom_resource():
    """Resource description."""
    return json.dumps(data)
```

## Related Services

The backend container runs multiple services via supervisord:

- **web** (port 8000): Admin web UI for managing URLs, RAG groups, MCPs, LLMs
- **app** (port 4000): Main FastAPI application with RAG ingestion and chat API
- **rag_mcp** (port 5000): RAG retrieval MCP service (this service)
- **url_watcher**: Background daemon for monitoring and fetching URLs

External services:
- **basic_tools_mcp_service** (port 5000): General search and utility tools
- **hyperparam_advisor_mcp_service** (port 5001): ML hyperparameter optimization with RAG
- **postgres**: Database with pgvector extension
- **ollama**: LLM and embedding generation service

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          Backend Container (supervisord)            │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │
│  │   web    │  │   app    │  │    rag_mcp       │ │
│  │ :8000    │  │ :4000    │  │    :5000         │ │
│  │ Admin UI │  │ Chat API │  │ RAG Retrieval    │ │
│  └──────────┘  └──────────┘  └──────────────────┘ │
│                                                      │
│  ┌────────────────────────────────────────────────┐ │
│  │         url_watcher (background)               │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
      ┌─────────────────────────────────────┐
      │  PostgreSQL + pgvector              │
      │  • rag_groups, rag_documents        │
      │  • document_embeddings collection   │
      └─────────────────────────────────────┘
                         │
                         ▼
      ┌─────────────────────────────────────┐
      │  Ollama                             │
      │  • nomic-embed-text (embeddings)    │
      │  • llama2:7b (chat)                 │
      └─────────────────────────────────────┘
```

## License

Part of the AgentKS project.
