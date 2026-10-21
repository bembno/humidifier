#!/usr/bin/env bash
# DEPRECATED: this boot script starts the legacy scheduler, which is
# superseded by the web service (humidifier-web.service).  Only one program
# may control the GPIO pins, so this script must not be started while the
# web service is running.

echo "Waiting for Wi-Fi connection..."

while ! hostname -I | grep -qE '([0-9]{1,3}\.){3}[0-9]{1,3}'
do
    sleep 1
done

echo "IP detected"

cd /home/pi/Desktop/humidifier/driver
/usr/bin/screen -dmS a /home/pi/Desktop/humidifier/driver/run_scheduler.sh
echo "Started scheduler in screen session 'a'"