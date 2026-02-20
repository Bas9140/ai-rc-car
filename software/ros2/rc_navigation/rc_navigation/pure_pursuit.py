"""
pure_pursuit.py
Pure pursuit sturing voor GPS waypoint navigatie.

Pure pursuit is een klassiek padvolg-algoritme dat een "blik-vooruit punt"
(lookahead point) op het pad projecteert en een cirkelboog berekent om
daar te komen.

Formule:
  κ = 2 * L_y / L²

  Waarbij:
    L   = lookahead afstand (m)
    L_y = laterale offset van lookahead punt in robot-frame (+ = links)
    κ   = rijkromming (1/m) → angular_z = v * κ

Coördinatenconventies:
  - Wereld: ENU-frame (X=Oost, Y=Noord)
  - Robot:  X=Vooruit, Y=Links
  - Koers:  θ in ENU-frame (0=Oost, π/2=Noord, positief=CCW)

De angular_z die we teruggeven volgt ROS2-conventie:
  angular_z > 0 = linksom draaien
  angular_z < 0 = rechtsom draaien

Referentie: Coulter (1992) "Implementation of the Pure Pursuit Path Tracking Algorithm"
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class PursuitResult:
    linear_x:     float     # Aanbevolen rijsnelheid (m/s)
    angular_z:    float     # Aanbevolen draaisnelheid (rad/s)
    cross_track_error: float # Laterale fout (m, + = doel links)
    heading_error: float     # Koersfout (rad, + = draai links)
    distance:      float     # Afstand tot doel (m)
    arrived:       bool      # Binnen target_radius


class PurePursuit:
    """
    Pure pursuit controller voor één doelpunt.

    Parameters
    ----------
    lookahead_m   : float   Blik-vooruit afstand (m). Groter = vloeiender maar trager.
    max_linear    : float   Maximale rijsnelheid (m/s).
    min_linear    : float   Minimale rijsnelheid als motor-dood-zone overschreden (m/s).
    max_angular   : float   Maximale draaisnelheid (rad/s).
    slow_radius_m : float   Binnen deze afstand: snelheid lineair reduceren.
    target_radius : float   Binnen deze afstand: 'arrived'.
    """

    def __init__(
        self,
        lookahead_m:   float = 2.5,
        max_linear:    float = 0.5,
        min_linear:    float = 0.1,
        max_angular:   float = 1.2,
        slow_radius_m: float = 3.0,
        target_radius: float = 1.5,
    ) -> None:
        self.lookahead_m   = lookahead_m
        self.max_linear    = max_linear
        self.min_linear    = min_linear
        self.max_angular   = max_angular
        self.slow_radius_m = slow_radius_m
        self.target_radius = target_radius

    def compute(
        self,
        robot_x:    float,
        robot_y:    float,
        robot_heading: float,      # ENU radialen
        target_x:   float,
        target_y:   float,
    ) -> PursuitResult:
        """
        Bereken de gewenste cmd_vel om het doelpunt te bereiken.

        Parameters
        ----------
        robot_x, robot_y   : float   Huidige positie (lokale ENU, m)
        robot_heading      : float   Huidige koers (ENU radialen)
        target_x, target_y : float   Doelpositie (lokale ENU, m)

        Returns
        -------
        PursuitResult
        """
        # ── Afstand en koers naar doel ──────────────────────────────────
        dx_world = target_x - robot_x
        dy_world = target_y - robot_y
        distance = math.hypot(dx_world, dy_world)

        if distance < self.target_radius:
            return PursuitResult(
                linear_x=0.0, angular_z=0.0,
                cross_track_error=0.0, heading_error=0.0,
                distance=distance, arrived=True,
            )

        # ── Transformeer naar robot-frame ───────────────────────────────
        cos_h = math.cos(robot_heading)
        sin_h = math.sin(robot_heading)

        # Robot-frame: X=Vooruit, Y=Links
        x_robot =  cos_h * dx_world + sin_h * dy_world
        y_robot = -sin_h * dx_world + cos_h * dy_world

        # ── Heading fout ────────────────────────────────────────────────
        heading_to_target = math.atan2(dy_world, dx_world)
        heading_error = _wrap(heading_to_target - robot_heading)

        # ── Edge case: doel grotendeels achter de robot (|heading_err| > 120°) ─
        # Pure pursuit werkt niet als y_robot ≈ 0 en x_robot < 0 (doel achter).
        # Schakel over naar proportionele heading controller om de robot om te draaien.
        if abs(heading_error) > math.radians(120):
            angular_z = float(
                max(-self.max_angular,
                    min(self.max_angular, 1.5 * heading_error)))
            # Niet vooruit rijden terwijl we draaien
            return PursuitResult(
                linear_x          = 0.0,
                angular_z          = angular_z,
                cross_track_error  = float(y_robot),
                heading_error      = float(heading_error),
                distance           = float(distance),
                arrived            = False,
            )

        # ── Lookahead punt ──────────────────────────────────────────────
        # Als doel dichterbij is dan lookahead: gebruik doel direct
        L = min(self.lookahead_m, distance)

        # Projecteer lookahead punt op de lijn robot → doel
        if distance > 1e-6:
            lx = x_robot * L / distance
            ly = y_robot * L / distance
        else:
            lx, ly = 0.0, 0.0

        # ── Pure pursuit kromming ───────────────────────────────────────
        L_sq = lx ** 2 + ly ** 2
        if L_sq < 1e-6:
            curvature = 0.0
        else:
            curvature = 2.0 * ly / L_sq

        # ── Snelheid: lineair reduceren bij nadering ────────────────────
        if distance <= self.slow_radius_m:
            t = distance / self.slow_radius_m         # 0 (doel) .. 1 (ver)
            linear_x = self.min_linear + t * (self.max_linear - self.min_linear)
        else:
            linear_x = self.max_linear

        # ── Angular: kromming × snelheid, geclampd ─────────────────────
        angular_z = float(
            max(-self.max_angular,
                min(self.max_angular, linear_x * curvature)))

        return PursuitResult(
            linear_x          = float(linear_x),
            angular_z          = angular_z,
            cross_track_error  = float(y_robot),
            heading_error      = float(heading_error),
            distance           = float(distance),
            arrived            = False,
        )


def _wrap(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))
