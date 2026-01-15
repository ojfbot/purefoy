"""
Deakins Forums Knowledge Base Scraper

An ultra-structured, composable, MCP-ready forum scraper for rogerdeakins.com/forums.

Design principles:
- Ultra-structured: Each post/topic/forum is a separate JSON leaf
- Composable: Clean layers (HTTP, parse, normalize, store, index, MCP)
- Incremental: ETag/Last-Modified conditional GET + content hashing
- Agent-friendly: SQLite FTS5 search + MCP tools/resources/prompts
"""

__version__ = "0.1.0"
