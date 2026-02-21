#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

POLL_SECONDS="${POLL_SECONDS:-15}"
PYTHON_BIN="${PYTHON_BIN:-python}"

cleanup() {
  if [[ -n "${WORKER_PID:-}" ]]; then
    kill "$WORKER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "[dev] starting autotune worker (poll=${POLL_SECONDS}s)"
$PYTHON_BIN -m agent_eval.autotune_service --poll-seconds "$POLL_SECONDS" &
WORKER_PID=$!

echo "[dev] starting next server"
npm run dev
