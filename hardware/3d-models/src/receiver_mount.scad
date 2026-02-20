// ============================================================
// receiver_mount.scad
// FlySky FS-BS6 ontvanger houder
//
// Monteert de ontvanger aan de achterkant/zijkant van de tray.
// Antennekabels worden geleid naar buiten via sleuven.
// Beschermt de ontvanger tegen schokken (zachte montagepunten).
//
// PRINT SETTINGS:
//   Material:  PETG
//   Layer:     0.2mm
//   Infill:    40%
//   Supports:  Niet nodig
//
// HARDWARE:
//   2× M3 × 8mm schroef  (bevestiging aan tray)
//   2× M3 brass inserts  (in tray)
//   Dubbelzijdig tape of foam tape (extra trilling isolatie)
// ============================================================

use <hardware_profiles.scad>

// ── Parameters ───────────────────────────────────────────────

EXTRA        =  1.0;   // Speling rondom ontvanger
MOUNT_WALL   =  2.5;   // Wanddikte houder
LID_H        =  3.0;   // Deksel dikte

ANTENNA_D    =  2.5;   // Antennekabel diameter
NUM_ANTENNAS =  2;     // FS-BS6 heeft 2 antennes

// ── Ontvanger bak ────────────────────────────────────────────

BOX_L = RX_L + 2*EXTRA + 2*MOUNT_WALL;
BOX_W = RX_W + 2*EXTRA + 2*MOUNT_WALL;
BOX_H = RX_H + 2;

module receiver_box() {
    difference() {
        rbox([BOX_L, BOX_W, BOX_H], r=2);

        // Binnenruimte voor ontvanger
        translate([MOUNT_WALL, MOUNT_WALL, MOUNT_WALL])
            cube([RX_L + 2*EXTRA, RX_W + 2*EXTRA, BOX_H]);

        // Antennekabel sleuven (linkerkant)
        for (i = [0:NUM_ANTENNAS-1]) {
            ay = MOUNT_WALL + RX_W*0.25 + i * RX_W * 0.5;
            translate([-0.5, ay - ANTENNA_D/2, MOUNT_WALL + 3])
                cube([MOUNT_WALL + 1, ANTENNA_D, ANTENNA_D + 2]);
        }

        // UART kabelgat (achterkant)
        translate([BOX_L/2 - 6, BOX_W - MOUNT_WALL - 0.5, MOUNT_WALL])
            cube([12, MOUNT_WALL + 1, 6]);

        // Bevestigings schroefgaten onderkant (voor montage op tray)
        for (x = [RX_HOLE_INSET, BOX_L - RX_HOLE_INSET]) {
            translate([x, BOX_W/2, -0.5])
                cylinder(d=M3_D, h=MOUNT_WALL + 1, $fn=FN_CYL);
        }

        // Snap-fit lip groef (voor deksel)
        translate([1, 1, BOX_H - 1.5])
            cube([BOX_L - 2, BOX_W - 2, 2]);
    }
}

// ── Deksel ───────────────────────────────────────────────────

module receiver_lid() {
    difference() {
        rbox([BOX_L, BOX_W, LID_H], r=2);

        // Snap-fit lip
        translate([1.5, 1.5, -0.5])
            cube([BOX_L - 3, BOX_W - 3, LID_H]);

        // Ventilatie gaatjes
        for (x = [BOX_L*0.25, BOX_L*0.5, BOX_L*0.75]) {
            for (y = [BOX_W*0.3, BOX_W*0.7]) {
                translate([x, y, -0.5])
                    cylinder(d=3, h=LID_H+1, $fn=FN_CYL);
            }
        }
    }
}

// ── Antennegeleider ───────────────────────────────────────────
// Kleine klem om antennekabels langs de tray te leiden

module antenna_clip(cable_d=ANTENNA_D) {
    od = cable_d + 4;
    h  = 8;
    difference() {
        union() {
            cylinder(d=od, h=h, $fn=FN_CYL);
            translate([-od/2, 0, 0])
                cube([od, od/2 + 4, h]);
        }
        // Kabelgat
        cylinder(d=cable_d + TOLERANCE, h=h+1, $fn=FN_CYL);
        // Opening voor kabel
        translate([-cable_d/2, -1, -0.5])
            cube([cable_d, od, h+1]);
        // Montageschroef
        translate([0, od/2 + 1, h/2])
            rotate([90, 0, 0])
                cylinder(d=M3_D, h=od + 3, $fn=FN_CYL);
    }
}

// ── Render ────────────────────────────────────────────────────

receiver_box();

// Deksel apart naast de bak (voor printen)
translate([BOX_L + 10, 0, 0])
    receiver_lid();

// 2 antenneklemmen
translate([0, BOX_W + 15, 0])
    antenna_clip();
translate([15, BOX_W + 15, 0])
    antenna_clip();
