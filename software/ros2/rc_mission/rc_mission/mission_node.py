"""
mission_node  –  Mode arbitration and command muxer

Modes:
  idle         Vehicle stands still, no commands forwarded
  manual       Commands from /dashboard/manual_cmd passed through
  autonomous   Commands from /navigation/cmd_vel passed through
  follow_me    Commands from /tracking/cmd_vel passed through

Priority (highest → lowest):
  1. emergency_stop  – overrides everything, cuts motors
  2. avoidance       – can override linear/angular in any auto mode
  3. autonomous      – Nav2 cmd_vel
  4. follow_me       – tracking cmd_vel
  5. manual          – dashboard joystick

Subscribes:
  /vehicle/emergency_stop   std_msgs/Bool
  /avoidance/override       geometry_msgs/Twist
  /avoidance/status         std_msgs/String
  /navigation/cmd_vel       geometry_msgs/Twist
  /tracking/cmd_vel         geometry_msgs/Twist
  /dashboard/manual_cmd     geometry_msgs/Twist

Publishes:
  /vehicle/cmd_vel          geometry_msgs/Twist
  /mission/mode             std_msgs/String

Services:
  /mission/set_mode         rc_interfaces/SetMode
"""

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String
from rc_interfaces.srv import SetMode

VALID_MODES = {'idle', 'manual', 'autonomous', 'follow_me'}


class MissionNode(Node):

    def __init__(self):
        super().__init__('mission_node')

        # ── State ─────────────────────────────────────────────────────
        self._mode      = 'idle'
        self._emergency = False

        # Latest commands from each source
        self._cmd_nav      = Twist()
        self._cmd_follow   = Twist()
        self._cmd_manual   = Twist()
        self._cmd_avoid    = None     # None = avoidance not active
        self._avoid_status = 'clear'

        # ── Subscriptions ─────────────────────────────────────────────
        self.create_subscription(Bool,   '/vehicle/emergency_stop',  self._estop_cb,  10)
        self.create_subscription(String, '/avoidance/status',        self._avoid_status_cb, 10)
        self.create_subscription(Twist,  '/avoidance/override',      self._avoid_cb,  10)
        self.create_subscription(Twist,  '/navigation/cmd_vel',      self._nav_cb,    10)
        self.create_subscription(Twist,  '/tracking/cmd_vel',        self._follow_cb, 10)
        self.create_subscription(Twist,  '/dashboard/manual_cmd',    self._manual_cb, 10)

        # ── Publishers ────────────────────────────────────────────────
        self._pub_cmd  = self.create_publisher(Twist,  '/vehicle/cmd_vel', 10)
        self._pub_mode = self.create_publisher(String, '/mission/mode',    10)

        # ── Service ───────────────────────────────────────────────────
        self.create_service(SetMode, '/mission/set_mode', self._set_mode_cb)

        # ── Timer: publish cmd at 20 Hz ───────────────────────────────
        self.create_timer(0.05, self._publish_cmd)

        self.get_logger().info(f'Mission node ready. Mode: {self._mode}')

    # ── Subscription callbacks ─────────────────────────────────────────

    def _estop_cb(self, msg: Bool):
        self._emergency = msg.data
        if self._emergency:
            self.get_logger().warn('EMERGENCY STOP received – halting vehicle')

    def _avoid_status_cb(self, msg: String):
        self._avoid_status = msg.data

    def _avoid_cb(self, msg: Twist):
        self._cmd_avoid = msg

    def _nav_cb(self, msg: Twist):
        self._cmd_nav = msg

    def _follow_cb(self, msg: Twist):
        self._cmd_follow = msg

    def _manual_cb(self, msg: Twist):
        self._cmd_manual = msg

    # ── Service callback ───────────────────────────────────────────────

    def _set_mode_cb(self, req: SetMode.Request, resp: SetMode.Response):
        mode = req.mode.lower()
        if mode not in VALID_MODES:
            resp.success = False
            resp.message = f'Unknown mode "{mode}". Valid: {sorted(VALID_MODES)}'
            return resp

        self._mode = mode
        resp.success = True
        resp.message = f'Mode set to {mode}'
        self.get_logger().info(f'Mode changed → {mode}')
        return resp

    # ── Main publish loop ─────────────────────────────────────────────

    def _publish_cmd(self):
        # Publish current mode
        mode_msg = String()
        mode_msg.data = self._mode if not self._emergency else 'emergency_stop'
        self._pub_mode.publish(mode_msg)

        # Build cmd
        cmd = self._select_cmd()
        self._pub_cmd.publish(cmd)

    def _select_cmd(self) -> Twist:
        zero = Twist()

        # 1. Emergency stop
        if self._emergency:
            return zero

        # 2. Idle
        if self._mode == 'idle':
            return zero

        # 3. Select base command from active mode
        if self._mode == 'autonomous':
            base = self._cmd_nav
        elif self._mode == 'follow_me':
            base = self._cmd_follow
        elif self._mode == 'manual':
            base = self._cmd_manual
        else:
            return zero

        # 4. Apply avoidance override when active
        if self._avoid_status in ('danger', 'stop') and self._cmd_avoid is not None:
            return self._cmd_avoid

        return base


def main(args=None):
    rclpy.init(args=args)
    node = MissionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
