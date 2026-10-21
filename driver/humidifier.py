import RPi.GPIO as GPIO
import time


class HumidifierDriver:
    ENABLE_PIN = 17
    STATUS_PIN = 27
    IMPULSE_DURATION = 0.5
    IMPULSE_DELAY = 0.1
    MAX_OFF_PULSES = 10

    def __init__(self, force_cleanup: bool = False):
        self._initialized = False
        self._force_cleanup = force_cleanup

    def initialize(self) -> None:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        try:
            GPIO.setup(self.ENABLE_PIN, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.setup(self.STATUS_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        except Exception as e:
            if "GPIO busy" in str(e) and self._force_cleanup:
                self._force_gpio_cleanup()
                GPIO.setup(self.ENABLE_PIN, GPIO.OUT, initial=GPIO.HIGH)
                GPIO.setup(self.STATUS_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            else:
                raise
        self._initialized = True

    def _force_gpio_cleanup(self) -> None:
        try:
            import lgpio
            h = lgpio.gpiochip_open(0)
            lgpio.gpio_free(h, self.ENABLE_PIN)
            lgpio.gpio_free(h, self.STATUS_PIN)
            lgpio.gpiochip_close(h)
        except Exception:
            pass
        try:
            GPIO.cleanup([self.ENABLE_PIN, self.STATUS_PIN])
        except Exception:
            pass

    def _send_impulse(self) -> None:
        GPIO.output(self.ENABLE_PIN, GPIO.LOW)
        time.sleep(self.IMPULSE_DURATION)
        GPIO.output(self.ENABLE_PIN, GPIO.HIGH)
        time.sleep(self.IMPULSE_DELAY)

    def set_stage(self, stage: int) -> None:
        if not self._initialized:
            raise RuntimeError("Call initialize() first")
        for _ in range(stage):
            self._send_impulse()

    def set_stage_auto(self, stage: int) -> None:
        if not self._initialized:
            raise RuntimeError("Call initialize() first")
        if not self.is_off():
            self.set_off()
        for _ in range(stage):
            self._send_impulse()

    def set_off(self) -> None:
        if not self._initialized:
            raise RuntimeError("Call initialize() first")
        for _ in range(self.MAX_OFF_PULSES):
            self._send_impulse()
            if self.is_off():
                break

    def is_off(self) -> bool:
        return GPIO.input(self.STATUS_PIN) == GPIO.HIGH

    def cleanup(self) -> None:
        if self._initialized:
            GPIO.output(self.ENABLE_PIN, GPIO.HIGH)
            GPIO.cleanup([self.ENABLE_PIN, self.STATUS_PIN])
            self._initialized = False

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, *args):
        self.cleanup()