"""
ros_bridge.py
Thread-safe brug tussen ROS2 en de FastAPI dashboard backend.

Architectuur:
  ROS2-thread  ─────► _state dict (threading.Lock) ◄────── FastAPI-thread
                                                              (reads, service calls)
  ROS2-thread  ──cv2.imencode──► _latest_frame (Lock) ◄──── /stream/color
  FastAPI WS   ─── 10 Hz timer ──► lees _state ──► stuur naar alle clients

Service-aanroepen:
  FastAPI-async ──► run_in_executor ──► blocking service call (ROS2-thread OK)

Mock mode (RCLPY niet beschikbaar of geen ROS2-master):
  Alle state bevat demo-waarden; services geven success=True.
"""

from __future__ import annotations

import json
import math
import os
import threading
import time
from typing import Any, Callable, Optional

# ── ROS2 (optioneel – mock als niet beschikbaar) ────────────────────────────
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
    from geometry_msgs.msg import Twist
    from sensor_msgs.msg import NavSatFix, Image
    from std_msgs.msg import Bool, String, Float32, Int32
    from std_srvs.srv import Trigger
    from rc_interfaces.msg import DetectionArray, TrackingTarget
    from rc_interfaces.srv import AddWaypoint, SetMode
    _HAS_ROS = True
except ImportError:
    _HAS_ROS = False

_SENSOR_QOS_DEPTH = 1


class RosBridge:
    """
    ROS2 → dashboard brug.

    Gebruik:
        bridge = RosBridge()
        bridge.start()          # Start ROS2 spin-thread
        ...
        bridge.stop()
    """

    def __init__(self) -> None:
        self._lock   = threading.Lock()
        self._frame_lock = threading.Lock()

        # ── Gedeelde state (lees-veilig na lock) ─────────────────────────
        self._state: dict[str, Any] = {
            "mode":             "idle",
            "emergency_stop":   False,
            "speed_ms":         0.0,
            "latitude":         None,
            "longitude":        None,
            "heading_deg":      None,
            "gps_quality":      0,
            "nav_status":       "idle",
            "nav_distance_m":   None,
            "avoidance_status": "clear",
            "ros_connected":    False,
            "detections":       [],
            "tracking":         {"tracking": False},
        }
        self._latest_frame: Optional[bytes] = None   # JPEG bytes

        # ── Waypoints in geheugen (dashboard beheert de wachtrij) ────────
        self._waypoints: list[dict] = []
        self._wp_lock = threading.Lock()

        # ── Intern ───────────────────────────────────────────────────────
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._node: Optional[Any] = None
        self._ws_clients: list[Callable] = []
        self._ws_lock = threading.Lock()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._ros_thread, name="ros_bridge", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    # ── WebSocket client registratie ─────────────────────────────────────────

    def register_ws(self, callback: Callable[[dict], None]) -> None:
        with self._ws_lock:
            self._ws_clients.append(callback)

    def unregister_ws(self, callback: Callable[[dict], None]) -> None:
        with self._ws_lock:
            try:
                self._ws_clients.remove(callback)
            except ValueError:
                pass

    def _broadcast(self, msg: dict) -> None:
        with self._ws_lock:
            dead = []
            for cb in self._ws_clients:
                try:
                    cb(msg)
                except Exception:
                    dead.append(cb)
            for cb in dead:
                self._ws_clients.remove(cb)

    # ── State lezen ──────────────────────────────────────────────────────────

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    def get_latest_frame(self) -> Optional[bytes]:
        with self._frame_lock:
            return self._latest_frame

    def get_waypoints(self) -> list[dict]:
        with self._wp_lock:
            return list(self._waypoints)

    # ── Waypoint beheer (lokaal + ROS2 service) ──────────────────────────────

    def add_waypoint(
        self,
        lat: float,
        lon: float,
        radius_m: float = 1.5,
        label: str = "",
    ) -> dict:
        """Voeg waypoint toe: lokaal opslaan + ROS2 service aanroepen."""
        wp_id = -1
        if _HAS_ROS and self._node is not None:
            try:
                cli = self._node.create_client(
                    AddWaypoint, "/navigation/add_waypoint")
                if cli.wait_for_service(timeout_sec=1.0):
                    req = AddWaypoint.Request()
                    req.latitude        = lat
                    req.longitude       = lon
                    req.target_radius_m = radius_m
                    future = cli.call_async(req)
                    # Blocking wait (we're already in a thread-pool executor)
                    deadline = time.monotonic() + 2.0
                    while not future.done() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    if future.done():
                        wp_id = future.result().waypoint_id
                self._node.destroy_client(cli)
            except Exception as exc:
                print(f"[ros_bridge] add_waypoint service fout: {exc}")

        with self._wp_lock:
            idx = len(self._waypoints)
            if not label:
                label = f"WP{idx + 1}"
            wp = {
                "wp_id":    wp_id if wp_id >= 0 else idx + 1,
                "latitude":  lat,
                "longitude": lon,
                "radius_m":  radius_m,
                "label":     label,
                "status":    "pending",
            }
            self._waypoints.append(wp)
        return wp

    def clear_waypoints(self) -> bool:
        """Wis alle waypoints: lokaal + ROS2 service."""
        ok = True
        if _HAS_ROS and self._node is not None:
            ok = self._call_trigger("/navigation/clear")
        with self._wp_lock:
            self._waypoints = []
        return ok

    def _sync_waypoint_status(self) -> None:
        """Update lokale waypoint status op basis van nav_status."""
        with self._lock:
            nav = self._state.get("nav_status", "idle")
            nav_dist = self._state.get("nav_distance_m")

        with self._wp_lock:
            active_idx = None
            done_count = 0
            for i, wp in enumerate(self._waypoints):
                if wp["status"] == "active":
                    active_idx = i
                elif wp["status"] == "done":
                    done_count += 1

            if nav == "complete":
                for wp in self._waypoints:
                    wp["status"] = "done"
            elif nav == "navigating":
                # Eerste 'pending' of 'active' is het huidige waypoint
                for i, wp in enumerate(self._waypoints):
                    if wp["status"] == "done":
                        continue
                    if wp["status"] in ("pending", "active"):
                        wp["status"] = "active"
                        break

    # ── Service aanroepen (blocking, voor run_in_executor) ───────────────────

    def call_set_mode(self, mode: str) -> bool:
        if not _HAS_ROS or self._node is None:
            with self._lock:
                self._state["mode"] = mode
            return True
        try:
            cli = self._node.create_client(SetMode, "/mission/set_mode")
            if not cli.wait_for_service(timeout_sec=1.0):
                return False
            req = SetMode.Request()
            req.mode = mode
            future = cli.call_async(req)
            deadline = time.monotonic() + 2.0
            while not future.done() and time.monotonic() < deadline:
                time.sleep(0.05)
            self._node.destroy_client(cli)
            return future.done() and future.result().success
        except Exception as exc:
            print(f"[ros_bridge] set_mode fout: {exc}")
            return False

    def call_emergency_stop(self, active: bool) -> None:
        with self._lock:
            self._state["emergency_stop"] = active
        if _HAS_ROS and self._node is not None and hasattr(self, "_pub_estop"):
            msg = Bool()
            msg.data = active
            self._pub_estop.publish(msg)

    def call_nav_start(self)  -> bool: return self._call_trigger("/navigation/start")
    def call_nav_pause(self)  -> bool: return self._call_trigger("/navigation/pause")
    def call_nav_resume(self) -> bool: return self._call_trigger("/navigation/resume")

    def _call_trigger(self, service_name: str) -> bool:
        if not _HAS_ROS or self._node is None:
            return True
        try:
            cli = self._node.create_client(Trigger, service_name)
            if not cli.wait_for_service(timeout_sec=1.0):
                return False
            future = cli.call_async(Trigger.Request())
            deadline = time.monotonic() + 2.0
            while not future.done() and time.monotonic() < deadline:
                time.sleep(0.05)
            self._node.destroy_client(cli)
            return future.done() and future.result().success
        except Exception as exc:
            print(f"[ros_bridge] {service_name} fout: {exc}")
            return False

    def publish_manual_cmd(self, linear_x: float, angular_z: float) -> None:
        if _HAS_ROS and self._node is not None and hasattr(self, "_pub_cmd"):
            msg = Twist()
            msg.linear.x  = float(linear_x)
            msg.angular.z = float(angular_z)
            self._pub_cmd.publish(msg)

    # ── ROS2 spin thread ─────────────────────────────────────────────────────

    def _ros_thread(self) -> None:
        if not _HAS_ROS:
            print("[ros_bridge] ROS2 niet beschikbaar – mock mode")
            self._mock_loop()
            return

        try:
            if not rclpy.ok():
                rclpy.init()
        except Exception:
            self._mock_loop()
            return

        qos = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=_SENSOR_QOS_DEPTH,
        )

        try:
            self._node = rclpy.create_node("dashboard_node")
            node = self._node

            # ── Publishers ───────────────────────────────────────────────
            self._pub_cmd   = node.create_publisher(Twist, "/dashboard/manual_cmd", 10)
            self._pub_estop = node.create_publisher(Bool,  "/vehicle/emergency_stop", 10)

            # ── Subscribers ──────────────────────────────────────────────
            node.create_subscription(String,  "/mission/mode",
                                     self._cb_mode, 10)
            node.create_subscription(Bool,    "/vehicle/emergency_stop",
                                     self._cb_estop, 10)
            node.create_subscription(NavSatFix, "/gps/fix",
                                     self._cb_gps, qos)
            node.create_subscription(Float32, "/navigation/heading_deg",
                                     self._cb_heading, 10)
            node.create_subscription(Int32,   "/navigation/gps_quality",
                                     self._cb_gpsq, 10)
            node.create_subscription(String,  "/navigation/status",
                                     self._cb_nav_status, 10)
            node.create_subscription(Float32, "/navigation/distance_m",
                                     self._cb_nav_dist, 10)
            node.create_subscription(String,  "/avoidance/status",
                                     self._cb_avoid, 10)
            node.create_subscription(DetectionArray, "/detections",
                                     self._cb_detections, qos)
            node.create_subscription(TrackingTarget, "/tracking/status",
                                     self._cb_tracking, 10)
            node.create_subscription(Image, "/camera/annotated/image_raw",
                                     self._cb_image, qos)

            with self._lock:
                self._state["ros_connected"] = True

            print("[ros_bridge] ROS2 verbonden – spinnen…")

            # Spin in eigen thread
            while not self._stop_event.is_set() and rclpy.ok():
                rclpy.spin_once(node, timeout_sec=0.05)

        except Exception as exc:
            print(f"[ros_bridge] ROS2 fout: {exc}")
        finally:
            with self._lock:
                self._state["ros_connected"] = False
            try:
                if self._node:
                    self._node.destroy_node()
                if rclpy.ok():
                    rclpy.shutdown()
            except Exception:
                pass

    # ── ROS2 callbacks ───────────────────────────────────────────────────────

    def _cb_mode(self, msg: "String") -> None:
        with self._lock:
            self._state["mode"] = msg.data

    def _cb_estop(self, msg: "Bool") -> None:
        with self._lock:
            self._state["emergency_stop"] = msg.data

    def _cb_gps(self, msg: "NavSatFix") -> None:
        with self._lock:
            if msg.status.status >= 0:
                self._state["latitude"]  = msg.latitude
                self._state["longitude"] = msg.longitude

    def _cb_heading(self, msg: "Float32") -> None:
        with self._lock:
            self._state["heading_deg"] = msg.data

    def _cb_gpsq(self, msg: "Int32") -> None:
        with self._lock:
            self._state["gps_quality"] = msg.data

    def _cb_nav_status(self, msg: "String") -> None:
        with self._lock:
            self._state["nav_status"] = msg.data
        self._sync_waypoint_status()

    def _cb_nav_dist(self, msg: "Float32") -> None:
        with self._lock:
            self._state["nav_distance_m"] = round(msg.data, 1)

    def _cb_avoid(self, msg: "String") -> None:
        with self._lock:
            self._state["avoidance_status"] = msg.data

    def _cb_detections(self, msg: "DetectionArray") -> None:
        dets = []
        for d in msg.detections:
            dets.append({
                "class_name":  d.class_name,
                "confidence":  round(d.confidence, 2),
                "distance_m":  round(d.z_mm / 1000.0, 1) if d.z_mm > 0 else None,
                "is_person":   d.is_person,
                "is_obstacle": d.is_obstacle,
                "bbox":        [d.xmin, d.ymin, d.xmax, d.ymax],
            })
        with self._lock:
            self._state["detections"] = dets
        self._broadcast({"type": "detections", "data": dets})

    def _cb_tracking(self, msg: "TrackingTarget") -> None:
        with self._lock:
            self._state["tracking"] = {
                "tracking":   msg.tracking,
                "class_name": msg.class_name,
                "distance_m": round(msg.z_mm / 1000.0, 1) if msg.z_mm > 0 else None,
            }

    def _cb_image(self, msg: "Image") -> None:
        """Zet ROS Image om naar JPEG bytes voor MJPEG stream."""
        try:
            import numpy as np
            import cv2
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(
                msg.height, msg.width, -1)
            if msg.encoding == "rgb8":
                arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            _, jpeg = cv2.imencode(
                ".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 70])
            with self._frame_lock:
                self._latest_frame = jpeg.tobytes()
        except Exception:
            pass

    # ── Mock loop (geen ROS2) ─────────────────────────────────────────────────

    def _mock_loop(self) -> None:
        """Genereer demo-data als ROS2 niet beschikbaar is."""
        t = 0.0
        while not self._stop_event.is_set():
            t += 0.1
            with self._lock:
                self._state.update({
                    "ros_connected":    False,
                    "mode":             "manual",
                    "latitude":         52.3676 + 0.0001 * math.sin(t * 0.05),
                    "longitude":        4.9041  + 0.0001 * math.cos(t * 0.05),
                    "heading_deg":      (t * 5) % 360,
                    "gps_quality":      1,
                    "nav_status":       "idle",
                    "avoidance_status": "clear",
                    "emergency_stop":   False,
                    "detections":       [
                        {"class_name": "person", "confidence": 0.87,
                         "distance_m": 2.3, "is_person": True,
                         "is_obstacle": False, "bbox": [100, 50, 200, 300]},
                    ],
                })
            time.sleep(0.1)
