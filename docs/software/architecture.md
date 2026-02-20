# Software Architectuur

## Overzicht

Het systeem is gebouwd op **ROS2 Humble** als middleware. ROS2 zorgt voor communicatie tussen alle modules via topics, services en actions. Alle modules draaien op de **NVIDIA Jetson Nano** aan boord van de auto.

```
┌─────────────────────────────────────────────────────────────┐
│                    NVIDIA Jetson Nano                        │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  GPS     │  │ RealSense│  │Ultrasoon │  │    IMU    │  │
│  │ node     │  │  node    │  │  node    │  │   node    │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │              │               │        │
│  ─────┴──────────────┴──────────────┴───────────────┴────── │
│                        ROS2 DDS Bus                         │
│  ─────┬──────────────┬──────────────┬───────────────┬────── │
│       │              │              │               │        │
│  ┌────┴─────┐  ┌─────┴────┐  ┌─────┴────┐  ┌──────┴────┐  │
│  │Navigation│  │Perception│  │Avoidance │  │  Vehicle  │  │
│  │  module  │  │  module  │  │  module  │  │ Control   │  │
│  └────┬─────┘  └─────┬────┘  └─────┬────┘  └──────┬────┘  │
│       │              │              │               │        │
│  ─────┴──────────────┴──────────────┴───────────────┴────── │
│                      Mission Manager                        │
│  ──────────────────────────────────────────────────────── │
│                      Web Dashboard Bridge                   │
└─────────────────────────────────────────────────────────────┘
                              │
                           WiFi
                              │
                    ┌─────────┴──────────┐
                    │   Web Dashboard    │
                    │ (browser / tablet) │
                    └────────────────────┘
```

## ROS2 Nodes

### Sensor Nodes

| Node | Package | Topics | Beschrijving |
|---|---|---|---|
| `gps_node` | `rc_sensors` | `/gps/fix`, `/gps/vel` | u-blox M8N via UART |
| `realsense_node` | `realsense2_camera` | `/camera/depth`, `/camera/color` | Intel RealSense D435i |
| `ultrasonic_node` | `rc_sensors` | `/ultrasonic/distances` | HC-SR04 x4 via GPIO |
| `imu_node` | `rc_sensors` | `/imu/data` | MPU-6050 via I2C |

### Processing Nodes

| Node | Package | Subscribeert | Publiceert | Beschrijving |
|---|---|---|---|---|
| `perception_node` | `rc_perception` | `/camera/color` | `/detections`, `/tracking` | YOLO object detectie |
| `depth_node` | `rc_perception` | `/camera/depth` | `/obstacles/depth` | Dieptekaart verwerking |
| `avoidance_node` | `rc_avoidance` | `/obstacles/*`, `/ultrasonic/*` | `/avoidance/cmd` | Obstakel vermijding logica |
| `navigation_node` | `rc_navigation` | `/gps/fix`, `/imu/data` | `/nav/cmd_vel` | GPS waypoint navigatie |

### Control Nodes

| Node | Package | Subscribeert | Publiceert | Beschrijving |
|---|---|---|---|---|
| `mission_node` | `rc_mission` | Alle | `/vehicle/cmd` | Modusselectie en arbitrage |
| `vehicle_node` | `rc_vehicle` | `/vehicle/cmd` | - | ESC + servo PWM output |
| `dashboard_bridge` | `rc_dashboard` | Alle | - | WebSocket bridge naar dashboard |

## Rijmodi

### Mode 1: Autonome GPS Navigatie

```
GPS waypoints (dashboard)
        ↓
  navigation_node
        ↓
  avoidance_node (override bij obstakels)
        ↓
  mission_node
        ↓
  vehicle_node → ESC + Servo
```

### Mode 2: Follow-Me

```
  realsense_node (RGB)
        ↓
  perception_node (YOLO persoon detectie)
        ↓
  tracking logica (afstand + hoek berekenen)
        ↓
  avoidance_node (check op obstakels)
        ↓
  mission_node
        ↓
  vehicle_node → ESC + Servo
```

### Mode 3: Handmatig + AI Override

```
  dashboard / RC zender
        ↓
  mission_node
        ↓ ← avoidance_node kan ingrijpen
  vehicle_node → ESC + Servo
```

## Web Dashboard

- **Frontend**: React + Leaflet.js (kaart voor waypoints)
- **Backend**: FastAPI (Python) op Jetson Nano
- **Communicatie**: WebSocket voor real-time telemetrie
- **Video stream**: MJPEG of WebRTC voor camerabeeld

### Dashboard functies
- Live camerabeeld (RGB + optioneel diepte overlay)
- Telemetrie: snelheid, GPS positie, batterij, modus
- Waypoint editor op kaart (klik = waypoint)
- Modusselectie (Autonoom / Follow-Me / Handmatig)
- Noodstop knop

## Tech Stack samenvatting

| Laag | Technologie |
|---|---|
| OS | Ubuntu 20.04 (Jetson Nano) |
| Middleware | ROS2 Humble |
| AI / Vision | Python, OpenCV, Ultralytics YOLO v8 |
| Navigatie | Nav2 (ROS2 navigatie stack) |
| Dashboard backend | FastAPI + WebSocket |
| Dashboard frontend | React + Leaflet.js |
| Hardware interface | Jetson GPIO, I2C, UART, USB3 |

## Development setup

> Ontwikkeling kan op een gewone laptop (met ROS2), deployment op Jetson Nano.
> Docker containers worden overwogen voor reproduceerbare builds.
