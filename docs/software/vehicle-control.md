# Vehicle Control

Laatste update: 2026-02-20

## Overzicht

De `vehicle_node` is de enige node die direct met hardware communiceert: de ESC (motor) en het servo (stuur). Alle andere nodes sturen alleen ROS2 berichten.

```
/vehicle/cmd_vel (Twist)
         │
         ▼
   vehicle_node
    ├── linear.x  → ESC PWM  → Borstelloze motor
    └── angular.z → Servo PWM → Stuurservo
```

---

## PWM Interface

### Signaalspecificaties

RC-systemen gebruiken standaard **50Hz PWM** met pulsbreedtes tussen 1000µs en 2000µs:

| Pulswijdte | Betekenis ESC | Betekenis Servo |
|---|---|---|
| 1000 µs | Vol achteruit | Vol links |
| 1500 µs | Stilstand / neutraal | Rechtdoor |
| 2000 µs | Vol vooruit | Vol rechts |

### Arrma Granite ESC (BLX80)

De BLX80 ESC in de Arrma heeft een **veiligheidssequentie** bij opstart:
1. Zet ESC aan met signaal op 1500µs (neutraal)
2. Wacht op armeringssignaal (LED groen)
3. Daarna kun je gas geven

```python
class ESCController:
    NEUTRAL_US = 1500
    MAX_FWD_US = 2000
    MAX_REV_US = 1000

    def __init__(self, gpio_pin: int):
        self.pin = gpio_pin
        self.pwm = GPIO.PWM(gpio_pin, 50)  # 50 Hz
        self.pwm.start(self._us_to_duty(self.NEUTRAL_US))
        time.sleep(2.0)  # Wacht op ESC armering

    def set_throttle(self, value: float):
        """
        value: -1.0 (vol achteruit) tot +1.0 (vol vooruit)
        """
        value = max(-1.0, min(1.0, value))
        if value >= 0:
            us = self.NEUTRAL_US + value * (self.MAX_FWD_US - self.NEUTRAL_US)
        else:
            us = self.NEUTRAL_US + value * (self.NEUTRAL_US - self.MAX_REV_US)
        self.pwm.ChangeDutyCycle(self._us_to_duty(int(us)))

    def _us_to_duty(self, us: int) -> float:
        # PWM period = 20000µs (50Hz), duty = us/period * 100
        return us / 20000.0 * 100.0
```

### Servo (BLS-2 / standaard RC servo)

```python
class ServoController:
    CENTER_US   = 1500
    MAX_LEFT_US = 1000
    MAX_RIGHT_US = 2000

    def set_steering(self, value: float):
        """
        value: -1.0 (vol links) tot +1.0 (vol rechts)
        Let op: negatieve angular.z = links in ROS2 conventie
        """
        value = max(-1.0, min(1.0, value))
        us = self.CENTER_US + value * (self.MAX_RIGHT_US - self.CENTER_US)
        self.pwm.ChangeDutyCycle(self._us_to_duty(int(us)))
```

---

## GPIO Pinout

### Raspberry Pi 5

| Functie | GPIO Pin | Fysieke pin | Opmerking |
|---|---|---|---|
| ESC PWM | GPIO 12 | Pin 32 | Hardware PWM (PWM0) |
| Servo PWM | GPIO 13 | Pin 33 | Hardware PWM (PWM1) |
| Ultrasoon TRIG voor | GPIO 17 | Pin 11 | Output |
| Ultrasoon ECHO voor | GPIO 27 | Pin 13 | Input (3.3V max!) |
| Ultrasoon TRIG achter | GPIO 22 | Pin 15 | Output |
| Ultrasoon ECHO achter | GPIO 23 | Pin 16 | Input |
| Ultrasoon TRIG links | GPIO 24 | Pin 18 | Output |
| Ultrasoon ECHO links | GPIO 25 | Pin 22 | Input |
| Ultrasoon TRIG rechts | GPIO 5  | Pin 29 | Output |
| Ultrasoon ECHO rechts | GPIO 6  | Pin 31 | Input |
| IMU I2C SDA | GPIO 2  | Pin 3  | I2C1 SDA |
| IMU I2C SCL | GPIO 3  | Pin 5  | I2C1 SCL |
| GPS UART TX→RX | GPIO 15 | Pin 22 | UART0 RX ← GPS TX |
| GPS UART RX→TX | GPIO 14 | Pin 8  | UART0 TX → GPS RX |

> **Let op HC-SR04 + RPi 5**: HC-SR04 geeft 5V op ECHO pin. De RPi 5 GPIO is 3.3V!
> Gebruik een spanningsdeler (1kΩ + 2kΩ) of een logica level shifter.

### Jetson Orin Nano

| Functie | Pin | Opmerking |
|---|---|---|
| ESC PWM | Pin 32 (PWM2) | Jetson GPIO hardware PWM |
| Servo PWM | Pin 33 (PWM3) | Jetson GPIO hardware PWM |
| Ultrasoon TRIG/ECHO | GPIO pins 15-40 | Zie Jetson pinout diagram |
| I2C (IMU) | Pin 3 (SDA), Pin 5 (SCL) | I2C bus 1 |
| UART (GPS) | Pin 8 (TX), Pin 10 (RX) | UART1 |

---

## Snelheidsbegrenzing

Voor veilig testen zijn er softwarematige begrenzingen in `vehicle_node`:

```python
# params.yaml
vehicle:
  max_linear_speed: 0.5    # m/s tijdens autonoom (≈ 1.8 km/h rustig)
  max_angular_speed: 1.0   # rad/s voor sturen
  test_mode_speed: 0.2     # m/s tijdens eerste tests

# Oplopend vrijgeven via parameter:
# ros2 param set /vehicle_node max_linear_speed 1.0
```

### Werkelijke snelheden Arrma Granite 3S BLX

| Instelling | Werkelijke snelheid |
|---|---|
| linear.x = 0.1 | ~2 km/h (stapvoets) |
| linear.x = 0.3 | ~8 km/h (rustig) |
| linear.x = 0.5 | ~15 km/h (normaal autonoom) |
| linear.x = 1.0 | ~40+ km/h (vol gas, RC modus) |

---

## Vehicle Node implementatie

```python
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool

class VehicleNode(Node):
    def __init__(self):
        super().__init__('vehicle_node')

        # Parameters
        self.max_linear  = self.declare_parameter('max_linear_speed', 0.5).value
        self.max_angular = self.declare_parameter('max_angular_speed', 1.0).value

        # ESC + Servo
        self.esc   = ESCController(gpio_pin=12)
        self.servo = ServoController(gpio_pin=13)

        # Subscriptions
        self.create_subscription(Twist, '/vehicle/cmd_vel',   self.cmd_cb, 10)
        self.create_subscription(Bool,  '/vehicle/emergency_stop', self.stop_cb, 10)

        # Watchdog: stop als geen commando ontvangen voor 0.5s
        self.last_cmd_time = self.get_clock().now()
        self.create_timer(0.1, self.watchdog)

    def cmd_cb(self, msg: Twist):
        self.last_cmd_time = self.get_clock().now()
        throttle = msg.linear.x  / self.max_linear
        steering = msg.angular.z / self.max_angular
        self.esc.set_throttle(throttle)
        self.servo.set_steering(steering)

    def stop_cb(self, msg: Bool):
        if msg.data:
            self.esc.set_throttle(0.0)
            self.servo.set_steering(0.0)

    def watchdog(self):
        elapsed = (self.get_clock().now() - self.last_cmd_time).nanoseconds / 1e9
        if elapsed > 0.5:
            self.esc.set_throttle(0.0)  # Veilig stoppen
```

---

## Kalibratie

### ESC kalibratie (eenmalig bij eerste gebruik)

```bash
# Kalibreer de ESC van de Arrma
# 1. Auto uit, zet ESC in kalibratie modus (houd knop ingedrukt)
# 2. Geef vol gas signaal (2000µs)
# 3. Geef neutraal signaal (1500µs)
# 4. Geef vol achteruit (1000µs)
# 5. ESC bevestigt met piepjes

ros2 run rc_vehicle calibrate_esc
```

### Servo trimmen

```bash
# Pas servo center aan zodat auto rechtdoor rijdt
ros2 param set /vehicle_node servo_center_us 1480   # Voorbeeld trim
```
