"""
avoidance_node.py
Obstakelvermijdingsnode voor de AI RC Car.

Combineert twee sensorbronnen:
  - /camera/obstacle_map  (ObstacleMap, 5 zone camera, OAK-D Lite depth_node)
  - /ultrasonic/distances (ObstacleMap, 4-richting ultrasoon, HC-SR04)

Publiceert naar mission_node:
  /avoidance/override     geometry_msgs/Twist   (override cmd_vel)
  /avoidance/status       std_msgs/String       ('clear'|'warning'|'danger'|'stop')
  /avoidance/active       std_msgs/Bool         (True als override actief is)

De mission_node activateert /avoidance/override als status in {'danger', 'stop'}.
Bij 'warning' wordt /avoidance/status gepubliceerd zodat andere nodes kunnen
reageren (bv. snelheid beperken) maar de rijstrategie wordt pas overreden bij
'danger' of 'stop'.

Parameters:
  stop_dist_mm    float   800.0   Afstand waaronder zone GEBLOKKEERD
  warn_dist_mm    float   1500.0  Afstand waaronder zone WAARSCHUWING
  max_linear      float   0.4     Maximale rijsnelheid (m/s)
  max_angular     float   1.2     Maximale draaisnelheid (rad/s)
  sensor_timeout  float   0.8     Sensor stale timeout (s)
  publish_rate    float   20.0    Loop frequentie (Hz)
"""

from __future__ import annotations

import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String

from rc_interfaces.msg import ObstacleMap

from .zone_analyzer import (
    ZoneState,
    AvoidanceDecision,
    HysteresisFilter,
    fuse_sources,
    analyze,
)

# ── QoS ────────────────────────────────────────────────────────────────────
_SENSOR_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)


class AvoidanceNode(Node):
    """
    Obstakelvermijding via sensor fusie (camera + ultrasoon).

    Statusmachine (zie zone_analyzer.py):
      clear   → geen override
      warning → override met gereduceerde snelheid + stuurcorrectie
      danger  → override: stop + harde stuurcorrectie
      stop    → override: volledig stilstand
    """

    def __init__(self) -> None:
        super().__init__("avoidance_node")

        # ── parameters ──────────────────────────────────────────────────
        self.declare_parameter("stop_dist_mm",   800.0)
        self.declare_parameter("warn_dist_mm",   1500.0)
        self.declare_parameter("max_linear",     0.4)
        self.declare_parameter("max_angular",    1.2)
        self.declare_parameter("sensor_timeout", 0.8)
        self.declare_parameter("publish_rate",   20.0)

        self._stop_mm:   float = self.get_parameter("stop_dist_mm").value
        self._warn_mm:   float = self.get_parameter("warn_dist_mm").value
        self._max_lin:   float = self.get_parameter("max_linear").value
        self._max_ang:   float = self.get_parameter("max_angular").value
        self._timeout:   float = self.get_parameter("sensor_timeout").value
        rate:            float = self.get_parameter("publish_rate").value

        # ── state ────────────────────────────────────────────────────────
        self._depth_map: Optional[ObstacleMap]  = None
        self._us_map:    Optional[ObstacleMap]  = None
        self._depth_ts:  float = 0.0
        self._us_ts:     float = 0.0

        self._hysteresis = HysteresisFilter(count=4)
        self._last_status = "clear"

        # ── publishers ──────────────────────────────────────────────────
        self._pub_override = self.create_publisher(
            Twist, "/avoidance/override", 10)
        self._pub_status = self.create_publisher(
            String, "/avoidance/status", 10)
        self._pub_active = self.create_publisher(
            Bool, "/avoidance/active", 10)

        # ── subscribers ─────────────────────────────────────────────────
        self.create_subscription(
            ObstacleMap, "/camera/obstacle_map",
            self._depth_cb, _SENSOR_QOS)
        self.create_subscription(
            ObstacleMap, "/ultrasonic/distances",
            self._us_cb, _SENSOR_QOS)

        # ── timer ───────────────────────────────────────────────────────
        self.create_timer(1.0 / rate, self._loop)

        self.get_logger().info(
            f"AvoidanceNode gestart | stop={self._stop_mm:.0f}mm "
            f"warn={self._warn_mm:.0f}mm rate={rate:.0f}Hz"
        )

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _depth_cb(self, msg: ObstacleMap) -> None:
        self._depth_map = msg
        self._depth_ts  = time.monotonic()

    def _us_cb(self, msg: ObstacleMap) -> None:
        self._us_map = msg
        self._us_ts  = time.monotonic()

    # ── Hoofdloop ────────────────────────────────────────────────────────────

    def _loop(self) -> None:
        now = time.monotonic()

        # ── Haal diepte-zones op (camera) ───────────────────────────────
        depth_zones: list[ZoneState] = []
        if (self._depth_map is not None
                and now - self._depth_ts < self._timeout):
            depth_zones = self._parse_depth_map(self._depth_map)

        # ── Haal ultrasoon-waarden op ───────────────────────────────────
        us_front = us_rear = us_left = us_right = -1.0
        if (self._us_map is not None
                and now - self._us_ts < self._timeout):
            us_front = float(self._us_map.front_m)
            us_rear  = float(self._us_map.rear_m)
            us_left  = float(self._us_map.left_m)
            us_right = float(self._us_map.right_m)

        # ── Geen sensordata beschikbaar ─────────────────────────────────
        if not depth_zones and us_front < 0:
            self._publish("clear", AvoidanceDecision(
                status="clear", linear_x=self._max_lin,
                angular_z=0.0, reason="Geen sensordata"))
            return

        # ── Fuseer bronnen ───────────────────────────────────────────────
        zones = fuse_sources(
            depth_zones  = depth_zones,
            us_front_m   = us_front,
            us_rear_m    = us_rear,
            us_left_m    = us_left,
            us_right_m   = us_right,
            stop_dist_mm = self._stop_mm,
            warn_dist_mm = self._warn_mm,
        )

        # ── Analyseer en besluit ─────────────────────────────────────────
        decision = analyze(
            zones        = zones,
            max_linear   = self._max_lin,
            max_angular  = self._max_ang,
            stop_dist_mm = self._stop_mm,
            warn_dist_mm = self._warn_mm,
        )

        # ── Hysterese ────────────────────────────────────────────────────
        smoothed_status = self._hysteresis.update(decision.status)
        smoothed_decision = AvoidanceDecision(
            status    = smoothed_status,
            linear_x  = decision.linear_x  if smoothed_status == decision.status else self._max_lin,
            angular_z = decision.angular_z if smoothed_status == decision.status else 0.0,
            reason    = decision.reason,
        )

        self._publish(smoothed_status, smoothed_decision)

    # ── Publiceren ──────────────────────────────────────────────────────────

    def _publish(self, status: str, decision: AvoidanceDecision) -> None:
        # Status string
        status_msg = String()
        status_msg.data = status
        self._pub_status.publish(status_msg)

        # Actief vlaggetje
        active = status in ("warning", "danger", "stop")
        active_msg = Bool()
        active_msg.data = active
        self._pub_active.publish(active_msg)

        # Override Twist (altijd publiceren zodat mission_node altijd iets heeft)
        cmd = Twist()
        if active:
            cmd.linear.x  = float(decision.linear_x)
            cmd.angular.z = float(decision.angular_z)

        self._pub_override.publish(cmd)

        # Log bij statuswijziging
        if status != self._last_status:
            level = {
                "clear":   self.get_logger().info,
                "warning": self.get_logger().warn,
                "danger":  self.get_logger().warn,
                "stop":    self.get_logger().error,
            }.get(status, self.get_logger().info)
            level(
                f"Avoidance status: {self._last_status} → {status} | "
                f"{decision.reason}"
            )
            self._last_status = status

    # ── Hulp ────────────────────────────────────────────────────────────────

    def _parse_depth_map(self, msg: ObstacleMap) -> list[ZoneState]:
        """Converteer ObstacleMap ROS bericht naar ZoneState lijst."""
        zones: list[ZoneState] = []
        for i, name in enumerate(msg.zone_names):
            if i >= len(msg.zone_statuses):
                break
            dist = msg.zone_distances_mm[i] if i < len(msg.zone_distances_mm) else -1.0
            zones.append(ZoneState(
                name         = name,
                distance_mm  = float(dist),
                status       = int(msg.zone_statuses[i]),
            ))
        return zones


def main(args=None) -> None:
    rclpy.init(args=args)
    node = AvoidanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
