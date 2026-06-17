#!/usr/bin/env bash
# Bring the stack up (detached) and keep an attachable log console in tmux,
# so the service survives SSH disconnects.
set -euo pipefail

SESSION="piserviceui"
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker first (see README)." >&2
  exit 1
fi

docker compose up -d

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Attaching to existing tmux session '$SESSION'…"
  exec tmux attach -t "$SESSION"
else
  echo "Starting tmux session '$SESSION' (Ctrl-b d to detach)…"
  exec tmux new-session -s "$SESSION" "docker compose logs -f; exec bash"
fi
