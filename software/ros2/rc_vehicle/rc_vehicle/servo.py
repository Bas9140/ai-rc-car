"""
Steering servo driver.

Standard RC servo: 1000 µs = full left, 1500 µs = centre, 2000 µs = full right.

The trim value compensates for mechanical misalignment so the car drives
straight when angular.z = 0.  Adjust via ROS2 parameter.
"""

from .pwm_interface import PwmChannel


class Servo:
    CENTER_US    = 1500
    MAX_LEFT_US  = 1000
    MAX_RIGHT_US = 2000

    def __init__(self, pin: int, trim_us: int = 0):
        """
        Args:
            pin:     GPIO pin number
            trim_us: mechanical trim offset in µs (positive = right bias)
        """
        self._pwm   = PwmChannel(pin)
        self._trim  = trim_us
        self.centre()

    def set_steering(self, value: float):
        """
        Set steering angle.

        Args:
            value: -1.0 (full left) to +1.0 (full right).
                   ROS2 convention: positive angular.z = left turn,
                   so we negate the value here.
        """
        value = max(-1.0, min(1.0, value))
        # Negate: positive angular.z (ROS2 = turn left) → servo left
        us = int(self.CENTER_US - value * (self.MAX_RIGHT_US - self.CENTER_US))
        us += self._trim
        self._pwm.set_pulse_us(us)

    def centre(self):
        """Return servo to centre position."""
        self._pwm.set_pulse_us(self.CENTER_US + self._trim)

    def set_trim(self, trim_us: int):
        self._trim = trim_us

    def close(self):
        self.centre()
        self._pwm.close()
