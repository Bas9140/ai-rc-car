"""
schemas.py
Pydantic datamodellen voor REST API request/response bodies.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


class WaypointCreate(BaseModel):
    latitude:   float = Field(..., ge=-90,  le=90)
    longitude:  float = Field(..., ge=-180, le=180)
    radius_m:   float = Field(1.5, ge=0.5, le=50.0)
    label:      str   = ""


class WaypointResponse(BaseModel):
    wp_id:     int
    latitude:  float
    longitude: float
    radius_m:  float
    label:     str
    status:    str    # "pending" | "active" | "done"


class ModeRequest(BaseModel):
    mode: str   # "idle" | "manual" | "autonomous" | "follow_me"


class ManualCmd(BaseModel):
    linear_x:  float = Field(0.0, ge=-1.0, le=1.0)
    angular_z: float = Field(0.0, ge=-1.0, le=1.0)


class ConfigUpdate(BaseModel):
    max_linear_speed:  Optional[float] = None
    max_angular_speed: Optional[float] = None
    servo_trim_us:     Optional[int]   = None
    lookahead_m:       Optional[float] = None
    target_radius_m:   Optional[float] = None
