"""
Tools Module

This module contains utilities and functions for working with MCP servers:
- client: MCP client utilities for connecting to and invoking MCP tools
  - client.py: Invoke MCP tools
  - discovery.py: Discover tools from MCP servers
- daemons: Background processes
  - watcher.py: MCP watcher daemon for auto-discovery
- models: Pydantic models for MCP-related data structures
- tool_discovery: Tool discovery and semantic search utilities
"""

from .client import run_mcp_tool_async, discover_mcp_tools, discover_mcp_tools_async
from .models import MCPSyncRequest, MCPServerConfig
from .tool_discovery import (
    discover_tools,
    discover_tools_hybrid,
    bind_discovered_tools_to_llm,
    index_tool_with_mcp_context,
    index_tool_simple,
    reindex_all_tools,
)

__all__ = [
    "run_mcp_tool_async",
    "discover_mcp_tools",
    "discover_mcp_tools_async",
    "MCPSyncRequest",
    "MCPServerConfig",
    "discover_tools",
    "discover_tools_hybrid",
    "bind_discovered_tools_to_llm",
    "index_tool_with_mcp_context",
    "index_tool_simple",
    "reindex_all_tools",
]
