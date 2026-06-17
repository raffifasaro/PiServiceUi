#!/usr/bin/env bash
# Run the FastAPI backend with autoreload for local development.
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
