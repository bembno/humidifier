#!/usr/bin/env python3
"""Usage example for JY-001 DIY-2 humidifier driver."""

import time
from driver import Humidifier
from driver.config import MIST_LEVEL_HIGH, MIST_LEVEL_MEDIUM, MIST_LEVEL_LOW, MIST_LEVEL_OFF
from driver.exceptions import (
    InvalidLevelError,
    OffDetectionTimeoutError,
    StateSyncError,
    OperationInProgressError,
    HardwareError,
)


def main() -> None:
    print("JY-001 DIY-2 Humidifier Driver Example")
    print("=" * 50)

    try:
        with Humidifier(skip_sync=True) as humidifier:
            print(f"Initial level: {humidifier.get_level()}")
            print(f"Is OFF: {humidifier.is_off()}")

            print("\n--- Quick calibration cycle to determine OFF mode ---")
            for level, name in [(MIST_LEVEL_HIGH, "High"), (MIST_LEVEL_MEDIUM, "Medium"), (MIST_LEVEL_LOW, "Low"), (MIST_LEVEL_OFF, "OFF")]:
                if level == MIST_LEVEL_OFF:
                    print(f"  Turning OFF...")
                    humidifier.turn_off()
                else:
                    print(f"  Setting {name} mist (Level {level})...")
                    humidifier.set_level(level)
                print(f"    Level: {humidifier.get_level()}, OFF detected: {humidifier.is_off()}")
                time.sleep(0.5)
            print("--- Calibration complete ---\n")

            # Cycle through all stages continuously
            stages = [
                (MIST_LEVEL_HIGH, "High mist"),
                (MIST_LEVEL_MEDIUM, "Medium mist"),
                (MIST_LEVEL_LOW, "Low mist"),
                (MIST_LEVEL_OFF, "OFF"),
            ]

            print("\n--- Cycling through all stages (5s each) ---")
            print("Press Ctrl+C to stop\n")

            cycle_count = 0
            while True:
                cycle_count += 1
                print(f"=== Cycle {cycle_count} ===")

                for level, name in stages:
                    if level == MIST_LEVEL_OFF:
                        print(f"Turning OFF...")
                        humidifier.turn_off()
                    else:
                        print(f"Setting {name} (Level {level})...")
                        humidifier.set_level(level)

                    print(f"  Driver level: {humidifier.get_level()}, GPIO27 OFF: {humidifier.is_off()}")

                    # Wait 5 seconds at this stage
                    for i in range(5, 0, -1):
                        print(f"  Waiting... {i}s", end="\r")
                        time.sleep(1)
                    print("  Waiting... done      ")

    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except StateSyncError as e:
        print(f"State sync failed: {e}")
        print("Check wiring and STARTUP_PULSES_TO_OFF config")
    except OffDetectionTimeoutError as e:
        print(f"OFF detection timeout: {e}")
        print("Check GPIO27 wiring and STATUS_PIN_ACTIVE_HIGH config")
    except OperationInProgressError as e:
        print(f"Operation in progress: {e}")
    except HardwareError as e:
        print(f"Hardware error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def demo_once() -> None:
    """Run through all stages once (for quick testing)."""
    print("JY-001 DIY-2 Humidifier - Single Cycle Demo")
    print("=" * 50)

    try:
        with Humidifier() as humidifier:
            stages = [
                (MIST_LEVEL_HIGH, "High mist"),
                (MIST_LEVEL_MEDIUM, "Medium mist"),
                (MIST_LEVEL_LOW, "Low mist"),
                (MIST_LEVEL_OFF, "OFF"),
            ]

            for level, name in stages:
                if level == MIST_LEVEL_OFF:
                    print(f"Turning OFF...")
                    humidifier.turn_off()
                else:
                    print(f"Setting {name} (Level {level})...")
                    humidifier.set_level(level)

                print(f"  Level: {humidifier.get_level()}, OFF: {humidifier.is_off()}")
                time.sleep(5)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        demo_once()
    else:
        main()