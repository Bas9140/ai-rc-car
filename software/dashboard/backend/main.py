"""
main.py
FastAPI dashboard backend voor de AI RC Car.

Start:
  cd software/dashboard
  uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload

Of met het start script:
  ./start.sh

WebSocket: ws://[auto-ip]:8080/ws
Video:     http://[auto-ip]:8080/stream/color
Frontend:  http://[auto-ip]:8080/
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .ros_bridge import RosBridge
from .routers.mission import router as mission_router, navigation_router
from .routers.waypoints import router as waypoints_router

import os

FRONTEND_DIST = os.path.join(
    os.path.dirname(__file__), "..", "frontend", "dist")
FRONTEND_INDEX = os.path.join(FRONTEND_DIST, "index.html")


# ── Lifespan (startup / shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    bridge = RosBridge()
    app.state.bridge = bridge
    bridge.start()
    print("[dashboard] Backend gestart op http://0.0.0.0:8080")
    yield
    bridge.stop()
    print("[dashboard] Backend gestopt")


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI RC Car Dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mission_router)
app.include_router(navigation_router)
app.include_router(waypoints_router)


# ── Status endpoint ──────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return app.state.bridge.get_state()


# ── WebSocket ────────────────────────────────────────────────────────────────

class ConnectionManager:
    """Beheert alle actieve WebSocket-verbindingen."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            try:
                self._connections.remove(ws)
            except ValueError:
                pass

    async def broadcast(self, data: dict) -> None:
        msg = json.dumps(data)
        async with self._lock:
            dead = []
            for ws in self._connections:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self._connections.remove(ws)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    bridge = app.state.bridge

    # Ontvang berichten van client (manual_cmd) terwijl we ook sturen
    async def receive_loop():
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                if msg.get("type") == "manual_cmd":
                    d = msg.get("data", {})
                    bridge.publish_manual_cmd(
                        d.get("linear_x", 0.0),
                        d.get("angular_z", 0.0),
                    )
                elif msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
        except (WebSocketDisconnect, Exception):
            pass

    async def send_loop():
        """Stuur telemetrie @ 10 Hz."""
        try:
            while True:
                state = bridge.get_state()
                wps   = bridge.get_waypoints()
                await ws.send_text(json.dumps({
                    "type": "status",
                    "data": {**state, "waypoints": wps},
                }))
                await asyncio.sleep(0.1)
        except (WebSocketDisconnect, Exception):
            pass

    # Beide loops parallel, stop als een van de twee stopt
    await asyncio.gather(
        receive_loop(),
        send_loop(),
        return_exceptions=True,
    )
    await manager.disconnect(ws)


# ── MJPEG video stream ───────────────────────────────────────────────────────

@app.get("/stream/color")
async def video_stream():
    bridge = app.state.bridge

    async def generate():
        while True:
            frame = bridge.get_latest_frame()
            if frame:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame +
                    b"\r\n"
                )
            else:
                # Placeholder als geen camera beschikbaar
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n"
            await asyncio.sleep(0.033)   # ~30 fps max

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


# ── Frontend ─────────────────────────────────────────────────────────────────

# Serveer React build als die bestaat
if os.path.isdir(FRONTEND_DIST):
    app.mount(
        "/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
else:
    @app.get("/")
    async def frontend_not_built():
        return HTMLResponse("""
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <title>AI RC Car – Dashboard</title>
  <style>
    body { font-family: sans-serif; max-width: 600px; margin: 80px auto; }
    code { background: #f0f0f0; padding: 2px 6px; border-radius: 3px; }
    pre  { background: #f0f0f0; padding: 12px; border-radius: 6px; }
  </style>
</head>
<body>
  <h1>🚗 AI RC Car Dashboard</h1>
  <p>Backend draait! Bouw nu de frontend:</p>
  <pre>cd software/dashboard/frontend
npm install
npm run build</pre>
  <p>Of gebruik het start script:</p>
  <pre>cd software/dashboard
./start.sh</pre>
  <p>API docs: <a href="/docs">/docs</a></p>
</body>
</html>
""")
