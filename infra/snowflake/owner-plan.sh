#!/usr/bin/env bash
# Prepared for the owner's already-confirmed November 4 SQL/profile setup.
set -euo pipefail
set +x
umask 077
if compgen -G "$HOME/.local/state/airline-user-adoption-bootstrap-*/verification-*/apply-started.json" >/dev/null; then
  echo "Adoption was already attempted. Do not rerun bootstrap; review the saved outcome and docs/snowflake-owner-adoption.md."
  exit 1
fi
[[ -t 0 ]] || { echo "Run in your own interactive terminal; never send a password to the agent." >&2; exit 1; }
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd -- "$HERE/../.." && pwd)"
OUTPUT="$HOME/.local/state/airline-user-adoption-bootstrap-$(date -u +%Y%m%dT%H%M%SZ)"
echo "Your confirmed owner SQL/profile setup is accepted; no worksheet steps to repeat."
echo "This command prepares and reviews a plan only. It cannot apply or change Snowflake objects."
exec "$PROJECT/.venv/bin/python" "$HERE/plan_user_adoption.py" "$OUTPUT" \
  --owner-preflight-confirmed --verified-bootstrap --prompt-owner-password \
  --terraform /tmp/opencode/airline-tools/terraform
