"""
PWM hardware abstraction layer.

Supports:
  - Raspberry Pi 5  : lgpio (hardware PWM via pigpio-compatible API)
  - Jetson Orin Nano: Jetson.GPIO
  - Mock (testing)  : no hardware needed, prints values to stdout
"""

import os
import time

def detect_platform() -> str:
    if os.path.exists('/proc/device-tree/model'):
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read().lower()
        if 'raspberry pi' in model:
            return 'rpi'
        if 'jetson' in model or 'nvidia' in model:
            return 'jetson'
    return 'mock'


PLATFORM = os.environ.get('RC_PLATFORM', detect_platform())


class PwmChannel:
    """Single PWM output channel. Outputs pulse widths in microseconds."""

    PERIOD_US = 20_000   # 50 Hz → 20 ms period

    def __init__(self, pin: int):
        self.pin = pin
        self._us = 1500
        self._setup()

    # ------------------------------------------------------------------
    # Platform setup
    # ------------------------------------------------------------------

    def _setup(self):
        if PLATFORM == 'rpi':
            self._setup_rpi()
        elif PLATFORM == 'jetson':
            self._setup_jetson()
        else:
            print(f"[PWM MOCK] Channel on pin {self.pin} initialised")

    def _setup_rpi(self):
        import lgpio
        self._h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self._h, self.pin)
        # Use lgpio tx_pwm: frequency Hz, duty cycle %
        lgpio.tx_pwm(self._h, self.pin, 50, self._us_to_duty(1500))

    def _setup_jetson(self):
        import Jetson.GPIO as GPIO
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        self._pwm = GPIO.PWM(self.pin, 50)
        self._pwm.start(self._us_to_duty(1500))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_pulse_us(self, us: int):
        """Set pulse width in microseconds (1000–2000)."""
        us = max(1000, min(2000, us))
        self._us = us
        if PLATFORM == 'rpi':
            import lgpio
            lgpio.tx_pwm(self._h, self.pin, 50, self._us_to_duty(us))
        elif PLATFORM == 'jetson':
            self._pwm.ChangeDutyCycle(self._us_to_duty(us))
        else:
            print(f"[PWM MOCK] pin={self.pin}  pulse={us}µs")

    def get_pulse_us(self) -> int:
        return self._us

    def close(self):
        if PLATFORM == 'rpi':
            import lgpio
            lgpio.tx_pwm(self._h, self.pin, 50, self._us_to_duty(1500))
            lgpio.gpiochip_close(self._h)
        elif PLATFORM == 'jetson':
            self._pwm.stop()
            import Jetson.GPIO as GPIO
            GPIO.cleanup(self.pin)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _us_to_duty(us: int) -> float:
        """Convert microseconds to duty-cycle percentage for 50 Hz PWM."""
        return us / PwmChannel.PERIOD_US * 100.0
