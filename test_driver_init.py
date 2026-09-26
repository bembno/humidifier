#!/usr/bin/env python3
"""Test exact driver initialization."""

from gpiozero import DigitalInputDevice

print("Creating control pin (17) as input...")
control = DigitalInputDevice(17)
print(f"  control.value = {control.value}")

print("Creating status pin (27) as input with pull_up=False...")
status = DigitalInputDevice(27, pull_up=False)
print(f"  status.value = {status.value}")

print("Switching control to output LOW...")
control.close()
from gpiozero import DigitalOutputDevice
control = DigitalOutputDevice(17, active_high=True, initial_value=False)
print(f"  control.value = {control.value}")

print("Releasing control to input...")
control.close()
control = DigitalInputDevice(17)
print(f"  control.value = {control.value}")

print("Cleanup...")
control.close()
status.close()
print("Done")