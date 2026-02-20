# Web Dashboard

Laatste update: 2026-02-20

## Overzicht

Het web dashboard biedt een real-time interface voor het besturen, monitoren en configureren van de AI RC auto. Het draait volledig in de browser en verbindt via WiFi met de auto.

```
Browser (tablet/laptop)
    │
    ├── HTTP  → FastAPI backend (poort 8080)
    │   └── REST: waypoints, modus, configuratie
    │
    ├── WebSocket → FastAPI backend (poort 8080/ws)
    │   └── Real-time: telemetrie, detecties, status
    │
    └── WebRTC / MJPEG → camerastream (poort 8081)
```

---

## Schermindeling

```
┌──────────────────────────────────────────────────────────────────┐
│  AI RC Car Dashboard          🔴 STOP    Modus: [Autonoom ▼]    │
├──────────────────────────────┬───────────────────────────────────┤
│                              │  STATUS                           │
│   LIVE CAMERA                │  ┌─────────────────────────────┐ │
│   [annotated video feed]     │  │ Snelheid:    2.3 km/h       │ │
│                              │  │ Batterij:    ████░░ 72%     │ │
│                              │  │ GPS:         ✓ 10 sat.      │ │
│   ┌──depth overlay toggle──┐ │  │ Obstakels:   Vrij           │ │
│   └────────────────────────┘ │  └─────────────────────────────┘ │
├──────────────────────────────┤  DETECTIES                        │
│   KAART (Leaflet.js)         │  ┌─────────────────────────────┐ │
│   [GPS positie + waypoints]  │  │ [persoon] 87% – 2.3m       │ │
│                              │  │ [auto]    71% – 5.1m        │ │
│   [klik = waypoint toevoegen]│  └─────────────────────────────┘ │
│   [◀ Start] [⏸ Pauzeer]     │  WAYPOINTS                        │
│                              │  1. 52.3701°N  4.8952°E  ✓      │
│                              │  2. 52.3699°N  4.8958°E  ➤      │
│                              │  3. 52.3697°N  4.8955°E  ○      │
│                              │  [+ Toevoegen] [🗑 Wissen]       │
└──────────────────────────────┴───────────────────────────────────┘
│  HANDMATIG RIJDEN (modus: manual)                                │
│  [◄◄]  [▲]  [▼]  [►►]   Stuur: ████████░░ +45°              │
└──────────────────────────────────────────────────────────────────┘
```

---

## Backend: FastAPI

### Bestandsstructuur

```
software/dashboard/
├── backend/
│   ├── main.py              # FastAPI app, startup
│   ├── ros_bridge.py        # ROS2 → WebSocket bridge
│   ├── routers/
│   │   ├── waypoints.py     # REST: waypoint CRUD
│   │   ├── mission.py       # REST: modus instellen
│   │   └── vehicle.py       # REST: calibratie, params
│   └── models/
│       └── schemas.py       # Pydantic datamodels
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── VideoFeed.jsx
│   │   │   ├── MapView.jsx
│   │   │   ├── StatusPanel.jsx
│   │   │   ├── DetectionList.jsx
│   │   │   ├── WaypointList.jsx
│   │   │   └── ManualControls.jsx
│   │   └── hooks/
│   │       └── useWebSocket.js
│   └── package.json
└── Dockerfile
```

### REST API endpoints

| Method | Endpoint | Beschrijving |
|---|---|---|
| `GET` | `/api/status` | Huidige voertuigstatus |
| `POST` | `/api/mission/mode` | Wissel modus (body: `{"mode": "autonomous"}`) |
| `POST` | `/api/mission/stop` | Noodstop |
| `GET` | `/api/waypoints` | Alle waypoints ophalen |
| `POST` | `/api/waypoints` | Waypoint toevoegen |
| `DELETE` | `/api/waypoints` | Alle waypoints wissen |
| `POST` | `/api/navigation/start` | Autonome navigatie starten |
| `POST` | `/api/navigation/pause` | Navigatie pauzeren |
| `GET` | `/api/config` | Voertuigparameters ophalen |
| `PUT` | `/api/config` | Voertuigparameters instellen |

### WebSocket protocol (`/ws`)

**Server → Client (elke 100ms):**
```json
{
  "type": "status",
  "data": {
    "mode": "autonomous",
    "speed_ms": 0.64,
    "battery_pct": 72,
    "latitude": 52.3701,
    "longitude": 4.8952,
    "heading_deg": 127.3,
    "avoidance_status": "clear",
    "emergency_stop": false
  }
}
```

**Server → Client (per detectie frame):**
```json
{
  "type": "detections",
  "data": [
    {"class": "person", "confidence": 0.87, "distance_m": 2.3,
     "bbox": [120, 80, 340, 520]},
    {"class": "car", "confidence": 0.71, "distance_m": 5.1,
     "bbox": [600, 200, 900, 450]}
  ]
}
```

**Client → Server (handmatig rijden):**
```json
{
  "type": "manual_cmd",
  "data": {
    "linear_x": 0.3,
    "angular_z": -0.5
  }
}
```

### Backend implementatie (vereenvoudigd)

```python
# backend/main.py
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
import rclpy, threading, asyncio

app = FastAPI()
ros_bridge = RosBridge()

@app.on_event("startup")
async def startup():
    threading.Thread(target=ros_bridge.spin, daemon=True).start()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    queue = ros_bridge.subscribe()
    try:
        while True:
            # Stuur ROS2 data naar browser
            data = await asyncio.get_event_loop().run_in_executor(
                None, queue.get, True, 0.1
            )
            await ws.send_json(data)
    except:
        ros_bridge.unsubscribe(queue)

@app.post("/api/mission/mode")
async def set_mode(body: dict):
    ros_bridge.call_service('/mission/set_mode', body['mode'])
    return {"success": True}

@app.post("/api/waypoints")
async def add_waypoint(wp: WaypointSchema):
    ros_bridge.call_service('/navigation/add_waypoint', wp)
    return {"success": True}

# Serveer frontend build
app.mount("/", StaticFiles(directory="../frontend/dist", html=True))
```

---

## Frontend: React + Leaflet.js

### Kaart met waypoints

```jsx
// components/MapView.jsx
import { MapContainer, TileLayer, Marker, Popup, useMapEvents } from 'react-leaflet'

function WaypointMap({ waypoints, currentPosition, onAddWaypoint }) {
  function ClickHandler() {
    useMapEvents({
      click: (e) => {
        onAddWaypoint(e.latlng.lat, e.latlng.lng)
      }
    })
    return null
  }

  return (
    <MapContainer center={currentPosition} zoom={19} style={{height: '350px'}}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <ClickHandler />

      {/* Auto positie */}
      <Marker position={currentPosition} icon={carIcon}>
        <Popup>Auto is hier</Popup>
      </Marker>

      {/* Waypoints */}
      {waypoints.map((wp, i) => (
        <Marker key={i} position={[wp.lat, wp.lon]} icon={waypointIcon(i, wp.status)}>
          <Popup>Waypoint {i+1}</Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
```

### WebSocket hook

```javascript
// hooks/useWebSocket.js
import { useEffect, useRef, useState } from 'react'

export function useVehicleWebSocket() {
  const ws = useRef(null)
  const [status, setStatus]     = useState(null)
  const [detections, setDetections] = useState([])

  useEffect(() => {
    ws.current = new WebSocket(`ws://${window.location.hostname}:8080/ws`)

    ws.current.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'status')     setStatus(msg.data)
      if (msg.type === 'detections') setDetections(msg.data)
    }

    return () => ws.current?.close()
  }, [])

  const sendManualCmd = (linear_x, angular_z) => {
    ws.current?.send(JSON.stringify({
      type: 'manual_cmd',
      data: { linear_x, angular_z }
    }))
  }

  return { status, detections, sendManualCmd }
}
```

---

## Video streaming

### Optie A: MJPEG (eenvoudig, ~100ms latency)

```python
# In backend/main.py
from fastapi.responses import StreamingResponse
import cv2

@app.get("/stream/color")
async def video_stream():
    def generate():
        while True:
            frame = ros_bridge.latest_frame
            if frame is not None:
                _, jpg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + jpg.tobytes() + b'\r\n')
    return StreamingResponse(generate(),
                             media_type='multipart/x-mixed-replace; boundary=frame')
```

```jsx
// In VideoFeed.jsx
<img src={`http://${host}/stream/color`} style={{width: '100%'}} />
```

### Optie B: WebRTC (lage latency, ~30ms, complexer)

Gebruik `aiortc` (Python) voor WebRTC server-side.
Aanbevolen voor fase 2 wanneer latency belangrijk wordt.

---

## Toegang tot dashboard

Het dashboard draait op de auto zelf. Toegang via:

1. **Lokaal WiFi**: auto verbindt met je WiFi netwerk
   - `http://192.168.x.x:8080` (IP van de auto)

2. **Auto als hotspot**: auto maakt eigen WiFi netspot
   - `http://10.42.0.1:8080` (standaard hotspot IP)
   - Handig buiten bereik van thuis-WiFi

3. **Via telefoon**: open browser op `http://192.168.x.x:8080`
   - Responsive design, werkt op mobiel

```bash
# Auto configureren als WiFi hotspot (NetworkManager)
nmcli con add type wifi ifname wlan0 con-name hotspot autoconnect yes \
  ssid "AI-RC-Car" mode ap ip4 10.42.0.1/24
nmcli con modify hotspot wifi-sec.key-mgmt wpa-psk wifi-sec.psk "rccar1234"
nmcli con up hotspot
```
