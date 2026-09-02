#!/usr/bin/env bash
# Point git at the versioned hooks in .githooks/ (run once per clone).
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
chmod +x .githooks/* scripts/*.py scripts/*.sh 2>/dev/null || true
git config core.hooksPath .githooks
echo "core.hooksPath -> .githooks"
python3 scripts/update_project_state.py
echo "done. every commit now refreshes docs/PROJECT_STATE.md"
