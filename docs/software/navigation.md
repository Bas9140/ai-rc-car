# GPS Navigatie

Laatste update: 2026-02-20

## Overzicht

De navigatiestack combineert GPS positie, IMU oriëntatie en Nav2 (ROS2 navigatie framework) voor waypoint-navigatie buiten op verharding.

```
u-blox M8N GPS  →  /gps/fix (NavSatFix)
MPU-6050 IMU    →  /imu/data                  ─┐
                                                ├→ robot_localization (EKF)
                                                │   → /odom (Odometry)
                                                │   → /tf  (odom → base_link)
                                                ─┘
/odom + /tf  →  Nav2 (navfn planner + DWB controller)
                   → /navigation/cmd_vel (Twist)
```

---

## GPS Node (`gps_node`)

### NMEA parsing van u-blox M8N

De u-blox M8N communiceert via UART op 9600 baud (instelbaar tot 115200).
Output: NMEA 0183 sentences (GGA, RMC, VTG).

```python
import serial, pynmea2

class GpsNode(Node):
    def __init__(self):
        super().__init__('gps_node')
        self.port = serial.Serial('/dev/ttyUSB0', baudrate=9600, timeout=1)
        self.pub  = self.create_publisher(NavSatFix, '/gps/fix', 10)
        self.create_timer(0.1, self.read_gps)

    def read_gps(self):
        line = self.port.readline().decode('ascii', errors='ignore').strip()
        if line.startswith('$GPGGA') or line.startswith('$GNGGA'):
            msg = pynmea2.parse(line)
            fix = NavSatFix()
            fix.latitude  = msg.latitude
            fix.longitude = msg.longitude
            fix.altitude  = float(msg.altitude or 0)
            fix.status.status = 0 if msg.gps_qual > 0 else -1
            # Positienauwkeurigheid: M8N ≈ 1-2m → covariantie = 4m²
            fix.position_covariance = [4.0, 0, 0, 0, 4.0, 0, 0, 0, 9.0]
            fix.position_covariance_type = 2  # DIAGONAL_KNOWN
            self.pub.publish(fix)
```

### GPS coördinaten omzetten naar lokaal frame

Voor navigatie converteren we GPS (lat/lon) naar een lokaal vlak coördinatensysteem (meters):

```python
from pyproj import Proj

class CoordinateConverter:
    def __init__(self, origin_lat: float, origin_lon: float):
        # UTM projectie gecentreerd op startpunt
        self.proj = Proj(proj='utm', zone=31, ellps='WGS84')
        self.origin_x, self.origin_y = self.proj(origin_lon, origin_lat)

    def gps_to_local(self, lat: float, lon: float):
        x, y = self.proj(lon, lat)
        return x - self.origin_x, y - self.origin_y
```

---

## Sensor Fusion: robot_localization (EKF)

GPS alleen is niet voldoende voor vloeiende navigatie (1-2m nauwkeurigheid, 10Hz, springerig).
We gebruiken een **Extended Kalman Filter (EKF)** die GPS en IMU combineert.

### Pakket: `robot_localization`

```yaml
# config/ekf_params.yaml
ekf_filter_node:
  frequency: 30.0         # Filter update rate
  sensor_timeout: 0.1

  odom_frame:  odom
  base_link_frame: base_link
  world_frame: odom

  # GPS: positie x,y (uit navsat_transform_node)
  odom0: /odometry/gps
  odom0_config: [true,  true,  false,   # x, y, z
                 false, false, false,   # roll, pitch, yaw
                 false, false, false,   # vx, vy, vz
                 false, false, false,   # vroll, vpitch, vyaw
                 false, false, false]   # ax, ay, az

  # IMU: oriëntatie + hoeksnelheid
  imu0: /imu/data
  imu0_config: [false, false, false,
                true,  true,  true,    # roll, pitch, yaw
                false, false, false,
                true,  true,  true,    # gyro
                true,  true,  false]   # accel x, y
```

---

## Waypoint Navigatie (`waypoint_node`)

### Werking

1. Gebruiker stuurt waypoints via dashboard (lat/lon per klik op kaart)
2. `waypoint_node` slaat waypoints op in een queue
3. Per waypoint: stuur als Nav2 NavigateToPose goal
4. Als binnen `target_radius` → next waypoint
5. Als alle waypoints bereikt → stop, meld dashboard

```python
class WaypointNode(Node):
    def __init__(self):
        super().__init__('waypoint_node')
        self.waypoints: list[tuple] = []  # [(lat, lon, radius_m), ...]
        self.current_idx = 0
        self.active = False

        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Services
        self.create_service(AddWaypoint, '/navigation/add_waypoint', self.add_wp_cb)
        self.create_service(Empty, '/navigation/start', self.start_cb)
        self.create_service(Empty, '/navigation/clear_waypoints', self.clear_cb)

    def start_cb(self, req, resp):
        if self.waypoints:
            self.active = True
            self.navigate_to_current()
        return resp

    def navigate_to_current(self):
        lat, lon, radius = self.waypoints[self.current_idx]
        x, y = self.converter.gps_to_local(lat, lon)

        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y

        self.nav_client.send_goal_async(goal, feedback_callback=self.feedback_cb)

    def feedback_cb(self, feedback):
        dist = feedback.feedback.distance_remaining
        if dist < self.waypoints[self.current_idx][2]:  # Binnen radius
            self.current_idx += 1
            if self.current_idx < len(self.waypoints):
                self.navigate_to_current()
            else:
                self.active = False
                self.get_logger().info("Alle waypoints bereikt!")
```

---

## Nav2 Configuratie voor RC Auto

Nav2 is ontworpen voor grote robots. We passen parameters aan voor een kleine, snelle RC auto.

```yaml
# config/nav2_params.yaml

controller_server:
  ros__parameters:
    controller_plugins: ["FollowPath"]
    FollowPath:
      plugin: "dwb_core::DWBLocalPlanner"
      max_vel_x: 0.8          # Max snelheid vooruit (m/s)
      min_vel_x: -0.3         # Lichte achteruit mogelijk
      max_vel_theta: 1.2      # Max draaisnelheid (rad/s)
      min_speed_xy: 0.05      # Minimale rijsnelheid
      acc_lim_x: 2.5          # Acceleratielimiet
      acc_lim_theta: 3.2

planner_server:
  ros__parameters:
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "nav2_navfn_planner/NavfnPlanner"
      tolerance: 0.5          # 50cm afwijking op pad OK

local_costmap:
  local_costmap:
    ros__parameters:
      width: 5.0              # 5x5 meter lokale kaart
      height: 5.0
      resolution: 0.05        # 5cm per cel

global_costmap:
  global_costmap:
    ros__parameters:
      resolution: 0.1         # 10cm per cel (buiten GPS-kaart)
```

---

## Nauwkeurigheid en beperkingen

| Eigenschap | Waarde | Opmerking |
|---|---|---|
| GPS nauwkeurigheid (u-blox M8N) | 1-2m CEP | In open veld |
| GPS nauwkeurigheid (bebouwing) | 3-10m | Verslechtering door multipath |
| GPS update rate | 10 Hz | Instelbaar tot 18 Hz |
| EKF output rate | 30 Hz | Tussen GPS updates interpolatie via IMU |
| Minimale waypoint afstand | ~3m | Kleiner is onbetrouwbaar met M8N |
| Upgrade naar RTK GPS | <0.02m | u-blox F9P, ~€200 extra |

### Aanbeveling testlocatie
- **Goed**: Open parkeerplaats, sportveld, industrieterrein
- **Matig**: Woonwijk (bebouwing verslechtert GPS)
- **Slecht**: Onder bomen, in smalle straten
