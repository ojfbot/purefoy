#!/usr/bin/env python3
"""
MCP (Model Context Protocol) server for Deakins Forums scraper.

Exposes the scraper as MCP tools that can be called by AI agents
in a multi-agent system with the same interface as CLI commands.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# MCP tool definitions matching CLI interface
MCP_TOOLS = [
    {
        "name": "scrape_deakins_forum",
        "description": "Scrape a Deakins forum with query provenance tracking. Captures who is querying, why, and tracks all topic access for research lineage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "forum_slug": {
                    "type": "string",
                    "description": "Forum slug to scrape (e.g., 'forum', 'camera', 'team-deakins', 'post', 'composition', 'film-talk', 'set-talk', 'still-photography')",
                    "enum": ["forum", "camera", "team-deakins", "post", "composition", "film-talk", "set-talk", "still-photography"]
                },
                "max_topics": {
                    "type": "integer",
                    "description": "Maximum number of topics to scrape. Use higher numbers to increase coverage towards 100%.",
                    "default": 1000
                },
                "query_name": {
                    "type": "string",
                    "description": "Human-readable name of the research query"
                },
                "querier_role": {
                    "type": "string",
                    "description": "Role of the person/agent making the query (e.g., 'Director', 'DP', 'Studio Head', 'Producer')"
                },
                "querier_department": {
                    "type": "string",
                    "description": "Department (e.g., 'Camera', 'Lighting', 'Production', 'Executive')"
                },
                "query_context": {
                    "type": "string",
                    "description": "Context of the query (e.g., 'Feature film development', 'TV series pre-production', 'Studio slate planning')"
                },
                "query_intent": {
                    "type": "string",
                    "description": "Research objective/question - what specific information is being sought"
                },
                "build_index": {
                    "type": "boolean",
                    "description": "Whether to rebuild the search index after scraping",
                    "default": True
                }
            },
            "required": ["forum_slug", "query_name", "querier_role", "querier_department", "query_context", "query_intent"]
        }
    },
    {
        "name": "get_coverage_report",
        "description": "Get current forum coverage statistics with colored CLI-style report showing which forums are scraped and to what percentage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "Report format: 'full' for detailed report, 'quick' for one-line summary",
                    "enum": ["full", "quick"],
                    "default": "full"
                }
            }
        }
    },
    {
        "name": "get_provenance_report",
        "description": "Get query provenance report showing research lineage - which queries accessed which topics, when, and by whom.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Optional: Show provenance for specific topic (format: 'forum__topic-slug')"
                },
                "query_id": {
                    "type": "string",
                    "description": "Optional: Show details for specific query ID"
                }
            }
        }
    }
]


class MCPServer:
    """MCP server wrapping the Deakins Forums scraper."""

    def __init__(self):
        self.tools = MCP_TOOLS

    def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools."""
        return self.tools

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool with given arguments.

        This executes the actual CLI command and returns results.
        Interface is identical whether called by AI prompt or MCP agent.
        """
        from .cli import build_app
        from .pipeline import DeakinsPipeline
        from .coverage import CoverageTracker
        from .report import print_coverage_report, print_quick_stats
        from .query_tracker import QueryTracker

        if tool_name == "scrape_deakins_forum":
            return self._scrape_forum(arguments)
        elif tool_name == "get_coverage_report":
            return self._get_coverage(arguments)
        elif tool_name == "get_provenance_report":
            return self._get_provenance(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _scrape_forum(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute forum scraping with query tracking."""
        from .cli import build_app
        from .query_tracker import QueryTracker

        # Build app
        pipeline, store, index, settings = build_app()

        forum_slug = args["forum_slug"]
        forum_url = f"{settings.base_url}/forums/forum/{forum_slug}/"

        # Initialize query tracking
        query_tracker = QueryTracker(settings.out_dir)
        query_metadata = query_tracker.start_query(
            query_name=args["query_name"],
            querier_role=args["querier_role"],
            querier_department=args["querier_department"],
            query_context=args["query_context"],
            query_intent=args["query_intent"],
            target_forums=[forum_slug]
        )

        # Track existing topics before scraping
        topics_before = set()
        topics_dir = settings.out_dir / "topics"
        if topics_dir.exists():
            topics_before = {
                f.stem for f in topics_dir.iterdir()
                if f.name.startswith(f"{forum_slug}__") and f.suffix == ".json"
            }

        # Execute scraping
        forum_leaf = pipeline.scrape_forum(
            forum_url=forum_url,
            forum_slug=forum_slug,
            max_pages=args.get("max_pages", 20),
            max_topics=args.get("max_topics", 1000)
        )

        # Track topic access
        topics_after = {
            f.stem for f in topics_dir.iterdir()
            if f.name.startswith(f"{forum_slug}__") and f.suffix == ".json"
        }

        newly_scraped = topics_after - topics_before

        # Log all accessed topics
        for topic_file in topics_dir.iterdir():
            if topic_file.name.startswith(f"{forum_slug}__") and topic_file.suffix == ".json":
                topic_slug = topic_file.stem.replace(f"{forum_slug}__", "")
                was_new = topic_file.stem in newly_scraped
                query_tracker.log_topic_access(
                    query_metadata=query_metadata,
                    topic_slug=topic_slug,
                    forum_slug=forum_slug,
                    was_new_scrape=was_new
                )

        # Finalize query
        query_tracker.finalize_query(query_metadata)

        # Build index if requested
        if args.get("build_index", True):
            index_stats = index.rebuild_from_json_leafs(settings.out_dir)
        else:
            index_stats = {"posts_indexed": 0}

        return {
            "success": True,
            "query_id": query_metadata.query_id,
            "forum": forum_slug,
            "topics_scraped": len(forum_leaf.topic_refs),
            "topics_accessed": len(query_metadata.topics_accessed),
            "topics_newly_scraped": len(query_metadata.topics_newly_scraped),
            "topics_revisited": len(query_metadata.topics_revisited),
            "posts_indexed": index_stats.get("posts_indexed", 0)
        }

    def _get_coverage(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get coverage report."""
        from .cli import build_app
        from .coverage import CoverageTracker

        pipeline, store, index, settings = build_app()
        tracker = CoverageTracker(settings.out_dir)

        previous = tracker.load_previous_coverage()
        current = tracker.generate_report(settings.out_dir)
        delta = tracker.calculate_delta(current) if previous else None
        tracker.save_coverage(current)

        # Return structured data
        return {
            "timestamp": current.timestamp,
            "overall_coverage_percent": round((current.topics_scraped / current.total_topics * 100) if current.total_topics > 0 else 0, 1),
            "total_forums": current.total_forums,
            "topics_scraped": current.topics_scraped,
            "total_topics": current.total_topics,
            "total_posts": current.total_posts,
            "forums": {
                slug: {
                    "name": forum.forum_name,
                    "coverage_percent": round(forum.coverage_percent, 1),
                    "topics_scraped": forum.topics_scraped,
                    "total_topics": forum.total_topics_available,
                    "posts": forum.posts_scraped
                }
                for slug, forum in current.forums.items()
            },
            "delta": delta
        }

    def _get_provenance(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get provenance report."""
        from .cli import build_app
        from .query_tracker import QueryTracker

        pipeline, store, index, settings = build_app()
        query_tracker = QueryTracker(settings.out_dir)

        if args.get("topic"):
            # Topic-specific provenance
            forum_slug, topic_slug = args["topic"].split("__", 1) if "__" in args["topic"] else (args["topic"], None)
            if topic_slug:
                accesses = query_tracker.get_topic_provenance(topic_slug, forum_slug)
                return {
                    "topic": args["topic"],
                    "access_count": len(accesses),
                    "accesses": accesses
                }
            else:
                return {"error": "Invalid topic format. Use: forum__topic-slug"}

        elif args.get("query_id"):
            # Query-specific details
            query_data = query_tracker.get_query_summary(args["query_id"])
            if query_data:
                return query_data
            else:
                return {"error": f"Query ID not found: {args['query_id']}"}

        else:
            # Full report
            log = query_tracker.load_query_log()
            return {
                "total_queries": len(log["queries"]),
                "unique_topics_accessed": len(log["topic_access_index"]),
                "queries": log["queries"],
                "topic_access_index": log["topic_access_index"]
            }


def serve():
    """Run MCP server (stdio-based protocol)."""
    server = MCPServer()

    # Read JSON-RPC requests from stdin
    for line in sys.stdin:
        try:
            request = json.loads(line)

            if request["method"] == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"tools": server.list_tools()}
                }

            elif request["method"] == "tools/call":
                tool_name = request["params"]["name"]
                arguments = request["params"].get("arguments", {})
                result = server.call_tool(tool_name, arguments)

                response = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}
                }

            else:
                response = {
                    "jsonrpc": "2.0",
                    "id": request["id"],
                    "error": {"code": -32601, "message": "Method not found"}
                }

            print(json.dumps(response), flush=True)

        except Exception as e:
            response = {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32603, "message": str(e)}
            }
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    serve()
