"""
navigation_node.py
GPS waypoint navigatie node voor de AI RC Car.

Werking:
  1. GPS-fix (NavSatFix) → lokale ENU positie via CoordinateTransform
  2. IMU gyro + GPS-positiedelta → koers via HeadingFilter (complementair)
  3. Pure pursuit controller → cmd_vel richting huidig waypoint
  4. Waypoint bereikt → volgende uit wachtrij; allemaal bereikt → COMPLETE

Geabonneerd op:
  /gps/fix              sensor_msgs/NavSatFix         (GPS positie)
  /imu/data             sensor_msgs/Imu               (gyro voor koers)
  /mission/mode         std_msgs/String               (alleen actief in 'autonomous')

Publiceert:
  /navigation/cmd_vel         geometry_msgs/Twist         (sturing, 20 Hz)
  /navigation/status          std_msgs/String             (IDLE/NAVIGATING/…)
  /navigation/distance_m      std_msgs/Float32            (afstand tot waypoint)
  /navigation/heading_deg     std_msgs/Float32            (huidige koers, debug)
  /navigation/gps_quality     std_msgs/Int32              (GPS fix kwaliteit)

Services:
  /navigation/add_waypoint    rc_interfaces/srv/AddWaypoint
  /navigation/start           std_srvs/srv/Trigger
  /navigation/pause           std_srvs/srv/Trigger
  /navigation/resume          std_srvs/srv/Trigger
  /navigation/clear           std_srvs/srv/Trigger

Action server:
  /navigation/navigate_to     rc_interfaces/action/NavigateTo
  (Voegt één waypoint toe, start navigatie, meldt resultaat)

Parameters:
  lookahead_m       float  2.5    Pure pursuit blik-vooruit (m)
  max_linear        float  0.5    Maximale rijsnelheid (m/s)
  min_linear        float  0.1    Minimale rijsnelheid bij nadering (m/s)
  max_angular       float  1.2    Maximale draaisnelheid (rad/s)
  slow_radius_m     float  3.0    Begin remmen op X meter van waypoint
  target_radius_m   float  1.5    Aankomstradius (m) – standaard, overschrijfbaar per wp
  gps_timeout_s     float  2.0    Stop als GPS langer dan X s wegvalt
  imu_alpha         float  0.95   IMU gewicht in heading filter
  min_speed_gps     float  0.4    Min GPS-snelheid voor koers-update (m/s)
  set_origin_on_start bool true   Gebruik eerste GPS-fix als nulpunt
"""

from __future__ import annotations

import math
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy

from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix, NavSatStatus, Imu
from std_msgs.msg import String, Float32, Int32
from std_srvs.srv import Trigger

from rc_interfaces.srv import AddWaypoint
from rc_interfaces.action import NavigateTo

from .coordinate_transform import CoordinateTransform, LocalPoint
from .heading_filter import HeadingFilter
from .pure_pursuit import PurePursuit, PursuitResult
from .waypoint_manager import WaypointManager, NavState

# ── QoS ────────────────────────────────────────────────────────────────────
_SENSOR_QOS = QoSProfile(
    reliability=QoSReliabilityPolicy.BEST_EFFORT,
    history=QoSHistoryPolicy.KEEP_LAST,
    depth=1,
)

# ── GPS kwaliteitsdrempel (NMEA GGA fix quality) ────────────────────────────
_MIN_GPS_QUALITY = 1   # 0=no fix, 1=GPS, 2=DGPS, 4=RTK


class NavigationNode(Node):
    """
    Waypoint-navigatie node.

    Integreert GPS, IMU, pure pursuit en waypoint-beheer in één node.
    Alleen actief als mission_mode == 'autonomous'.
    """

    def __init__(self) -> None:
        super().__init__("navigation_node")

        # ── parameters ──────────────────────────────────────────────────
        self.declare_parameter("lookahead_m",        2.5)
        self.declare_parameter("max_linear",         0.5)
        self.declare_parameter("min_linear",         0.1)
        self.declare_parameter("max_angular",        1.2)
        self.declare_parameter("slow_radius_m",      3.0)
        self.declare_parameter("target_radius_m",    1.5)
        self.declare_parameter("gps_timeout_s",      2.0)
        self.declare_parameter("imu_alpha",          0.95)
        self.declare_parameter("min_speed_gps",      0.4)
        self.declare_parameter("set_origin_on_start", True)
        self.declare_parameter("publish_rate",       20.0)

        pp_params = {
            "lookahead_m":   self.get_parameter("lookahead_m").value,
            "max_linear":    self.get_parameter("max_linear").value,
            "min_linear":    self.get_parameter("min_linear").value,
            "max_angular":   self.get_parameter("max_angular").value,
            "slow_radius_m": self.get_parameter("slow_radius_m").value,
            "target_radius": self.get_parameter("target_radius_m").value,
        }

        self._gps_timeout    = self.get_parameter("gps_timeout_s").value
        self._set_origin_auto = self.get_parameter("set_origin_on_start").value
        rate: float          = self.get_parameter("publish_rate").value

        # ── componenten ─────────────────────────────────────────────────
        self._transform   = CoordinateTransform()
        self._heading_flt = HeadingFilter(
            alpha         = self.get_parameter("imu_alpha").value,
            min_speed_ms  = self.get_parameter("min_speed_gps").value,
        )
        self._pursuit     = PurePursuit(**pp_params)
        self._waypoints   = WaypointManager()

        # ── runtime state ────────────────────────────────────────────────
        self._position:     Optional[LocalPoint] = None
        self._gps_quality:  int   = 0
        self._gps_speed_ms: float = 0.0
        self._last_gps_ts:  float = 0.0
        self._last_imu_ts:  float = 0.0
        self._mission_mode: str   = "idle"
        self._action_goal_handle = None

        # ── publishers ──────────────────────────────────────────────────
        self._pub_cmd     = self.create_publisher(Twist,   "/navigation/cmd_vel",      10)
        self._pub_status  = self.create_publisher(String,  "/navigation/status",        10)
        self._pub_dist    = self.create_publisher(Float32, "/navigation/distance_m",    10)
        self._pub_heading = self.create_publisher(Float32, "/navigation/heading_deg",   10)
        self._pub_gpsq    = self.create_publisher(Int32,   "/navigation/gps_quality",   10)

        # ── subscribers ─────────────────────────────────────────────────
        self.create_subscription(
            NavSatFix, "/gps/fix", self._gps_cb, _SENSOR_QOS)
        self.create_subscription(
            Imu, "/imu/data", self._imu_cb, _SENSOR_QOS)
        self.create_subscription(
            String, "/mission/mode", self._mode_cb, 10)

        # ── services ────────────────────────────────────────────────────
        self.create_service(AddWaypoint, "/navigation/add_waypoint",
                            self._add_waypoint_cb)
        self.create_service(Trigger, "/navigation/start",  self._start_cb)
        self.create_service(Trigger, "/navigation/pause",  self._pause_cb)
        self.create_service(Trigger, "/navigation/resume", self._resume_cb)
        self.create_service(Trigger, "/navigation/clear",  self._clear_cb)

        # ── action server ───────────────────────────────────────────────
        self._action_server = ActionServer(
            self, NavigateTo, "/navigation/navigate_to",
            self._navigate_to_cb,
        )

        # ── timer ───────────────────────────────────────────────────────
        self.create_timer(1.0 / rate, self._control_loop)

        self.get_logger().info(
            f"NavigationNode gestart | lookahead={pp_params['lookahead_m']}m "
            f"max_v={pp_params['max_linear']}m/s rate={rate:.0f}Hz"
        )

    # ── GPS callback ─────────────────────────────────────────────────────────

    def _gps_cb(self, msg: NavSatFix) -> None:
        """Verwerk GPS-fix: update positie en koer (via heading filter)."""
        self._gps_quality = int(msg.status.status)

        if msg.status.status < _MIN_GPS_QUALITY:
            return   # Geen fix

        lat = msg.latitude
        lon = msg.longitude

        # Origin instellen op eerste geldige fix
        if not self._transform.has_origin and self._set_origin_auto:
            self._transform.set_origin(lat, lon)
            self.get_logger().info(
                f"GPS origin ingesteld: lat={lat:.6f} lon={lon:.6f}")

        if not self._transform.has_origin:
            return

        new_pos = self._transform.gps_to_local(lat, lon)

        # Koers-update via positiedelta
        self._heading_flt.update_gps_position(
            new_pos.x, new_pos.y, self._gps_speed_ms or None)

        self._position   = new_pos
        self._last_gps_ts = time.monotonic()

    # ── IMU callback ─────────────────────────────────────────────────────────

    def _imu_cb(self, msg: Imu) -> None:
        """Verwerk IMU gyro-meting: integreer koers."""
        now = time.monotonic()
        if self._last_imu_ts > 0:
            dt = now - self._last_imu_ts
            if dt < 0.5:   # Negeer grote sprongen (eerste cyclus of lag)
                self._heading_flt.update_gyro(
                    msg.angular_velocity.z, dt)
        self._last_imu_ts = now

    # ── Mission mode callback ─────────────────────────────────────────────────

    def _mode_cb(self, msg: String) -> None:
        self._mission_mode = msg.data

    # ── Service callbacks ─────────────────────────────────────────────────────

    def _add_waypoint_cb(
        self,
        req: AddWaypoint.Request,
        resp: AddWaypoint.Response,
    ) -> AddWaypoint.Response:
        wp_id = self._waypoints.add(
            latitude  = req.latitude,
            longitude = req.longitude,
            radius_m  = float(req.target_radius_m) if req.target_radius_m > 0
                        else self.get_parameter("target_radius_m").value,
        )
        resp.success        = True
        resp.waypoint_id    = wp_id
        resp.total_waypoints = self._waypoints.total_waypoints
        self.get_logger().info(
            f"Waypoint {wp_id} toegevoegd: lat={req.latitude:.6f} "
            f"lon={req.longitude:.6f} r={req.target_radius_m:.1f}m"
        )
        return resp

    def _start_cb(
        self, req: Trigger.Request, resp: Trigger.Response
    ) -> Trigger.Response:
        if self._waypoints.start():
            resp.success = True
            resp.message = f"Navigatie gestart: {self._waypoints.total_waypoints} waypoints"
            self.get_logger().info(resp.message)
        else:
            resp.success = False
            resp.message = "Geen waypoints in wachtrij"
        return resp

    def _pause_cb(
        self, req: Trigger.Request, resp: Trigger.Response
    ) -> Trigger.Response:
        self._waypoints.pause()
        resp.success = True
        resp.message = "Navigatie gepauzeerd"
        return resp

    def _resume_cb(
        self, req: Trigger.Request, resp: Trigger.Response
    ) -> Trigger.Response:
        ok = self._waypoints.resume()
        resp.success = ok
        resp.message = "Navigatie hervat" if ok else "Niet gepauzeerd"
        return resp

    def _clear_cb(
        self, req: Trigger.Request, resp: Trigger.Response
    ) -> Trigger.Response:
        self._waypoints.clear()
        resp.success = True
        resp.message = "Waypoints gewist"
        self.get_logger().info("Alle waypoints gewist")
        return resp

    # ── Action server ──────────────────────────────────────────────────────

    def _navigate_to_cb(self, goal_handle) -> NavigateTo.Result:
        """
        NavigateTo action: voeg één waypoint toe, start navigatie,
        volg voortgang via feedback en meld resultaat.
        """
        req = goal_handle.request
        self.get_logger().info(
            f"NavigateTo goal ontvangen: lat={req.latitude:.6f} "
            f"lon={req.longitude:.6f}")

        # Reset en voeg waypoint toe
        self._waypoints.clear()
        self._waypoints.add(
            req.latitude, req.longitude,
            float(req.target_radius_m) if req.target_radius_m > 0
            else self.get_parameter("target_radius_m").value,
        )
        self._waypoints.start()
        self._action_goal_handle = goal_handle

        start_time = time.monotonic()

        # Wacht tot COMPLETE, ERROR, of goal gecanceld
        feedback = NavigateTo.Feedback()
        while rclpy.ok():
            state = self._waypoints.state

            if goal_handle.is_cancel_requested:
                self._waypoints.pause()
                goal_handle.canceled()
                self._action_goal_handle = None
                result = NavigateTo.Result()
                result.success             = False
                result.distance_traveled_m = 0.0
                result.duration_s          = float(time.monotonic() - start_time)
                return result

            if state == NavState.COMPLETE:
                goal_handle.succeed()
                self._action_goal_handle = None
                result = NavigateTo.Result()
                result.success             = True
                result.distance_traveled_m = 0.0   # TODO: track
                result.duration_s          = float(time.monotonic() - start_time)
                self.get_logger().info("NavigateTo: doel bereikt")
                return result

            if state == NavState.ERROR:
                goal_handle.abort()
                self._action_goal_handle = None
                result = NavigateTo.Result()
                result.success             = False
                result.distance_traveled_m = 0.0
                result.duration_s          = float(time.monotonic() - start_time)
                return result

            # Feedback publiceren
            if self._position is not None:
                wp = self._waypoints.current_waypoint
                if wp is not None:
                    target = self._transform.gps_to_local(
                        wp.latitude, wp.longitude)
                    dist = self._position.distance_to(target)
                    feedback.distance_remaining_m = float(dist)
                    feedback.current_speed_ms     = self._gps_speed_ms
                    feedback.status               = str(state)
                    goal_handle.publish_feedback(feedback)

            time.sleep(0.2)

        result = NavigateTo.Result()
        result.success = False
        return result

    # ── Hoofdcontrolelus ──────────────────────────────────────────────────────

    def _control_loop(self) -> None:
        """20 Hz: bereken cmd_vel en publiceer status."""
        now = time.monotonic()

        # ── GPS timeout check ────────────────────────────────────────────
        gps_age = now - self._last_gps_ts if self._last_gps_ts > 0 else 999.0
        if gps_age > self._gps_timeout and self._waypoints.is_navigating:
            self.get_logger().warn(
                f"GPS verloren ({gps_age:.1f}s) – navigatie gestopt")
            self._waypoints.set_error("GPS timeout")

        # ── Publiceer debug info ─────────────────────────────────────────
        self._pub_status.publish(
            self._make_str(self._waypoints.state_str))
        self._pub_gpsq.publish(self._make_int32(self._gps_quality))

        if self._heading_flt.heading_deg is not None:
            self._pub_heading.publish(
                self._make_float(self._heading_flt.heading_deg))

        # ── Alleen navigeren als in autonomous modus ─────────────────────
        if self._mission_mode != "autonomous":
            self._pub_cmd.publish(Twist())
            return

        if not self._waypoints.is_navigating:
            self._pub_cmd.publish(Twist())
            return

        # ── Positie en koers beschikbaar? ───────────────────────────────
        if self._position is None:
            self.get_logger().warn("Wacht op GPS-fix…", throttle_duration_sec=5.0)
            self._pub_cmd.publish(Twist())
            return

        if self._heading_flt.heading is None:
            self.get_logger().info(
                "Wacht op koersschatting (rij langzaam vooruit om te calibreren)…",
                throttle_duration_sec=5.0,
            )
            # Langzaam recht vooruit rijden zodat heading-filter initialiseren kan
            cmd = Twist()
            cmd.linear.x = self.get_parameter("min_linear").value
            self._pub_cmd.publish(cmd)
            return

        # ── Huidig waypoint ──────────────────────────────────────────────
        wp = self._waypoints.current_waypoint
        if wp is None:
            self._pub_cmd.publish(Twist())
            return

        target = self._transform.gps_to_local(wp.latitude, wp.longitude)

        # ── Pure pursuit ─────────────────────────────────────────────────
        result = self._pursuit.compute(
            robot_x       = self._position.x,
            robot_y       = self._position.y,
            robot_heading = self._heading_flt.heading,
            target_x      = target.x,
            target_y      = target.y,
        )

        # Afstand publeren
        self._pub_dist.publish(self._make_float(result.distance))

        # ── Waypoint bereikt? ────────────────────────────────────────────
        if result.arrived or result.distance < wp.radius_m:
            label = wp.label
            has_next = self._waypoints.mark_arrived()
            if has_next:
                next_wp = self._waypoints.current_waypoint
                self.get_logger().info(
                    f"Waypoint '{label}' bereikt → volgende: {next_wp.label}")
            else:
                self.get_logger().info(
                    f"Waypoint '{label}' bereikt – route COMPLETE")
            self._pub_cmd.publish(Twist())
            return

        # ── Publiceer cmd_vel ────────────────────────────────────────────
        cmd = Twist()
        cmd.linear.x  = result.linear_x
        cmd.angular.z = result.angular_z
        self._pub_cmd.publish(cmd)

        self.get_logger().debug(
            f"Nav: dist={result.distance:.1f}m "
            f"hdg_err={math.degrees(result.heading_error):.1f}° "
            f"v={result.linear_x:.2f}m/s w={result.angular_z:.2f}rad/s",
            throttle_duration_sec=1.0,
        )

    # ── Hulp ────────────────────────────────────────────────────────────────

    def _make_str(self, s: str) -> String:
        m = String()
        m.data = s
        return m

    def _make_float(self, v: float) -> Float32:
        m = Float32()
        m.data = float(v)
        return m

    def _make_int32(self, v: int) -> Int32:
        m = Int32()
        m.data = int(v)
        return m


def main(args=None) -> None:
    rclpy.init(args=args)
    node = NavigationNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
