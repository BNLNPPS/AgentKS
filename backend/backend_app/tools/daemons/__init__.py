"""
Daemons Module

Background processes for tool management:
- watcher: MCP watcher daemon for auto-discovery
"""

from .watcher import main_loop

__all__ = [
    "main_loop",
]
