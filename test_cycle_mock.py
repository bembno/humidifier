#!/usr/bin/env python3
"""Test cycling through all stages with mock."""

import os
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

import time
from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin
from driver import Humidifier
from driver.config import MIST_LEVEL_HIGH, MIST_LEVEL_MEDIUM, MIST_LEVEL_LOW, MIST_LEVEL_OFF

Device.pin_factory = MockFactory(pin_class=MockPWMPin)

print("Cycling through all stages (2s each)...")
print("=" * 50)

h = Humidifier(skip_sync=True)

# Mock status to always return OFF after pulses
def mock_read():
    return True
h._read_status = mock_read

stages = [
    (MIST_LEVEL_HIGH, "High mist"),
    (MIST_LEVEL_MEDIUM, "Medium mist"),
    (MIST_LEVEL_LOW, "Low mist"),
    (MIST_LEVEL_OFF, "OFF"),
]

for level, name in stages:
    if level == MIST_LEVEL_OFF:
        print(f"Turning OFF...")
        h.turn_off()
    else:
        print(f"Setting {name} (Level {level})...")
        h.set_level(level)
    print(f"  Level: {h.get_level()}, OFF: {h.is_off()}")
    time.sleep(2)

h.close()
print("Done")