#!/usr/bin/env bash
# enable-deployment-protection.sh — Enable Vercel Deployment Protection on all org projects.
#
# Requires:
#   VERCEL_TOKEN  — a Vercel personal/team token with project-settings access
#   jq            — JSON processor (brew install jq)
#
# Usage:
#   VERCEL_TOKEN=<token> bash scripts/ci-hardening/enable-deployment-protection.sh
#
# Idempotent — safe to re-run for compliance checks.
# If the Vercel plan does not support the deploymentProtection API field,
# the script prints dashboard instructions instead.

set -euo pipefail

TEAM_ID="team_f3IAKsJ4bSJyzzmDOTI1FMct"
API_BASE="https://api.vercel.com"

if [[ -z "${VERCEL_TOKEN:-}" ]]; then
  echo "ERROR: VERCEL_TOKEN env var is required." >&2
  echo "Get one from: https://vercel.com/account/tokens" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required. Install with: brew install jq" >&2
  exit 1
fi

AUTH="Authorization: Bearer $VERCEL_TOKEN"

echo "Fetching projects for team $TEAM_ID..."
projects_json=$(curl -sf -H "$AUTH" "$API_BASE/v9/projects?teamId=$TEAM_ID&limit=100")

if [[ -z "$projects_json" ]] || ! echo "$projects_json" | jq -e '.projects' &>/dev/null; then
  echo "ERROR: Failed to fetch projects. Check your VERCEL_TOKEN and team ID." >&2
  exit 1
fi

project_count=$(echo "$projects_json" | jq '.projects | length')
echo "Found $project_count projects."
echo ""

# ── Phase 1: Enable deployment protection ──────────────────────────────────

echo "Enabling Standard Protection (production) on each project..."
echo "─────────────────────────────────────────────────────────────"

failed=0

echo "$projects_json" | jq -r '.projects[] | .id + "\t" + .name' | while IFS=$'\t' read -r id name; do
  response=$(curl -sf -X PATCH \
    -H "$AUTH" \
    -H "Content-Type: application/json" \
    -d '{
      "security": {
        "deployment_protection": {
          "prod_deployment": "standard_protection"
        }
      }
    }' \
    "$API_BASE/v9/projects/$id?teamId=$TEAM_ID" 2>&1) || true

  if echo "$response" | jq -e '.id' &>/dev/null; then
    echo "  ✓ $name"
  else
    error_code=$(echo "$response" | jq -r '.error.code // "unknown"' 2>/dev/null || echo "unknown")
    if [[ "$error_code" == "forbidden" ]] || [[ "$error_code" == "plan_limit" ]]; then
      echo "  ✗ $name — plan may not support Deployment Protection API"
      failed=1
    else
      echo "  ✗ $name — $error_code"
      failed=1
    fi
  fi
done

echo ""

# ── Phase 2: Verify ───────────────────────────────────────────────────────

echo "Verifying deployment protection status..."
echo "─────────────────────────────────────────────────────────────"
printf "%-30s %s\n" "PROJECT" "PROTECTION"
printf "%-30s %s\n" "───────" "──────────"

echo "$projects_json" | jq -r '.projects[] | .id + "\t" + .name' | while IFS=$'\t' read -r id name; do
  proj_json=$(curl -sf -H "$AUTH" "$API_BASE/v9/projects/$id?teamId=$TEAM_ID" 2>/dev/null || echo "{}")
  protection=$(echo "$proj_json" | jq -r '.security.deployment_protection.prod_deployment // "not set"' 2>/dev/null || echo "unknown")
  printf "%-30s %s\n" "$name" "$protection"
done

echo ""

if [[ "$failed" -ne 0 ]]; then
  echo "Some projects could not be configured via API."
  echo ""
  echo "Dashboard fallback — for each project:"
  echo "  1. Go to https://vercel.com/<project>/settings/deployment-protection"
  echo "  2. Under Production, enable 'Standard Protection'"
  echo "  3. Under Preview, enable 'Vercel Authentication'"
  echo "  4. Save"
fi
