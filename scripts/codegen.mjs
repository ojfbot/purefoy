#!/usr/bin/env node
/**
 * pnpm codegen — Full type generation pipeline.
 *
 * Steps:
 *   1. Run scripts/generate_schema.py → openapi.json
 *   2. Run openapi-typescript openapi.json → packages/shared/src/generated/schema.ts
 *
 * Usage:
 *   pnpm codegen
 *
 * Prerequisites:
 *   - Python env with deakins_forums installed (source .venv/bin/activate OR use python3.13)
 *   - openapi-typescript installed (pnpm add -D openapi-typescript --filter @purefoy/shared)
 *   - Run from repo root
 *
 * When to run:
 *   - After any change to deakins_forums/models.py
 *   - After any change to scripts/tools/transcribe_episodes.py dataclasses
 *   - Commit openapi.json and packages/shared/src/generated/schema.ts together
 */

import { execSync } from 'child_process'
import { existsSync } from 'fs'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(__dirname, '..')
const OPENAPI_PATH = resolve(REPO_ROOT, 'openapi.json')
const GENERATED_OUT = resolve(REPO_ROOT, 'packages/shared/src/generated/schema.ts')

function run(cmd, label) {
  console.log(`\n→ ${label}`)
  try {
    execSync(cmd, { cwd: REPO_ROOT, stdio: 'inherit' })
  } catch (e) {
    console.error(`✗ ${label} failed`)
    process.exit(1)
  }
}

// Step 1 — Python schema export
// Try .venv first (installed env), fall back to system python3
const pythonBin = existsSync(resolve(REPO_ROOT, '.venv/bin/python3'))
  ? '.venv/bin/python3'
  : 'python3'

run(
  `${pythonBin} scripts/generate_schema.py`,
  'Python schema export (Pydantic → openapi.json)'
)

if (!existsSync(OPENAPI_PATH)) {
  console.error('✗ openapi.json not found after generate_schema.py — aborting')
  process.exit(1)
}

// Step 2 — openapi-typescript
// Installed as devDep of @purefoy/shared — run via pnpm exec from its package dir
run(
  `pnpm --filter @purefoy/shared exec openapi-typescript ${OPENAPI_PATH} -o ${GENERATED_OUT}`,
  `openapi-typescript → ${GENERATED_OUT.replace(REPO_ROOT + '/', '')}`
)

console.log('\n✓ codegen complete')
console.log('  Commit openapi.json and packages/shared/src/generated/schema.ts together.')
