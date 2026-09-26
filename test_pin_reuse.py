#!/usr/bin/env python3
from gpiozero import DigitalInputDevice
d1 = DigitalInputDevice(17)
print('d1:', d1.value)
d1.close()
d2 = DigitalInputDevice(17)
print('d2:', d2.value)
d2.close()