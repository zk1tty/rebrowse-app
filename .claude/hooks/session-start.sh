#!/bin/bash
# SessionStart hook: install backend (api/), frontend (ui/) and extension deps
# so linters, tests and dev servers work in Claude Code on the web.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# --- Backend (FastAPI, Python 3.11) ---
cd "$ROOT/api"
[ -d .venv ] || uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python ruff pytest pytest-asyncio httpx
# Match the pre-installed browsers in /opt/pw-browsers (Playwright 1.56 / chromium-1194)
# so no browser download is needed. Local/Docker installs are unaffected.
uv pip install --python .venv/bin/python "playwright==1.56.0" "patchright==1.56.0"

# --- Frontend (Vite + React) ---
# postinstall generates src/lib/api/apigen.d.ts from the committed openapi.json.
cd "$ROOT/ui"
npm install --no-audit --no-fund

# --- Chrome extension (WXT) ---
cd "$ROOT/extension"
npm install --no-audit --no-fund

# Persist env for the session
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$ROOT/api/.venv/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
  echo "export VIRTUAL_ENV=\"$ROOT/api/.venv\"" >> "$CLAUDE_ENV_FILE"
  echo "export PYTHONPATH=\"$ROOT/api${PYTHONPATH:+:$PYTHONPATH}\"" >> "$CLAUDE_ENV_FILE"
fi
