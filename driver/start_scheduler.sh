#!/usr/bin/env bash

echo "Waiting for Wi-Fi connection..."

while ! hostname -I | grep -qE '([0-9]{1,3}\.){3}[0-9]{1,3}'
do
    sleep 1
done

echo "IP detected"

cd /home/pi/Desktop/humidifier/driver
/usr/bin/screen -dmS a /home/pi/Desktop/humidifier/driver/run_scheduler.sh
echo "Started scheduler in screen session 'a'"