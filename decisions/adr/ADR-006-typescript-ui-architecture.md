# ADR-006: TypeScript UI Architecture — pnpm Workspace + Node.js Filesystem Reader

**Status:** Accepted — scaffold committed 2026-03-16
**Date:** 2026-03-16
**Deciders:** Jim Green

---

## Context

Purefoy is a Python project producing a read-only flat-file JSON corpus (~347 episode dirs,
~278 forum posts, SQLite FTS5 index). We need a TypeScript browser UI to integrate with the
Frame OS shell (Module Federation at port 3020) and expose an HTTP API for the
`PurefoyDomainAgent` in frame-agent.

The Python codebase is a batch write system (transcription + scraping). The TypeScript layer
is a read-only consumer of Python-produced data.

## Decision

Add a **pnpm workspace** at the repo root alongside the existing Python code:

```
purefoy/                    ← repo root (Python + Node coexist)
├── packages/
│   ├── shared/             ← generated + hand-written shared types
│   ├── api/                ← Express, port 3021
│   └── browser-app/        ← React/Carbon, Vite MF remote, port 3020
├── package.json            ← pnpm workspace root
├── pyproject.toml          ← Python tooling (unchanged)
└── openapi.json            ← generated schema (committed)
```

The Node.js API (`packages/api`) reads the Python-produced data **directly from the
filesystem** — no Python process at API runtime, no inter-process communication.

Data access paths:
- `DOWNLOADS_DIR` → episode `metadata.json`, `run_manifest.json`, `extraction_report.json`, `chapters.json`, `transcript_segments.jsonl`
- `LIBRARY_DIR/forums/posts/` → forum `PostLeaf` JSON files
- `LIBRARY_DIR/forums/topics/` → forum `TopicLeaf` JSON files
- `LIBRARY_DIR/forums/_site/index.db` → SQLite FTS5 (opened read-only via `better-sqlite3`)

## Alternatives considered

| Option | Rejected because |
|---|---|
| FastAPI bridge (Python HTTP server) | Adds a Python process at runtime; requires Python env in production; complexity for a read-only use case |
| Node spawns Python subprocess per request | Per-request overhead; coupling; subprocess startup latency |
| Pure MCP stdio integration | MCP is for AI-to-tool calls; not suitable for a browser UI — no HTTP, no streaming, no pagination |
| Separate TypeScript repo | More operational overhead; cross-repo type sync harder; Frame OS convention is one repo per app |

## Consequences

**Positive:**
- Zero Python dependency at runtime — `pnpm start:api` runs with Node only
- Transcription batch can run in parallel without blocking the UI
- `better-sqlite3` gives synchronous FTS5 queries appropriate for read-only search
- Same pattern as other Frame OS sub-apps (cv-builder, BlogEngine, TripPlanner)

**Negative / risks:**
- Schema drift: Python data shapes can evolve without the TS types knowing. Mitigated by ADR-007 (openapi-typescript codegen).
- Episode list performance: 290+ episodes × 3 JSON reads = ~870 file reads per request. Mitigated by ADR-008 (startup cache).
- `better-sqlite3` requires native build — CI must have build tools. Use `--ignore-scripts` workaround if CI doesn't support native modules.

## Headless mode

The API can run without the browser-app (`pnpm dev:headless` / `pnpm start:api`).
This is the production path for frame-agent queries — the LLM calls the API directly,
the browser-app is only for human browsing.
