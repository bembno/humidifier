#!/usr/bin/env bash
# Start the humidifier web service.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

export PYTHONUNBUFFERED=1
export HUMIDIFIER_HOST="${HUMIDIFIER_HOST:-127.0.0.1}"
export HUMIDIFIER_PORT="${HUMIDIFIER_PORT:-8080}"

VENV="$APP_DIR/.venv"
if [ -x "$VENV/bin/python" ]; then
  exec "$VENV/bin/python" "$APP_DIR/app.py"
fi

echo "Virtual environment missing, falling back to the system python3" >&2
exec /usr/bin/python3 "$APP_DIR/app.py"
