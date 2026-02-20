// ============================================================
// electronics_tray.scad
// Main electronics mounting tray for Arrma Granite 4x4 V3
//
// Mounts via body post clips (4 corners).
// Holds: Raspberry Pi 5 OR Jetson Orin Nano
//        FS-BS6 receiver (rear)
//        MPU-6050 IMU
//        Powerbank / LiPo voeding (onderaan)
//
// PRINT SETTINGS:
//   Material:  PETG (outdoor) or ASA (best UV resistance)
//   Layer:     0.2mm
//   Infill:    40%
//   Perimeters: 4
//   Supports:  Geen nodig (ontwerp is support-vrij)
//
// HARDWARE NEEDED:
//   4× M2.5 × 8mm screws + M2.5 brass inserts  (RPi5 mounting)
//   4× M3  × 8mm screws + M3  brass inserts     (body post clips)
//   4× M3  × 10mm screws                        (clip retention)
// ============================================================

use <hardware_profiles.scad>

// ── Parameters (pas aan als nodig) ───────────────────────────

TRAY_L       = 210;   // Tray lengte (voor-achter)
TRAY_W       = 135;   // Tray breedte (links-rechts)
TRAY_WALL    = WALL;
TRAY_FLOOR   = FLOOR;
TRAY_H       =  32;   // Interne hoogte (ruimte voor elektronica)

// Brain keuze: "rpi5" of "jetson"
BRAIN        = "rpi5";

// Tilt camera mount zijde (voor = positieve Y richting)
CAMERA_SIDE  = "front";

// Body post clip positie (meting van midden tray)
CLIP_INSET_X =  18;   // mm van rand naar clip hart (langs lengte)
CLIP_INSET_Y =  12;   // mm van rand naar clip hart (langs breedte)

// ── Hoofd geometrie ──────────────────────────────────────────

module tray_body() {
    difference() {
        // Buitenkant
        rbox([TRAY_L, TRAY_W, TRAY_H + TRAY_FLOOR], r=3);

        // Uitholling (binnenkant)
        translate([TRAY_WALL, TRAY_WALL, TRAY_FLOOR])
            cube([TRAY_L - 2*TRAY_WALL,
                  TRAY_W - 2*TRAY_WALL,
                  TRAY_H + 1]);

        // Kabelgat onderzijde (voor USB-C powerbank kabel)
        translate([TRAY_L/2 - 8, -1, TRAY_FLOOR + 5])
            cube([16, TRAY_WALL + 2, 10]);

        // Ventilatie sleuven bovenkant
        for (i = [0:4]) {
            translate([30 + i*30, TRAY_W/2 - 20, TRAY_H + TRAY_FLOOR - 1])
                cube([12, 40, TRAY_FLOOR + 2]);
        }

        // Kabelgeleiding gaten zijkant (linkerkant)
        for (z = [10, 22]) {
            translate([-1, TRAY_W*0.25, z])
                rotate([0, 90, 0])
                    cylinder(d=8, h=TRAY_WALL+2, $fn=FN_CYL);
            translate([-1, TRAY_W*0.75, z])
                rotate([0, 90, 0])
                    cylinder(d=8, h=TRAY_WALL+2, $fn=FN_CYL);
        }

        // Body post gaten in bodem
        _body_post_holes();
    }
}

// ── Body post clips ──────────────────────────────────────────

// Clip: grijpt om de body post, vergrendelt met M3 schroef
module body_post_clip(post_d=BODY_POST_DIAMETER) {
    clip_od  = post_d + 2*TRAY_WALL;
    clip_h   = 18;
    gap      = post_d * 0.4;   // opening breedte

    difference() {
        cylinder(d=clip_od, h=clip_h, $fn=FN_CYL);

        // Post gat (+ tolerantie)
        cylinder(d=post_d + TOLERANCE, h=clip_h+1, $fn=FN_CYL);

        // Insteek opening
        translate([-gap/2, 0, -0.5])
            cube([gap, clip_od/2 + 1, clip_h + 1]);

        // M3 klemschroef dwars door clip
        translate([0, clip_od/2, clip_h/2])
            rotate([90, 0, 0])
                cylinder(d=M3_D, h=clip_od+1, $fn=FN_CYL);
    }
}

module _body_post_holes() {
    // Gaten in de bodem voor de clips (4 hoeken)
    clip_od = BODY_POST_DIAMETER + 2*TRAY_WALL;
    positions = [
        [CLIP_INSET_X,          CLIP_INSET_Y],
        [TRAY_L - CLIP_INSET_X, CLIP_INSET_Y],
        [CLIP_INSET_X,          TRAY_W - CLIP_INSET_Y],
        [TRAY_L - CLIP_INSET_X, TRAY_W - CLIP_INSET_Y],
    ];
    for (p = positions) {
        translate([p[0], p[1], -0.5])
            cylinder(d=clip_od + 1, h=TRAY_FLOOR+1, $fn=FN_CYL);
    }
}

// ── Brain standoffs ──────────────────────────────────────────

module brain_standoffs() {
    if (BRAIN == "rpi5") {
        _rpi5_standoffs();
    } else {
        _jetson_standoffs();
    }
}

module _rpi5_standoffs() {
    // RPi5 gecentreerd op de tray, iets naar achter
    ox = (TRAY_L - RPI_L) / 2;
    oy = (TRAY_W - RPI_W) / 2;

    positions = [
        [ox + RPI_HOLE_OX,            oy + RPI_HOLE_OY],
        [ox + RPI_HOLE_OX + RPI_HOLE_L, oy + RPI_HOLE_OY],
        [ox + RPI_HOLE_OX,            oy + RPI_HOLE_OY + RPI_HOLE_W],
        [ox + RPI_HOLE_OX + RPI_HOLE_L, oy + RPI_HOLE_OY + RPI_HOLE_W],
    ];
    for (p = positions) {
        translate([p[0], p[1], TRAY_FLOOR])
            standoff(h=RPI_STANDOFF_H, od=6, insert_d=INS_M2_OD, insert_depth=5);
    }
}

module _jetson_standoffs() {
    ox = (TRAY_L - JETSON_L) / 2;
    oy = (TRAY_W - JETSON_W) / 2;

    positions = [
        [ox + (JETSON_L - JETSON_HOLE_L)/2,              oy + (JETSON_W - JETSON_HOLE_W)/2],
        [ox + (JETSON_L - JETSON_HOLE_L)/2 + JETSON_HOLE_L, oy + (JETSON_W - JETSON_HOLE_W)/2],
        [ox + (JETSON_L - JETSON_HOLE_L)/2,              oy + (JETSON_W - JETSON_HOLE_W)/2 + JETSON_HOLE_W],
        [ox + (JETSON_L - JETSON_HOLE_L)/2 + JETSON_HOLE_L, oy + (JETSON_W - JETSON_HOLE_W)/2 + JETSON_HOLE_W],
    ];
    for (p = positions) {
        translate([p[0], p[1], TRAY_FLOOR])
            standoff(h=JETSON_STANDOFF_H, od=7, insert_d=INS_M3_OD, insert_depth=6);
    }
}

// ── Receiver mount (achter) ───────────────────────────────────

module receiver_pocket() {
    // Verzonken pocket voor FS-BS6 aan achterkant tray
    rx_x = TRAY_L - TRAY_WALL - RX_L - 5;
    rx_y = (TRAY_W - RX_W) / 2;
    rx_z = TRAY_FLOOR;

    translate([rx_x, rx_y, rx_z]) {
        // Pocket
        cube([RX_L + TOLERANCE, RX_W + TOLERANCE, RX_H]);

        // Kabelgat achter
        translate([RX_L/2 - 6, -2, 0])
            cube([12, TRAY_WALL + 4, 8]);
    }
}

// ── Kabel tie railing ────────────────────────────────────────

module cable_rails() {
    // Kleine lusvormige pinnen voor kabelbinders
    for (x = [40, 100, 160]) {
        for (y = [TRAY_WALL + 3, TRAY_W - TRAY_WALL - 3]) {
            translate([x, y, TRAY_FLOOR + TRAY_H - 6]) {
                difference() {
                    cylinder(d=6, h=8, $fn=FN_CYL);
                    cylinder(d=3.5, h=9, $fn=FN_CYL);
                    translate([-2, -4, 3])
                        cube([4, 8, 6]);
                }
            }
        }
    }
}

// ── Camera mount adapter rail (voorkant) ─────────────────────

module camera_rail() {
    // T-slot rail aan de voorkant voor camera mount
    // Camera mount schuift hier in en wordt vastgezet met M3 schroef
    rail_w = 30;
    rail_h =  8;
    rail_d =  6;

    translate([(TRAY_L - rail_w)/2, 0, TRAY_FLOOR + TRAY_H - rail_h]) {
        difference() {
            cube([rail_w, TRAY_WALL + rail_d, rail_h]);
            // T-slot opening
            translate([5, -0.5, 2])
                cube([rail_w - 10, TRAY_WALL + rail_d + 1, rail_h]);
            // T-slot kop (bredere opening)
            translate([3, TRAY_WALL, 4])
                cube([rail_w - 6, rail_d + 1, rail_h]);
            // M3 klemschroef
            translate([rail_w/2, TRAY_WALL + rail_d/2, -0.5])
                cylinder(d=M3_D, h=rail_h + 1, $fn=FN_CYL);
        }
    }
}

// ── GPS mast mount (rechter achterkant) ──────────────────────

module gps_mount_boss() {
    // Cilinder met M3 insert voor GPS mast bevestiging
    translate([TRAY_L - 25, TRAY_W - 25, TRAY_FLOOR])
        difference() {
            cylinder(d=12, h=8, $fn=FN_CYL);
            cylinder(d=INS_M3_OD + TOLERANCE, h=7, $fn=FN_CYL);
        }
}

// ── Assemblage ───────────────────────────────────────────────

module full_tray() {
    tray_body();
    brain_standoffs();
    cable_rails();
    camera_rail();
    gps_mount_boss();

    // Verwijder receiver pocket uit het geheel
    difference() {
        union() {}
        receiver_pocket();
    }
}

// Clips apart printen (4 stuks)
module print_clips() {
    for (i = [0:3]) {
        translate([i * (BODY_POST_DIAMETER + 2*TRAY_WALL + 5), 0, 0])
            body_post_clip();
    }
}

// ── Render ───────────────────────────────────────────────────
// Uncomment wat je wilt renderen/exporteren:

full_tray();                    // Hoofdtray
//translate([0, -50, 0]) print_clips();   // 4× clip apart
