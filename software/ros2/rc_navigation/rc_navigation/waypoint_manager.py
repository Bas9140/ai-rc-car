"""
waypoint_manager.py
Waypoint wachtrij en statusmachine voor GPS-routenavigatie.

Statusmachine:
  IDLE ──start()──► NAVIGATING ──arrived──► NAVIGATING (next wp)
                                         └─ COMPLETE   (alle bereikt)
       ◄─clear()───────────────────────────────────────────────────
                   ──pause()──► PAUSED ──resume()──► NAVIGATING
                   ──clear()──► IDLE

Waypoints worden toegevoegd via add(), één voor één of als batch.
Waypoints worden verwijderd nadat ze bereikt zijn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class NavState(Enum):
    IDLE       = auto()
    NAVIGATING = auto()
    PAUSED     = auto()
    COMPLETE   = auto()
    ERROR      = auto()

    def __str__(self) -> str:
        return self.name.lower()


@dataclass
class Waypoint:
    latitude:   float
    longitude:  float
    radius_m:   float = 1.5     # Aankomstradius (meter)
    wp_id:      int   = 0
    label:      str   = ""      # Optionele naam (dashboard gebruik)


class WaypointManager:
    """
    Beheert de waypoint-wachtrij en de navigatiestatus.

    Thread-safe vanwege GIL (Python), maar niet expliciet gesynchroniseerd.
    Roep alleen aan vanuit één ROS2 executor-thread.
    """

    def __init__(self) -> None:
        self._queue:    list[Waypoint] = []
        self._current:  int = 0
        self._state:    NavState = NavState.IDLE
        self._wp_counter: int = 0

    # ── Eigenschappen ──────────────────────────────────────────────────────

    @property
    def state(self) -> NavState:
        return self._state

    @property
    def state_str(self) -> str:
        return str(self._state)

    @property
    def total_waypoints(self) -> int:
        return len(self._queue)

    @property
    def current_index(self) -> int:
        return self._current

    @property
    def remaining_waypoints(self) -> int:
        return max(0, len(self._queue) - self._current)

    @property
    def current_waypoint(self) -> Optional[Waypoint]:
        """Geeft het actieve waypoint terug, of None als er geen is."""
        if self._state in (NavState.NAVIGATING, NavState.PAUSED):
            if 0 <= self._current < len(self._queue):
                return self._queue[self._current]
        return None

    @property
    def is_navigating(self) -> bool:
        return self._state == NavState.NAVIGATING

    # ── Beheer ────────────────────────────────────────────────────────────

    def add(
        self,
        latitude:  float,
        longitude: float,
        radius_m:  float = 1.5,
        label:     str   = "",
    ) -> int:
        """
        Voeg een waypoint toe aan het einde van de wachtrij.

        Returns
        -------
        int  Waypoint-ID (uniek, oplopend)
        """
        self._wp_counter += 1
        wp = Waypoint(
            latitude  = latitude,
            longitude = longitude,
            radius_m  = radius_m,
            wp_id     = self._wp_counter,
            label     = label or f"WP{self._wp_counter}",
        )
        self._queue.append(wp)
        return self._wp_counter

    def clear(self) -> None:
        """Verwijder alle waypoints en reset naar IDLE."""
        self._queue   = []
        self._current = 0
        self._state   = NavState.IDLE

    def start(self) -> bool:
        """
        Start navigatie. Alleen mogelijk vanuit IDLE of COMPLETE.

        Returns
        -------
        bool  True als gestart, False als er geen waypoints zijn.
        """
        if not self._queue:
            return False
        if self._state in (NavState.IDLE, NavState.COMPLETE):
            self._current = 0
            self._state   = NavState.NAVIGATING
            return True
        return False

    def pause(self) -> None:
        """Pauzeer navigatie (huidige positie vasthouden)."""
        if self._state == NavState.NAVIGATING:
            self._state = NavState.PAUSED

    def resume(self) -> bool:
        """Hervat navigatie na pauze."""
        if self._state == NavState.PAUSED:
            self._state = NavState.NAVIGATING
            return True
        return False

    # ── Voortgang ──────────────────────────────────────────────────────────

    def mark_arrived(self) -> bool:
        """
        Markeer het huidige waypoint als bereikt en ga naar het volgende.

        Returns
        -------
        bool  True als er een volgend waypoint is, False als de route klaar is.
        """
        if self._state != NavState.NAVIGATING:
            return False

        self._current += 1

        if self._current >= len(self._queue):
            self._state = NavState.COMPLETE
            return False

        return True   # Volgend waypoint beschikbaar

    def set_error(self, reason: str = "") -> None:
        """Zet status op ERROR (bv. bij GPS-verlies)."""
        self._state = NavState.ERROR
