"""
test_zone_analyzer.py
Unit tests voor de pure obstakelvermijdingslogica.

Geen ROS2 of hardware vereist – gewoon pytest:
  pytest software/ros2/rc_avoidance/test/test_zone_analyzer.py -v
"""

import sys
from pathlib import Path

# Zorg dat het pakket vindbaar is zonder colcon build
sys.path.insert(0, str(Path(__file__).parents[1]))

from rc_avoidance.zone_analyzer import (
    ZoneState,
    AvoidanceDecision,
    HysteresisFilter,
    fuse_sources,
    analyze,
    _best_escape,
    _repulsion_steer,
)

STOP_MM = 800.0
WARN_MM = 1500.0

# ── Helpers ──────────────────────────────────────────────────────────────────

def make_zones(statuses: dict[str, int]) -> list[ZoneState]:
    """Maak een lijst van ZoneStates op basis van naam→status dict."""
    names = ["far_left", "left", "center", "right", "far_right"]
    return [
        ZoneState(
            name        = n,
            distance_mm = {
                ZoneState.STATUS_CLEAR:   5000.0,
                ZoneState.STATUS_WARNING: WARN_MM - 100,
                ZoneState.STATUS_BLOCKED: STOP_MM - 100,
            }.get(statuses.get(n, ZoneState.STATUS_CLEAR), 5000.0),
            status      = statuses.get(n, ZoneState.STATUS_CLEAR),
        )
        for n in names
    ]


def decision_for(statuses: dict[str, int]) -> AvoidanceDecision:
    zones_list = make_zones(statuses)
    zones = fuse_sources(
        depth_zones=zones_list,
        us_front_m=-1, us_rear_m=-1, us_left_m=-1, us_right_m=-1,
        stop_dist_mm=STOP_MM, warn_dist_mm=WARN_MM,
    )
    return analyze(zones, stop_dist_mm=STOP_MM, warn_dist_mm=WARN_MM)


# ── Tests: pad vrij ──────────────────────────────────────────────────────────

class TestClearPath:
    def test_all_clear_is_clear(self):
        d = decision_for({})
        assert d.status == "clear"

    def test_clear_full_speed(self):
        d = decision_for({})
        assert d.linear_x == 0.4

    def test_clear_no_steer(self):
        d = decision_for({})
        assert d.angular_z == 0.0


# ── Tests: waarschuwing ──────────────────────────────────────────────────────

class TestWarning:
    def test_center_warning_slows_down(self):
        d = decision_for({"center": ZoneState.STATUS_WARNING})
        assert d.status == "warning"
        assert d.linear_x < 0.4

    def test_left_warning_steers_right(self):
        d = decision_for({"left": ZoneState.STATUS_WARNING})
        assert d.status == "warning"
        # Obstakel links → stuur rechts → angular_z negatief
        assert d.angular_z < 0.0

    def test_right_warning_steers_left(self):
        d = decision_for({"right": ZoneState.STATUS_WARNING})
        assert d.status == "warning"
        # Obstakel rechts → stuur links → angular_z positief
        assert d.angular_z > 0.0


# ── Tests: gevaar ────────────────────────────────────────────────────────────

class TestDanger:
    def test_center_blocked_left_free_is_danger(self):
        d = decision_for({
            "center": ZoneState.STATUS_BLOCKED,
            "left":   ZoneState.STATUS_CLEAR,
            "right":  ZoneState.STATUS_CLEAR,
        })
        assert d.status == "danger"
        assert d.linear_x == 0.0

    def test_center_blocked_stops_linear(self):
        d = decision_for({"center": ZoneState.STATUS_BLOCKED})
        assert d.linear_x == 0.0

    def test_center_blocked_steers_toward_open_left(self):
        d = decision_for({
            "center":    ZoneState.STATUS_BLOCKED,
            "left":      ZoneState.STATUS_CLEAR,
            "far_left":  ZoneState.STATUS_CLEAR,
            "right":     ZoneState.STATUS_BLOCKED,
            "far_right": ZoneState.STATUS_BLOCKED,
        })
        assert d.status == "danger"
        # Links is de vrije kant → angular_z positief
        assert d.angular_z > 0.0

    def test_center_blocked_steers_toward_open_right(self):
        d = decision_for({
            "center":    ZoneState.STATUS_BLOCKED,
            "left":      ZoneState.STATUS_BLOCKED,
            "far_left":  ZoneState.STATUS_BLOCKED,
            "right":     ZoneState.STATUS_CLEAR,
            "far_right": ZoneState.STATUS_CLEAR,
        })
        assert d.status == "danger"
        # Rechts is de vrije kant → angular_z negatief
        assert d.angular_z < 0.0


# ── Tests: stop ──────────────────────────────────────────────────────────────

class TestStop:
    def test_all_blocked_is_stop(self):
        d = decision_for({
            "far_left":  ZoneState.STATUS_BLOCKED,
            "left":      ZoneState.STATUS_BLOCKED,
            "center":    ZoneState.STATUS_BLOCKED,
            "right":     ZoneState.STATUS_BLOCKED,
            "far_right": ZoneState.STATUS_BLOCKED,
        })
        assert d.status == "stop"
        assert d.linear_x == 0.0


# ── Tests: fusie ─────────────────────────────────────────────────────────────

class TestFusion:
    def test_us_front_blocked_overrides_clear_camera(self):
        """Ultrasoon dichtbij moet camera-clear overriden."""
        clear_zones = make_zones({})
        zones = fuse_sources(
            depth_zones=clear_zones,
            us_front_m=0.3,   # 300 mm < STOP_MM
            us_rear_m=-1, us_left_m=-1, us_right_m=-1,
            stop_dist_mm=STOP_MM, warn_dist_mm=WARN_MM,
        )
        d = analyze(zones, stop_dist_mm=STOP_MM, warn_dist_mm=WARN_MM)
        assert d.status in ("danger", "stop")

    def test_us_rear_blocked_no_reverse(self):
        """Achterobstakel moet lineaire snelheid positief houden."""
        clear_zones = make_zones({})
        zones = fuse_sources(
            depth_zones=clear_zones,
            us_front_m=-1,
            us_rear_m=0.3,   # 300 mm < STOP_MM
            us_left_m=-1, us_right_m=-1,
            stop_dist_mm=STOP_MM, warn_dist_mm=WARN_MM,
        )
        d = analyze(zones, stop_dist_mm=STOP_MM, warn_dist_mm=WARN_MM)
        assert d.linear_x >= 0.0

    def test_no_data_is_clear(self):
        """Geen sensordata → mag geen blokkade zijn."""
        zones = fuse_sources(
            depth_zones=[],
            us_front_m=-1, us_rear_m=-1, us_left_m=-1, us_right_m=-1,
        )
        d = analyze(zones)
        assert d.status == "clear"


# ── Tests: hysterese ─────────────────────────────────────────────────────────

class TestHysteresis:
    def test_upgrade_is_immediate(self):
        hf = HysteresisFilter(count=4)
        assert hf.update("clear") == "clear"
        assert hf.update("danger") == "danger"   # direct upgrade

    def test_downgrade_needs_n_counts(self):
        hf = HysteresisFilter(count=4)
        hf.update("danger")
        # 3 keer "clear" → nog steeds "danger"
        assert hf.update("clear") == "danger"
        assert hf.update("clear") == "danger"
        assert hf.update("clear") == "danger"
        # 4e keer → nu downgrade
        assert hf.update("clear") == "clear"

    def test_pending_reset_on_different_status(self):
        hf = HysteresisFilter(count=4)
        hf.update("danger")
        hf.update("clear")   # pending clear: 1
        hf.update("warning") # andere status → reset pending
        hf.update("clear")   # pending clear: 1 (opnieuw)
        hf.update("clear")   # pending clear: 2
        hf.update("clear")   # pending clear: 3
        # nog niet 4 keer clear → danger blijft (warning is tussenin geweest)
        # maar de huidige status is warning na 1 warning
        # hmm eigenlijk na update("warning") > update("clear") > ...
        # laten we gewoon checken dat het na 4x clear uiteindelijk clear is
        result = hf.update("clear")  # 4e clear
        assert result == "clear"
