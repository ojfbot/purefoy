# ADR-001: HTTP Client — `requests` (current) vs `httpx` (template target)

**Status:** Accepted (defer migration)
**Date:** 2026-02-27
**Deciders:** Jim Green

---

## Context

The Frame OS `python-scraper` canonical template (`node-template/domain-knowledge/app-templates.md`)
specifies `httpx>=0.27` as the HTTP client. Purefoy was built before that template was formalised
and uses `requests>=2.32.0` throughout `HttpClient` (`deakins_forums/http_client.py`).

`httpx` offers async-first design, HTTP/2 support, and tighter typing, which would be valuable if
the MCP server ever needs to make concurrent scrape requests. `requests` is synchronous-only and
has weaker type stubs.

## Decision

**Keep `requests` for now.** Migrate to `httpx` as a standalone task when Phase 2 work touches
`http_client.py` for other reasons (e.g. adding concurrent topic fetching).

## Rationale

- `HttpClient` is ~200 lines of working production code. A swap is a real migration, not a config change.
- All 3,000+ posts were scraped successfully with the current client; there is no functional gap.
- The scraper is synchronous by design (rate-limited 3 s delay between requests). Async provides no
  immediate benefit.
- mypy stubs for `requests` (`types-requests`) are now in dev deps, so type coverage is achievable
  without the migration.

## Consequences

- CI type checks install `types-requests` to provide stubs for mypy.
- When `http_client.py` is next touched for a feature reason, evaluate httpx migration at that point.
- `deakins_forums.http_client` is in the mypy `ignore_errors` override list until the migration lands
  (see `ADR-002`).

## Migration path (when ready)

1. Replace `import requests` → `import httpx` in `http_client.py`.
2. Replace `requests.Session` → `httpx.Client` (sync) or `httpx.AsyncClient` (async).
3. Update `pyproject.toml` dependencies: swap `requests>=2.32.0` for `httpx>=0.27`.
4. Remove `types-requests` from dev deps (httpx ships its own stubs).
5. Remove `deakins_forums.http_client` from mypy `ignore_errors` overrides.
