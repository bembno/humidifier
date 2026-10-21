#!/usr/bin/env bash
# Create the virtual environment and install the python dependencies.
# The environment inherits the system packages so that RPi.GPIO stays
# available inside the virtual environment.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

PYTHON="${PYTHON:-/usr/bin/python3}"

if [ ! -d "$APP_DIR/.venv" ]; then
  echo "Creating the virtual environment in $APP_DIR/.venv"
  "$PYTHON" -m venv --system-site-packages "$APP_DIR/.venv"
fi

"$APP_DIR/.venv/bin/pip" install --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "Done. Start the service with: sudo systemctl start humidifier-web"
