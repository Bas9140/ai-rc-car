# Software Architectuur

Laatste update: 2026-02-20

## Inhoudsopgave

1. [Systeemoverzicht](#1-systeemoverzicht)
2. [ROS2 Package structuur](#2-ros2-package-structuur)
3. [Dataflow per modus](#3-dataflow-per-modus)
4. [Modules gedetailleerd](#4-modules-gedetailleerd)
5. [Tech stack](#5-tech-stack)
6. [Development workflow](#6-development-workflow)

Gedetailleerde docs per onderwerp:
- [ros2-topics.md](ros2-topics.md) – Alle topics, services en actions
- [ai-pipeline.md](ai-pipeline.md) – YOLO detectie, tracking, diepte-verwerking
- [vehicle-control.md](vehicle-control.md) – PWM, ESC, servo, motorbesturing
- [navigation.md](navigation.md) – GPS, waypoints, pathplanning
- [dashboard.md](dashboard.md) – Web UI API en WebSocket protocol

---

## 1. Systeemoverzicht

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Jetson Orin Nano / Raspberry Pi 5                 │
│                                                                      │
│  SENSOREN                                                            │
│  ┌─────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────┐  │
│  │ GPS     │ │  RealSense   │ │  Ultrasoon   │ │     IMU        │  │
│  │ M8N     │ │  D435i       │ │  HC-SR04 x4  │ │  MPU-6050      │  │
│  │ UART    │ │  USB3        │ │  GPIO        │ │  I2C           │  │
│  └────┬────┘ └──────┬───────┘ └──────┬───────┘ └───────┬────────┘  │
│       │             │                │                  │           │
│  ─────┴─────────────┴────────────────┴──────────────────┴─────────  │
│                          ROS2 DDS Bus (Humble)                       │
│  ─────┬─────────────┬────────────────┬──────────────────┬─────────  │
│       │             │                │                  │           │
│  VERWERKING                                                          │
│  ┌────┴──────┐ ┌────┴──────┐ ┌───────┴──────┐ ┌────────┴───────┐   │
│  │Navigation │ │Perception │ │  Avoidance   │ │    Mission     │   │
│  │           │ │(YOLO +    │ │  (depth +    │ │    Manager     │   │
│  │GPS+Nav2   │ │ tracking) │ │  ultrasoon)  │ │  (arbitrage)   │   │
│  └────┬──────┘ └────┬──────┘ └───────┬──────┘ └────────┬───────┘   │
│       │             │                │                  │           │
│  ─────┴─────────────┴────────────────┴──────────────────┴─────────  │
│                          /vehicle/cmd_vel                            │
│  ──────────────────────────────┬─────────────────────────────────   │
│                                │                                     │
│  ┌─────────────────────────────┴──────────────────────────────────┐  │
│  │                    Vehicle Control Node                        │  │
│  │         PWM out → ESC (gas/rem)   PWM out → Servo (stuur)     │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │              Dashboard Bridge (FastAPI + WebSocket)            │  │
│  └──────────────────────────────┬─────────────────────────────────┘  │
└─────────────────────────────────┼────────────────────────────────────┘
                                  │ WiFi
                    ┌─────────────┴─────────────┐
                    │       Web Dashboard        │
                    │  React + Leaflet.js        │
                    │  live video / telemetrie   │
                    │  waypoint editor / modus   │
                    └───────────────────────────┘
```

---

## 2. ROS2 Package structuur

```
software/ros2/
├── rc_bringup/              # Launch files voor het hele systeem
│   ├── launch/
│   │   ├── all.launch.py        # Start alle nodes
│   │   ├── sensors.launch.py    # Alleen sensoren
│   │   └── sim.launch.py        # Simulatie (Gazebo)
│   └── config/
│       ├── params.yaml          # Globale parameters
│       └── nav2_params.yaml     # Nav2 configuratie
│
├── rc_sensors/              # Sensor driver nodes
│   ├── rc_sensors/
│   │   ├── gps_node.py          # u-blox M8N → /gps/fix
│   │   ├── ultrasonic_node.py   # HC-SR04 x4 → /ultrasonic/distances
│   │   └── imu_node.py          # MPU-6050 → /imu/data
│   └── package.xml
│
├── rc_perception/           # AI vision nodes
│   ├── rc_perception/
│   │   ├── yolo_node.py         # YOLO v8 detectie → /detections
│   │   ├── tracking_node.py     # Object tracking → /tracking/target
│   │   └── depth_node.py        # RealSense diepte → /obstacles/depth
│   ├── models/                  # YOLO .pt model bestanden (gitignored)
│   └── package.xml
│
├── rc_avoidance/            # Obstakelvermijding
│   ├── rc_avoidance/
│   │   └── avoidance_node.py    # Sensor fusion → /avoidance/override
│   └── package.xml
│
├── rc_navigation/           # GPS navigatie
│   ├── rc_navigation/
│   │   ├── waypoint_node.py     # Waypoint manager → /navigation/goal
│   │   └── path_node.py        # Pathplanning (Nav2 wrapper)
│   └── package.xml
│
├── rc_mission/              # Modus beheer en arbitrage
│   ├── rc_mission/
│   │   └── mission_node.py      # Arbitrage → /vehicle/cmd_vel
│   └── package.xml
│
├── rc_vehicle/              # Hardware interface
│   ├── rc_vehicle/
│   │   └── vehicle_node.py      # cmd_vel → PWM (ESC + servo)
│   └── package.xml
│
├── rc_dashboard/            # Dashboard bridge
│   ├── rc_dashboard/
│   │   └── bridge_node.py       # ROS2 → WebSocket
│   └── package.xml
│
└── rc_interfaces/           # Custom msg/srv/action definities
    ├── msg/
    │   ├── Detection.msg        # Bounding box + klasse + confidence
    │   ├── TrackingTarget.msg   # Getrackt object + afstand + hoek
    │   ├── ObstacleMap.msg      # Obstakel zones rondom auto
    │   └── VehicleStatus.msg    # Batterij, snelheid, modus, GPS
    ├── srv/
    │   ├── SetMode.srv          # Wissel rijmodus
    │   └── AddWaypoint.srv      # Voeg waypoint toe
    ├── action/
    │   └── NavigateTo.action    # Navigeer naar coördinaat
    └── package.xml
```

---

## 3. Dataflow per modus

### Modus 1 – Autonome GPS Navigatie

```
Dashboard (browser)
  → POST /api/waypoints         # Waypoints insturen via REST
  → waypoint_node               # Slaat op, stuurt één voor één
  → /navigation/goal (PoseStamped)
  → Nav2 (action server)        # A* pathplanning
  → /cmd_vel (Twist)
  → mission_node                # Modus = AUTONOMOUS, doorsturen
  ← avoidance_node              # Kan /cmd_vel overschrijven
  → vehicle_node                # Zet om naar PWM signalen
  → ESC + Servo
```

### Modus 2 – Follow-Me

```
realsense_node → /camera/color/image_raw
  → yolo_node                   # Detecteer persoon (klasse 0)
  → /detections
  → tracking_node               # Selecteer dichtste persoon
                                # Bereken afstand (via depth frame)
                                # Bereken hoek (via bounding box center)
  → /tracking/target (TrackingTarget)
  → mission_node                # Modus = FOLLOW, converteer naar cmd_vel
  ← avoidance_node              # Blokkeert bij obstakel < 0.5m
  → vehicle_node → ESC + Servo
```

### Modus 3 – Handmatig + AI override

```
Dashboard joystick / RC zender
  → /joy of /dashboard/manual_cmd
  → mission_node                # Modus = MANUAL, doorsturen
  ← avoidance_node              # Override als obstakel < 0.3m
  → vehicle_node → ESC + Servo
```

### Noodstop (altijd actief)

```
avoidance_node
  → als obstakel < 0.2m voor    # Harde stop, alle modi
  → publiceert /vehicle/emergency_stop
  → vehicle_node stopt ESC onmiddellijk
```

---

## 4. Modules gedetailleerd

### 4.1 Mission Manager (`mission_node`)

De centrale arbitrage-laag. Bepaalt welke bron de rijcommando's levert.

**Prioriteitsvolgorde (hoog → laag):**
1. Noodstop (emergency_stop) – altijd actief
2. Avoidance override – actief in alle auto-modi
3. Autonomous navigation (Nav2 cmd_vel)
4. Follow-Me tracking cmd_vel
5. Manual cmd_vel (dashboard / RC)

**State machine:**
```
         ┌──────────────┐
    ┌───►│    IDLE      │◄──────────────┐
    │    └──────┬───────┘               │
    │           │ set_mode              │
    │    ┌──────▼───────────────────────┴──┐
    │    │         ACTIVE                  │
    │    │  ┌──────────┐  ┌─────────────┐  │
    │    │  │AUTONOMOUS│  │  FOLLOW_ME  │  │
    │    │  └──────────┘  └─────────────┘  │
    │    │  ┌──────────┐                   │
    │    │  │  MANUAL  │                   │
    │    │  └──────────┘                   │
    │    └─────────────────────────────────┘
    │                  │ emergency_stop
    │    ┌─────────────▼──────┐
    └────│   EMERGENCY_STOP   │
         └────────────────────┘
```

### 4.2 Vehicle Control (`vehicle_node`)

Zet `geometry_msgs/Twist` om naar PWM pulsen voor ESC en servo.

**Mapping:**
```
cmd_vel.linear.x  →  ESC PWM
  +1.0 = vol gas vooruit  = 2000µs
   0.0 = neutraal/rem     = 1500µs
  -1.0 = vol gas achteruit = 1000µs

cmd_vel.angular.z →  Servo PWM
  +1.0 = vol links        = 1000µs
   0.0 = rechtdoor        = 1500µs
  -1.0 = vol rechts       = 2000µs
```

**Hardware interface:** Jetson GPIO library (of `pigpio` op RPi 5)

### 4.3 Avoidance Node (`avoidance_node`)

Combineert dieptedata (RealSense) en ultrasoon in één obstakelkaart.

**Zones:**
```
        [VOOR]
    ┌───────────┐
    │  kritiek  │  < 0.3m  → noodstop
    │  gevaar   │  < 0.7m  → afremmen + stuur weg
    │  waarsch. │  < 1.5m  → vertraag
    └───────────┘
  [L]  [AUTO]  [R]
    ┌───┐     ┌───┐
    │0.4│     │0.4│  zijkanten < 0.4m → stuur weg
    └───┘     └───┘
        [ACHTER]
    ┌───────────┐
    │  < 0.3m   │  → stop achteruitrijden
    └───────────┘
```

**Output:** publiceert gecorrigeerde `Twist` op `/avoidance/override` wanneer ingrijpen nodig is.

---

## 5. Tech Stack

| Laag | Technologie | Versie | Reden |
|---|---|---|---|
| **OS** | Ubuntu 22.04 LTS | 22.04 | JetPack 6 / RPi officieel |
| **Middleware** | ROS2 Humble | Humble LTS | LTS tot 2027, breed gedragen |
| **AI detectie** | Ultralytics YOLO v8 | v8.3+ | Beste speed/accuracy, Python API |
| **AI model** | YOLOv8n (nano) | - | Snel op CPU (RPi), of v8m op GPU |
| **Computer vision** | OpenCV | 4.x | Beeldverwerking, frame manipulatie |
| **Diepte SDK** | Intel RealSense SDK 2.0 | 2.x | ROS2 package: `realsense2_camera` |
| **Navigatie** | Nav2 | Humble | ROS2 navigatie stack, A* planning |
| **Dashboard backend** | FastAPI | 0.115+ | Async Python, WebSocket support |
| **Dashboard frontend** | React + Vite | React 18 | Snel en modern |
| **Kaart** | Leaflet.js | 1.9 | Open source kaartbibliotheek |
| **Video stream** | WebRTC (aiortc) | - | Lage latency live video |
| **GPIO** | Jetson.GPIO / lgpio | - | PWM voor ESC en servo |
| **GPS parser** | pyserial + pynmea2 | - | NMEA parsing van u-blox M8N |
| **IMU** | smbus2 | - | I2C communicatie MPU-6050 |

---

## 6. Development Workflow

### Lokaal ontwikkelen (laptop)
```bash
# ROS2 Humble installeren op Ubuntu 22.04
# Ontwikkel en test nodes zonder hardware

# Simulatie met Gazebo (optioneel)
ros2 launch rc_bringup sim.launch.py

# Unit tests draaien
colcon test --packages-select rc_perception
```

### Deployen op het voertuig
```bash
# SSH naar het voertuig
ssh bas@<IP-van-auto>

# Code synchen (of git pull)
cd ~/ai-rc-car && git pull

# ROS2 workspace builden
cd ~/ros2_ws && colcon build --symlink-install

# Alles starten
ros2 launch rc_bringup all.launch.py
```

### Aanbevolen ontwikkel-volgorde
1. `rc_vehicle` – motor/servo aansturen, handmatig testen
2. `rc_sensors` – alle sensoren inlezen, data valideren
3. `rc_perception` – YOLO draaien op camerabeelden
4. `rc_avoidance` – obstakels detecteren, testen op bureau
5. `rc_navigation` – GPS waypoints, testen buiten
6. `rc_mission` – modi integreren
7. `rc_dashboard` – web UI bouwen

> Begin altijd met een fysieke noodstop (kill switch op RC zender) voordat je autonoom rijdt.
