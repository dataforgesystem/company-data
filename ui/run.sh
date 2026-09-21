#!/usr/bin/env bash
# Launches the Chainlit chat UI from inside this folder.
#
# Chainlit resolves its app root (chainlit.md, .chainlit/, .files/) from
# CHAINLIT_APP_ROOT, defaulting to the current directory. Pointing it at ui/
# keeps every UI artifact inside this folder, so removing the UI is a single
# `rm -rf ui/` and the repository root stays clean.
set -euo pipefail

cd "$(dirname "$0")"
export CHAINLIT_APP_ROOT="$PWD"

# Prefer this repository's virtualenv (where the project deps live), then an
# activated/PATH install. CHAINLIT_BIN overrides both.
if [ -n "${CHAINLIT_BIN:-}" ]; then
    chainlit_bin="$CHAINLIT_BIN"
elif [ -x ../.venv/bin/chainlit ]; then
    chainlit_bin="../.venv/bin/chainlit"
else
    chainlit_bin="chainlit"
fi

exec "$chainlit_bin" run app.py "$@"
