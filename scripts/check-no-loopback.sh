#!/usr/bin/env sh
# check-no-loopback.sh
# Fails if a browser bundle contains a loopback URL. A public page that fetches
# localhost triggers the browser's Local Network Access prompt for every
# visitor, so dev-only defaults must sit behind import.meta.env.DEV.
#
# Used by: .github/workflows/ci.yml (after building browser-app)
# Usage:   sh scripts/check-no-loopback.sh [dist-dir ...]

DIRS="${*:-packages/browser-app/dist}"

for dir in $DIRS; do
  if [ ! -d "$dir" ]; then
    echo "❌ $dir not found — run pnpm build first"
    exit 1
  fi
done

# Requires a port (or a template-literal port) after the host: real API
# defaults always carry one, while libraries such as axios use a bare
# 'http://localhost' only as a URL-parsing base and never fetch it.
# shellcheck disable=SC2086
HITS=$(grep -rnoE --include='*.js' --include='*.html' \
  'https?://(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]):' $DIRS || true)

if [ -n "$HITS" ]; then
  echo ""
  echo "❌ LOOPBACK URL IN BROWSER BUNDLE"
  echo "$HITS" | cut -c1-200
  echo ""
  echo "Gate the default behind import.meta.env.DEV (empty in prod = no API configured)."
  exit 1
fi

echo "✅ No loopback URLs in $DIRS"
