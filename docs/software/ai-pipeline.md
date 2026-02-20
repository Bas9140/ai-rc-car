# AI Pipeline

Laatste update: 2026-02-20

## Overzicht

De AI pipeline bestaat uit drie stappen die in serie draaien op elk cameraframe:

```
RealSense D435i
      │
      ├── RGB frame (1280x720 @ 30fps)
      │         │
      │         ▼
      │   ┌─────────────┐
      │   │  yolo_node  │  Object detectie (YOLO v8)
      │   └──────┬──────┘
      │          │ /detections
      │          ▼
      │   ┌──────────────┐
      │   │tracking_node │  Target selectie + volg-logica
      │   └──────┬───────┘
      │          │ /tracking/target
      │          ▼
      │   ┌──────────────┐
      │   │ mission_node │  Omzetten naar rijcommando
      │   └──────────────┘
      │
      └── Depth frame (1280x720 @ 30fps, uint16 mm)
                │
                ▼
         ┌──────────────┐
         │  depth_node  │  Obstakels detecteren
         └──────┬───────┘
                │ /obstacles/depth
                ▼
         ┌──────────────────┐
         │  avoidance_node  │  Samenvoegen met ultrasoon
         └──────────────────┘
```

---

## 1. YOLO Detectie Node (`yolo_node`)

### Model keuze

| Model | Parameters | GPU fps (Jetson) | CPU fps (RPi5) | Aanbevolen voor |
|---|---|---|---|---|
| YOLOv8n (nano) | 3.2M | 60+ fps | 8-12 fps | RPi 5 / begin fase |
| YOLOv8s (small) | 11.2M | 45 fps | 3-5 fps | RPi 5 (langzaam) |
| YOLOv8m (medium) | 25.9M | 30 fps | te langzaam | Jetson Orin Nano |
| YOLOv8l (large) | 43.7M | 20 fps | te langzaam | Jetson Orin Nano |

**Aanbeveling:**
- Raspberry Pi 5: gebruik `yolov8n.pt`
- Jetson Orin Nano: gebruik `yolov8m.pt` (met TensorRT export → nog sneller)

### COCO klassen die relevant zijn

```python
RELEVANT_CLASSES = {
    0:  "person",       # Follow-Me modus
    1:  "bicycle",
    2:  "car",
    3:  "motorcycle",
    5:  "bus",
    7:  "truck",
    9:  "traffic light",
    11: "stop sign",
}
```

### Node logica (pseudocode)

```python
class YoloNode(Node):
    def __init__(self):
        self.model = YOLO('yolov8n.pt')
        self.model.conf = 0.45      # Minimum confidence
        self.model.iou  = 0.5       # NMS IoU threshold
        self.model.classes = [0, 2, 3, 5, 7]  # Alleen relevante klassen

    def image_callback(self, msg):
        frame = ros_image_to_cv2(msg)
        results = self.model(frame, verbose=False)

        detections = []
        for box in results[0].boxes:
            det = Detection()
            det.class_id   = int(box.cls)
            det.confidence = float(box.conf)
            det.x_min, det.y_min, det.x_max, det.y_max = box.xyxy[0]
            detections.append(det)

        self.pub_detections.publish(detections)

        # Annoteer frame voor dashboard
        annotated = results[0].plot()
        self.pub_annotated.publish(cv2_to_ros_image(annotated))
```

### TensorRT optimalisatie (Jetson Orin Nano)

```bash
# Exporteer model naar TensorRT formaat (eenmalig op de Jetson)
yolo export model=yolov8m.pt format=engine device=0 half=True

# Gebruik in node
self.model = YOLO('yolov8m.engine')  # 2-3x sneller dan .pt
```

---

## 2. Tracking Node (`tracking_node`)

### Doel
Selecteer uit de YOLO detecties één doelwit om te volgen, en houd dat vast over frames heen.

### Algoritme

```
Nieuwe frame met detecties
         │
         ▼
    Zijn er personen (class_id=0)?
    ├── Nee → target = None, /tracking/active = False
    └── Ja
         │
         ▼
    Hebben we al een actief doelwit?
    ├── Nee → kies dichtste persoon (grootste bounding box)
    └── Ja → zoek overlap (IoU) met vorig frame
         ├── IoU > 0.3 → zelfde persoon, update positie
         └── IoU < 0.3 → verloren, wacht 10 frames, dan nieuwe selectie
         │
         ▼
    Bereken rijcommando-parameters:
    ├── afstand_m = diepteframe[center_x, center_y] / 1000.0
    ├── hoek_deg  = (center_x - frame_width/2) / frame_width * FOV_DEG
    └── publiceer /tracking/target
```

### Diepte ophalen

```python
def get_depth_at_bbox(depth_frame, x_min, y_min, x_max, y_max):
    """
    Gemiddelde diepte van het midden 50% van de bounding box.
    Negeert 0-waarden (geen dieptedata).
    """
    cx1 = int(x_min + (x_max - x_min) * 0.25)
    cy1 = int(y_min + (y_max - y_min) * 0.25)
    cx2 = int(x_min + (x_max - x_min) * 0.75)
    cy2 = int(y_min + (y_max - y_min) * 0.75)

    roi = depth_frame[cy1:cy2, cx1:cx2]
    valid = roi[roi > 0]
    return np.median(valid) / 1000.0 if len(valid) > 0 else 0.0
```

### Follow-Me rijlogica

```python
TARGET_DISTANCE_M = 1.5   # Gewenste afstand tot persoon
DISTANCE_DEADZONE = 0.2   # +/- 20cm = geen gas/rem
ANGLE_DEADZONE_DEG = 5.0  # +/- 5 graden = rechtdoor

def tracking_to_cmd_vel(target: TrackingTarget) -> Twist:
    cmd = Twist()

    # Gas/rem op basis van afstand
    distance_error = target.distance_m - TARGET_DISTANCE_M
    if abs(distance_error) > DISTANCE_DEADZONE:
        cmd.linear.x = clamp(distance_error * 0.4, -0.6, 0.8)

    # Sturen op basis van hoek
    if abs(target.angle_deg) > ANGLE_DEADZONE_DEG:
        cmd.angular.z = clamp(-target.angle_deg * 0.03, -1.0, 1.0)

    return cmd
```

---

## 3. Depth Processing Node (`depth_node`)

### Diepteframe → obstakelkaart

De RealSense levert een diepteframe van 1280x720 pixels. Elke pixel is de afstand in millimeters.

```python
def depth_frame_to_obstacles(depth_frame) -> ObstacleMap:
    h, w = depth_frame.shape
    obstacles = ObstacleMap()

    # Definieer zones (als fracties van het frame)
    zones = {
        'front':       depth_frame[h//3:2*h//3,  w//3:2*w//3],   # Midden
        'front_left':  depth_frame[h//3:2*h//3,  0:w//3],         # Links
        'front_right': depth_frame[h//3:2*h//3,  2*w//3:w],       # Rechts
    }

    for name, zone in zones.items():
        valid = zone[(zone > 100) & (zone < 8000)]  # 10cm - 8m
        if len(valid) > 0:
            # Gebruik 10e percentiel: dichtste obstakel, negeert ruis
            min_dist = np.percentile(valid, 10) / 1000.0
        else:
            min_dist = 9.9  # Vrij

        setattr(obstacles, f'{name}_m', min_dist)

    obstacles.source = "depth"
    return obstacles
```

---

## 4. Sensor Fusion in Avoidance Node

```
RealSense depth → /obstacles/depth   ─┐
HC-SR04 x4      → /ultrasonic/distances ─┤→ fusion → /avoidance/status
                                       ─┘             /avoidance/override
```

### Fusielogica

```python
def fuse_obstacles(depth: ObstacleMap, ultrasonic: ObstacleMap) -> ObstacleMap:
    """Neem de dichtste waarde per richting."""
    fused = ObstacleMap()
    fused.front_m = min(depth.front_m, ultrasonic.front_m)
    fused.rear_m  = min(depth.rear_m,  ultrasonic.rear_m)
    fused.left_m  = min(depth.left_m,  ultrasonic.left_m)
    fused.right_m = min(depth.right_m, ultrasonic.right_m)
    fused.source  = "fused"
    return fused

def compute_avoidance_override(fused: ObstacleMap, cmd: Twist) -> Twist:
    """Pas rijcommando aan op basis van obstakels."""
    override = Twist()
    override.linear.x  = cmd.linear.x
    override.angular.z = cmd.angular.z

    front = fused.front_m

    if front < 0.3:                         # Noodstop
        override.linear.x  = 0.0
        override.angular.z = 0.0
        publish_emergency_stop()

    elif front < 0.7:                       # Gevaar: afremmen + stuur weg
        override.linear.x = min(cmd.linear.x, 0.0)
        # Stuur naar de ruimste kant
        if fused.left_m > fused.right_m:
            override.angular.z = 0.6
        else:
            override.angular.z = -0.6

    elif front < 1.5:                       # Waarschuwing: vertraag
        override.linear.x = min(cmd.linear.x, 0.3)

    return override
```

---

## 5. Model Training (optioneel)

Voor betere herkenning in specifieke omstandigheden (nacht, regen, specifieke objecten) kun je YOLO fine-tunen op eigen data.

```bash
# Verzamel eigen data met de auto
ros2 run rc_perception capture_dataset --output /datasets/rc_car/

# Label met Label Studio of Roboflow

# Train
yolo train model=yolov8n.pt data=rc_car.yaml epochs=50 imgsz=640

# Exporteer naar TensorRT (Jetson)
yolo export model=runs/train/exp/weights/best.pt format=engine device=0
```
