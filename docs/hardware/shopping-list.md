# Hardware Shopping List

Laatste update: 2026-02-20

> **Belangrijk**: De originele NVIDIA Jetson Nano 4GB is **End-of-Life** (EOL).
> Twee brain-opties uitgewerkt: aangeraden (Jetson Orin Nano Super) en budget (Raspberry Pi 5).

---

## Optie A – Aangeraden setup (~€995)

| # | Component | Model | Prijs | Winkel | Link |
|---|---|---|---|---|---|
| 1 | **Chassis** | ARRMA Granite 4x4 3S BLX V3 RTR | ~€300 | TopRC.nl | [toprc.nl](https://www.toprc.nl/arrma-granite-4x4-3s-blx-v3-groen.html) |
| 2 | **AI Brein** | NVIDIA Jetson Orin Nano Super Dev Kit | €274.95 | Antratek.nl | [antratek.nl](https://www.antratek.nl/nvidia-jetson-orin-nano-super-developer-kit) |
| 3 | **Dieptecamera** | Intel RealSense D435i | €224.00 | Beat-IT.nl | [beat-it.nl](https://www.beat-it.nl/intel-82635d435idk5p) |
| 4 | **GPS module** | Holybro M8N GPS (met kompas) | ~€48 | Holybro Store | [holybro.com](https://holybro.com/products/m8n-gps) |
| 5 | **IMU** | GY-521 MPU-6050 (accel + gyro) | €2.55 | Opencircuit | [opencircuit.shop](https://opencircuit.shop/product/6-dof-gyroscope-accelerometer-module-gy-521) |
| 6 | **Ultrasoon x4** | HC-SR04 (4 stuks) | €8.60 (4x €2.15) | Opencircuit | [opencircuit.shop](https://opencircuit.shop/product/hc-sr04-ultrasonic-distance-detection-module) |
| 7 | **MicroSD** | Samsung EVO Plus 128GB (U3, A2) | ~€18 | Bol.com | [bol.com zoeken](https://www.bol.com/nl/nl/s/?searchtext=samsung+evo+plus+128gb+microsd) |
| 8 | **LiPo rijden** | TRC 3S 5000mAh 50C EC5 | ~€55 | TopRC.nl | [toprc.nl](https://www.toprc.nl/trc-lipo-50c-3s-5000mah-ec5-stekker.html) |
| 9 | **LiPo Jetson** | 3S 3000mAh of USB-C powerbank 20Ah | ~€30 | Bol.com / TopRC | Apart bestellen |
| 10 | **UBEC** | Hobbywing 5V 5A UBEC (LiPo → 5V) | ~€10 | AliExpress / eBay | [aliexpress zoeken](https://www.aliexpress.com/w/wholesale-hobbywing-5v-5a-ubec.html) |
| 11 | **Bedrading** | Dupont jumper wires + servo verlengkabels | ~€10 | AliExpress | [aliexpress zoeken](https://www.aliexpress.com/w/wholesale-dupont-jumper-wires.html) |
| 12 | **Behuizing** | PETG/ASA filament + hardware | ~€15 | 3D printer | Eigen print |
| | | | **~€996** | | |

---

## Optie B – Budget setup (~€810)

Zelfde als optie A, maar met **Raspberry Pi 5 8GB** als brein (€90 vs €275).
Minder AI-rekenkracht, maar voldoende voor YOLO v8n (nano model) en ROS2.

| # | Component | Model | Prijs | Winkel | Link |
|---|---|---|---|---|---|
| 2 | **AI Brein** | Raspberry Pi 5 8GB | ~€90 | Kiwi Electronics | [kiwi-electronics.com](https://www.kiwi-electronics.com/en/raspberry-pi-5-8gb-11580) |
| | Overige componenten | Zelfde als Optie A | ~€720 | | |
| | | | **~€810** | | |

> Voor de Raspberry Pi 5 gebruik je een USB-C voeding (27W) i.p.v. UBEC → 5V.

---

## Gedetailleerde component beschrijvingen

### 1. Chassis – ARRMA Granite 4x4 3S BLX V3
- **Waarom**: Bewezen brushless 4WD platform, waterdichte elektronica, metalen aandrijving
- **Motor**: BLX3660 3200kV brushless + BLX80 ESC (al aanwezig in RTR versie)
- **Servo**: BLS-2 high-torque servo (al aanwezig)
- **Accuhouder**: Standaard EC5 connector, past TRC/Spektrum 3S
- **Alternatief**: [Arrma Granite 223S DSC 4x4 (2025 versie)](https://www.toemen.nl/en/product/arrma-1-10-granite-223s-dsc-4x4-brushless-monster-truck-rtr-gun-metal-versie-2025) bij Toemen

---

### 2a. AI Brein – NVIDIA Jetson Orin Nano Super Developer Kit
- **Waarom aangeraden**: 67 TOPS AI performance, ingebouwde GPU, ideaal voor YOLO real-time
- **CPU**: 6-core Arm Cortex-A78AE, **GPU**: 1024-core NVIDIA Ampere
- **RAM**: 8GB LPDDR5, **opslag**: NVMe SSD slot aanwezig
- **Voeding**: 19V DC (5.5/2.5mm jack) → aparte UBEC of 19V powerbank nodig
- **OS**: JetPack 6 (Ubuntu 22.04)
- **Leverancier NL**: [Antratek Electronics](https://www.antratek.nl/nvidia-jetson-orin-nano-super-developer-kit) – €274.95
- **Leverancier NL**: [Kiwi Electronics](https://www.kiwi-electronics.com/en/nvidia-jetson-orin-nano-super-developer-kit-11461)
- **Let op**: RS Online levert ook ([rs-online.com](https://nl.rs-online.com/web/p/processor-development-tools/2647384))

---

### 2b. AI Brein – Raspberry Pi 5 8GB (budget)
- **CPU**: 4-core Arm Cortex-A76 @ 2.4GHz, **GPU**: VideoCore VII (geen CUDA)
- **RAM**: 8GB LPDDR4X
- **Voeding**: USB-C 27W (5V 5A) – simpel via powerbank
- **Beperking**: Geen GPU → YOLO draait op CPU (~5-10fps), voldoende voor volg-modus
- **Oplossing**: Gebruik lichtgewicht YOLO v8n model
- **Leverancier NL**: [Kiwi Electronics](https://www.kiwi-electronics.com/en/raspberry-pi-5-8gb-11580) ~€90
- **Leverancier NL**: [Opencircuit](https://opencircuit.shop/product/raspberry-pi-5-8gb) ~€90

---

### 3. Dieptecamera – Intel RealSense D435i
- **Waarom**: Stereo dieptecamera + RGB + ingebouwde IMU (D435**i**)
- **Bereik**: 0.2m – 10m, **resolutie**: 1280x720 depth @ 30fps
- **Interface**: USB 3.0 (type-C)
- **Software**: Officiële ROS2 driver beschikbaar (`realsense2_camera` package)
- **NL kopen**: [Beat-IT.nl](https://www.beat-it.nl/intel-82635d435idk5p) – €224.00
- **NL kopen**: [MaxICT.nl](https://maxict.nl/intel-realsense-d435i-camera-zilver-p10141009.html)

---

### 4. GPS module – Holybro M8N
- **Waarom**: Bewezen kwaliteits-GPS voor drones/robots, inclusief kompas (HMC5883L), UART aansluiting
- **Nauwkeurigheid**: 1-2 meter CEP
- **Connector**: JST-GH 6-pin (past direct op Pixhawk/Jetson UART)
- **Kopen**: [Holybro Store](https://holybro.com/products/m8n-gps) – ~$51 (~€48 + verzending)
- **Alternatief goedkoop**: [GY-NEO6MV2 via AliExpress](https://www.aliexpress.com/w/wholesale-gy-neo6mv2-gps.html) ~€6 (minder nauwkeurig)

---

### 5. IMU – GY-521 MPU-6050
- **Waarom**: 6-assige IMU (3-as accel + 3-as gyro), I2C interface, breed ondersteund in ROS2
- **Let op**: De RealSense D435i heeft ook een ingebouwde IMU → MPU-6050 optioneel
- **Kopen**: [Opencircuit.shop](https://opencircuit.shop/product/6-dof-gyroscope-accelerometer-module-gy-521) – €2.55
- **Kopen**: [Hobbyelectronica.nl](https://www.hobbyelectronica.nl/en/product/mpu-6050/) – idem prijs

---

### 6. Ultrasoon sensoren – HC-SR04 (x4)
- **Waarom**: Goedkope dichtbij-detectie (2-400cm), voor/achter/links/rechts
- **Interface**: GPIO (trigger + echo pins)
- **Let op**: Werkt op 5V – levelshifter nodig voor 3.3V GPIO (bijv. Raspberry Pi 5)
- **Kopen**: [Opencircuit.shop](https://opencircuit.shop/product/hc-sr04-ultrasonic-distance-detection-module) – €2.15/stuk
- **Kopen**: [Tinytronics.nl](https://www.tinytronics.nl/en/sensors/distance/ultrasonic-sensor-hc-sr04)
- **Kopen**: [Kiwi Electronics](https://www.kiwi-electronics.com/en/ultrasonic-sensor-hc-sr04-2592)

---

### 7. MicroSD – Samsung EVO Plus 128GB
- **Waarom**: Snel (UHS-I U3, A2), betrouwbaar voor OS + logging
- **Kopen**: [Bol.com](https://www.bol.com/nl/nl/s/?searchtext=samsung+evo+plus+128gb+microsd) – ~€18
- **Let op Jetson Orin Nano**: Heeft NVMe M.2 slot → ook SSD optie mogelijk

---

### 8. LiPo accu voor rijden – 3S 5000mAh 50C
- **Waarom**: Past in Arrma Granite (EC5 aansluiting), voldoende capaciteit
- **Kopen**: [TopRC.nl TRC merk](https://www.toprc.nl/trc-lipo-50c-3s-5000mah-ec5-stekker.html) – ~€55
- **Alternatief**: [Gens Ace 5000mAh 3S bij Toemen](https://www.toemen.nl/en/onderdelen-toebehoren/accus-laders/accus-en-laders/lipo-3s-11-1v) – idem prijs
- **Let op**: Aparte LiPo lader nodig als je die nog niet hebt

---

### 9. Voeding AI Brein
- **Optie A (Jetson Orin Nano)**: Vereist 19V DC, 45W
  - Gebruik een DC-DC converter (LiPo 3S → 19V) OF aparte 19V powerbank
  - Aanbevolen: [Renogy E.POWER 20000mAh 60W](https://www.bol.com) ~€50
- **Optie B (Raspberry Pi 5)**: USB-C 27W (5V 5A)
  - Powerbank met 27W PD output: ~€25-35

---

### 10. UBEC – 5V 5A
- **Waarom**: Stabiele 5V voeding voor sensoren (GPS, IMU, ultrasoon) vanuit LiPo
- **Kopen**: [AliExpress Hobbywing 5A UBEC](https://www.aliexpress.com/w/wholesale-hobbywing-5v-5a-ubec.html) – ~€8
- **Let op**: Optioneel als je een powerbank gebruikt voor sensoren

---

## Budget totaaloverzicht

### Optie A (Jetson Orin Nano Super) – ~€996

| Categorie | Bedrag |
|---|---|
| Chassis (Arrma Granite 3S BLX V3) | ~€300 |
| AI Brein (Jetson Orin Nano Super) | €275 |
| Dieptecamera (RealSense D435i) | €224 |
| GPS (Holybro M8N) | €48 |
| IMU (MPU-6050) | €3 |
| Ultrasoon x4 (HC-SR04) | €9 |
| MicroSD 128GB | €18 |
| LiPo accu rijden (3S 5000mAh) | €55 |
| Voeding Jetson (powerbank 19V) | €50 |
| UBEC + bedrading | €20 |
| Behuizing (filament + hardware) | €15 |
| **Totaal** | **~€1017** |

> Besparen: gebruik een tweedehands Arrma chassis van Marktplaats (€100-150) → totaal ~€800

### Optie B (Raspberry Pi 5 8GB) – ~€830

| Categorie | Bedrag |
|---|---|
| Chassis + overige componenten | ~€740 |
| Raspberry Pi 5 8GB | €90 |
| **Totaal** | **~€830** |

---

## Aanbeveling

**Begin met Optie B (Raspberry Pi 5)** voor de eerste bouwfase en softwareontwikkeling.
Upgrade naar Jetson Orin Nano Super zodra je klaar bent voor zwaardere AI (real-time YOLO + diepte).

De Raspberry Pi 5 heeft voldoende kracht voor:
- ROS2 navigatie en sensordata
- Camera streaming
- YOLO v8n op CPU (~8fps) voor follow-me modus

De Jetson Orin Nano Super voegt toe:
- YOLO v8m/l op GPU (30+fps)
- Zwaardere diepte-verwerking
- Toekomstbestendig voor uitbreidingen

---

## Nog te regelen

- [ ] LiPo lader (als je die nog niet hebt) – bijv. [iCharger of Junsi](https://www.toprc.nl/laders/)
- [ ] RC zender + ontvanger (om manueel te kunnen rijden + noodstop)
  - Bestaande zender hergebruiken of FlySky FS-i6 (~€35) erbij
- [ ] 3D printer toegang voor behuizing (of uitbesteden aan [Treatstock](https://www.treatstock.com))
- [ ] Soldeerbout (voor voedingsbedrading)
