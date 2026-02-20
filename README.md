# AI RC Car - Autonomous 1:10 Scale Vehicle

An autonomous 1:10 scale RC car powered by AI, capable of GPS navigation, obstacle avoidance, and person/object following.

## Project Status

> **Phase**: Concept & Planning

## Concept

A 1:10 scale RC car platform enhanced with an AI brain (NVIDIA Jetson Nano), depth camera, GPS and ultrasonic sensors. The vehicle can operate in three modes:

| Mode | Description |
|---|---|
| **Autonomous Navigation** | Drive to GPS waypoints without human input |
| **Follow-Me** | Detect and follow a person using YOLO object detection |
| **Assisted Manual** | Human control with AI obstacle avoidance override |

## Hardware Overview

| Component | Part | Status |
|---|---|---|
| Chassis | Arrma Granite 4x4 Mega 1:10 | Planning |
| AI Brain | NVIDIA Jetson Nano 4GB | Planning |
| Depth Camera | Intel RealSense D435i | Planning |
| GPS | u-blox M8N | Planning |
| IMU | MPU-6050 | Planning |
| Ultrasonic | HC-SR04 x4 | Planning |

Full hardware list: [docs/hardware/shopping-list.md](docs/hardware/shopping-list.md)

## Software Stack

```
ROS2 Humble (robotics middleware)
├── Navigation     → GPS waypoints + path planning
├── Perception     → RealSense D435i + YOLO object detection
├── Avoidance      → Depth map + ultrasonic sensor fusion
├── Tracking       → Person/object follow mode
└── Dashboard      → Web UI: live feed, telemetry, control
```

Full architecture: [docs/software/architecture.md](docs/software/architecture.md)

## Repository Structure

```
ai-rc-car/
├── docs/
│   ├── concept.md              # Full project concept
│   ├── hardware/
│   │   ├── shopping-list.md    # Components with prices and links
│   │   └── wiring-diagrams/    # Wiring and connection diagrams
│   └── software/
│       └── architecture.md     # Software architecture details
├── hardware/
│   └── 3d-models/              # STL files for 3D printed parts
├── software/
│   ├── ros2/                   # ROS2 packages
│   ├── ai/                     # AI models and inference code
│   ├── dashboard/              # Web dashboard (frontend + backend)
│   └── scripts/                # Utility and setup scripts
└── tests/                      # Test scripts and validation
```

## Getting Started

> Documentation in progress. Check back as the project evolves.

## License

MIT
