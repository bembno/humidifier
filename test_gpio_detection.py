#!/usr/bin/env python3
"""Test GPIO27 OFF-state detection with simulated hardware behavior."""

import os
os.environ['GPIOZERO_PIN_FACTORY'] = 'mock'

from gpiozero import Device
from gpiozero.pins.mock import MockFactory, MockPWMPin
from driver import Humidifier
from driver.config import MIST_LEVEL_OFF

# Set up mock factory
Device.pin_factory = MockFactory(pin_class=MockPWMPin)

print("Testing GPIO27 OFF-state detection...")
print("=" * 50)

# Create humidifier with skip_sync for mock testing
humidifier = Humidifier(startup_pulses_to_off=0, skip_sync=True)

# Track the simulated humidifier state
class MockHumidifierState:
    def __init__(self):
        self.current_level = MIST_LEVEL_OFF  # Start at OFF
        self.pulse_count = 0
    
    def pulse(self):
        """Simulate one pulse advancing the level"""
        self.pulse_count += 1
        # Cycle: 1 -> 2 -> 3 -> 4(OFF) -> 1 -> ...
        self.current_level = (self.current_level % 4) + 1
        print(f"  [HW Sim] Pulse #{self.pulse_count} -> Level {self.current_level}")
        return self.current_level
    
    def is_off(self):
        return self.current_level == MIST_LEVEL_OFF

hw_state = MockHumidifierState()

# Override _generate_pulse to simulate hardware
original_generate_pulse = humidifier._generate_pulse
def mock_generate_pulse():
    hw_state.pulse()
    # Still do the GPIO pin manipulation for driver logic
    original_generate_pulse()
humidifier._generate_pulse = mock_generate_pulse

# Override _read_status to read from simulated hardware
def mock_read_status():
    # Simulate GPIO27: HIGH (1) when OFF, LOW (0) when ON
    # Assumes STATUS_PIN_ACTIVE_HIGH = True
    return 1 if hw_state.is_off() else 0
humidifier._read_status = mock_read_status

# Set initial driver state to match hardware
humidifier._current_level = hw_state.current_level

print(f"Initial state: Level {hw_state.current_level} (OFF={hw_state.is_off()})")
print(f"Driver thinks: Level {humidifier.get_level()}")
print(f"GPIO27 reads: {mock_read_status()} (1=OFF, 0=ON)")
print()

# Test sequence: 1 -> 2 -> 3 -> OFF
for level in [1, 2, 3]:
    print(f"--- Setting level {level} ---")
    print(f"Before: HW Level {hw_state.current_level}, Driver Level {humidifier.get_level()}")
    humidifier.set_level(level)
    print(f"After:  HW Level {hw_state.current_level}, Driver Level {humidifier.get_level()}")
    print(f"GPIO27: {mock_read_status()} (1=OFF, 0=ON)")
    assert humidifier.get_level() == level, f"Driver level mismatch: {humidifier.get_level()} != {level}"
    assert hw_state.current_level == level, f"HW level mismatch: {hw_state.current_level} != {level}"
    assert not hw_state.is_off(), f"Should not be OFF at level {level}"
    print("✓ Level set correctly\n")

# Test OFF detection
print("--- Turning OFF ---")
print(f"Before: HW Level {hw_state.current_level}, Driver Level {humidifier.get_level()}")
humidifier.turn_off()
print(f"After:  HW Level {hw_state.current_level}, Driver Level {humidifier.get_level()}")
print(f"GPIO27: {mock_read_status()} (1=OFF, 0=ON)")
assert humidifier.get_level() == MIST_LEVEL_OFF, f"Driver should be OFF: {humidifier.get_level()}"
assert hw_state.is_off(), "Hardware should be OFF"
print("✓ OFF detected correctly via GPIO27\n")

# Test idempotent OFF
print("--- Turning OFF again (idempotent) ---")
humidifier.turn_off()
print(f"Driver Level: {humidifier.get_level()}, GPIO27: {mock_read_status()}")
assert humidifier.get_level() == MIST_LEVEL_OFF
print("✓ Idempotent OFF works\n")

# Test setting level from OFF
print("--- Setting level 2 from OFF ---")
print(f"Before: HW Level {hw_state.current_level}, Driver Level {humidifier.get_level()}")
humidifier.set_level(2)
print(f"After:  HW Level {hw_state.current_level}, Driver Level {humidifier.get_level()}")
print(f"GPIO27: {mock_read_status()} (1=OFF, 0=ON)")
assert humidifier.get_level() == 2
assert hw_state.current_level == 2
assert not hw_state.is_off()
print("✓ Level change from OFF works\n")

humidifier.close()
print("=" * 50)
print("All GPIO27 detection tests PASSED! ✓")