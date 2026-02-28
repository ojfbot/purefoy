# ADR-003: MCP stdio as the AI Integration Path (not REST API / LangGraph)

**Status:** Accepted
**Date:** 2026-02-27
**Deciders:** Jim Green

---

## Context

Purefoy will integrate into Frame OS as a remote at `purefoy.jim.software` (port 3020). The other
Frame sub-apps (cv-builder, BlogEngine, TripPlanner) expose REST APIs and use LangGraph agent graphs
for AI orchestration — domain intelligence is routed through `frame-agent`.

Purefoy is fundamentally different: it is a **knowledge base**, not a productivity app. Its value
is in the data it stores, not in interactive user sessions. The question was: how should Claude Code
(and eventually frame-agent) consume purefoy's data?

Three options were evaluated:

| Option | Pros | Cons |
|--------|------|------|
| REST API (Express/FastAPI) | Consistent with other sub-apps | Adds a web server to a CLI tool; forces containerisation early |
| LangGraph agent | Consistent with Frame AI pattern | Heavyweight for a read-only knowledge store; no user session needed |
| MCP stdio server | Zero infrastructure; Claude reads leaves directly; provenance-first | Not HTTP-native; requires Claude Code or MCP-compatible client |

## Decision

**Use MCP stdio** (`deakins_forums/mcp_server.py`) as the primary AI integration path.

The MCP server exposes three tools:
- `scrape_deakins_forum` — trigger scraping with query provenance
- `get_coverage_report` — coverage stats
- `get_provenance_report` — research lineage audit

## Rationale

- Purefoy's leaf files are already agent-friendly JSON — Claude can read them directly without
  a retrieval API layer.
- MCP is the Frame OS pattern for Python tools (per `app-templates.md` python-scraper template).
- A REST server would require authentication, containerisation, and a port allocation — none of
  which add value at this stage of the roadmap.
- The Module Federation remote at port 3020 (per `frame-os-context.md`) will be a thin React UI
  that reads leaf files or calls the MCP server, added in a future phase.

## Consequences

- `mcp_server.py` is the primary integration surface; it must be tested before Phase 2 declares
  MCP "operational".
- When Frame OS Phase 3 (cross-domain coordination) requires purefoy data in frame-agent, the
  preferred path is frame-agent calling the MCP server tools, not a direct REST call.
- A REST API may be added in Phase 4+ if the Module Federation remote needs it; this decision does
  not preclude that.
