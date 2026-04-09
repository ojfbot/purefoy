#!/usr/bin/env zsh
# vercel-prod-guard.zsh — Blocks local `vercel deploy --prod` commands.
#
# Source this from ~/.zshrc:
#   source ~/ojfbot/purefoy/scripts/ci-hardening/vercel-prod-guard.zsh
#
# Production deploys must go through GitHub Actions CI.
# The `command vercel` escape hatch exists for genuine emergencies.
#
# Recommended: also create a dedicated CI token in Vercel Dashboard
# (Account Settings > Tokens > "ojfbot-ci-deploy") and rotate VERCEL_TOKEN
# in all GitHub repo secrets to use it. Never store the CI token locally.

vercel() {
  if [[ "$*" == *"--prod"* ]] && [[ -z "$CI" ]] && [[ -z "$GITHUB_ACTIONS" ]]; then
    echo "ERROR: Production deploys must go through CI." >&2
    echo "Push to main and let GitHub Actions handle it." >&2
    echo "" >&2
    echo "To force (emergency only): command vercel $*" >&2
    return 1
  fi
  command vercel "$@"
}
