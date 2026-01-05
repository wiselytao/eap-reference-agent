#!/usr/bin/env bash
set -euo pipefail

PIDFILE="${PIDFILE:-data/ra.pid}"
LOGFILE="${LOGFILE:-data/ra.log}"

mkdir -p "$(dirname "$PIDFILE")"
mkdir -p "$(dirname "$LOGFILE")"

if [[ -f "$PIDFILE" ]]; then
  if kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Reference Agent already running (pid $(cat "$PIDFILE"))."
    exit 0
  fi
  rm -f "$PIDFILE"
fi

if [[ -f ".env.local" ]]; then
  set -a
  . ./.env.local
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

nohup "$PYTHON_BIN" -m reference_agent.main >"$LOGFILE" 2>&1 &
echo $! >"$PIDFILE"
echo "Reference Agent started (pid $!). Logs: $LOGFILE"
