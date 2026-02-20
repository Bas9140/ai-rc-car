# ROS2 Topics, Services & Actions

Laatste update: 2026-02-20

## Topics overzicht

### Sensor topics (gepubliceerd door sensor nodes)

| Topic | Msg type | Hz | Publisher | Beschrijving |
|---|---|---|---|---|
| `/gps/fix` | `sensor_msgs/NavSatFix` | 10 | `gps_node` | GPS positie (lat/lon/alt, covariantie) |
| `/gps/vel` | `geometry_msgs/TwistWithCovarianceStamped` | 10 | `gps_node` | GPS snelheid (m/s) |
| `/imu/data` | `sensor_msgs/Imu` | 100 | `imu_node` | Versnelling + gyro + orientatie |
| `/ultrasonic/distances` | `rc_interfaces/ObstacleMap` | 20 | `ultrasonic_node` | Afstanden voor/achter/links/rechts (m) |
| `/camera/color/image_raw` | `sensor_msgs/Image` | 30 | `realsense_node` | RGB cameraframe (1280x720) |
| `/camera/depth/image_rect_raw` | `sensor_msgs/Image` | 30 | `realsense_node` | Diepteframe in mm (uint16) |
| `/camera/color/camera_info` | `sensor_msgs/CameraInfo` | 30 | `realsense_node` | Camerakalibratie (intrinsics) |
| `/camera/depth/camera_info` | `sensor_msgs/CameraInfo` | 30 | `realsense_node` | Dieptecamera kalibratie |
| `/camera/imu` | `sensor_msgs/Imu` | 200 | `realsense_node` | Ingebouwde IMU van D435i |

---

### Perception topics (gepubliceerd door perception nodes)

| Topic | Msg type | Hz | Publisher | Beschrijving |
|---|---|---|---|---|
| `/detections` | `rc_interfaces/Detection[]` | 10-30 | `yolo_node` | Lijst van gedetecteerde objecten |
| `/tracking/target` | `rc_interfaces/TrackingTarget` | 10-30 | `tracking_node` | Huidig getrackt doel (positie, afstand, hoek) |
| `/tracking/active` | `std_msgs/Bool` | 10 | `tracking_node` | True als er een actief doelwit is |
| `/obstacles/depth` | `rc_interfaces/ObstacleMap` | 15 | `depth_node` | Obstakels gevonden via dieptekaart |
| `/camera/annotated` | `sensor_msgs/Image` | 10 | `yolo_node` | Geannoteerd cameraframe (voor dashboard) |

---

### Navigation topics

| Topic | Msg type | Hz | Publisher | Beschrijving |
|---|---|---|---|---|
| `/navigation/goal` | `geometry_msgs/PoseStamped` | event | `waypoint_node` | Huidige navigatiedoelstelling |
| `/navigation/waypoints` | `nav_msgs/Path` | event | `waypoint_node` | Lijst van alle waypoints |
| `/navigation/cmd_vel` | `geometry_msgs/Twist` | 10 | Nav2 | Rijcommando vanuit navigatie |
| `/map` | `nav_msgs/OccupancyGrid` | 1 | Nav2 | Kaart (optioneel, voor obstakelplanning) |
| `/odom` | `nav_msgs/Odometry` | 10 | `gps_node` | Odometrie (GPS + IMU gefused) |
| `/tf` | `tf2_msgs/TFMessage` | 100 | meerdere | Coördinaatframes (base_link, map, odom) |

---

### Avoidance topics

| Topic | Msg type | Hz | Publisher | Beschrijving |
|---|---|---|---|---|
| `/avoidance/override` | `geometry_msgs/Twist` | 20 | `avoidance_node` | Gecorrigeerde rijcommando |
| `/avoidance/status` | `std_msgs/String` | 10 | `avoidance_node` | "clear" / "warning" / "danger" / "stop" |
| `/vehicle/emergency_stop` | `std_msgs/Bool` | event | `avoidance_node` | Noodstop trigger |

---

### Control topics

| Topic | Msg type | Hz | Publisher | Beschrijving |
|---|---|---|---|---|
| `/vehicle/cmd_vel` | `geometry_msgs/Twist` | 20 | `mission_node` | Definitieve rijcommando naar voertuig |
| `/vehicle/status` | `rc_interfaces/VehicleStatus` | 5 | `vehicle_node` | Batterij, modus, snelheid, GPS |
| `/dashboard/manual_cmd` | `geometry_msgs/Twist` | 20 | `bridge_node` | Handmatig commando vanuit dashboard |
| `/mission/mode` | `std_msgs/String` | event | `mission_node` | Huidig actieve modus |
| `/joy` | `sensor_msgs/Joy` | 50 | RC zender driver | RC zender input (optioneel) |

---

## Custom Message definities

### `rc_interfaces/msg/Detection.msg`
```
# Één gedetecteerd object (output van YOLO)
std_msgs/Header header
int32   class_id        # COCO klasse ID (0=persoon, 2=auto, etc.)
string  class_name      # Leesbare klassenaam
float32 confidence      # Betrouwbaarheid 0.0-1.0
float32 x_min           # Bounding box links (pixels)
float32 y_min           # Bounding box boven (pixels)
float32 x_max           # Bounding box rechts (pixels)
float32 y_max           # Bounding box onder (pixels)
float32 depth_m         # Afstand in meters (van diepteframe, 0 als onbekend)
```

### `rc_interfaces/msg/TrackingTarget.msg`
```
# Het actief getrackte doelwit (output van tracking_node)
std_msgs/Header header
bool    active          # Is er een actief doelwit?
int32   track_id        # Uniek ID van dit object
float32 distance_m      # Afstand tot doelwit in meters
float32 angle_deg       # Hoek t.o.v. rijrichting in graden (- = links, + = rechts)
float32 bbox_center_x   # Horizontale positie in frame (0.0-1.0, 0.5=midden)
float32 bbox_center_y   # Verticale positie in frame (0.0-1.0)
float32 bbox_width      # Breedte bounding box (0.0-1.0 van framebreedtebredte)
```

### `rc_interfaces/msg/ObstacleMap.msg`
```
# Obstakelafstanden rondom de auto
std_msgs/Header header
float32 front_m         # Obstakel voor (min afstand in cone voor)
float32 rear_m          # Obstakel achter
float32 left_m          # Obstakel links
float32 right_m         # Obstakel rechts
float32 front_left_m    # Diagonaal voor-links (van dieptekaart)
float32 front_right_m   # Diagonaal voor-rechts (van dieptekaart)
string  source          # "ultrasonic" / "depth" / "fused"
```

### `rc_interfaces/msg/VehicleStatus.msg`
```
# Volledige voertuigstatus voor dashboard
std_msgs/Header header
string  mode            # "idle" / "autonomous" / "follow_me" / "manual"
float32 speed_ms        # Huidige snelheid m/s
float32 battery_pct     # Batterijpercentage 0-100
float64 latitude        # GPS breedtegraad
float64 longitude       # GPS lengtegraad
float32 heading_deg     # Rijrichting in graden (0=Noord)
string  avoidance_status # "clear" / "warning" / "danger" / "stop"
bool    emergency_stop  # Noodstop actief?
```

---

## Services

| Service | Type | Server | Beschrijving |
|---|---|---|---|
| `/mission/set_mode` | `rc_interfaces/SetMode` | `mission_node` | Wissel rijmodus |
| `/navigation/add_waypoint` | `rc_interfaces/AddWaypoint` | `waypoint_node` | Voeg waypoint toe |
| `/navigation/clear_waypoints` | `std_srvs/Empty` | `waypoint_node` | Wis alle waypoints |
| `/navigation/start` | `std_srvs/Empty` | `waypoint_node` | Start autonome navigatie |
| `/navigation/pause` | `std_srvs/Empty` | `waypoint_node` | Pauzeer navigatie |
| `/vehicle/calibrate` | `std_srvs/Empty` | `vehicle_node` | Kalibreer ESC/servo |

### `rc_interfaces/srv/SetMode.srv`
```
# Request
string mode   # "idle" / "autonomous" / "follow_me" / "manual"
---
# Response
bool success
string message
```

### `rc_interfaces/srv/AddWaypoint.srv`
```
# Request
float64 latitude
float64 longitude
float32 target_radius_m  # Bereikt als auto binnen deze radius komt
---
# Response
bool    success
int32   waypoint_id
int32   total_waypoints
```

---

## Actions

### `rc_interfaces/action/NavigateTo.action`
```
# Goal
float64 latitude
float64 longitude
float32 target_radius_m
---
# Result
bool    success
float32 distance_traveled_m
float32 duration_s
---
# Feedback (elke seconde)
float32 distance_remaining_m
float32 current_speed_ms
string  status
```
