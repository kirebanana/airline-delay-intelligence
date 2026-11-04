#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077
[[ -t 0 ]] || { echo "Run interactively in your own terminal; never send a password to the agent." >&2; exit 1; }
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd -- "$HERE/../.." && pwd)"
echo "Applying only the exact plan you approved (684434be...1df4626), then checking with the official provider."
echo "No setup questions to repeat. One hidden local password prompt; never paste it into chat."
exec "$PROJECT/.venv/bin/python" "$HERE/apply_user_adoption.py"
