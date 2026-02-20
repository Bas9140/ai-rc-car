"""
gps_node  –  u-blox M8N GPS driver

Publishes:
  /gps/fix   sensor_msgs/NavSatFix       GPS position (lat/lon/alt)
  /gps/vel   geometry_msgs/TwistWithCovarianceStamped  GPS velocity

The M8N outputs NMEA 0183 sentences over UART.
Default baud rate: 9600.  Can be increased to 115200 for 10 Hz updates.
"""

import rclpy
from rclpy.node import Node

import serial
import pynmea2

from sensor_msgs.msg import NavSatFix, NavSatStatus
from geometry_msgs.msg import TwistWithCovarianceStamped


# Position covariance for u-blox M8N (1.5m CEP → ~4m² variance)
_POS_COV = [4.0, 0.0, 0.0,
            0.0, 4.0, 0.0,
            0.0, 0.0, 9.0]


class GpsNode(Node):

    def __init__(self):
        super().__init__('gps_node')

        self.declare_parameter('port',     '/dev/ttyUSB0')
        self.declare_parameter('baudrate', 9600)
        self.declare_parameter('frame_id', 'gps_link')

        port     = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        self._frame = self.get_parameter('frame_id').value

        self._pub_fix = self.create_publisher(NavSatFix, '/gps/fix', 10)
        self._pub_vel = self.create_publisher(
            TwistWithCovarianceStamped, '/gps/vel', 10)

        try:
            self._serial = serial.Serial(port, baudrate=baudrate, timeout=1.0)
            self.get_logger().info(f'GPS connected on {port} @ {baudrate} baud')
        except serial.SerialException as e:
            self.get_logger().error(f'Cannot open GPS port {port}: {e}')
            self._serial = None

        self.create_timer(0.05, self._read)   # Poll at 20 Hz, GPS outputs 10 Hz

    def _read(self):
        if self._serial is None or not self._serial.in_waiting:
            return
        try:
            raw = self._serial.readline().decode('ascii', errors='ignore').strip()
        except serial.SerialException as e:
            self.get_logger().warn(f'GPS read error: {e}')
            return

        if not raw.startswith('$'):
            return

        try:
            msg = pynmea2.parse(raw)
        except pynmea2.ParseError:
            return

        stamp = self.get_clock().now().to_msg()

        # GGA: position + fix quality
        if isinstance(msg, pynmea2.GGA):
            self._publish_fix(msg, stamp)

        # VTG: ground speed + course
        elif isinstance(msg, pynmea2.VTG):
            self._publish_vel(msg, stamp)

    def _publish_fix(self, msg, stamp):
        fix = NavSatFix()
        fix.header.stamp    = stamp
        fix.header.frame_id = self._frame

        if msg.gps_qual and msg.gps_qual > 0:
            fix.status.status  = NavSatStatus.STATUS_FIX
        else:
            fix.status.status  = NavSatStatus.STATUS_NO_FIX

        fix.status.service = NavSatStatus.SERVICE_GPS

        fix.latitude  = msg.latitude  if msg.latitude  else 0.0
        fix.longitude = msg.longitude if msg.longitude else 0.0
        fix.altitude  = float(msg.altitude) if msg.altitude else 0.0

        fix.position_covariance      = _POS_COV
        fix.position_covariance_type = NavSatFix.COVARIANCE_TYPE_DIAGONAL_KNOWN

        self._pub_fix.publish(fix)

    def _publish_vel(self, msg, stamp):
        if not msg.spd_over_grnd_kmph:
            return

        speed_ms = float(msg.spd_over_grnd_kmph) / 3.6

        vel = TwistWithCovarianceStamped()
        vel.header.stamp    = stamp
        vel.header.frame_id = self._frame
        vel.twist.twist.linear.x = speed_ms   # Forward speed (no heading yet)

        self._pub_vel.publish(vel)

    def destroy_node(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = GpsNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
