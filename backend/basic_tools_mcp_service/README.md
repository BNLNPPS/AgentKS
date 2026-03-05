# Basic Tools MCP Service

FastMCP SSE server exposing search and research tools to the AgentKS agent pipeline.
Runs on **port 5010**.

---

## Files

```
basic_tools_mcp_service/
├── main.py           # FastMCP server + general search tools
├── hep.py            # High Energy Physics tools (registered into main mcp)
├── requirements.txt
└── Dockerfile
```

---

## Tools

### General Search & Utility (`main.py`)

| Tool | Description |
|------|-------------|
| `echo` | Returns provided text (utility / smoke-test) |
| `add` | Adds two numbers |
| `ddg_search` | DuckDuckGo web search |
| `arxiv_search` | Academic paper search (arXiv) |
| `wikipedia_search` | Wikipedia article search |
| `pubmed_search` | Medical / life-science literature (PubMed) |
| `searxng_search` | Privacy-focused meta-search via local SearXNG instance |
| `tavily_search` | AI-powered search with answer generation (requires API key) |

### High Energy Physics (`hep.py`)

| Tool | Description |
|------|-------------|
| `inspirehep_search` | INSPIRE-HEP literature database |
| `cds_search` | CERN Document Server (theses, reports, publications) |
| `arxiv_hep_search` | arXiv search scoped to HEP categories (hep-ph/th/ex/lat) |

---

## Endpoints

| Path | Description |
|------|-------------|
| `GET /sse` | SSE transport — MCP JSON-RPC 2.0 |
| `GET /health` | Health check |
| `GET /.well-known/mcp` | Discovery metadata (JSON) |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SEARXNG_URL` | `http://searxng:8080` | SearXNG instance URL |
| `TAVILY_API_KEY` | — | Required for `tavily_search` |
| `INSPIRE_BASE_URL` | `https://inspirehep.net` | INSPIRE-HEP API base |
| `CDS_BASE_URL` | `https://cds.cern.ch` | CERN Document Server base |
| `ARXIV_API_URL` | `http://export.arxiv.org/api/query` | arXiv API URL |

---

## Running

```bash
# Full stack
docker compose up -d basic_tools_mcp_service

# Local dev
cd backend/basic_tools_mcp_service
pip install -r requirements.txt
python main.py
```

---

## Registering in Admin UI

1. Navigate to **Admin → MCPs → Add MCP**
2. Enter endpoint: `http://basic_tools_mcp_service:5010`
3. Click **Discover** — the server's `/.well-known/mcp` metadata auto-fills the form

---

## Adding Tools

Add a decorated function to `main.py` (or a new module like `hep.py`):

```python
@mcp.tool()
def my_tool(query: str, max_results: int = 5) -> dict:
    """Short description used by the LLM for tool selection."""
    return {"results": [...]}
```

For domain-specific tools, create a module with a registration function and call it from `main.py`:

```python
# my_tools.py
def register_my_tools(mcp):
    @mcp.tool()
    def specialized_tool(query: str) -> dict:
        """Tool description."""
        return {"result": "..."}
```

```python
# main.py
from my_tools import register_my_tools
register_my_tools(mcp)
```

---

## See Also

- [`docs/services/mcp_services/basic_tools.md`](../../docs/services/mcp_services/basic_tools.md)
