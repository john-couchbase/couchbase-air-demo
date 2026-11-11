#!/usr/bin/env bash
# Build the web app, then serve the API and the built app together on :8010.
#
# Run this from a terminal you own, not from an editor's preview/launch
# manager. A process the editor started is one the editor can reap, and in the
# AIDP Financial demo it did, mid-demo, with nothing in the logs. The Vite dev
# server on :5174 is for editing only; never present from it.
#
# Always rebuilds first: presenting a days-old web/dist is the other way this
# goes wrong. No --reload, so a stray file save cannot restart the server live.
#
# AIDP_ENV=sandbox-local is the sandbox-like local mode: it also starts the
# Model Service stand-in (aidpair/gateway.py) on :8020 with the GATEWAY_*
# settings from .env.sandbox-local, points the ai_completion UDF at it, and
# stops it again when the demo stops. See the README, "Sandbox-like local mode".
set -euo pipefail
cd "$(dirname "$0")/.."
npm run build --prefix web

if [ "${AIDP_ENV:-}" = "sandbox-local" ]; then
  ENVF=.env.sandbox-local
  [ -f "$ENVF" ] || { echo "$ENVF is missing: cp .env.sandbox-local.example $ENVF"; exit 1; }
  # A setting's value, with any trailing "# comment" and spaces removed.
  setting() { grep -E "^$1=" "$ENVF" | tail -1 | cut -d= -f2- | sed -E 's/[[:space:]]*#.*$//' || true; }
  # The gateway reads only GATEWAY_* settings, from the environment.
  for name in $(grep -oE '^GATEWAY_[A-Z_]+' "$ENVF" || true); do export "$name=$(setting "$name")"; done
  .venv/bin/python -m uvicorn aidpair.gateway:app --host 0.0.0.0 --port 8020 --log-level warning &
  GW=$!
  trap 'kill $GW 2>/dev/null' EXIT
  for _ in $(seq 1 30); do curl -s -o /dev/null localhost:8020/stats && break; sleep 0.5; done
  echo "gateway stand-in on :8020: $(curl -s localhost:8020/stats)"
  if [ "$(setting CLASSIFY_VIA)" = "sqlpp" ]; then
    FLAGS="--gateway"
    [ "$(setting SANDBOX_AI_FUNCTIONS_USE_CACHE)" = "false" ] && FLAGS="$FLAGS --skip-cache"
    .venv/bin/python scripts/local_ai_functions.py $FLAGS
  fi
  # Not exec: the trap has to outlive uvicorn to stop the gateway with it.
  .venv/bin/python -m uvicorn aidpair.api:app --host 127.0.0.1 --port "${PORT:-8010}"
  exit
fi

exec .venv/bin/python -m uvicorn aidpair.api:app --host 127.0.0.1 --port "${PORT:-8010}"
