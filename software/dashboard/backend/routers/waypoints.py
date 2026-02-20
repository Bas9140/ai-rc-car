"""
routers/waypoints.py
REST endpoints voor waypoint beheer.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Request
from ..models.schemas import WaypointCreate, WaypointResponse

router = APIRouter(prefix="/api/waypoints", tags=["waypoints"])


def _bridge(request: Request):
    return request.app.state.bridge


@router.get("", response_model=list[WaypointResponse])
async def get_waypoints(request: Request):
    return _bridge(request).get_waypoints()


@router.post("", response_model=WaypointResponse)
async def add_waypoint(body: WaypointCreate, request: Request):
    loop = asyncio.get_event_loop()
    wp = await loop.run_in_executor(
        None,
        _bridge(request).add_waypoint,
        body.latitude, body.longitude,
        body.radius_m, body.label,
    )
    return wp


@router.delete("")
async def clear_waypoints(request: Request):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _bridge(request).clear_waypoints)
    return {"success": True, "cleared": True}
