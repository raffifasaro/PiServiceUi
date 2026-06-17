#!/usr/bin/env bash
# Run the Vite dev server (proxies /api to the backend on :8080).
set -euo pipefail
cd "$(dirname "$0")/../web"
npm install
exec npm run dev
