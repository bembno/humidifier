#!/usr/bin/env bash

cd /home/pi/Desktop/humidifier/driver

# Trap signals to prevent wrapper from dying
trap 'echo "Received signal, restarting..."; continue' SIGINT SIGTERM

while true; do
    echo "Starting scheduler..."
    /usr/bin/python3 scheduler.py
    echo "Scheduler crashed with exit code $?. Restarting in 10 seconds..."
    sleep 10
done