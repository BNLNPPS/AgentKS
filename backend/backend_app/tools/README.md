# Tools Module (MCP Integration)

Utilities for discovering and invoking tools from MCP servers, and for semantic
tool search within the AgentKS agent pipeline.

---

## Directory Structure

```
tools/
├── __init__.py          # Module exports
├── models.py            # Pydantic models (MCPServerConfig, MCPSyncRequest)
├── tool_discovery.py    # Semantic + hybrid tool search and indexing
├── client/
│   ├── client.py        # MCP tool invocation (run_mcp_tool_async)
│   └── discovery.py     # MCP server tool discovery
├── daemons/
│   ├── __main__.py
│   └── watcher.py       # MCP watcher daemon (tools_watcher supervisord process)
└── README.md            # This file
```

---

## Components

### `client/client.py`

Connects to an MCP server (SSE transport) and invokes a named tool.

```python
from tools import run_mcp_tool_async

result = await run_mcp_tool_async(
    mcp_url="http://basic_tools_mcp_service:5010/mcp",
    headers={},
    tool_name="arxiv_search",
    payload={"query": "quantum computing"}
)
```

### `client/discovery.py`

Discovers the list of tools exposed by an MCP server.

```python
from tools import discover_mcp_tools

tools = discover_mcp_tools({
    "endpoint": "http://basic_tools_mcp_service:5010/mcp",
    "auth": None
})
# Returns: [{"name": "arxiv_search", "description": "...", "inputSchema": {...}}, ...]
```

### `models.py`

| Model | Purpose |
|-------|---------|
| `MCPServerConfig` | Configuration record for a registered MCP server |
| `MCPSyncRequest` | Request model for triggering tool sync from an MCP server |

### `tool_discovery.py`

Semantic and hybrid tool search used by `tools_skill.py` to select which tools
to offer the LLM for a given query.

| Function | Description |
|----------|-------------|
| `discover_tools(query, ...)` | Semantic search — returns ranked tool list |
| `discover_tools_hybrid(query, ...)` | Semantic + keyword combined scoring |
| `bind_discovered_tools_to_llm(llm, tools)` | Bind tool list to a LangChain LLM |
| `index_tool_with_mcp_context(...)` | Index a tool with full MCP context |
| `index_tool_simple(...)` | Index a tool without MCP context |
| `reindex_all_tools()` | Re-index all tools in the database |

```python
from tools import discover_tools, bind_discovered_tools_to_llm

tools = discover_tools(
    query="search for physics papers",
    user_scope="global",
    top_k=5,
    enabled_only=True
)

llm_with_tools = bind_discovered_tools_to_llm(llm, tools)
```

### `daemons/watcher.py`

Background daemon (runs as `tools_watcher` under `supervisord`) that polls the
`mcps` table, discovers tools from newly registered MCP servers, and indexes
them for semantic search.

```bash
# Run manually for testing
cd backend/backend_app
python -m tools.daemons
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_CHECK_INTERVAL` | `60` | Poll interval (seconds) |
| `MCP_CLAIM_LIMIT` | `5` | Max MCPs processed per cycle |
| `DATABASE_URL` | from env | PostgreSQL connection string |

---

## Full Import Reference

```python
from tools import (
    run_mcp_tool_async,       # Invoke an MCP tool
    discover_mcp_tools,       # Discover tools from an MCP server (sync)
    discover_mcp_tools_async, # Discover tools from an MCP server (async)
    discover_tools,           # Semantic tool search
    discover_tools_hybrid,    # Semantic + keyword tool search
    bind_discovered_tools_to_llm,
    MCPSyncRequest,
    MCPServerConfig,
)
```

---

## Integration Points

| Consumer | What it uses |
|----------|-------------|
| `agents/tools_skill.py` | `discover_tools`, `run_mcp_tool_async` |
| `admin/main.py` | `MCPSyncRequest`, `discover_mcp_tools` |
| `daemons/watcher.py` | `discover_mcp_tools`, `index_tool_with_mcp_context` |

---

## Troubleshooting

**`ImportError: langchain_mcp_adapters not found`**  
Install: `pip install langchain-mcp-adapters`

**Connection refused / Timeout**  
Check the MCP service is running: `curl http://basic_tools_mcp_service:5010/health`

**Tool not found**  
List available tools with `discover_mcp_tools(mcp_config)` and verify the name matches exactly (case-sensitive).
