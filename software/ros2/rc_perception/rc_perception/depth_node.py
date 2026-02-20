"""
depth_node.py
Verwerkt het diepteframe van de OAK-D Lite naar een ObstacleMap.

De ObstacleMap verdeelt het gezichtsveld in zones:
  - 5 horizontale zones (LINKS_BUITEN, LINKS, MIDDEN, RECHTS, RECHTS_BUITEN)
  - 2 afstandsdrempels: DICHTBIJ (< warn_dist_mm) en VER_WEG (< stop_dist_mm)

Gepubliceerde topics:
  /camera/obstacle_map    rc_interfaces/msg/ObstacleMap   (10 Hz)

Geabonneerde topics:
  /camera/depth/image_rect_raw    sensor_msgs/Image (mono16, mm)

Aanpak:
  - Elke zone is een percentage-strip van het breedte
  - Mediaan van de pixel-waarden in de zone (robuust voor ruis)
  - Drempel 1 (stop_dist_mm): obstakel TE DICHTBIJ  → rijstrook geblokkeerd
  - Drempel 2 (warn_dist_mm): obstakel AANKOMEND    → waarschuwing

  De avoidance_node (rc_avoidance package, TODO) leest de ObstacleMap
  en berekent uitwijkmanoeuvres.
"""

from __future__ import annotations

import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from sensor_msgs.msg import Image

from rc_interfaces.msg import ObstacleMap

# ── QoS ────────────────────────────────────────────────────────────────────
_SENSOR_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

# ── Zone definities (x-fractie van frame breedte) ──────────────────────────
# 5 horizontale kolommen
ZONES = [
    ("far_left",    0.00, 0.20),
    ("left",        0.20, 0.40),
    ("center",      0.40, 0.60),
    ("right",       0.60, 0.80),
    ("far_right",   0.80, 1.00),
]

# Alleen de onderste helft van het frame (weg/grond, niet lucht)
DEPTH_ROW_START_FRAC = 0.4
DEPTH_ROW_END_FRAC   = 0.9

# Ongeldige dieptemetingen (0 = geen meting, 65535 = max)
DEPTH_MIN_VALID = 100    # mm
DEPTH_MAX_VALID = 8000   # mm


class DepthNode(Node):
    """
    Converteert diepteframes naar een gesegmenteerde ObstacleMap.

    Parameters (ROS2):
      stop_dist_mm   float   800.0    Afstand waaronder zone GEBLOKKEERD is
      warn_dist_mm   float   1500.0   Afstand waaronder zone WAARSCHUWING
      publish_rate   float   10.0     Hz
    """

    def __init__(self) -> None:
        super().__init__("depth_node")

        self.declare_parameter("stop_dist_mm", 800.0)
        self.declare_parameter("warn_dist_mm", 1500.0)
        self.declare_parameter("publish_rate", 10.0)

        self._stop_dist: float = self.get_parameter("stop_dist_mm").value
        self._warn_dist: float = self.get_parameter("warn_dist_mm").value
        rate: float            = self.get_parameter("publish_rate").value

        self._latest_depth: np.ndarray | None = None
        self._latest_stamp = None

        # ── subscriber ──────────────────────────────────────────────────
        self.create_subscription(
            Image, "/camera/depth/image_rect_raw",
            self._depth_callback, _SENSOR_QOS)

        # ── publisher ───────────────────────────────────────────────────
        self._pub = self.create_publisher(ObstacleMap, "/camera/obstacle_map", 10)

        # ── timer ───────────────────────────────────────────────────────
        self.create_timer(1.0 / rate, self._process)

        self.get_logger().info(
            f"DepthNode gestart | stop={self._stop_dist:.0f}mm "
            f"warn={self._warn_dist:.0f}mm rate={rate:.0f}Hz"
        )

    def _depth_callback(self, msg: Image) -> None:
        """Sla het laatste diepteframe op."""
        # mono16: 2 bytes per pixel, little-endian, waarden in mm
        arr = np.frombuffer(msg.data, dtype=np.uint16).reshape(
            (msg.height, msg.width))
        self._latest_depth = arr
        self._latest_stamp = msg.header.stamp

    def _process(self) -> None:
        """Verwerk het opgeslagen diepteframe en publiceer ObstacleMap."""
        if self._latest_depth is None:
            return

        frame = self._latest_depth
        h, w = frame.shape

        # Rijbereik: alleen het lagere deel van het frame
        r0 = int(h * DEPTH_ROW_START_FRAC)
        r1 = int(h * DEPTH_ROW_END_FRAC)
        roi = frame[r0:r1, :]

        msg = ObstacleMap()
        msg.header.stamp = (
            self._latest_stamp
            if self._latest_stamp is not None
            else self.get_clock().now().to_msg()
        )
        msg.header.frame_id = "oak_rgb_camera_optical_frame"
        msg.num_zones = len(ZONES)

        for name, x_frac_start, x_frac_end in ZONES:
            c0 = int(w * x_frac_start)
            c1 = int(w * x_frac_end)
            strip = roi[:, c0:c1]

            # Filter ongeldige waarden
            valid = strip[(strip >= DEPTH_MIN_VALID) & (strip <= DEPTH_MAX_VALID)]

            if valid.size == 0:
                min_dist = float("inf")
            else:
                # Mediaan is robuuster dan minimum voor rauwe dieptedata
                min_dist = float(np.median(valid))

            # Status bepalen
            if min_dist < self._stop_dist:
                status = ObstacleMap.STATUS_BLOCKED
            elif min_dist < self._warn_dist:
                status = ObstacleMap.STATUS_WARNING
            else:
                status = ObstacleMap.STATUS_CLEAR

            msg.zone_names.append(name)
            msg.zone_distances_mm.append(
                min_dist if min_dist != float("inf") else -1.0)
            msg.zone_statuses.append(status)

        self._pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = DepthNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
