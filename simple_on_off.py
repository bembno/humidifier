#!/usr/bin/env python3
"""Simple example: Turn ON level 1, wait, then turn OFF.

For mock testing (no hardware): GPIOZERO_PIN_FACTORY=mock python3 simple_on_off.py --mock
For hardware: python3 simple_on_off.py
"""

import sys
import time
from driver import Humidifier

mock_mode = "--mock" in sys.argv

with Humidifier(skip_sync=mock_mode) as h:
    # For mock: simulate GPIO27 returning OFF after pulses
    if mock_mode:
        def mock_read():
            return True
        h._read_status = mock_read

    print("Turning ON level 1 (High mist)...")
    h.set_level(1)
    print(f"Level: {h.get_level()}, OFF: {h.is_off()}")

    print("Running for 10 seconds...")
    time.sleep(10)

    print("Turning OFF...")
    h.turn_off()
    print(f"Level: {h.get_level()}, OFF: {h.is_off()}")

print("Done")