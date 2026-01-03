#!/usr/bin/env bash
set -euo pipefail

PIDFILE="${PIDFILE:-data/ra.pid}"

if [[ ! -f "$PIDFILE" ]]; then
  echo "No PID file found: $PIDFILE"
  exit 0
fi

PID="$(cat "$PIDFILE")"
if ! kill -0 "$PID" 2>/dev/null; then
  echo "Process not running (pid $PID)."
  rm -f "$PIDFILE"
  exit 0
fi

kill "$PID"
for _ in {1..10}; do
  if kill -0 "$PID" 2>/dev/null; then
    sleep 0.5
  else
    break
  fi
done

if kill -0 "$PID" 2>/dev/null; then
  echo "Process did not stop in time (pid $PID)."
  exit 1
fi

rm -f "$PIDFILE"
echo "Reference Agent stopped."
