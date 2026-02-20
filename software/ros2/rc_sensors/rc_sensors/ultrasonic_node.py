"""
ultrasonic_node  –  HC-SR04 x4 driver

Four HC-SR04 sensors: front, rear, left, right.

IMPORTANT – voltage:
  HC-SR04 ECHO pin outputs 5 V.
  Raspberry Pi 5 GPIO is 3.3 V tolerant only.
  Use a voltage divider (1kΩ + 2kΩ) or level shifter on each ECHO pin.
  Jetson Orin Nano GPIO is 3.3 V tolerant as well — same precaution applies.

Publishes:
  /ultrasonic/distances  rc_interfaces/ObstacleMap  @ 20 Hz
"""

import time
import rclpy
from rclpy.node import Node
from rc_interfaces.msg import ObstacleMap


# ── Platform GPIO abstraction ────────────────────────────────────────

import os

def _platform():
    if os.path.exists('/proc/device-tree/model'):
        with open('/proc/device-tree/model') as f:
            m = f.read().lower()
        if 'raspberry' in m: return 'rpi'
        if 'jetson'    in m: return 'jetson'
    return 'mock'

PLATFORM = os.environ.get('RC_PLATFORM', _platform())


def _setup_gpio():
    if PLATFORM == 'rpi':
        import lgpio
        return lgpio.gpiochip_open(0)
    elif PLATFORM == 'jetson':
        import Jetson.GPIO as GPIO
        GPIO.setmode(GPIO.BOARD)
        return GPIO
    return None

def _gpio_out(handle, pin):
    if PLATFORM == 'rpi':
        import lgpio
        lgpio.gpio_claim_output(handle, pin, 0)
    elif PLATFORM == 'jetson':
        handle.setup(pin, handle.OUT)

def _gpio_in(handle, pin):
    if PLATFORM == 'rpi':
        import lgpio
        lgpio.gpio_claim_input(handle, pin)
    elif PLATFORM == 'jetson':
        handle.setup(pin, handle.IN)

def _gpio_write(handle, pin, val):
    if PLATFORM == 'rpi':
        import lgpio
        lgpio.gpio_write(handle, pin, val)
    elif PLATFORM == 'jetson':
        handle.output(pin, val)

def _gpio_read(handle, pin) -> int:
    if PLATFORM == 'rpi':
        import lgpio
        return lgpio.gpio_read(handle, pin)
    elif PLATFORM == 'jetson':
        return handle.input(pin)
    return 0


# ── Sensor ───────────────────────────────────────────────────────────

SOUND_SPEED = 343.0   # m/s at ~20°C
MAX_DIST_M  = 4.0     # HC-SR04 max reliable range
TIMEOUT_S   = 0.025   # 25 ms ≈ 4 m round trip


class HcSr04:
    """Single HC-SR04 sensor."""

    def __init__(self, handle, trig_pin: int, echo_pin: int):
        self._h    = handle
        self._trig = trig_pin
        self._echo = echo_pin
        _gpio_out(handle, trig_pin)
        _gpio_in( handle, echo_pin)

    def measure_m(self) -> float:
        """
        Return distance in metres.
        Returns MAX_DIST_M if no echo received within timeout.
        """
        if PLATFORM == 'mock':
            return MAX_DIST_M

        # Trigger pulse
        _gpio_write(self._h, self._trig, 1)
        time.sleep(0.00001)          # 10 µs
        _gpio_write(self._h, self._trig, 0)

        # Wait for echo HIGH
        t0 = time.monotonic()
        while _gpio_read(self._h, self._echo) == 0:
            if time.monotonic() - t0 > TIMEOUT_S:
                return MAX_DIST_M

        rise = time.monotonic()

        # Wait for echo LOW
        while _gpio_read(self._h, self._echo) == 1:
            if time.monotonic() - rise > TIMEOUT_S:
                return MAX_DIST_M

        fall = time.monotonic()

        distance = (fall - rise) * SOUND_SPEED / 2.0
        return min(distance, MAX_DIST_M)


# ── ROS2 Node ────────────────────────────────────────────────────────

class UltrasonicNode(Node):

    def __init__(self):
        super().__init__('ultrasonic_node')

        # GPIO pins (BOARD numbering on RPi, configurable via params)
        self.declare_parameter('trig_front', 11)
        self.declare_parameter('echo_front', 13)
        self.declare_parameter('trig_rear',  15)
        self.declare_parameter('echo_rear',  16)
        self.declare_parameter('trig_left',  18)
        self.declare_parameter('echo_left',  22)
        self.declare_parameter('trig_right', 29)
        self.declare_parameter('echo_right', 31)

        self._handle = _setup_gpio()

        self._sensors = {
            'front': HcSr04(self._handle,
                            self.get_parameter('trig_front').value,
                            self.get_parameter('echo_front').value),
            'rear':  HcSr04(self._handle,
                            self.get_parameter('trig_rear').value,
                            self.get_parameter('echo_rear').value),
            'left':  HcSr04(self._handle,
                            self.get_parameter('trig_left').value,
                            self.get_parameter('echo_left').value),
            'right': HcSr04(self._handle,
                            self.get_parameter('trig_right').value,
                            self.get_parameter('echo_right').value),
        }

        self._pub = self.create_publisher(ObstacleMap, '/ultrasonic/distances', 10)
        self.create_timer(0.05, self._measure)   # 20 Hz

        self.get_logger().info('Ultrasonic node ready (4× HC-SR04)')

    def _measure(self):
        msg = ObstacleMap()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.source = 'ultrasonic'

        msg.front_m = self._sensors['front'].measure_m()
        msg.rear_m  = self._sensors['rear' ].measure_m()
        msg.left_m  = self._sensors['left' ].measure_m()
        msg.right_m = self._sensors['right'].measure_m()

        # Diagonals not available from ultrasonic; set to max
        msg.front_left_m  = MAX_DIST_M
        msg.front_right_m = MAX_DIST_M

        self._pub.publish(msg)

    def destroy_node(self):
        if PLATFORM == 'rpi' and self._handle:
            import lgpio
            lgpio.gpiochip_close(self._handle)
        elif PLATFORM == 'jetson' and self._handle:
            self._handle.cleanup()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = UltrasonicNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
