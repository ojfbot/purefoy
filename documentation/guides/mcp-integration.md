# MCP (Model Context Protocol) Integration

## Overview

The Deakins Forums scraper is now **MCP-compliant**, meaning it can be called identically by:
- Human users via CLI
- AI agents (like Claude) via prompting
- MCP agent hierarchies in multi-agent systems
- Programmatic API calls

The interface is **consistent across all invocation methods**.

## MCP Tools Available

### 1. `scrape_deakins_forum`

Scrape a forum with full query provenance tracking.

**Input Schema:**
```json
{
  "forum_slug": "forum|camera|team-deakins|post|composition|film-talk|set-talk|still-photography",
  "max_topics": 1000,
  "query_name": "Research query name",
  "querier_role": "Role (e.g., 'Director', 'DP', 'Studio Head')",
  "querier_department": "Department (e.g., 'Camera', 'Executive')",
  "query_context": "Context (e.g., 'Feature film development')",
  "query_intent": "What specific information is being sought",
  "build_index": true
}
```

**Output:**
```json
{
  "success": true,
  "query_id": "director_2026-01-15T10-01-51",
  "forum": "camera",
  "topics_scraped": 30,
  "topics_accessed": 30,
  "topics_newly_scraped": 5,
  "topics_revisited": 25,
  "posts_indexed": 850
}
```

### 2. `get_coverage_report`

Get current forum coverage statistics.

**Input Schema:**
```json
{
  "format": "full|quick"
}
```

**Output:**
```json
{
  "timestamp": "2026-01-15T10:20:15",
  "overall_coverage_percent": 85.5,
  "total_forums": 8,
  "topics_scraped": 305,
  "total_topics": 356,
  "total_posts": 950,
  "forums": {
    "camera": {
      "name": "Camera",
      "coverage_percent": 85.0,
      "topics_scraped": 27,
      "total_topics": 32,
      "posts": 105
    }
  }
}
```

### 3. `get_provenance_report`

Get query provenance/lineage report.

**Input Schema:**
```json
{
  "topic": "camera__eyes-wide-shut-moving-mirror",  // optional
  "query_id": "director_2026-01-15T10-01-51"        // optional
}
```

**Output:**
```json
{
  "total_queries": 28,
  "unique_topics_accessed": 305,
  "queries": { /* query metadata */ },
  "topic_access_index": { /* topic → accesses mapping */ }
}
```

## Usage Examples

### CLI Usage

```bash
# Scrape with query tracking
./venv/bin/python -m deakins_forums.cli scrape-forum camera \
  --max-topics 40 \
  --query-name "Lens choices for indie drama" \
  --querier-role "Director of Photography" \
  --querier-department "Camera" \
  --query-context "Indie feature pre-production" \
  --query-intent "Research vintage lens aesthetics for period-appropriate look"

# Get coverage report
./venv/bin/python -m deakins_forums.cli coverage --format full

# Get provenance report
./venv/bin/python -m deakins_forums.cli provenance
./venv/bin/python -m deakins_forums.cli provenance --topic "camera__barrel-distortion"
```

### MCP Server Usage

Start the MCP server:
```bash
python -m deakins_forums.mcp_server
```

The server accepts JSON-RPC requests on stdin:

```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "tools/call",
  "params": {
    "name": "scrape_deakins_forum",
    "arguments": {
      "forum_slug": "camera",
      "max_topics": 40,
      "query_name": "Lens choices for indie drama",
      "querier_role": "Director of Photography",
      "querier_department": "Camera",
      "query_context": "Indie feature pre-production",
      "query_intent": "Research vintage lens aesthetics"
    }
  }
}
```

### Programmatic Usage (Python)

```python
from deakins_forums.mcp_server import MCPServer

server = MCPServer()

# Call tool
result = server.call_tool(
    tool_name="scrape_deakins_forum",
    arguments={
        "forum_slug": "camera",
        "max_topics": 40,
        "query_name": "Lens choices for indie drama",
        "querier_role": "Director of Photography",
        "querier_department": "Camera",
        "query_context": "Indie feature pre-production",
        "query_intent": "Research vintage lens aesthetics"
    }
)

print(result)
```

## Multi-Agent Hierarchy Example

### Studio Head → Production Executives → Production Companies

```
Studio Head (Agent)
  ├─> VP of Cinematography (Agent)
  │     ├─> Action/Thriller DP (Agent) → scrape_deakins_forum(lighting)
  │     └─> Documentary DP (Agent) → scrape_deakins_forum(camera)
  │
  ├─> SVP of Post Production (Agent)
  │     ├─> Genre Colorist (Agent) → scrape_deakins_forum(post)
  │     └─> DIT (Agent) → scrape_deakins_forum(post)
  │
  └─> Chief Creative Officer (Agent)
        ├─> Director (Agent) → scrape_deakins_forum(composition)
        └─> Showrunner (Agent) → scrape_deakins_forum(film-talk)
```

Each agent calls the same MCP tool interface:
- **Studio Head** coordinates the hierarchy
- **Production Executives** supervise domain-specific research
- **Production Companies** execute specific queries

**All queries are tracked** with full provenance showing the organizational hierarchy.

## Provenance Tracking Benefits

1. **Research Lineage:** Know who accessed what and when
2. **Cross-Departmental Overlap:** Identify collaboration patterns
3. **Audit Trail:** Complete history of research activity
4. **Content Reuse:** Track which topics are revisited vs newly scraped
5. **Organizational Intelligence:** See how research flows through company hierarchy

## Interface Consistency Guarantee

The scraper **behaves identically** whether called by:
- ✅ CLI command line arguments
- ✅ AI agent prompting (like Claude)
- ✅ MCP JSON-RPC protocol
- ✅ Direct Python API calls
- ✅ Multi-agent hierarchies

**Same input → Same output → Same provenance tracking**

## Example: Studio-Wide 100% Coverage Initiative

```python
# Studio Head coordinates comprehensive research
studio_queries = [
    {
        "role": "VP of Cinematography",
        "forum": "forum",
        "max_topics": 100,
        "intent": "Complete lighting knowledge base"
    },
    {
        "role": "SVP Camera & Lens",
        "forum": "camera",
        "max_topics": 40,
        "intent": "Complete camera technology survey"
    },
    # ... more queries
]

for query in studio_queries:
    result = server.call_tool(
        "scrape_deakins_forum",
        arguments={
            "forum_slug": query["forum"],
            "max_topics": query["max_topics"],
            "query_name": f"Studio initiative - {query['intent']}",
            "querier_role": query["role"],
            "querier_department": "Executive",
            "query_context": "Studio-wide 100% coverage initiative",
            "query_intent": query["intent"]
        }
    )
```

After all queries complete:
```python
# Get final coverage
coverage = server.call_tool("get_coverage_report", {"format": "full"})
print(f"Coverage: {coverage['overall_coverage_percent']}%")

# Get provenance
provenance = server.call_tool("get_provenance_report", {})
print(f"Total queries: {provenance['total_queries']}")
print(f"Topics accessed: {provenance['unique_topics_accessed']}")
```

## Future Enhancements

Potential additions to the MCP interface:
- Streaming progress updates during scraping
- Batch query submission
- Query scheduling and prioritization
- Real-time collaboration detection
- Department-level analytics
- Coverage gap analysis

---

**Status:** ✅ MCP-compliant and production-ready
**Last Updated:** 2026-01-15
**Interface Version:** 1.0
