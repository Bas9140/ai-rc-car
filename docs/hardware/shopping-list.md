# Hardware Shopping List

Geschatte totaalprijs: **~€710**
Budget: €600 - €1000

## Kern componenten

| Component | Model | Prijs (est.) | Leverancier | Status | Notities |
|---|---|---|---|---|---|
| **Chassis** | Arrma Granite 4x4 Mega 1:10 BLX | ~€200 | Amain / HobbyKing | Gepland | BLX = brushless, 4WD, robuust voor buiten |
| **AI Brein** | NVIDIA Jetson Nano 4GB Developer Kit | ~€140 | Amazon / Alternate | Gepland | 4GB RAM, GPU voor AI inference |
| **Dieptecamera** | Intel RealSense D435i | ~€220 | Intel / Amazon | Gepland | Dieptedata + RGB, 30fps, USB3 |
| **GPS module** | u-blox M8N (met kompas) | ~€35 | AliExpress / Amazon | Gepland | 1-2m nauwkeurigheid, I2C/UART |
| **IMU** | GY-521 MPU-6050 | ~€10 | AliExpress | Gepland | Versnellingsmeter + gyroscoop, I2C |
| **Ultrasoon x4** | HC-SR04 | ~€15 | AliExpress | Gepland | Dichtbij obstakeldetectie, voor/achter/links/rechts |
| **MicroSD** | Samsung EVO 128GB (UHS-I) | ~€20 | Bol.com | Gepland | OS + data opslag Jetson Nano |

## Stroom & Bedrading

| Component | Model | Prijs (est.) | Notities |
|---|---|---|---|
| **LiPo accu extra** | 3S 5000mAh 50C | ~€50 | Voor rijden (chassis) |
| **LiPo accu Jetson** | 3S 3000mAh of powerbank 20000mAh | ~€30 | Aparte voeding Jetson Nano |
| **UBEC / Voltage regulator** | 5V 5A UBEC | ~€10 | LiPo → 5V voor Jetson/sensoren |
| **Servo verlengkabels + dupont** | Set | ~€10 | Bedrading |
| **PWM kabel ESC → Jetson** | Male-Female jumper wires | ~€5 | PWM signalen |

## Behuizing

| Component | Model | Prijs (est.) | Notities |
|---|---|---|---|
| **Behuizing** | 3D-geprinte bak (eigen ontwerp) | ~€15 filament | PETG of ASA (UV/weerbestendig) |
| **Velcro + schuimrubber** | Set | ~€10 | Montage en trillingsdemping |
| **Kabelbinders + management** | Set | ~€5 | |

## Totaaloverzicht

| Categorie | Bedrag |
|---|---|
| Kern componenten | ~€620 |
| Stroom & bedrading | ~€105 |
| Behuizing | ~€30 |
| **Totaal** | **~€755** |

> Budget buffer: ~€245 voor onverwachte kosten, extra accessoires of upgrades

## Mogelijke upgrades (later)

| Upgrade | Prijs | Voordeel |
|---|---|---|
| RTK GPS (u-blox F9P) | ~€200 | Centimeter nauwkeurigheid |
| RPLidar A1 | ~€100 | 360° lidar voor betere obstakelvermijding |
| NVIDIA Jetson Orin Nano | ~€350 | 4x meer AI rekenkracht |
| 4G/LTE module | ~€50 | Remote monitoring buiten WiFi bereik |
| Stereocamera (ZED 2) | ~€400 | Betere dieptedata dan RealSense |
