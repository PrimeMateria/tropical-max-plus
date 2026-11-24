#!/usr/bin/env bash
# Install the ADR-0034 pre-commit gate for the tropical router repository.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SOURCE="$SCRIPT_DIR/.githooks/pre-commit"

if [[ ! -f "$HOOK_SOURCE" ]]; then
  echo "Missing hook source: $HOOK_SOURCE" >&2
  exit 1
fi

if [[ ! -d "$SCRIPT_DIR/.git" ]]; then
  echo "[ADR-0034] No .git directory at $SCRIPT_DIR; hook staged but not installed." >&2
  echo "[ADR-0034] Run this installer once the subsystem is a git work tree." >&2
  exit 0
fi

chmod +x "$HOOK_SOURCE"
cp "$HOOK_SOURCE" "$SCRIPT_DIR/.git/hooks/pre-commit"
chmod +x "$SCRIPT_DIR/.git/hooks/pre-commit"
echo "[ADR-0034] Installed pre-commit hook at .git/hooks/pre-commit"
