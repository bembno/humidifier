#!/usr/bin/env python3
"""Test humidifier driver with mock GPIO."""

import os
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin
from driver import Humidifier

# Set up mock factory
Device.pin_factory = MockFactory(pin_class=MockPWMPin)

print("Testing with mock GPIO...")
print("=" * 40)

# Create humidifier with custom startup pulses for mock
humidifier = Humidifier(startup_pulses_to_off=0, skip_sync=True)

# Mock the status pin to return True (OFF) after pulses
original_read_status = humidifier._read_status
def mock_read_status():
    return True  # Always return OFF state
humidifier._read_status = mock_read_status

print(f"Initial level: {humidifier.get_level()}")
print(f"Is OFF: {humidifier.is_off()}")

print("\n--- Setting mist levels ---")

print("Setting level 1 (High mist)...")
humidifier.set_level(1)
print(f"Current level: {humidifier.get_level()}")

print("Setting level 2 (Medium mist)...")
humidifier.set_level(2)
print(f"Current level: {humidifier.get_level()}")

print("Setting level 3 (Low mist)...")
humidifier.set_level(3)
print(f"Current level: {humidifier.get_level()}")

print("Setting level 1 again (should skip pulses)...")
humidifier.set_level(1)
print(f"Current level: {humidifier.get_level()}")

print("\n--- Turning OFF ---")
print("Turning humidifier OFF...")
humidifier.turn_off()
print(f"Current level: {humidifier.get_level()}")
print(f"Is OFF: {humidifier.is_off()}")

humidifier.close()
print("\nTest completed successfully!")