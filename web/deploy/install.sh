#!/usr/bin/env bash
# Install the humidifier web interface on the Raspberry Pi.
# Run it as root:  sudo bash /home/pi/Desktop/humidifier/web/deploy/install.sh
set -euo pipefail

APP_DIR="/home/pi/Desktop/humidifier/web"
DEPLOY_DIR="$APP_DIR/deploy"
SERVICE_NAME="humidifier-web"

log() { echo -e "\n==> $*"; }

log "1/6 Installing the web server (nginx)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends nginx

log "2/6 Preparing the python environment"
mkdir -p "$APP_DIR/logs"
chown -R pi:pi "$APP_DIR"
chmod +x "$APP_DIR/run.sh" "$APP_DIR/setup.sh" 2>/dev/null || true
sudo -u pi bash "$APP_DIR/setup.sh"

log "3/6 Installing the systemd service"
cp "$DEPLOY_DIR/humidifier-web.service" "/etc/systemd/system/${SERVICE_NAME}.service"
chmod 644 "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

log "4/6 Configuring nginx"
cp "$DEPLOY_DIR/nginx-humidifier.conf" /etc/nginx/sites-available/humidifier
ln -sf /etc/nginx/sites-available/humidifier /etc/nginx/sites-enabled/humidifier
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx

log "5/6 Stopping the legacy scheduler (it would fight over the GPIO pins)"
if crontab -u pi -l 2>/dev/null | grep -q "start_scheduler.sh"; then
  crontab -u pi -l 2>/dev/null | grep -v "start_scheduler.sh" | crontab -u pi -
  echo "Removed the legacy @reboot entry from the crontab of the user pi"
fi
if pgrep -f "driver/run_scheduler.sh" > /dev/null 2>&1; then
  pkill -f "driver/run_scheduler.sh" || true
  sleep 1
fi
if pgrep -f "driver/scheduler.py" > /dev/null 2>&1; then
  pkill -f "driver/scheduler.py" || true
  sleep 1
fi
screen -S a -X quit > /dev/null 2>&1 || true
pkill -f "SCREEN -dmS a" > /dev/null 2>&1 || true

log "6/6 Enabling and starting the humidifier service"
systemctl enable "$SERVICE_NAME"
systemctl restart "$SERVICE_NAME"
sleep 2
systemctl --no-pager --lines=10 status "$SERVICE_NAME" || true

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
echo "----------------------------------------------------------------"
echo " The humidifier web interface is available at:"
echo "     http://${IP:-<pi-ip>}/"
echo "----------------------------------------------------------------"
