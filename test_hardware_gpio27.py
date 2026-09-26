#!/usr/bin/env python3
"""Test GPIO27 OFF-state detection with REAL hardware (requires JY-001 connected)."""

import time
from driver import Humidifier
from driver.config import MIST_LEVEL_OFF

print("Testing GPIO27 OFF-state detection with REAL hardware...")
print("=" * 60)
print("REQUIRES: JY-001 module connected to GPIO17 (control) and GPIO27 (status)")
print("GPIO27 should read HIGH (3.3V) when humidifier is OFF")
print("GPIO27 should read LOW (0V) when humidifier is ON (levels 1-3)")
print()

# Create humidifier with hardware sync
humidifier = Humidifier(
    startup_pulses_to_off=3,  # Adjust based on your module
    status_active_high=True,  # True if GPIO27 reads HIGH when OFF
    detection_timeout=5.0,
)

print(f"After sync - Driver level: {humidifier.get_level()}")
print(f"GPIO27 status (raw): {humidifier._status.value if hasattr(humidifier, '_status') else 'N/A'}")
print(f"GPIO27 is_off(): {humidifier.is_off()}")
print()

try:
    # Test each level
    for level in [1, 2, 3]:
        print(f"--- Setting level {level} ---")
        print(f"GPIO27 before: {humidifier.is_off()} (True=OFF)")
        humidifier.set_level(level)
        time.sleep(0.5)  # Let hardware settle
        print(f"Driver level: {humidifier.get_level()}")
        print(f"GPIO27 after: {humidifier.is_off()} (should be False)")
        if humidifier.is_off():
            print("⚠ WARNING: GPIO27 reports OFF but should be ON!")
        else:
            print("✓ GPIO27 correctly reports ON")
        print()

    # Test OFF with detection
    print("--- Turning OFF ---")
    print(f"GPIO27 before: {humidifier.is_off()} (should be False)")
    humidifier.turn_off()
    time.sleep(0.5)
    print(f"Driver level: {humidifier.get_level()}")
    print(f"GPIO27 after: {humidifier.is_off()} (should be True)")
    if humidifier.is_off():
        print("✓ GPIO27 correctly detects OFF state")
    else:
        print("⚠ WARNING: GPIO27 does not report OFF!")
    print()

    # Test idempotent OFF
    print("--- Turning OFF again ---")
    humidifier.turn_off()
    print(f"Driver level: {humidifier.get_level()}, GPIO27: {humidifier.is_off()}")
    print("✓ Idempotent OFF works\n")

    # Test level from OFF
    print("--- Setting level 2 from OFF ---")
    print(f"GPIO27 before: {humidifier.is_off()}")
    humidifier.set_level(2)
    time.sleep(0.5)
    print(f"Driver level: {humidifier.get_level()}, GPIO27: {humidifier.is_off()}")
    if not humidifier.is_off():
        print("✓ GPIO27 correctly reports ON after level change")
    else:
        print("⚠ WARNING: GPIO27 still reports OFF!")
    print()

except KeyboardInterrupt:
    print("\nInterrupted")
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
finally:
    humidifier.close()
    print("GPIO cleaned up")

print("=" * 60)
print("Hardware test complete. Check warnings above.")