// ============================================================
// assembly.scad
// Volledige visualisatie van alle 3D onderdelen samen.
// Gebruik dit om de plaatsing te controleren voor het printen.
//
// Niet bedoeld voor printen – gebruik de losse bestanden.
// ============================================================

use <hardware_profiles.scad>
use <electronics_tray.scad>
use <camera_mount.scad>
use <gps_mast.scad>
use <receiver_mount.scad>

// Kleur per onderdeel (voor visualisatie)
TRAY_COLOR     = [0.2, 0.5, 0.9, 0.9];   // Blauw
CAMERA_COLOR   = [0.9, 0.4, 0.1, 0.9];   // Oranje
GPS_COLOR      = [0.2, 0.8, 0.2, 0.9];   // Groen
RX_COLOR       = [0.7, 0.2, 0.7, 0.9];   // Paars
HARDWARE_COLOR = [0.8, 0.7, 0.1, 1.0];   // Goud (hardware)

// ── Tray (centrum) ───────────────────────────────────────────
color(TRAY_COLOR)
    full_tray();

// ── Camera mount (voorkant, midden) ─────────────────────────
color(CAMERA_COLOR)
    translate([(210 - 28)/2, -10, 32 + 3])
        camera_mount_assembly();

// ── GPS mast (rechtse achterkant) ────────────────────────────
color(GPS_COLOR)
    translate([210 - 25, 135 - 25, 32 + 3])
        full_mast();

// ── Ontvanger (achterkant) ───────────────────────────────────
color(RX_COLOR)
    translate([210 - 10 - (RX_L + 2*1.0 + 2*2.5),
               (135 - (RX_W + 2*1.0 + 2*2.5))/2,
               32 + 3])
        receiver_box();

// ── Arrma Granite chassis silhouet (referentie, transparant) ─
%translate([-133, -20, -47])
    cube([CHASSIS_LENGTH, INNER_WIDTH, 10]);   // chassis plaat approximatie

// ── Info in console ───────────────────────────────────────────
echo("=== AI RC Car 3D Assembly ===");
echo(str("Tray: ", 210, " × ", 135, " × ", 32+3, " mm"));
echo(str("Camera tilt: ", 8, "°"));
echo(str("GPS mast hoogte: ", 85+10+6, " mm totaal"));
