"""
zone_analyzer.py
Pure-Python obstakelvermijdingslogica – geen ROS afhankelijkheden.

Verwerkt twee informatiebronnen:
  1. Camera diepte-zones (5 zones, OAK-D Lite, front-facing)
  2. Ultrasoon (4 richtingen: front/rear/left/right, HC-SR04)

Geeft een AvoidanceDecision terug met:
  - status:    'clear' | 'warning' | 'danger' | 'stop'
  - linear_x:  aanbevolen rijsnelheid (positief = vooruit, 0 = stop)
  - angular_z: aanbevolen draairichting (+ = links, – = rechts, ROS2 conv.)
  - reason:    leesbare uitleg

=== Zonelayout (camera, front-facing) ===

  far_left | left | center | right | far_right
  ─────────────────────────────────────────────
                     AUTO

  Obstakel LINKS  → stuur RECHTS → angular_z negatief
  Obstakel RECHTS → stuur LINKS  → angular_z positief

=== Statusmachine ===

  clear    – geen obstakels, geen override
  warning  – obstakel nadering, snelheid verlaagd, lichte correctie
  danger   – obstakel dichtbij, hard sturen, sterk geremd
  stop     – centrum geblokkeerd én geen uitwijkrichting beschikbaar

=== Hysterese ===

  Statuswijzigingen naar 'erger' zijn direct.
  Statuswijzigingen naar 'beter' vereisen N opeenvolgende betere metingen
  (HYSTERESIS_COUNT), zodat de auto niet heen-en-weer schakelt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Zone layout en gewichten ────────────────────────────────────────────────

# Kameraoenen in volgorde (index → naam)
ZONE_NAMES = ["far_left", "left", "center", "right", "far_right"]

# Lateraal stuurgewicht per zone:
#   negatief = obstakel duwt naar rechts (angular_z negatief = draaien naar rechts)
#   positief = obstakel duwt naar links
ZONE_PUSH_WEIGHT = {
    "far_left":  -1.5,
    "left":      -1.0,
    "center":     0.0,   # center heeft geen laterale voorkeur
    "right":     +1.0,
    "far_right": +1.5,
}

# Statuscode volgorde (voor vergelijking)
STATUS_RANK = {"clear": 0, "warning": 1, "danger": 2, "stop": 3}

# Afstandsdrempels voor ultrasoon (m)
US_STOP_M    = 0.40   # < 40 cm → gevaar
US_WARN_M    = 0.80   # < 80 cm → waarschuwing

# Hysterese: N opeenvolgende betere metingen vóór downgrade
HYSTERESIS_COUNT = 4


# ── Datastructuren ──────────────────────────────────────────────────────────

@dataclass
class ZoneState:
    """Gecombineerde zone-informatie na fusie van camera + ultrasoon."""
    name: str
    distance_mm: float       # -1 = geen meting
    status: int              # 0=CLEAR, 1=WARNING, 2=BLOCKED

    STATUS_CLEAR   = 0
    STATUS_WARNING = 1
    STATUS_BLOCKED = 2


@dataclass
class AvoidanceDecision:
    """Resultaat van de obstakelvermijdingsanalyse."""
    status: str              # 'clear' | 'warning' | 'danger' | 'stop'
    linear_x: float          # aanbevolen rijsnelheid (m/s); 0 = stop
    angular_z: float         # aanbevolen draairichting (rad/s)
    reason: str              # leesbare uitleg


# ── Fusie ───────────────────────────────────────────────────────────────────

def fuse_sources(
    depth_zones:      list[ZoneState],
    us_front_m:       float,
    us_rear_m:        float,
    us_left_m:        float,
    us_right_m:       float,
    stop_dist_mm:     float = 800.0,
    warn_dist_mm:     float = 1500.0,
) -> dict[str, ZoneState]:
    """
    Combineer camera-zones en ultrasoon tot één gecombineerde zonekaart.

    Camera (5 zones, voor) en ultrasoon (4 richtingen, rondom) vullen
    elkaar aan. Per zone: neem de meest conservatieve status.

    Returns
    -------
    dict[str, ZoneState]  –  "far_left", "left", "center", "right",
                              "far_right", "rear", "us_left", "us_right"
    """
    zones: dict[str, ZoneState] = {}

    # ── Camera-zones (front) ──────────────────────────────────────────
    for z in depth_zones:
        zones[z.name] = z

    # ── Ultrasoon voor: verfijnt camera center/left/right ────────────
    if us_front_m >= 0:
        us_front_mm = us_front_m * 1000.0
        us_status = (
            ZoneState.STATUS_BLOCKED if us_front_mm < stop_dist_mm else
            ZoneState.STATUS_WARNING if us_front_mm < warn_dist_mm else
            ZoneState.STATUS_CLEAR
        )
        # Combineer met camera-center: neem ergste status
        cam_center = zones.get("center")
        if cam_center is None:
            zones["center"] = ZoneState("center", us_front_mm, us_status)
        else:
            if us_status > cam_center.status:
                zones["center"] = ZoneState(
                    "center",
                    min(cam_center.distance_mm, us_front_mm)
                    if cam_center.distance_mm > 0 else us_front_mm,
                    us_status,
                )

    # ── Ultrasoon achter ─────────────────────────────────────────────
    if us_rear_m >= 0:
        us_rear_mm = us_rear_m * 1000.0
        us_status = (
            ZoneState.STATUS_BLOCKED if us_rear_mm < stop_dist_mm else
            ZoneState.STATUS_WARNING if us_rear_mm < warn_dist_mm else
            ZoneState.STATUS_CLEAR
        )
        zones["rear"] = ZoneState("rear", us_rear_mm, us_status)

    # ── Ultrasoon flank (left/right) ──────────────────────────────────
    for side, dist_m, cam_zone in [
        ("us_left",  us_left_m,  "left"),
        ("us_right", us_right_m, "right"),
    ]:
        if dist_m < 0:
            continue
        dist_mm = dist_m * 1000.0
        status = (
            ZoneState.STATUS_BLOCKED if dist_mm < stop_dist_mm * 0.6 else
            ZoneState.STATUS_WARNING if dist_mm < warn_dist_mm * 0.6 else
            ZoneState.STATUS_CLEAR
        )
        zones[side] = ZoneState(side, dist_mm, status)

        # Combineer met camera-flank
        cam = zones.get(cam_zone)
        if cam is not None and status > cam.status:
            zones[cam_zone] = ZoneState(
                cam_zone,
                min(cam.distance_mm, dist_mm) if cam.distance_mm > 0 else dist_mm,
                status,
            )

    return zones


# ── Beslissing ───────────────────────────────────────────────────────────────

def analyze(
    zones:         dict[str, ZoneState],
    max_linear:    float = 0.4,
    max_angular:   float = 1.2,
    stop_dist_mm:  float = 800.0,
    warn_dist_mm:  float = 1500.0,
) -> AvoidanceDecision:
    """
    Bereken de optimale uitwijkmanoeuvre op basis van de zonekaart.

    Algoritme:
    1. Camera center BLOCKED + geen uitwijkruimte → STOP
    2. Camera center BLOCKED + uitwijkruimte → DANGER: hard sturen
    3. Camera center WARNING → WARNING: geleidelijk remmen + sturen
    4. Alleen zijzones WARNING/BLOCKED → lichte correctie
    5. Achter BLOCKED → voorkom achteruit rijden
    6. Anders → CLEAR
    """
    front_zones = [zones.get(n) for n in ZONE_NAMES]
    center  = zones.get("center")
    rear    = zones.get("rear")

    # ── Stap 1-2: Centrum geblokkeerd ────────────────────────────────
    if center is not None and center.status == ZoneState.STATUS_BLOCKED:
        steer, escape_dir = _best_escape(zones)

        if escape_dir is None:
            return AvoidanceDecision(
                status    = "stop",
                linear_x  = 0.0,
                angular_z = steer,
                reason    = f"Centrum geblokkeerd ({center.distance_mm:.0f}mm), geen uitwijkroute",
            )

        ang = float(min(max_angular, abs(steer))) * (1 if steer > 0 else -1)
        return AvoidanceDecision(
            status    = "danger",
            linear_x  = 0.0,
            angular_z = ang,
            reason    = f"Centrum geblokkeerd ({center.distance_mm:.0f}mm) → uitwijken {escape_dir}",
        )

    # ── Stap 3: Centrum in waarschuwing ──────────────────────────────
    if center is not None and center.status == ZoneState.STATUS_WARNING:
        steer, _ = _repulsion_steer(zones, max_angular)
        # Snelheid schalen op basis van afstand tot drempel
        dist     = max(center.distance_mm, 1.0)
        speed_f  = _scale(dist, stop_dist_mm, warn_dist_mm, 0.0, 0.4)
        return AvoidanceDecision(
            status    = "warning",
            linear_x  = speed_f * max_linear,
            angular_z = steer * 0.6,
            reason    = f"Centrum nadering ({center.distance_mm:.0f}mm)",
        )

    # ── Stap 4: Alleen zijzones (camera + ultrasoon flank) ───────────
    steer, _ = _repulsion_steer(zones, max_angular)
    has_side_warning = any(
        z is not None and z.status >= ZoneState.STATUS_WARNING
        for n, z in zones.items()
        if n != "center" and n != "rear"
    )

    if has_side_warning:
        return AvoidanceDecision(
            status    = "warning",
            linear_x  = max_linear,         # snelheid niet verminderen voor zijdelingse dreiging
            angular_z = steer * 0.4,
            reason    = "Zijobstakel gedetecteerd, koerscorrectie",
        )

    # ── Stap 5: Achter geblokkeerd → blokeer achteruit ───────────────
    if rear is not None and rear.status == ZoneState.STATUS_BLOCKED:
        return AvoidanceDecision(
            status    = "warning",
            linear_x  = max(0.0, max_linear * 0.3),   # geen achteruit
            angular_z = 0.0,
            reason    = f"Achter geblokkeerd ({rear.distance_mm:.0f}mm), achteruit geblokkeerd",
        )

    # ── Vrij ─────────────────────────────────────────────────────────
    return AvoidanceDecision(
        status    = "clear",
        linear_x  = max_linear,
        angular_z = 0.0,
        reason    = "Pad vrij",
    )


# ── Hulpfuncties ─────────────────────────────────────────────────────────────

def _best_escape(zones: dict[str, ZoneState]) -> tuple[float, Optional[str]]:
    """
    Geeft de beste uitwijkrichting terug als (angular_z, richting_naam).
    Geeft (0.0, None) als er geen vrije richting is.

    Strategie: kies de zijde met de grootste vrije afstand.
    Links vrij → angular_z positief (draai links)
    Rechts vrij → angular_z negatief (draai rechts)
    """
    left_zones  = ["left",  "far_left",  "us_left"]
    right_zones = ["right", "far_right", "us_right"]

    left_clear  = all(
        zones.get(n) is None or zones[n].status < ZoneState.STATUS_BLOCKED
        for n in left_zones
    )
    right_clear = all(
        zones.get(n) is None or zones[n].status < ZoneState.STATUS_BLOCKED
        for n in right_zones
    )

    # Bepaal openste kant op basis van mediaan afstand
    left_dist  = _median_dist(zones, left_zones)
    right_dist = _median_dist(zones, right_zones)

    if left_clear and (not right_clear or left_dist >= right_dist):
        return +1.2, "links"
    if right_clear:
        return -1.2, "rechts"

    # Beide zijden geblokkeerd; geef toch de minder slechte kant
    if left_dist > right_dist:
        return +1.2, None
    return -1.2, None


def _repulsion_steer(
    zones: dict[str, ZoneState],
    max_angular: float,
) -> tuple[float, str]:
    """
    Bereken een gecombineerde stuurcorrectie via een repulsieveld.

    Elk obstakel "duwt" de auto weg met een kracht evenredig aan de urgentie.
    Urgentie: BLOCKED=1.0, WARNING=0.5, CLEAR=0.0
    Gewicht per zone: zie ZONE_PUSH_WEIGHT.
    """
    total = 0.0
    for name, weight in ZONE_PUSH_WEIGHT.items():
        z = zones.get(name)
        if z is None:
            continue
        urgency = {
            ZoneState.STATUS_CLEAR:   0.0,
            ZoneState.STATUS_WARNING: 0.5,
            ZoneState.STATUS_BLOCKED: 1.0,
        }.get(z.status, 0.0)
        total += weight * urgency

    clamped = float(max(-max_angular, min(max_angular, total)))
    direction = "links" if clamped > 0 else "rechts" if clamped < 0 else "recht"
    return clamped, direction


def _median_dist(zones: dict[str, ZoneState], names: list[str]) -> float:
    dists = [zones[n].distance_mm for n in names
             if n in zones and zones[n].distance_mm > 0]
    if not dists:
        return 9999.0
    dists.sort()
    return dists[len(dists) // 2]


def _scale(val: float, lo: float, hi: float, out_lo: float, out_hi: float) -> float:
    """Lineaire interpolatie: val in [lo, hi] → output in [out_lo, out_hi]."""
    if hi <= lo:
        return out_lo
    t = max(0.0, min(1.0, (val - lo) / (hi - lo)))
    return out_lo + t * (out_hi - out_lo)


# ── Hysterese ────────────────────────────────────────────────────────────────

class HysteresisFilter:
    """
    Vertraagt downgrade van status zodat korte valse positieven genegeerd worden.

    Upgrade (worse) → direct
    Downgrade (better) → pas na HYSTERESIS_COUNT opeenvolgende betere metingen
    """

    def __init__(self, count: int = HYSTERESIS_COUNT) -> None:
        self._count   = count
        self._current = "clear"
        self._pending: Optional[str] = None
        self._pending_n = 0

    def update(self, new_status: str) -> str:
        if STATUS_RANK[new_status] >= STATUS_RANK[self._current]:
            # Upgrade of gelijk: direct overnemen
            self._current = new_status
            self._pending = None
            self._pending_n = 0
        else:
            # Downgrade: wacht op N opeenvolgende betere metingen
            if self._pending == new_status:
                self._pending_n += 1
            else:
                self._pending   = new_status
                self._pending_n = 1

            if self._pending_n >= self._count:
                self._current   = new_status
                self._pending   = None
                self._pending_n = 0

        return self._current
