"""
vehicle_node  –  ESC + servo control

Subscribes:
  /vehicle/cmd_vel          geometry_msgs/Twist   → drive commands
  /vehicle/emergency_stop   std_msgs/Bool         → hard stop

Publishes:
  /vehicle/status           rc_interfaces/VehicleStatus

Parameters:
  esc_pin           (int,   default 12)    GPIO pin for ESC PWM
  servo_pin         (int,   default 13)    GPIO pin for servo PWM
  max_linear_speed  (float, default 0.5)   m/s cap for autonomous mode
  max_angular_speed (float, default 1.0)   rad/s cap
  servo_trim_us     (int,   default 0)     mechanical trim offset µs
  watchdog_timeout  (float, default 0.5)   seconds without cmd → stop
"""

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from builtin_interfaces.msg import Time

from rc_interfaces.msg import VehicleStatus

from .esc   import ESC
from .servo import Servo


class VehicleNode(Node):

    def __init__(self):
        super().__init__('vehicle_node')

        # ── Parameters ────────────────────────────────────────────────
        self.declare_parameter('esc_pin',           12)
        self.declare_parameter('servo_pin',         13)
        self.declare_parameter('max_linear_speed',  0.5)
        self.declare_parameter('max_angular_speed', 1.0)
        self.declare_parameter('servo_trim_us',     0)
        self.declare_parameter('watchdog_timeout',  0.5)

        esc_pin   = self.get_parameter('esc_pin').value
        servo_pin = self.get_parameter('servo_pin').value
        trim_us   = self.get_parameter('servo_trim_us').value
        max_lin   = self.get_parameter('max_linear_speed').value

        self.max_linear  = max_lin
        self.max_angular = self.get_parameter('max_angular_speed').value
        self.watchdog_t  = self.get_parameter('watchdog_timeout').value

        self.get_logger().info(
            f'Vehicle node starting – ESC pin {esc_pin}, servo pin {servo_pin}, '
            f'max speed {max_lin} m/s'
        )

        # ── Hardware ──────────────────────────────────────────────────
        self.esc   = ESC(pin=esc_pin, max_throttle=max_lin)
        self.servo = Servo(pin=servo_pin, trim_us=trim_us)

        # ── State ─────────────────────────────────────────────────────
        self._emergency = False
        self._last_cmd  = self.get_clock().now()

        # ── Subscriptions ─────────────────────────────────────────────
        self.create_subscription(
            Twist, '/vehicle/cmd_vel', self._cmd_cb, 10)
        self.create_subscription(
            Bool, '/vehicle/emergency_stop', self._estop_cb, 10)

        # ── Publisher ─────────────────────────────────────────────────
        self._status_pub = self.create_publisher(
            VehicleStatus, '/vehicle/status', 10)

        # ── Timers ────────────────────────────────────────────────────
        self.create_timer(0.1,  self._watchdog)          # 10 Hz watchdog
        self.create_timer(0.2,  self._publish_status)    # 5 Hz status

        # ── Parameter callback ────────────────────────────────────────
        self.add_on_set_parameters_callback(self._param_cb)

        self.get_logger().info('Vehicle node ready.')

    # ── Callbacks ─────────────────────────────────────────────────────

    def _cmd_cb(self, msg: Twist):
        if self._emergency:
            return

        self._last_cmd = self.get_clock().now()

        throttle = msg.linear.x  / self.max_linear
        steering = msg.angular.z / self.max_angular

        self.esc.set_throttle(throttle)
        self.servo.set_steering(steering)

    def _estop_cb(self, msg: Bool):
        if msg.data:
            self._emergency = True
            self._hard_stop()
            self.get_logger().warn('EMERGENCY STOP activated!')
        else:
            self._emergency = False
            self.get_logger().info('Emergency stop cleared.')

    def _watchdog(self):
        """Stop the vehicle if no command received within timeout."""
        if self._emergency:
            return
        elapsed = (self.get_clock().now() - self._last_cmd).nanoseconds / 1e9
        if elapsed > self.watchdog_t:
            self.esc.stop()

    def _publish_status(self):
        msg = VehicleStatus()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.mode         = 'active' if not self._emergency else 'emergency_stop'
        msg.emergency_stop = self._emergency
        self._status_pub.publish(msg)

    def _param_cb(self, params):
        for p in params:
            if p.name == 'max_linear_speed':
                self.max_linear = p.value
                self.esc.set_max_throttle(p.value)
            elif p.name == 'max_angular_speed':
                self.max_angular = p.value
            elif p.name == 'servo_trim_us':
                self.servo.set_trim(int(p.value))
            elif p.name == 'watchdog_timeout':
                self.watchdog_t = p.value
        return rclpy.parameter.ParameterEventHandler

    # ── Helpers ───────────────────────────────────────────────────────

    def _hard_stop(self):
        self.esc.stop()
        self.servo.centre()

    def destroy_node(self):
        self._hard_stop()
        self.esc.close()
        self.servo.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VehicleNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
