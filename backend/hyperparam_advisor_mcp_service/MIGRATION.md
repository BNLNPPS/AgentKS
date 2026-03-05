# Hyperparameter Advisor MCP Service - Migration Notes

## Migration Summary

This service was migrated from `backend_app/hyperparam_advisor_mcp/` to become a standalone Docker service (`backend/hyperparam_advisor_mcp_service/`) on February 9, 2024.

## Changes Made

### 1. Directory Structure
- **Old location**: `backend_app/hyperparam_advisor_mcp/`
- **New location**: `backend/hyperparam_advisor_mcp_service/`
- **Pattern**: Now follows the same structure as `basic_tools_mcp_service`

### 2. File Changes
- **Renamed**: `server.py` → `main.py` (consistency with other services)
- **Created**: `Dockerfile` for containerization
- **Created**: `rag_common.py` (minimal standalone version with only needed utilities)
- **Updated**: `requirements.txt` (added langchain dependencies: langchain-core, langchain-ollama, langchain-postgres)
- **Removed**: `sys.path` manipulation for imports (no longer needed)

### 3. Dependencies Resolution
- Previously imported `rag_common` from `backend_app/rag/`
- Now has self-contained `rag_common.py` with only the required `get_vector_store_for_model()` function
- Added langchain dependencies to support RAG vector store operations

### 4. Docker Compose Integration
Added service entry to `docker-compose.yml`:
```yaml
hyperparam_advisor_mcp_service:
  build: ./backend/hyperparam_advisor_mcp_service
  restart: unless-stopped
  ports:
    - "5020:5020"
  environment:
    - PYTHONUNBUFFERED=1
    - DATABASE_URL=postgresql+psycopg://${AK_POSTGRES_USER}:${AK_POSTGRES_PASSWORD}@postgres:5432/${AK_POSTGRES_DB}
    - OLLAMA_BASE_URL=http://ollama:11434
    - OLLAMA_EMBED_MODEL=nomic-embed-text
    - LLM_API_URL=http://backend:4000/v1/chat/completions
    - RAG_INJECTOR_URL=http://rag_mcp_service:5001
  depends_on:
    - postgres
```

### 5. Documentation Updates
- Updated `README.md` to reflect new service location
- Added entry to main repository structure documentation
- Added to services table in main README

## Port Allocation
- **Port 5020**: stdio MCP server for hyperparameter optimization tools

## Environment Variables Required
- `DATABASE_URL`: PostgreSQL connection string with pgvector support
- `OLLAMA_BASE_URL`: Ollama API endpoint for embeddings (default: http://ollama:11434)
- `OLLAMA_EMBED_MODEL`: Embedding model name (default: nomic-embed-text)
- `LLM_API_URL`: LLM API endpoint for intelligent suggestions (optional)
- `RAG_INJECTOR_URL`: RAG injection API endpoint (optional)

## Testing
To test the standalone service:

```bash
# Build the image
docker compose build hyperparam_advisor_mcp_service

# Start the service
docker compose up -d hyperparam_advisor_mcp_service

# View logs
docker compose logs -f hyperparam_advisor_mcp_service

# Test from Python
python -c "
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command='docker',
    args=['exec', '-i', 'agentks-hyperparam_advisor_mcp_service-1', 'python', 'main.py']
)

async def test():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f'Available tools: {[t.name for t in tools.tools]}')

import asyncio
asyncio.run(test())
"
```

## Benefits of Migration
1. **Independent deployment**: Can be scaled separately from main backend
2. **Cleaner dependencies**: No cross-module imports from backend_app
3. **Consistent pattern**: Follows same structure as basic_tools_mcp_service
4. **Better isolation**: Service failures don't affect other components
5. **Easier testing**: Can test service independently

## Original Features Preserved
All original functionality remains intact:
- ✅ Categorical hyperparameter support
- ✅ LLM-based intelligent suggestions
- ✅ Heuristic fallback mode
- ✅ RAG-based context retrieval
- ✅ Comprehensive validation
- ✅ Test suite and documentation

## Migration Checklist
- [x] Create new service directory structure
- [x] Copy all source files
- [x] Rename server.py → main.py
- [x] Create Dockerfile
- [x] Create standalone rag_common.py
- [x] Update requirements.txt
- [x] Remove sys.path manipulations
- [x] Add docker-compose.yml entry
- [x] Update documentation
- [x] Remove old directory (backend_app/hyperparam_advisor_mcp/)
- [ ] Test Docker build
- [ ] Test service startup
- [ ] Verify MCP tool discovery
- [ ] Validate RAG integration

## Next Steps
1. Build and test the Docker image
2. Verify service integrates with mcp_watcher daemon
3. Test tool discovery from agent backend
4. Validate RAG querying with vector store
5. Performance testing under load
