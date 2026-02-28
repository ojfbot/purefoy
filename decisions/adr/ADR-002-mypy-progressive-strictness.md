# ADR-002: mypy — Progressive Strictness via Per-Module Overrides

**Status:** Accepted
**Date:** 2026-02-27
**Deciders:** Jim Green

---

## Context

The Frame OS coding standards require `strict = true` mypy for all projects. Purefoy has 9 modules
with existing type errors (82 errors across `normalize`, `pipeline`, `parser_bbpress`, etc.) that
predate the mypy requirement. Running `mypy --strict` on the full package would block CI immediately.

## Decision

Use **per-module `ignore_errors = true` overrides** in `pyproject.toml` as a progressive strictness
baseline. CI passes from day one. Each module override is an explicit tech debt item — removing an
entry from the list is the signal that the module is clean.

Modules currently in the override list (as of 2026-02-27):

| Module | Primary error type |
|--------|--------------------|
| `coverage` | Return type annotations missing |
| `export` | Untyped function arguments |
| `http_client` | `requests` type stubs gaps (see ADR-001) |
| `index_sqlite` | sqlite3 result type narrowing |
| `normalize` | `bs4.AttributeValueList` vs `str` mismatches |
| `parser_bbpress` | Complex bs4 return types |
| `parser_blog` | Untyped list comprehensions |
| `pipeline` | `dateutil` import-untyped, Literal narrowing |
| `reply_tree` | Recursive dict type annotations |

## Rationale

- A failing CI is worse than a lenient CI — it stops the PR workflow entirely.
- Named overrides are explicit and reviewable; a blanket `# mypy: ignore` in source is invisible.
- This is the same pattern used by large Python projects (e.g. Pydantic itself during v2 migration).

## Consequences

- New modules written from this point forward must pass mypy without an override entry.
- `/validate` checks that the override list is not growing.
- Target: zero override entries by Phase 3 (when MCP server and cross-reference work require solid typing).

## Exit criteria per module

Remove a module from the override list when:
1. `mypy deakins_forums/<module>.py --ignore-missing-imports` reports zero errors.
2. PR description notes the removal explicitly.
