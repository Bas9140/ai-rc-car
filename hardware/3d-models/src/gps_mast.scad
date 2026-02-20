// ============================================================
// gps_mast.scad
// GPS antenne mast voor Holybro M8N (puck stijl)
//
// Houdt de GPS puck hoog boven de elektronica (minimaal 5cm
// afstand van metalen onderdelen voor goede ontvangst).
// Monteert op de electronics_tray via M3 schroef.
//
// PRINT SETTINGS:
//   Material:  PETG
//   Layer:     0.2mm
//   Infill:    60%  (stevige mast)
//   Supports:  Niet nodig
//
// HARDWARE:
//   1× M3 × 12mm schroef  (mast bevestiging aan tray)
//   1× M3 moer of brass insert
// ============================================================

use <hardware_profiles.scad>

// ── Parameters ───────────────────────────────────────────────

MAST_H       = 85;     // Mast hoogte (mm) – GPS boven elektronica
MAST_OD      = 14;     // Buitendiameter mast
MAST_ID      =  7;     // Binnendiameter (holle kern = kabel doorvoer)

BASE_D       = 28;     // Diameter voet
BASE_H       = 10;     // Hoogte voet

TOP_D        = GPS_PUCK_D + 4;   // Diameter top ring
TOP_H        =  6;                // Hoogte top ring

// ── Voet ─────────────────────────────────────────────────────

module mast_base() {
    difference() {
        // Voet cilinder
        cylinder(d=BASE_D, h=BASE_H, $fn=FN_CYL);

        // M3 montageschroef (van onderen)
        translate([0, 0, -0.5])
            cylinder(d=INS_M3_OD + TOLERANCE, h=BASE_H - 2, $fn=FN_CYL);

        // Kabeluitgang zijkant (onderkant mast)
        translate([-GPS_CABLE_D/2, -BASE_D/2 - 0.5, BASE_H/2 - GPS_CABLE_D/2])
            cube([GPS_CABLE_D, BASE_D/2 + 1, GPS_CABLE_D]);
    }
}

// ── Mast buis ─────────────────────────────────────────────────

module mast_tube() {
    difference() {
        cylinder(d=MAST_OD, h=MAST_H, $fn=FN_CYL);
        // Holle kern voor kabel
        translate([0, 0, -0.5])
            cylinder(d=MAST_ID, h=MAST_H + 1, $fn=FN_CYL);
    }
}

// ── Top: GPS puck houder ──────────────────────────────────────

module gps_top() {
    difference() {
        union() {
            // Buitenring
            cylinder(d=TOP_D, h=TOP_H, $fn=FN_CYL);
            // Kleine lip om puck op te laten rusten
            translate([0, 0, TOP_H - 2])
                cylinder(d=GPS_PUCK_D - 2, h=2, $fn=FN_CYL);
        }

        // Puck uitsparing
        translate([0, 0, 2])
            cylinder(d=GPS_PUCK_D + TOLERANCE, h=TOP_H, $fn=FN_CYL);

        // Kabelgat omhoog door top
        translate([0, 0, -0.5])
            cylinder(d=MAST_ID, h=TOP_H + 1, $fn=FN_CYL);

        // Kabeluitgang zijkant (bovenop mast, voor GPS kabel)
        translate([-GPS_CABLE_D/2, -TOP_D/2 - 0.5, 1])
            cube([GPS_CABLE_D, TOP_D/2 + 1, GPS_CABLE_D]);
    }
}

// ── Versteviging (ribben op mast) ────────────────────────────

module ribs() {
    for (a = [0, 90, 180, 270]) {
        rotate([0, 0, a])
            translate([MAST_OD/2 - 0.5, -1.5, BASE_H])
                cube([2.5, 3, MAST_H * 0.4]);
    }
}

// ── Complete mast ─────────────────────────────────────────────

module full_mast() {
    mast_base();
    translate([0, 0, BASE_H])
        mast_tube();
    ribs();
    translate([0, 0, BASE_H + MAST_H])
        gps_top();
}

full_mast();
