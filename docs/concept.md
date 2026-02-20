# Project Concept: AI RC Car

## Samenvatting

Een autonoom rijdende RC auto op schaal 1:10, aangedreven door een NVIDIA Jetson Nano en uitgerust met een Intel RealSense dieptecamera, GPS, IMU en ultrasoon sensoren. Het voertuig kan zelfstandig GPS-waypoints afleggen, obstakels vermijden en personen/objecten volgen via computer vision.

## Doelstellingen

1. **Autonoom navigeren** van punt A naar punt B via GPS waypoints
2. **Obstakels detecteren en vermijden** in real-time via dieptecamera en ultrasoon
3. **Persoon/object volgen** via YOLO object detectie en camera tracking
4. **Web dashboard** voor monitoring, bediening en het instellen van waypoints
5. **Modulair ontwerp** zodat functionaliteit stapsgewijs uitgebreid kan worden

## Gebruik

### Modus 1: Autonome GPS Navigatie
- Gebruiker stelt waypoints in via web dashboard (kaartinterface)
- Auto rijdt zelfstandig langs de waypoints
- Obstakels worden automatisch vermeden
- Status en live camerabeeld zichtbaar op dashboard

### Modus 2: Follow-Me
- Auto detecteert een persoon via YOLO op de RealSense camera
- Volgt op een instelbare afstand (bijv. 1.5 meter)
- Houdt de persoon gecentreerd in beeld
- Stopt automatisch bij obstakels

### Modus 3: Handmatig met AI-ondersteuning
- Gebruiker bestuurt via web dashboard of RC zender
- AI grijpt in als er een obstakel gedetecteerd wordt
- Modus voor testen en demonstratie

## Fasering

### Fase 1 - Hardware (weken 1-3)
- Chassis aanschaffen en controleren
- Jetson Nano monteren en OS installeren
- RealSense camera aansluiten en testen
- GPS en IMU aansluiten
- Ultrasoon sensoren bedraden
- Jetson Nano verbinden met ESC/servo via PWM

### Fase 2 - Basale rijdende software (weken 4-6)
- ROS2 installeren op Jetson Nano
- ROS2 node voor motorbesturing (ESC + servo)
- Joystick/keyboard besturing testen
- Sensordata inlezen (GPS, IMU, ultrasoon)
- Camera feed streamen naar dashboard

### Fase 3 - AI Perceptie (weken 7-10)
- Intel RealSense dieptedata verwerken
- YOLO object detectie implementeren
- Obstakel detectie en basisvermijding
- Persoon tracking implementeren

### Fase 4 - Navigatie (weken 11-14)
- GPS waypoint navigatie
- Path planning algoritme
- Integratie obstakelvermijding + navigatie
- Testen buiten op verharding

### Fase 5 - Dashboard & Afwerking (weken 15-18)
- Web dashboard bouwen
- Live camerastream
- Telemetrie weergave
- Waypoint interface op kaart
- 3D-geprinte behuizing voor elektronica

## Risico's en uitdagingen

| Risico | Impact | Oplossing |
|---|---|---|
| Jetson Nano stroombehoefte | Hoog | Aparte LiPo voor Jetson Nano |
| Waterbestendigheid elektronica | Hoog | 3D-geprinte behuizing + foam afdichting |
| GPS nauwkeurigheid | Middel | u-blox M8N (1-2m nauwkeurig) |
| Latency camera → rijden | Middel | Optimaliseren ROS2 pipeline |
| ROS2 leercurve | Laag | Goede documentatie + community |
