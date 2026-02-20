"""
receiver_node  –  FlySky FS-BS6 iBUS receiver driver

Hardware setup:
  FS-BS6 iBUS port  →  RPi5/Jetson UART RX pin  (one wire + GND)

  FS-BS6 iBUS connector (3-pin servo plug):
    Pin 1 (signal) → UART RX on Pi (GPIO 15, physical pin 10)
    Pin 2 (VCC 5V) → do NOT connect to Pi GPIO (5V only for BS6 power if needed)
    Pin 3 (GND)    → GND on Pi

  Enable iBUS output on FS-GT5:
    RX Setup → iBUS output → select the iBUS port on BS6

iBUS packet format (32 bytes, 115200 baud, ~7 ms interval):
  Byte  0   : 0x20  (packet length = 32)
  Byte  1   : 0x40  (command: channel data)
  Bytes 2-29: 14 channels × 2 bytes little-endian uint16 (values 1000–2000)
  Bytes 30-31: checksum = 0xFFFF − sum(bytes 0..29)

FS-GT5 channel mapping (default):
  CH1  Steering wheel  (1000=left, 1500=centre, 2000=right)
  CH2  Throttle trigger (1000=full brake/reverse, 1500=neutral, 2000=full forward)
  CH3  Not used (default 1500)
  CH4  Not used (default 1500)
  CH5  SWA – 2-position switch  → KILL SWITCH  (2000=armed, 1000=STOP)
  CH6  SWB – 3-position switch  → MODE SELECT  (1000=manual, 1500=follow_me, 2000=autonomous)

Publishes:
  /dashboard/manual_cmd    geometry_msgs/Twist      manual drive commands
  /vehicle/emergency_stop  std_msgs/Bool            kill switch state
  /rc/mode_select          std_msgs/String          mode from 3-pos switch
  /rc/channels             std_msgs/Int32MultiArray  raw channel values (debug)
"""

import serial
import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String
from std_msgs.msg import Int32MultiArray

# iBUS constants
IBUS_LEN      = 32
IBUS_HEADER0  = 0x20
IBUS_HEADER1  = 0x40
IBUS_NUM_CH   = 14   # Packet always has 14 channels; BS6 populates 6

# Channel indices (0-based)
CH_STEER    = 0   # CH1
CH_THROTTLE = 1   # CH2
CH_KILL     = 4   # CH5  SWA
CH_MODE     = 5   # CH6  SWB

# Kill switch threshold
KILL_THRESHOLD = 1500   # < 1500 = kill active

# Mode switch thresholds
MODE_MANUAL    = 1250
MODE_FOLLOW    = 1750


def _map(value: int, in_min: int, in_max: int,
         out_min: float, out_max: float) -> float:
    """Linear map with clamp."""
    value = max(in_min, min(in_max, value))
    return (value - in_min) / (in_max - in_min) * (out_max - out_min) + out_min


class ReceiverNode(Node):

    def __init__(self):
        super().__init__('receiver_node')

        self.declare_parameter('port',              '/dev/ttyAMA0')
        self.declare_parameter('baudrate',          115200)
        self.declare_parameter('deadzone',          0.05)   # 5% stick deadzone
        self.declare_parameter('max_linear_speed',  0.5)    # m/s at full throttle
        self.declare_parameter('max_angular_speed', 1.0)    # rad/s at full steer

        port     = self.get_parameter('port').value
        baudrate = self.get_parameter('baudrate').value
        self._dz      = self.get_parameter('deadzone').value
        self._max_lin = self.get_parameter('max_linear_speed').value
        self._max_ang = self.get_parameter('max_angular_speed').value

        # Publishers
        self._pub_cmd    = self.create_publisher(Twist,           '/dashboard/manual_cmd',   10)
        self._pub_estop  = self.create_publisher(Bool,            '/vehicle/emergency_stop', 10)
        self._pub_mode   = self.create_publisher(String,          '/rc/mode_select',         10)
        self._pub_raw    = self.create_publisher(Int32MultiArray, '/rc/channels',            10)

        # State
        self._killed       = False
        self._last_mode    = ''
        self._buf          = bytearray()

        # Serial
        try:
            self._serial = serial.Serial(port, baudrate=baudrate, timeout=0.02)
            self.get_logger().info(f'RC receiver connected on {port}')
        except serial.SerialException as e:
            self.get_logger().error(f'Cannot open receiver port {port}: {e}')
            self._serial = None

        # Read loop at ~100 Hz (iBUS arrives ~143 Hz, we process as fast as it comes)
        self.create_timer(0.01, self._read)

    # ── Serial read & parse ────────────────────────────────────────────

    def _read(self):
        if self._serial is None:
            return
        try:
            waiting = self._serial.in_waiting
            if waiting:
                self._buf.extend(self._serial.read(waiting))
        except serial.SerialException as e:
            self.get_logger().warn(f'Serial read error: {e}')
            return

        self._process_buffer()

    def _process_buffer(self):
        """Extract complete iBUS packets from the buffer and process them."""
        while len(self._buf) >= IBUS_LEN:
            # Find packet start
            idx = -1
            for i in range(len(self._buf) - 1):
                if self._buf[i] == IBUS_HEADER0 and self._buf[i+1] == IBUS_HEADER1:
                    idx = i
                    break

            if idx == -1:
                # No header found, keep last byte in case it's the first header byte
                self._buf = self._buf[-1:]
                return

            if idx > 0:
                # Discard bytes before header
                self._buf = self._buf[idx:]

            if len(self._buf) < IBUS_LEN:
                return  # Wait for more bytes

            packet = self._buf[:IBUS_LEN]

            if self._verify_checksum(packet):
                channels = self._parse_channels(packet)
                self._handle_channels(channels)

            # Advance buffer past this packet
            self._buf = self._buf[IBUS_LEN:]

    @staticmethod
    def _verify_checksum(packet: bytearray) -> bool:
        checksum = 0xFFFF
        for b in packet[:30]:
            checksum -= b
        received = packet[30] | (packet[31] << 8)
        return checksum == received

    @staticmethod
    def _parse_channels(packet: bytearray) -> list:
        channels = []
        for i in range(IBUS_NUM_CH):
            lo = packet[2 + i * 2]
            hi = packet[3 + i * 2]
            channels.append(lo | (hi << 8))
        return channels

    # ── Channel handling ───────────────────────────────────────────────

    def _handle_channels(self, ch: list):
        # Publish raw channels for debugging
        raw = Int32MultiArray()
        raw.data = ch
        self._pub_raw.publish(raw)

        # Kill switch (CH5 / SWA)
        killed = ch[CH_KILL] < KILL_THRESHOLD
        if killed != self._killed:
            self._killed = killed
            msg = Bool()
            msg.data = killed
            self._pub_estop.publish(msg)
            if killed:
                self.get_logger().warn(
                    'RC KILL SWITCH ACTIVATED – emergency stop published')
            else:
                self.get_logger().info('RC kill switch released')

        # Mode switch (CH6 / SWB) – only publish on change
        mode = self._decode_mode(ch[CH_MODE])
        if mode != self._last_mode:
            self._last_mode = mode
            msg = String()
            msg.data = mode
            self._pub_mode.publish(msg)
            self.get_logger().info(f'RC mode switch → {mode}')

        # Manual drive command (always publish so mission_node has fresh data)
        cmd = self._channels_to_twist(ch)
        self._pub_cmd.publish(cmd)

    def _decode_mode(self, value: int) -> str:
        if value < MODE_MANUAL:
            return 'manual'
        elif value < MODE_FOLLOW:
            return 'follow_me'
        else:
            return 'autonomous'

    def _channels_to_twist(self, ch: list) -> Twist:
        """Convert steering + throttle channels to Twist message."""
        # Throttle: 1000=reverse, 1500=neutral, 2000=forward → -1.0..+1.0
        throttle = _map(ch[CH_THROTTLE], 1000, 2000, -1.0, 1.0)
        # Steer: 1000=left, 1500=centre, 2000=right → +1.0..-1.0 (ROS left=positive)
        steer    = _map(ch[CH_STEER],    1000, 2000,  1.0, -1.0)

        # Apply deadzone
        throttle = 0.0 if abs(throttle) < self._dz else throttle
        steer    = 0.0 if abs(steer)    < self._dz else steer

        cmd = Twist()
        cmd.linear.x  = throttle * self._max_lin
        cmd.angular.z = steer    * self._max_ang
        return cmd

    # ── Cleanup ────────────────────────────────────────────────────────

    def destroy_node(self):
        if self._serial and self._serial.is_open:
            self._serial.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ReceiverNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
