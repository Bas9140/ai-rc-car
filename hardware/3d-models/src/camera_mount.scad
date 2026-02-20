// ============================================================
// camera_mount.scad
// Luxonis OAK-D Lite camera mount voor de Arrma Granite
//
// Schuift in de T-slot rail van de electronics_tray.
// Verstelbare tilt: 0° – 15° omhoog (betere zichthoek op de weg).
// Beschermt de camera onderkant en zijkanten.
//
// PRINT SETTINGS:
//   Material:  PETG
//   Layer:     0.2mm
//   Infill:    50%
//   Supports:  Minimaal (alleen voor tilt bracket overhang)
//
// HARDWARE:
//   2× M3 × 12mm schroef + M3 moer  (camera klem)
//   1× M3 × 8mm  schroef            (rail vergrendeling)
//   1× M6 × 10mm schroef            (1/4" tripod adapter OAK-D)
// ============================================================

use <hardware_profiles.scad>

// ── Parameters ───────────────────────────────────────────────

TILT_DEG     =  8;     // Camera tilt naar boven (graden)
ARM_LENGTH   = 40;     // Afstand camera tot tray rand
ARM_W        = 24;     // Breedte van de arm
ARM_H        = 30;     // Hoogte van de arm (camera hoogte boven tray)

// Camera klem afmetingen (omhult de OAK-D Lite)
CLAMP_EXTRA  =  1.5;   // Speling rondom de OAK-D
CLAMP_WALL   =  3.5;   // Wanddikte van de klem

// Rail slider afmetingen (moet passen in camera_rail() van tray)
SLIDER_W     = 28;
SLIDER_H     =  8;
SLIDER_D     = 10;

// ── Rail slider ───────────────────────────────────────────────

module rail_slider() {
    // Past in de T-slot rail van de tray
    difference() {
        cube([SLIDER_W, SLIDER_D, SLIDER_H]);

        // M3 klemschroef gat (midden)
        translate([SLIDER_W/2, SLIDER_D/2, -0.5])
            cylinder(d=M3_D, h=SLIDER_H+1, $fn=FN_CYL);

        // T-slot profiel (afgeronde onderkant schuift in rail)
        translate([3, -0.5, 0])
            cube([SLIDER_W - 6, SLIDER_D * 0.5 + 1, 3]);
    }
}

// ── Arm ──────────────────────────────────────────────────────

module arm() {
    // Verticale arm van slider naar camera
    hull() {
        // Basis bij slider
        translate([0, 0, 0])
            cube([ARM_W, SLIDER_D, WALL]);
        // Top bij camera
        translate([0, ARM_LENGTH - WALL, ARM_H])
            cube([ARM_W, WALL, WALL]);
    }
}

// ── Camera klem ───────────────────────────────────────────────

// Twee-delige klem: achterplaat + frontplaat (2 M3 schroeven)
// De OAK-D Lite wordt geklemd: geen gaten in de camera zelf.

OAK_CLAMP_L = OAK_L + 2*CLAMP_EXTRA;
OAK_CLAMP_H = OAK_H + 2*CLAMP_EXTRA;
OAK_CLAMP_D = OAK_D + 2*CLAMP_EXTRA;

module camera_clamp_back() {
    // Achterplaat – verbindt met de arm
    difference() {
        union() {
            // Camera pocket (half diepte)
            cube([OAK_CLAMP_L + 2*CLAMP_WALL,
                  CLAMP_WALL + OAK_CLAMP_D/2,
                  OAK_CLAMP_H + 2*CLAMP_WALL]);

            // Arm verbinding rib
            translate([(OAK_CLAMP_L + 2*CLAMP_WALL - ARM_W)/2, 0, 0])
                cube([ARM_W, CLAMP_WALL + 8, OAK_CLAMP_H + 2*CLAMP_WALL]);
        }

        // Camera pocket uitsparing
        translate([CLAMP_WALL, CLAMP_WALL, CLAMP_WALL])
            cube([OAK_CLAMP_L, OAK_CLAMP_D/2 + 1, OAK_CLAMP_H]);

        // USB-C kabelgat (rechts)
        translate([OAK_CLAMP_L + 2*CLAMP_WALL - CLAMP_WALL - 0.5,
                   CLAMP_WALL,
                   CLAMP_WALL + (OAK_CLAMP_H - 12)/2])
            cube([CLAMP_WALL + 1, OAK_CLAMP_D/2 + 1, 12]);

        // M3 klemschroef gaten (boven en onder)
        for (z = [CLAMP_WALL + 5, OAK_CLAMP_H + CLAMP_WALL - 5]) {
            translate([-0.5, CLAMP_WALL + OAK_CLAMP_D/4, z])
                rotate([0, 90, 0])
                    cylinder(d=M3_D, h=OAK_CLAMP_L + 2*CLAMP_WALL + 1, $fn=FN_CYL);
        }

        // 1/4" (M6) tripod schroefgat boven (voor optionele extra bevestiging)
        translate([OAK_CLAMP_L/2 + CLAMP_WALL,
                   -0.5,
                   OAK_CLAMP_H/2 + CLAMP_WALL])
            rotate([-90, 0, 0])
                cylinder(d=M6_D, h=CLAMP_WALL + 1, $fn=FN_CYL);
    }
}

module camera_clamp_front() {
    // Frontplaat – sluit de klem
    difference() {
        cube([OAK_CLAMP_L + 2*CLAMP_WALL,
              CLAMP_WALL + OAK_CLAMP_D/2,
              OAK_CLAMP_H + 2*CLAMP_WALL]);

        // Camera pocket uitsparing
        translate([CLAMP_WALL, 0, CLAMP_WALL])
            cube([OAK_CLAMP_L, OAK_CLAMP_D/2, OAK_CLAMP_H]);

        // Lens openingen (3 stuks: kleur + 2× stereo IR)
        for (x = [(OAK_CLAMP_L + 2*CLAMP_WALL)/2 - OAK_BASELINE/2,
                  (OAK_CLAMP_L + 2*CLAMP_WALL)/2,
                  (OAK_CLAMP_L + 2*CLAMP_WALL)/2 + OAK_BASELINE/2]) {
            translate([x, -0.5, OAK_CLAMP_H/2 + CLAMP_WALL])
                rotate([-90, 0, 0])
                    cylinder(d=10, h=CLAMP_WALL + 1, $fn=FN_CYL);
        }

        // M3 klemschroef gaten (boven en onder) – doorgaand
        for (z = [CLAMP_WALL + 5, OAK_CLAMP_H + CLAMP_WALL - 5]) {
            translate([-0.5, CLAMP_WALL + OAK_CLAMP_D/4, z])
                rotate([0, 90, 0])
                    cylinder(d=M3_D, h=OAK_CLAMP_L + 2*CLAMP_WALL + 1, $fn=FN_CYL);
        }
    }
}

// ── Complete camera mount assemblage ─────────────────────────

module camera_mount_assembly() {
    // Slider (onderaan)
    rail_slider();

    // Arm (omhoog, met tilt)
    translate([( SLIDER_W - ARM_W) / 2, 0, SLIDER_H])
        arm();

    // Camera klem achterplaat (bovenop arm, gekanteld)
    translate([(SLIDER_W - OAK_CLAMP_L - 2*CLAMP_WALL)/2,
               ARM_LENGTH,
               SLIDER_H + ARM_H])
        rotate([TILT_DEG, 0, 0])
            camera_clamp_back();
}

// ── Print oriëntatie ─────────────────────────────────────────
// De klem achterplaat en frontplaat apart printen:

// Optie 1: alles in één (zonder tilt voor betere printbaarheid)
camera_mount_assembly();

// Optie 2: onderdelen apart voor optimale printoriëntatie
// camera_clamp_back();
// translate([OAK_CLAMP_L + 2*CLAMP_WALL + 10, 0, 0])
//     camera_clamp_front();
