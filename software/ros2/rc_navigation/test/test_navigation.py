"""
test_navigation.py
Unit tests voor navigatielogica (geen ROS of hardware vereist).

  pytest software/ros2/rc_navigation/test/test_navigation.py -v
"""

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from rc_navigation.coordinate_transform import CoordinateTransform, LocalPoint
from rc_navigation.pure_pursuit import PurePursuit
from rc_navigation.heading_filter import HeadingFilter
from rc_navigation.waypoint_manager import WaypointManager, NavState


# ── CoordinateTransform ──────────────────────────────────────────────────────

class TestCoordinateTransform:
    def test_origin_returns_zero(self):
        ct = CoordinateTransform()
        ct.set_origin(52.0, 5.0)
        pt = ct.gps_to_local(52.0, 5.0)
        assert abs(pt.x) < 0.01
        assert abs(pt.y) < 0.01

    def test_north_is_positive_y(self):
        ct = CoordinateTransform()
        ct.set_origin(52.0, 5.0)
        # 0.001 graad noord ≈ 111 m
        pt = ct.gps_to_local(52.001, 5.0)
        assert pt.y > 100.0
        assert abs(pt.x) < 1.0

    def test_east_is_positive_x(self):
        ct = CoordinateTransform()
        ct.set_origin(52.0, 5.0)
        pt = ct.gps_to_local(52.0, 5.001)
        assert pt.x > 50.0     # Lengtegraden zijn korter op 52°N
        assert abs(pt.y) < 1.0

    def test_round_trip(self):
        ct = CoordinateTransform()
        ct.set_origin(52.3676, 4.9041)   # Amsterdam CS
        lat, lon = 52.3690, 4.9060
        pt = ct.gps_to_local(lat, lon)
        lat2, lon2 = ct.local_to_gps(pt)
        assert abs(lat2 - lat) < 1e-7
        assert abs(lon2 - lon) < 1e-7

    def test_distance_to(self):
        a = LocalPoint(0.0, 0.0)
        b = LocalPoint(3.0, 4.0)
        assert abs(a.distance_to(b) - 5.0) < 1e-9

    def test_bearing_to_north(self):
        a = LocalPoint(0.0, 0.0)
        b = LocalPoint(0.0, 10.0)  # Noord
        bearing = a.bearing_to(b)
        assert abs(bearing - math.pi / 2) < 1e-9

    def test_bearing_to_east(self):
        a = LocalPoint(0.0, 0.0)
        b = LocalPoint(10.0, 0.0)  # Oost
        bearing = a.bearing_to(b)
        assert abs(bearing) < 1e-9

    def test_no_origin_raises(self):
        ct = CoordinateTransform()
        try:
            ct.gps_to_local(52.0, 5.0)
            assert False, "Verwacht RuntimeError"
        except RuntimeError:
            pass


# ── PurePursuit ──────────────────────────────────────────────────────────────

class TestPurePursuit:
    def setup_method(self):
        self.pp = PurePursuit(
            lookahead_m=2.0, max_linear=0.5, min_linear=0.1,
            max_angular=1.2, slow_radius_m=3.0, target_radius=1.0,
        )

    def test_arrived_within_radius(self):
        result = self.pp.compute(0, 0, 0.0, 0.5, 0.0)
        assert result.arrived is True
        assert result.linear_x == 0.0

    def test_straight_ahead_no_steer(self):
        # Doel recht voor de robot (oost)
        result = self.pp.compute(0, 0, 0.0, 10.0, 0.0)
        assert result.arrived is False
        assert abs(result.angular_z) < 0.1   # Lichte sturing toegestaan

    def test_target_left_steers_left(self):
        # Robot kijkt oost, doel recht-noord → links van robot → angular_z positief
        result = self.pp.compute(0, 0, 0.0, 5.0, 5.0)
        assert result.angular_z > 0.0

    def test_target_right_steers_right(self):
        # Robot kijkt oost, doel recht-zuid → rechts van robot → angular_z negatief
        result = self.pp.compute(0, 0, 0.0, 5.0, -5.0)
        assert result.angular_z < 0.0

    def test_speed_reduces_near_target(self):
        far  = self.pp.compute(0, 0, 0.0, 20.0, 0.0)
        near = self.pp.compute(0, 0, 0.0,  2.0, 0.0)
        assert far.linear_x >= near.linear_x

    def test_angular_clamped_to_max(self):
        # Doel direct links naast robot → maximale stuurhoek
        result = self.pp.compute(0, 0, 0.0, 0.1, 10.0)
        assert abs(result.angular_z) <= self.pp.max_angular + 1e-9

    def test_heading_north_target_east_steers_right(self):
        # Robot kijkt noord (π/2), doel oost → rechts van robot → angular_z negatief
        result = self.pp.compute(0, 0, math.pi / 2, 10.0, 0.0)
        assert result.angular_z < 0.0

    def test_heading_south_target_north(self):
        # Robot kijkt zuid (-π/2), doel noord → 180° omdraaien nodig
        result = self.pp.compute(0, 0, -math.pi / 2, 0.0, 10.0)
        # Er moet gestuurd worden (niet recht vooruit)
        assert abs(result.angular_z) > 0.1


# ── HeadingFilter ────────────────────────────────────────────────────────────

class TestHeadingFilter:
    def test_initial_heading_none(self):
        hf = HeadingFilter()
        assert hf.heading is None

    def test_first_gps_position_no_heading(self):
        hf = HeadingFilter()
        hf.update_gps_position(0.0, 0.0, speed_ms=1.0)
        assert hf.heading is None   # Eerste fix: sla op als referentie

    def test_heading_from_gps_positions_east(self):
        hf = HeadingFilter(min_speed_ms=0.1)
        hf.update_gps_position(0.0, 0.0, speed_ms=1.0)
        hf.update_gps_position(10.0, 0.0, speed_ms=1.0)  # Beweging oost
        assert hf.heading is not None
        assert abs(hf.heading) < 0.3   # ≈ 0 rad (oost)

    def test_heading_from_gps_positions_north(self):
        hf = HeadingFilter(min_speed_ms=0.1)
        hf.update_gps_position(0.0, 0.0, speed_ms=1.0)
        hf.update_gps_position(0.0, 10.0, speed_ms=1.0)  # Beweging noord
        assert hf.heading is not None
        assert abs(hf.heading - math.pi / 2) < 0.3   # ≈ π/2 (noord)

    def test_gyro_integrates_when_heading_known(self):
        hf = HeadingFilter(min_speed_ms=0.1, alpha=1.0)   # Alleen gyro
        hf.update_gps_position(0.0, 0.0, speed_ms=1.0)
        hf.update_gps_position(10.0, 0.0, speed_ms=1.0)  # Koers ≈ 0 (oost)
        initial = hf.heading
        hf.update_gyro(1.0, 0.1)   # 1 rad/s × 0.1 s = 0.1 rad
        assert abs(hf.heading - (initial + 0.1)) < 0.01

    def test_gyro_no_effect_before_gps(self):
        hf = HeadingFilter()
        hf.update_gyro(5.0, 1.0)
        assert hf.heading is None

    def test_too_slow_gps_ignored(self):
        hf = HeadingFilter(min_speed_ms=1.0)
        hf.update_gps_position(0.0, 0.0, speed_ms=0.5)
        hf.update_gps_position(10.0, 0.0, speed_ms=0.5)   # Te langzaam
        assert hf.heading is None

    def test_reset_clears_heading(self):
        hf = HeadingFilter(min_speed_ms=0.1)
        hf.update_gps_position(0.0, 0.0, speed_ms=1.0)
        hf.update_gps_position(10.0, 0.0, speed_ms=1.0)
        hf.reset()
        assert hf.heading is None

    def test_force_heading(self):
        hf = HeadingFilter()
        hf.force_heading(math.pi / 2)
        assert abs(hf.heading - math.pi / 2) < 1e-9


# ── WaypointManager ──────────────────────────────────────────────────────────

class TestWaypointManager:
    def setup_method(self):
        self.wm = WaypointManager()

    def test_initial_state_idle(self):
        assert self.wm.state == NavState.IDLE

    def test_add_waypoint_returns_id(self):
        wp_id = self.wm.add(52.0, 5.0)
        assert wp_id == 1
        assert self.wm.total_waypoints == 1

    def test_start_requires_waypoints(self):
        assert self.wm.start() is False

    def test_start_with_waypoints(self):
        self.wm.add(52.0, 5.0)
        assert self.wm.start() is True
        assert self.wm.state == NavState.NAVIGATING

    def test_current_waypoint_when_navigating(self):
        self.wm.add(52.0, 5.0)
        self.wm.start()
        wp = self.wm.current_waypoint
        assert wp is not None
        assert abs(wp.latitude - 52.0) < 1e-9

    def test_mark_arrived_advances(self):
        self.wm.add(52.0, 5.0)
        self.wm.add(52.1, 5.1)
        self.wm.start()
        has_next = self.wm.mark_arrived()
        assert has_next is True
        assert self.wm.current_index == 1

    def test_mark_arrived_last_sets_complete(self):
        self.wm.add(52.0, 5.0)
        self.wm.start()
        has_next = self.wm.mark_arrived()
        assert has_next is False
        assert self.wm.state == NavState.COMPLETE

    def test_pause_and_resume(self):
        self.wm.add(52.0, 5.0)
        self.wm.start()
        self.wm.pause()
        assert self.wm.state == NavState.PAUSED
        assert not self.wm.is_navigating
        self.wm.resume()
        assert self.wm.state == NavState.NAVIGATING

    def test_clear_resets_to_idle(self):
        self.wm.add(52.0, 5.0)
        self.wm.start()
        self.wm.clear()
        assert self.wm.state == NavState.IDLE
        assert self.wm.total_waypoints == 0

    def test_waypoint_id_increments(self):
        id1 = self.wm.add(52.0, 5.0)
        id2 = self.wm.add(52.1, 5.1)
        assert id2 == id1 + 1

    def test_remaining_waypoints(self):
        self.wm.add(52.0, 5.0)
        self.wm.add(52.1, 5.1)
        self.wm.add(52.2, 5.2)
        self.wm.start()
        assert self.wm.remaining_waypoints == 3
        self.wm.mark_arrived()
        assert self.wm.remaining_waypoints == 2
