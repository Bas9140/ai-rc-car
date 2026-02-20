"""
heading_filter.py
Complementaire filter voor koersschatting (GPS + IMU gyro).

Probleem:
  - GPS geeft positie, geen directe koers → afgeleid uit opeenvolgende posities
    (alleen betrouwbaar als snelheid > 0.5 m/s)
  - IMU gyro integreert yaw-rate → geen drift-correctie over lange tijd
  - Combinatie: gyro geeft snelle response, GPS corrigeert drift

Algoritme (complementaire filter):
  heading_new = α * (heading_old + gyro_z * dt)   ← IMU integratie
              + (1-α) * gps_heading               ← GPS correctie

  α = 0.95 → 95% IMU, 5% GPS per cyclus @ 30 Hz
      na 1 s: GPS draagt ~(1 - 0.95^30) ≈ 78% bij

Koersconventie (ENU-frame, standaard ROS2/wiskunde):
  0     rad → oost  (+X)
  π/2   rad → noord (+Y)
  π     rad → west  (-X)
  -π/2  rad → zuid  (-Y)
  Positief = linksom (CCW van boven)

GPS-koers wordt bepaald op basis van positionele delta's.
"""

from __future__ import annotations

import math
from typing import Optional


def _wrap(angle: float) -> float:
    """Wikkel hoek naar [-π, π]."""
    return math.atan2(math.sin(angle), math.cos(angle))


class HeadingFilter:
    """
    Complementaire filter: GPS-positiedelta + IMU gyro → koers.

    Parameters
    ----------
    alpha : float
        IMU gewicht per update (0 = alleen GPS, 1 = alleen gyro).
        Standaard 0.95 (bij 30 Hz komt ~5% GPS gewicht per cyclus).
    min_speed_ms : float
        Minimale GPS-snelheid (m/s) voor een betrouwbare GPS-koers.
    """

    def __init__(self, alpha: float = 0.95, min_speed_ms: float = 0.4) -> None:
        self._alpha      = alpha
        self._min_speed  = min_speed_ms
        self._heading:   Optional[float] = None   # radialen, ENU
        self._prev_x:    Optional[float] = None
        self._prev_y:    Optional[float] = None

    @property
    def heading(self) -> Optional[float]:
        """Huidige koers in radialen (ENU-frame). None als nog niet geïnitialiseerd."""
        return self._heading

    @property
    def heading_deg(self) -> Optional[float]:
        """Koers in graden."""
        return math.degrees(self._heading) if self._heading is not None else None

    def update_gyro(self, gyro_z: float, dt: float) -> None:
        """
        Verwerk IMU gyro-meting (hoeksnelheid Z in rad/s).

        Mag elk IMU-sample aangeroepen worden (100 Hz).
        Heeft geen effect als nog geen GPS-koers beschikbaar is.
        """
        if self._heading is None:
            return
        self._heading = _wrap(self._heading + gyro_z * dt)

    def update_gps_position(
        self,
        x: float,
        y: float,
        speed_ms: Optional[float] = None,
    ) -> None:
        """
        Verwerk nieuwe GPS-positie (lokaal ENU, meters).

        Berekent koers uit positionele delta als snelheid > min_speed.
        Bij de eerste positie: sla op als referentie.

        Parameters
        ----------
        x, y : float   Lokale ENU positie (meter)
        speed_ms : float | None   GPS-snelheid (m/s). Als None: geschat uit delta.
        """
        if self._prev_x is None:
            self._prev_x = x
            self._prev_y = y
            return

        dx = x - self._prev_x
        dy = y - self._prev_y
        self._prev_x = x
        self._prev_y = y

        delta_dist = math.hypot(dx, dy)
        gps_speed  = speed_ms if speed_ms is not None else delta_dist / 0.1

        if gps_speed < self._min_speed or delta_dist < 0.05:
            # Te langzaam → GPS-koers onbetrouwbaar, alleen gyro gebruiken
            return

        gps_heading = math.atan2(dy, dx)   # ENU: 0=Oost, π/2=Noord

        if self._heading is None:
            self._heading = gps_heading
        else:
            # Complementaire correctie: wikkel verschil voor juiste richting
            err = _wrap(gps_heading - self._heading)
            self._heading = _wrap(self._heading + (1.0 - self._alpha) * err)

    def reset(self) -> None:
        """Reset naar ongekende koers (bv. na lang stilstaan)."""
        self._heading = None
        self._prev_x  = None
        self._prev_y  = None

    def force_heading(self, heading_rad: float) -> None:
        """Stel koers direct in (bv. bij start vanuit bekende richting)."""
        self._heading = _wrap(heading_rad)
