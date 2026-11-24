#!/usr/bin/env bash
# Convenience wrapper for the ADR-0034 authoritative verification runner.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/run_tests.py" "$@"
