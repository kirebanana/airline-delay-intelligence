#!/usr/bin/env bash
# Compatibility alias for the former setup wizard; no browser/setup/secret writers.
set -euo pipefail
set +x
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$HERE/owner-plan.sh"
