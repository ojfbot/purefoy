# Implementation notes

## Deviations

- 2026-10-01 (no loopback in prod): plan treated every Frame remote as frontend-only in prod; territory: purefoy has a real prod backend — `VITE_API_URL` is set on the Vercel project to `https://tde.jim.software` (verified in the live purefoy.jim.software bundle). Kept that path unchanged; only the unset fallback became dev-only. The leaking default in prod was `VITE_FRAME_AGENT_URL` → `localhost:4001` (chat), now empty in prod ⇒ "Agent not configured" instead of a loopback fetch.
- 2026-10-01 (no loopback in prod): plan said add the guard after `pnpm build` in ci.yml; territory: ci.yml never builds the browser-app (only type-check + API tests). Added an explicit `pnpm --filter @purefoy/browser-app build` step before `pnpm check:no-loopback` in the ts-typecheck job.
