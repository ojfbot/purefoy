# ADR-007: OpenAPI Schema Generation — Python → JSON Schema → TypeScript

**Status:** Accepted — pipeline scaffolded 2026-03-16
**Date:** 2026-03-16
**Deciders:** Jim Green

---

## Context

The project has two schema sources in Python:

1. **`deakins_forums/models.py`** — Pydantic v2 `BaseModel` classes (PostLeaf, TopicLeaf,
   ForumLeaf, etc.)
2. **`scripts/tools/transcribe_episodes.py`** — stdlib `@dataclass` classes (SegmentResult,
   ChapterResult, ExtractionReport, etc.)

The Node.js API (`packages/api`) reads files produced by these Python classes. Without a
formal type sync mechanism, the TypeScript types would be hand-maintained and would drift
whenever Python models change.

## Decision

**Python → OpenAPI JSON → TypeScript via `openapi-typescript`**

Pipeline (run via `pnpm codegen`):

```
deakins_forums/models.py              ─┐
  .model_json_schema()                 │→ scripts/generate_schema.py → openapi.json
scripts/tools/transcribe_episodes.py  ─┘   (hand-maintained schemas for dataclasses)
                                              ↓
                                        openapi-typescript
                                              ↓
                              packages/shared/src/generated/schema.ts
```

**What goes where:**

| File | Source | Edit policy |
|---|---|---|
| `openapi.json` | `pnpm codegen` step 1 | Never edit manually — committed, regenerated on model change |
| `packages/shared/src/generated/schema.ts` | `pnpm codegen` step 2 | Never edit manually — committed |
| `packages/shared/src/api-types.ts` | Hand-written | HTTP envelope types (pagination, query params) — no Python counterpart |
| `packages/api/src/types.ts` | Hand-written | API response shapes (computed aggregations not in raw Python data) |

**Trigger:** Run `pnpm codegen` and commit both `openapi.json` and `schema.ts` when:
- Any field is added/removed/renamed in `deakins_forums/models.py`
- Any dataclass field changes in `scripts/tools/transcribe_episodes.py`
- Pipeline version bumps to a new schema version

## Alternatives considered

| Option | Rejected because |
|---|---|
| Full FastAPI app to generate OpenAPI | Requires writing HTTP routes for a read-only schema — all overhead, no benefit |
| `datamodel-code-generator` (reverse: JSON → Pydantic) | Wrong direction — Python is source of truth |
| Manual TypeScript types only | Already causes drift; TS types were hand-written in scaffold and will diverge |
| `pydantic-to-typescript` | Uses `ts-json-schema-generator` — limited Pydantic v2 support |
| `json-schema-to-typescript` | Alternative to `openapi-typescript`; both work; chose `openapi-typescript` for ecosystem familiarity |

## Dataclass limitation

`scripts/tools/transcribe_episodes.py` uses stdlib `@dataclass`, not `pydantic.dataclasses`.
These do not have `.model_json_schema()`. The schemas for transcript types are **hand-maintained**
in `scripts/generate_schema.py → transcript_dataclass_schemas()`.

**Future improvement:** Migrate `transcribe_episodes.py` to `pydantic.dataclasses` so both
sources are auto-generated. Low priority — transcript schema is stable post-v2.0.0.

## CI guard

Add a CI check step (not yet implemented) that:
1. Runs `pnpm codegen`
2. Fails if `openapi.json` or `schema.ts` has uncommitted changes

This ensures PRs that change Python models also regenerate the TS types.

```yaml
# TODO: add to .github/workflows/ci.yml
- name: Check schema codegen is up to date
  run: |
    pnpm codegen
    git diff --exit-code openapi.json packages/shared/src/generated/schema.ts
```
