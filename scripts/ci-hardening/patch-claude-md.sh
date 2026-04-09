#!/usr/bin/env bash
# patch-claude-md.sh — Append the standard deployment rule to CLAUDE.md across all ojfbot repos.
#
# Usage:
#   bash scripts/ci-hardening/patch-claude-md.sh          # dry-run (default)
#   bash scripts/ci-hardening/patch-claude-md.sh --apply   # actually patch files
#
# Idempotent — skips repos that already have the rule.

set -euo pipefail

OJFBOT_ROOT="/Users/yuri/ojfbot"
DRY_RUN=true

if [[ "${1:-}" == "--apply" ]]; then
  DRY_RUN=false
fi

# Repos known to have Vercel deployments (excluding purefoy — already done)
REPOS=(
  shell
  cv-builder
  blogengine
  daily-logger
  TripPlanner
  gastown-pilot
  core-reader
  lean-canvas
  seh-study
)

DEPLOY_RULE='## Deployment

**NEVER deploy directly to production** via CLI (`vercel deploy --prod`, `vercel promote`, etc.).
All production deployments go through the GitHub PR → CI → merge → automated deploy pipeline.
The only exception is `workflow_dispatch` for manual CI triggers.
Local Vercel CLI usage is restricted to preview deploys only.'

patched=0
skipped=0
missing=0

for repo in "${REPOS[@]}"; do
  claude_md="$OJFBOT_ROOT/$repo/CLAUDE.md"

  if [[ ! -f "$claude_md" ]]; then
    echo "MISSING: $repo — no CLAUDE.md (create one manually if this is a Vercel app)"
    ((missing++))
    continue
  fi

  if grep -q "NEVER deploy directly to production" "$claude_md"; then
    echo "OK:      $repo — rule already present"
    ((skipped++))
    continue
  fi

  if $DRY_RUN; then
    echo "WOULD PATCH: $repo"
  else
    # Ensure trailing newline before appending
    [[ -z "$(tail -c 1 "$claude_md")" ]] || echo "" >> "$claude_md"
    echo "" >> "$claude_md"
    echo "$DEPLOY_RULE" >> "$claude_md"
    echo "PATCHED: $repo"
  fi
  ((patched++))
done

echo ""
echo "Summary: $patched patched, $skipped already present, $missing missing CLAUDE.md"

if $DRY_RUN && [[ $patched -gt 0 ]]; then
  echo ""
  echo "This was a dry run. Re-run with --apply to patch files:"
  echo "  bash scripts/ci-hardening/patch-claude-md.sh --apply"
fi
