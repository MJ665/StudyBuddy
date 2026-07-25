#!/usr/bin/env bash
# Push every variable from .env.vercel into your Vercel project (Production +
# Preview). Reads the gitignored .env.vercel, so this script holds NO secrets.
#
# Prereqs (once):
#   npm i -g vercel        # or: npx vercel@latest ...
#   cd apps/web-next && vercel link      # link this dir to your Vercel project
#
# Run:
#   cd apps/web-next && bash push-vercel-env.sh
#
# Re-runnable: --force overwrites existing values.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=".env.vercel"
[ -f "$ENV_FILE" ] || { echo "❌ $ENV_FILE not found (are you in apps/web-next?)"; exit 1; }

TARGETS=("production" "preview")

while IFS= read -r line || [ -n "$line" ]; do
  # skip blanks + comments
  case "$line" in ''|\#*) continue ;; esac
  key="${line%%=*}"
  val="${line#*=}"
  key="$(printf '%s' "$key" | xargs)"   # trim whitespace
  [ -z "$key" ] && continue
  for t in "${TARGETS[@]}"; do
    printf '%s' "$val" | vercel env add "$key" "$t" --force >/dev/null 2>&1 \
      && echo "✅ $key → $t" \
      || echo "⚠️  $key → $t (check: is the dir linked with 'vercel link'?)"
  done
done < "$ENV_FILE"

echo "Done. Redeploy for the new vars to take effect:  vercel --prod"
