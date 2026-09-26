#!/usr/bin/env python3
"""Non-interactive test: sends pulses and checks GPIO27."""

import sys
sys.path.insert(0, '/home/pi/Desktop/humidifier')

import os
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin
from driver2 import PulseDriver
from gpiozero import DigitalInputDevice

Device.pin_factory = MockFactory(pin_class=MockPWMPin)

print("Test: send 3 pulses, check GPIO27 after each")
print("=" * 50)

status_pin = DigitalInputDevice(27, pull_up=False)

with PulseDriver(pin=17, pulse_duration=0.5) as driver:
    for i in range(3):
        print(f"\nPulse {i+1}:")
        driver.pulse()
        import time
        time.sleep(0.1)
        gpio27_state = status_pin.value
        print(f"  GPIO27: {gpio27_state} ({'HIGH' if gpio27_state else 'LOW'})")

status_pin.close()
print("\nDone")