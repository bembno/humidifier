#!/usr/bin/env python3
"""Wait for 'z' key press, send one pulse via GPIO17, wait 0.1s, check GPIO27. Infinite loop."""

import sys
sys.path.insert(0, '/home/pi/Desktop/humidifier')

from driver2 import PulseDriver
from gpiozero import DigitalInputDevice


def main():
    print("Pulse Driver - Press 'z' + Enter to send pulse and check GPIO27, 'q' to quit")
    print("=" * 60)

    # GPIO27 as input (pull_down so it reads 0 when floating)
    status_pin = DigitalInputDevice(27, pull_up=False)

    with PulseDriver(pin=17, pulse_duration=0.5) as driver:
        while True:
            try:
                key = input("> ").strip().lower()
                
                if key == 'q':
                    print("Quitting...")

                elif key == 'a':  
                    # Check GPIO27
                    gpio27_state = status_pin.value
                    print(f"  GPIO27 state: {gpio27_state} ({'HIGH' if gpio27_state else 'LOW'})")
                                      
                elif key == 'z':
                    print("  Sending pulse...")
                    driver.pulse()
                    print("  Pulse sent, waiting 0.1s...")
                    import time
                    time.sleep(0.1)
                    
                    # Check GPIO27
                    gpio27_state = status_pin.value
                    print(f"  GPIO27 state: {gpio27_state} ({'HIGH' if gpio27_state else 'LOW'})")
                elif key == '':
                    continue
                else:
                    print(f"  Unknown: '{key}' (use 'z' or 'q')")
                    
            except KeyboardInterrupt:
                print("\nInterrupted")
                break
            except EOFError:
                break

    status_pin.close()
    print("Done")


if __name__ == "__main__":
    main()