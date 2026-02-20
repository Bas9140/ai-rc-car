"""
tracking_node.py
Persoon-volgmodus (follow-me) op basis van camera-detecties.

Logica:
  1. Luistert naar /detections (DetectionArray van oak_node)
  2. Selecteert het meest geschikte target (dichtste persoon, of
     handmatig geselecteerde ID via /tracking/select_target)
  3. Berekent een cmd_vel op basis van het verschil tussen het
     midden van de bounding box en het frame midden (proportioneel)
  4. Publiceert /tracking/cmd_vel → mission_node gebruikt dit
     in follow_me modus

Coördinatenconventie:
  camera +X = rechts, ROS2 +Y_angular = links (tegenwijzers)
  → stuurcorrectie: angular.z = +gain × (bbox_cx - frame_cx) / frame_w
                    maar:  positieve angular.z = linksom draaien
  camera: positief x_offset = target rechts van midden
  robot:  linksomdraaien = positieve angular.z
  → angular.z = -gain_angular × (x_offset / frame_w)   ← negatief

  Afstand:  z_mm groot  → target ver weg  → meer voorwaartse snelheid
            z_mm klein  → target dichtbij → stop of achteruit

Gepubliceerde topics:
  /tracking/cmd_vel        geometry_msgs/Twist
  /tracking/status         rc_interfaces/msg/TrackingTarget

Geabonneerde topics:
  /detections              rc_interfaces/msg/DetectionArray
"""

from __future__ import annotations

import math
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

from rc_interfaces.msg import DetectionArray, Detection, TrackingTarget

# ── QoS ────────────────────────────────────────────────────────────────────
_SENSOR_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

# ── Constanten ──────────────────────────────────────────────────────────────
FRAME_W = 640
FRAME_H = 352

# Doelafstand (mm) waarbij de auto stil staat
TARGET_DISTANCE_MM = 1500.0   # 1.5 meter

# Dode zone: als target binnen dit bereik is hoeft er niet gecorrigeerd
ANGULAR_DEADZONE_PX = 30      # pixels
DISTANCE_DEADZONE_MM = 200    # mm

# Maximale snelheden
MAX_LINEAR_MPS  = 0.4         # m/s
MAX_ANGULAR_RPS = 1.2         # rad/s

# Overschrijd timeout: als er X seconden geen detectie is → stop
LOST_TIMEOUT_S = 1.5


class TrackingNode(Node):
    """
    Follow-me controller.

    Parameters (ROS2):
      gain_angular    float   1.8    P-gain voor stuurcorrectie
      gain_linear     float   0.0004 P-gain voor afstandscorrectie
      target_dist_mm  float   1500.0 Gewenste volgafstand
      max_linear      float   0.4    Maximale voorwaartse snelheid (m/s)
      max_angular     float   1.2    Maximale draaisnelheid (rad/s)
      lost_timeout    float   1.5    Stop na X s geen target gezien
    """

    def __init__(self) -> None:
        super().__init__("tracking_node")

        # ── parameters ──────────────────────────────────────────────────
        self.declare_parameter("gain_angular",   1.8)
        self.declare_parameter("gain_linear",    0.0004)
        self.declare_parameter("target_dist_mm", TARGET_DISTANCE_MM)
        self.declare_parameter("max_linear",     MAX_LINEAR_MPS)
        self.declare_parameter("max_angular",    MAX_ANGULAR_RPS)
        self.declare_parameter("lost_timeout",   LOST_TIMEOUT_S)

        self._k_ang:    float = self.get_parameter("gain_angular").value
        self._k_lin:    float = self.get_parameter("gain_linear").value
        self._tgt_dist: float = self.get_parameter("target_dist_mm").value
        self._max_lin:  float = self.get_parameter("max_linear").value
        self._max_ang:  float = self.get_parameter("max_angular").value
        self._timeout:  float = self.get_parameter("lost_timeout").value

        # ── state ────────────────────────────────────────────────────────
        self._last_det_time: Optional[float] = None
        self._target_lost = True

        # ── publishers ──────────────────────────────────────────────────
        self._pub_cmd = self.create_publisher(
            Twist, "/tracking/cmd_vel", 10)
        self._pub_status = self.create_publisher(
            TrackingTarget, "/tracking/status", 10)

        # ── subscribers ─────────────────────────────────────────────────
        self.create_subscription(
            DetectionArray, "/detections",
            self._det_callback, _SENSOR_QOS)

        # ── watchdog: stop als target te lang weg is ────────────────────
        self.create_timer(0.1, self._watchdog)

        self.get_logger().info(
            f"TrackingNode gestart | k_ang={self._k_ang} "
            f"k_lin={self._k_lin} tgt={self._tgt_dist:.0f}mm"
        )

    # ── Callback ────────────────────────────────────────────────────────────

    def _det_callback(self, msg: DetectionArray) -> None:
        """Verwerk nieuwe detecties en stuur de auto bij."""
        now = self.get_clock().now().nanoseconds * 1e-9

        # Selecteer het beste target: dichtstbijzijnde persoon
        target = self._select_target(msg.detections)

        if target is None:
            # Geen persoon gezien → status bijwerken, watchdog pakt dit op
            status = TrackingTarget()
            status.tracking = False
            self._pub_status.publish(status)
            return

        self._last_det_time = now
        self._target_lost = False

        # ── Bereken fouten ───────────────────────────────────────────────
        bbox_cx = (target.xmin + target.xmax) / 2.0
        x_offset = bbox_cx - FRAME_W / 2.0       # + = target rechts

        z_mm = target.z_mm
        dist_err = z_mm - self._tgt_dist          # + = te ver weg

        # ── Proportionele controller ─────────────────────────────────────
        # Hoeksnelheid: negatief omdat camera +x rechts is en
        # robot positief angular.z = linksom
        if abs(x_offset) < ANGULAR_DEADZONE_PX:
            angular_z = 0.0
        else:
            angular_z = -self._k_ang * (x_offset / FRAME_W)
            angular_z = float(
                max(-self._max_ang, min(self._max_ang, angular_z)))

        # Lineaire snelheid: positief = vooruit
        if abs(dist_err) < DISTANCE_DEADZONE_MM:
            linear_x = 0.0
        else:
            linear_x = self._k_lin * dist_err
            linear_x = float(
                max(-self._max_lin * 0.5, min(self._max_lin, linear_x)))

        # ── Publiceer cmd_vel ────────────────────────────────────────────
        cmd = Twist()
        cmd.linear.x  = linear_x
        cmd.angular.z = angular_z
        self._pub_cmd.publish(cmd)

        # ── Publiceer status ─────────────────────────────────────────────
        status = TrackingTarget()
        status.tracking    = True
        status.class_id    = target.class_id
        status.class_name  = target.class_name
        status.confidence  = target.confidence
        status.x_mm        = target.x_mm
        status.y_mm        = target.y_mm
        status.z_mm        = z_mm
        status.x_offset_px = x_offset
        self._pub_status.publish(status)

    def _select_target(
        self, dets: list[Detection]
    ) -> Optional[Detection]:
        """
        Kies de beste persoon om te volgen.

        Strategie: dichtste persoon met z_mm > 200 mm
        (detecties van < 200mm zijn onbetrouwbaar op OAK-D Lite).
        """
        persons = [d for d in dets if d.is_person and d.z_mm > 200]
        if not persons:
            return None
        # Sorteer op afstand
        return min(persons, key=lambda d: d.z_mm)

    # ── Watchdog ────────────────────────────────────────────────────────────

    def _watchdog(self) -> None:
        """Stuur stopcommando als target te lang niet gezien is."""
        if self._target_lost:
            return

        now = self.get_clock().now().nanoseconds * 1e-9
        if (self._last_det_time is not None
                and now - self._last_det_time > self._timeout):
            self._target_lost = True
            self.get_logger().warn("Target verloren – stoppend")
            self._pub_cmd.publish(Twist())   # nul-snelheid

            status = TrackingTarget()
            status.tracking = False
            self._pub_status.publish(status)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TrackingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
