#!/bin/bash
sudo apt update && sudo apt install -y pigpio
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
sleep 2
python3 -c "import pigpio; pi = pigpio.pi(); print('pigpio connected:', pi.connected); pi.stop()"