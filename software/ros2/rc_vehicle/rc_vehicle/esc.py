"""
ESC (Electronic Speed Controller) driver.

Compatible with the Arrma BLX80 ESC and most standard RC ESCs.
Neutral pulse = 1500 µs.  Full forward = 2000 µs.  Full reverse = 1000 µs.

The BLX80 requires an arming sequence on startup:
  1. Send neutral (1500 µs) for at least 2 seconds → ESC arms (green LED)
  2. After arming, normal control is possible
"""

import time
from .pwm_interface import PwmChannel


class ESC:
    NEUTRAL_US   = 1500
    MAX_FWD_US   = 2000
    MAX_REV_US   = 1000

    # Safety: clamp max autonomous speed to 50% of full range
    # Increase via ROS2 parameter when comfortable
    DEFAULT_MAX_THROTTLE = 0.5

    def __init__(self, pin: int, max_throttle: float = DEFAULT_MAX_THROTTLE):
        self._pwm = PwmChannel(pin)
        self._max_throttle = max(0.0, min(1.0, max_throttle))
        self._arm()

    def _arm(self):
        """Send neutral signal and wait for ESC to arm."""
        self._pwm.set_pulse_us(self.NEUTRAL_US)
        time.sleep(2.0)

    def set_throttle(self, value: float):
        """
        Set throttle.

        Args:
            value: -1.0 (full reverse) to +1.0 (full forward).
                   Values are clamped to ±max_throttle.
        """
        value = max(-self._max_throttle, min(self._max_throttle, value))

        if value >= 0.0:
            us = int(self.NEUTRAL_US + value * (self.MAX_FWD_US - self.NEUTRAL_US))
        else:
            us = int(self.NEUTRAL_US + value * (self.NEUTRAL_US - self.MAX_REV_US))

        self._pwm.set_pulse_us(us)

    def stop(self):
        """Immediately cut throttle to neutral."""
        self._pwm.set_pulse_us(self.NEUTRAL_US)

    def set_max_throttle(self, value: float):
        self._max_throttle = max(0.0, min(1.0, value))

    def close(self):
        self.stop()
        self._pwm.close()
