"""Simple pulse driver - sends one 0.5s LOW pulse on GPIO17."""

import time
from gpiozero import DigitalInputDevice, DigitalOutputDevice


class PulseDriver:
    """Send single pulses on GPIO17 (HIGH-Z normally, LOW for pulse)."""

    def __init__(self, pin: int = 17, pulse_duration: float = 0.5):
        self.pin = pin
        self.pulse_duration = pulse_duration
        # Start in HIGH-Z (input mode)
        self._dev = DigitalInputDevice(pin)

    def pulse(self) -> None:
        """Send one pulse: LOW for pulse_duration, then return to HIGH-Z."""
        # Switch to output LOW
        self._dev.close()
        self._dev = DigitalOutputDevice(self.pin, active_high=True, initial_value=False)
        time.sleep(self.pulse_duration)
        # Return to HIGH-Z (input)
        self._dev.close()
        self._dev = DigitalInputDevice(self.pin)

    def close(self) -> None:
        """Cleanup - leave pin in HIGH-Z."""
        self._dev.close()
        self._dev = DigitalInputDevice(self.pin)
        self._dev.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main():
    """Interactive: press 'z' + Enter to send pulse."""
    print("Simple Pulse Driver - Press 'z' + Enter to send pulse, 'q' to quit")
    print("=" * 50)

    with PulseDriver() as driver:
        while True:
            try:
                key = input("Press 'z' for pulse, 'q' to quit: ").strip().lower()
                if key == 'q':
                    break
                elif key == 'z':
                    print("  Sending pulse...")
                    driver.pulse()
                    print("  Pulse sent")
                else:
                    print("  Unknown key")
            except KeyboardInterrupt:
                break
            except EOFError:
                break

    print("Done")


if __name__ == "__main__":
    main()