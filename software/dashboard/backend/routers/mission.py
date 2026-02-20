"""
routers/mission.py
REST endpoints voor modus-wisseling, noodstop en navigatiebeheer.
"""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, HTTPException, Request
from ..models.schemas import ModeRequest, ManualCmd

router = APIRouter(prefix="/api/mission", tags=["mission"])

VALID_MODES = {"idle", "manual", "autonomous", "follow_me"}


def _bridge(request: Request):
    return request.app.state.bridge


@router.post("/mode")
async def set_mode(body: ModeRequest, request: Request):
    if body.mode not in VALID_MODES:
        raise HTTPException(400, f"Ongeldig modus '{body.mode}'. Kies uit: {sorted(VALID_MODES)}")
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(
        None, _bridge(request).call_set_mode, body.mode)
    if not ok:
        raise HTTPException(503, "ROS2 service niet beschikbaar")
    return {"success": True, "mode": body.mode}


@router.post("/stop")
async def emergency_stop(request: Request):
    _bridge(request).call_emergency_stop(True)
    return {"success": True, "emergency_stop": True}


@router.post("/resume")
async def resume_from_stop(request: Request):
    _bridge(request).call_emergency_stop(False)
    return {"success": True, "emergency_stop": False}


@router.post("/manual_cmd")
async def manual_cmd(body: ManualCmd, request: Request):
    _bridge(request).publish_manual_cmd(body.linear_x, body.angular_z)
    return {"success": True}


navigation_router = APIRouter(prefix="/api/navigation", tags=["navigation"])


@navigation_router.post("/start")
async def nav_start(request: Request):
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, _bridge(request).call_nav_start)
    return {"success": ok}


@navigation_router.post("/pause")
async def nav_pause(request: Request):
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, _bridge(request).call_nav_pause)
    return {"success": ok}


@navigation_router.post("/resume")
async def nav_resume(request: Request):
    loop = asyncio.get_event_loop()
    ok = await loop.run_in_executor(None, _bridge(request).call_nav_resume)
    return {"success": ok}
