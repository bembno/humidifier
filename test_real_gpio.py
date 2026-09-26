#!/usr/bin/env python3
"""Test real GPIO with different pin factories."""

import sys

print("Testing GPIO factories...")

# Test 1: Default (lgpio)
print("\n1. Testing default lgpio factory...")
try:
    from gpiozero import DigitalInputDevice
    d = DigitalInputDevice(17)
    print(f"   GPIO17: {d.value}")
    d.close()
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 2: PiGPIOFactory with soft
print("\n2. Testing PiGPIOFactory (soft)...")
try:
    from gpiozero.pins.pigpio import PiGPIOFactory
    from gpiozero import DigitalInputDevice
    f = PiGPIOFactory()
    d = DigitalInputDevice(17, pin_factory=f)
    print(f"   GPIO17: {d.value}")
    d.close()
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 3: RPi.GPIO
print("\n3. Testing RPi.GPIO...")
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.IN)
    val = GPIO.input(17)
    print(f"   GPIO17: {val}")
    GPIO.cleanup()
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 4: Native gpiod
print("\n4. Testing gpiod...")
try:
    import gpiod
    chip = gpiod.Chip('gpiochip0')
    line = chip.get_line(17)
    line.request(consumer="test", type=gpiod.LINE_REQ_DIR_IN)
    val = line.get_value()
    print(f"   GPIO17: {val}")
    line.release()
    print("   OK")
except Exception as e:
    print(f"   FAILED: {e}")