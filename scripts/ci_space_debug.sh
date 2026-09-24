#!/usr/bin/env bash
# CI hook — run from repo root or pass --space / --app-path.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPACE="${HF_SPACE:-${1:-}}"
APP_PATH="${APP_PATH:-./app.py}"
FORMAT="${FORMAT:-markdown}"
OUTPUT="${OUTPUT:-diagnostic-report.md}"

if [[ -z "$SPACE" ]]; then
  echo "Set HF_SPACE or pass owner/name as the first argument." >&2
  exit 2
fi

if [[ -f "$APP_PATH" ]]; then
  APP_FLAG=(--app-path "$APP_PATH")
else
  APP_FLAG=()
fi

python "$SCRIPT_DIR/hf_space_debugger.py" \
  --space "$SPACE" \
  "${APP_FLAG[@]}" \
  --format "$FORMAT" \
  --output "$OUTPUT"
