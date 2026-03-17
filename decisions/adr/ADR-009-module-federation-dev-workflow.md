# ADR-009: Module Federation Dev Workflow

**Status:** Accepted — 2026-03-16
**Date:** 2026-03-16
**Deciders:** Jim Green

---

## Context

`@originjs/vite-plugin-federation` only generates `remoteEntry.js` on `vite build`, not on
`vite dev`. This is a known constraint across all Frame OS sub-apps (cv-builder, BlogEngine,
TripPlanner all hit this — see `shell/domain-knowledge/shell-mf-integration.md`).

Purefoy needs three distinct runtime modes:

1. **Standalone component dev** — fast HMR, no shell, no MF
2. **MF remote for shell** — built remote served at port 3020; shell connects
3. **Headless API** — API only, no browser-app; used by frame-agent in prod and testing

## Decision

Three dev entry points, one prod entry:

```
pnpm dev:app          → vite           (standalone, HMR, port 3020 via vite dev)
pnpm dev:app:mf       → vite build && vite preview  (MF remote for shell, port 3020)
pnpm dev:api          → tsx watch src/index.ts       (API only, port 3021)
pnpm dev:all          → concurrently dev:api + dev:app:mf  (full stack for shell)
pnpm dev:headless     → pnpm dev:api   (API only — frame-agent integration testing)

pnpm start:api        → node dist/index.js  (prod API, no UI)
```

### Which mode to use when

| Task | Command |
|---|---|
| Working on a React component in isolation | `pnpm dev:app` — fast HMR |
| Testing shell integration (purefoy tab in Frame) | `pnpm dev:all` — builds MF remote |
| Running frame-agent locally without UI | `pnpm dev:headless` |
| Production deployment (API only, MF served from CDN) | `pnpm start:api` |
| Production deployment (full stack) | `pnpm build && pnpm start:api` (API) + serve `dist/` from CDN |

### Why `vite build && vite preview` for MF mode (not `vite build --watch`)

`vite build --watch` re-triggers builds on file changes but does NOT serve the output —
a separate static file server is still needed. `vite preview` serves the `dist/` directory
on the configured port. Therefore `vite build && vite preview` is the minimal working chain.

The rebuild on file change limitation (no watch mode + preview restart) is acceptable
because MF integration testing is a less frequent activity than component development.
Use `pnpm dev:app` (standalone HMR) for iteration speed.

## `vite.config.ts` — standalone vs MF mode

Standalone `vite dev` runs without the MF federation plugin actively generating remotes.
The shared singleton map in the federation config is still present — this is harmless in
dev mode as the shared libraries resolve normally.

The `cssInjectedByJs` plugin is also harmless in standalone mode — it processes CSS as
expected.

## Consequences

**Positive:**
- Same pattern as cv-builder/BlogEngine/TripPlanner — no new concepts for Frame OS engineers
- Fast component iteration via standalone mode
- Clean headless mode for frame-agent CI tests

**Negative:**
- No hot-reload for MF integration testing — must run `pnpm dev:app:mf` after each change
  (which rebuilds and restarts preview server). This is a vite-plugin-federation constraint.

## Port assignments

| Port | Service |
|---|---|
| 3020 | browser-app (vite dev standalone OR vite preview MF remote) |
| 3021 | api (Express) |
| 4000 | shell (Frame OS host) |
