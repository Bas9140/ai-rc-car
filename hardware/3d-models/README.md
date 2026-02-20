# 3D Modellen – AI RC Car

Alle onderdelen zijn parametrisch in OpenSCAD geschreven.
Pas `hardware_profiles.scad` aan als jouw componenten iets afwijken in maat.

## Onderdelen

| Bestand | Onderdeel | Stuks | Printtijd | Gewicht |
|---|---|---|---|---|
| `electronics_tray.scad` | Elektronica tray | 1 | ~4u | ~85g |
| `electronics_tray.scad` (clips) | Body post clips | 4 | ~1u | ~15g |
| `camera_mount.scad` | OAK-D Lite camera mount | 1 | ~2u | ~30g |
| `gps_mast.scad` | GPS antenne mast | 1 | ~1u | ~20g |
| `receiver_mount.scad` | FS-BS6 ontvanger houder | 1 | ~1u | ~15g |
| `receiver_mount.scad` (deksel) | Ontvanger deksel | 1 | ~30m | ~5g |
| `receiver_mount.scad` (clips) | Antenneklem | 2 | ~15m | ~3g |

## Printinstellingen

| Parameter | Waarde | Reden |
|---|---|---|
| **Materiaal** | PETG | Weerbestendig, UV-bestendig, sterk |
| **Alternatief** | ASA | Nóg beter UV-bestendig, moeilijker te printen |
| **Laagdikte** | 0.2mm | Balans sterkte / snelheid |
| **Infill tray** | 40% gyroid | Schokabsorptie |
| **Infill mast** | 60% | Stevigheid |
| **Perimeters** | 4 | Buitenwand sterkte |
| **Support** | Niet nodig | Ontwerp is support-vrij |
| **Bed temp PETG** | 80°C | Goede hechting |
| **Nozzle temp** | 235°C | Standaard PETG |

## Benodigde hardware

### Electronics tray
- 4× M3 × 12mm + M3 moer (body post clips)
- 4× M2.5 × 8mm + M2.5 brass heat-set inserts (RPi5 mounting)
  of 4× M3 × 10mm + M3 inserts (Jetson Orin Nano)

### Camera mount
- 2× M3 × 12mm + M3 moer (camera klem)
- 1× M3 × 8mm (rail vergrendeling)

### GPS mast
- 1× M3 × 12mm (montage aan tray)
- 1× M3 brass heat-set insert

### Ontvanger houder
- 2× M3 × 8mm (montage aan tray)
- 2× M3 brass heat-set inserts (in tray)

## Assembly volgorde

1. **Brass inserts plaatsen** – verwarm met soldeerbout en druk in de gaten
2. **Body post clips monteren** – schuif over de 4 body posts van het Arrma chassis
3. **Tray plaatsen** – druk de tray over de clips, schroef vast met M3
4. **RPi5 / Jetson monteren** – M2.5 schroeven in de standoffs
5. **Camera mount** – schuif in de T-slot rail, stel tilt in, vastschroeven
6. **GPS mast** – schroef in de boss (rechts achter op de tray)
7. **Ontvanger** – leg in de pocket, deksel erop
8. **Bedrading** – gebruik de kabelbinders en railpinnen

## Aanpassen

Open `hardware_profiles.scad` om alle maten te wijzigen:

```openscad
// Pas hier aan als je Jetson gebruikt in plaats van RPi5:
BRAIN = "jetson";  // in electronics_tray.scad

// Pas tilt aan:
TILT_DEG = 10;    // in camera_mount.scad (0-15 graden)

// Pas mast hoogte aan:
MAST_H = 100;     // in gps_mast.scad
```

## BELANGRIJK: Maten verifiëren voor printen

**Meet de volgende maten op je echte Arrma Granite voordat je print:**

- [ ] Body post buitendiameter (nominaal 17mm)
- [ ] Body post hart-op-hart afstand voor-achter
- [ ] Body post hart-op-hart afstand links-rechts
- [ ] Beschikbare hoogte boven chassis (tot body onderkant)

Pas `CLIP_INSET_X` en `CLIP_INSET_Y` in `electronics_tray.scad` aan op basis van je meting.
