"""
coordinate_transform.py
GPS lat/lon ↔ lokaal ENU XY coördinaten.

Gebruikt een flat-earth benadering (nauwkeurig tot <1mm voor afstanden < 10 km):
  X = East  (meters oost van origin)
  Y = North (meters noord van origin)

Geen externe dependencies (geen pyproj) nodig.

Referentie: https://en.wikipedia.org/wiki/Geographic_coordinate_system
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# WGS-84 ellipsoïde constanten
_WGS84_A  = 6_378_137.0          # Semi-major axis (m)
_WGS84_E2 = 0.006694379990141316  # Eccentricity² = 2f - f²

# 1 graad breedtegraad in meters (bijna constant)
_M_PER_DEG_LAT = math.pi * _WGS84_A * (1 - _WGS84_E2) / 180.0  # ≈ 111 320 m


@dataclass
class LocalPoint:
    x: float   # meter oost
    y: float   # meter noord

    def distance_to(self, other: "LocalPoint") -> float:
        return math.hypot(other.x - self.x, other.y - self.y)

    def bearing_to(self, other: "LocalPoint") -> float:
        """Hoek naar ander punt (radialen, ENU-frame: 0=Oost, +π/2=Noord)."""
        return math.atan2(other.y - self.y, other.x - self.x)


class CoordinateTransform:
    """
    Converteert GPS lat/lon naar lokale ENU coördinaten.

    Het nulpunt (origin) wordt ingesteld via `set_origin()`.
    Vóór de eerste fix is de transformatie niet beschikbaar.
    """

    def __init__(self) -> None:
        self._origin_lat: Optional[float] = None
        self._origin_lon: Optional[float] = None
        self._m_per_deg_lon: float = 0.0  # Afhankelijk van breedtegraad

    @property
    def has_origin(self) -> bool:
        return self._origin_lat is not None

    def set_origin(self, lat: float, lon: float) -> None:
        """Stel het nulpunt in (bv. op de eerste GPS-fix of op een vaste locatie)."""
        self._origin_lat = lat
        self._origin_lon = lon
        # Lengtegraden worden korter naarmate je verder van de evenaar bent
        lat_rad = math.radians(lat)
        n = _WGS84_A / math.sqrt(1 - _WGS84_E2 * math.sin(lat_rad) ** 2)
        self._m_per_deg_lon = math.pi * n * math.cos(lat_rad) / 180.0

    def gps_to_local(self, lat: float, lon: float) -> LocalPoint:
        """Converteer GPS coördinaten naar lokaal ENU punt (meters)."""
        if not self.has_origin:
            raise RuntimeError(
                "Origin niet ingesteld. Roep set_origin() eerst aan.")
        x = (lon - self._origin_lon) * self._m_per_deg_lon
        y = (lat - self._origin_lat) * _M_PER_DEG_LAT
        return LocalPoint(x=x, y=y)

    def local_to_gps(self, point: LocalPoint) -> tuple[float, float]:
        """Converteer lokaal ENU punt terug naar GPS (lat, lon)."""
        if not self.has_origin:
            raise RuntimeError("Origin niet ingesteld.")
        lat = self._origin_lat + point.y / _M_PER_DEG_LAT
        lon = self._origin_lon + point.x / self._m_per_deg_lon
        return lat, lon
