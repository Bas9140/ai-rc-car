// ============================================================
// hardware_profiles.scad
// Central library of all hardware dimensions.
// Edit this file if your components differ slightly.
// Include with: use <hardware_profiles.scad>
// ============================================================

// ── Print settings ───────────────────────────────────────────
WALL       = 3.0;   // Wall thickness (mm) – 3mm for PETG strength
FLOOR      = 3.0;   // Floor/ceiling thickness
TOLERANCE  = 0.3;   // Fit tolerance for holes and slots
FN_CYL     = 64;    // Cylinder smoothness ($fn)

// ── Arrma Granite 4x4 V3 (1:10) ─────────────────────────────
// Overall
CHASSIS_LENGTH      = 476;  // mm  (bumper to bumper)
CHASSIS_WIDTH       = 342;  // mm  (tread width)
CHASSIS_HEIGHT      = 206;  // mm  (ground to top of body)
CHASSIS_CLEARANCE   =  47;  // mm  (ground clearance)

// Inner chassis plate (aluminium frame between wheels)
INNER_WIDTH         =  95;  // mm  (usable inner width)

// Body posts (standard Arrma 1:10)
BODY_POST_DIAMETER  =  17;  // mm
BODY_POST_WALL      =   2;  // mm  (post wall thickness for clip grip)
BODY_POST_CLIP_H    =   8;  // mm  (height of body clip groove)

// Body post positions relative to chassis centre (x=length, y=width)
// Measured from centre of chassis, approximate – verify when you have the car!
BP_FRONT_X  =  145;  // mm  front posts, distance from centre forward
BP_REAR_X   = -145;  // mm  rear posts, distance from centre backward
BP_Y        =  105;  // mm  posts, half-width between left and right

// ── Raspberry Pi 5 ───────────────────────────────────────────
RPI_L       = 85;    // PCB length
RPI_W       = 56;    // PCB width
RPI_H       =  1.4; // PCB thickness
RPI_HOLE_L  = 58;    // Mounting hole spacing along length
RPI_HOLE_W  = 49;    // Mounting hole spacing along width
RPI_HOLE_D  =  2.7; // M2.5 clearance hole diameter
RPI_HOLE_OX = (RPI_L - RPI_HOLE_L) / 2;  // Hole offset from edge (x)
RPI_HOLE_OY = (RPI_W - RPI_HOLE_W) / 2;  // Hole offset from edge (y)
RPI_STANDOFF_H = 5;  // Height of PCB standoff

// ── NVIDIA Jetson Orin Nano (Developer Kit carrier board) ────
JETSON_L    = 100;
JETSON_W    =  79;
JETSON_H    =   1.6;
JETSON_HOLE_L = 86;
JETSON_HOLE_W = 58;
JETSON_HOLE_D =  3.2;  // M3 clearance
JETSON_STANDOFF_H = 5;

// ── Luxonis OAK-D Lite ───────────────────────────────────────
OAK_L       = 91.0;  // Width (long axis, along stereo baseline)
OAK_H       = 28.0;  // Height
OAK_D       = 17.5;  // Depth
OAK_BASELINE = 75.0; // Stereo camera baseline
// 1/4"-20 tripod mount: bottom centre
OAK_MOUNT_X = OAK_L / 2;
OAK_MOUNT_Y = OAK_D / 2;
OAK_MOUNT_D =  6.4;  // 1/4"-20 thread → M6 clearance hole

// ── Holybro M8N GPS ──────────────────────────────────────────
GPS_PUCK_D  = 38.0;  // Puck diameter
GPS_PUCK_H  =  7.5;  // Puck height
GPS_CABLE_D =  4.0;  // Cable diameter

// ── FlySky FS-BS6 Receiver ───────────────────────────────────
RX_L        = 43.0;
RX_W        = 23.0;
RX_H        = 14.0;
RX_HOLE_D   =  3.2;  // M3 clearance
RX_HOLE_INSET = 5;   // Hole inset from edge

// ── MPU-6050 GY-521 IMU ──────────────────────────────────────
IMU_L       = 21.0;
IMU_W       = 16.0;
IMU_H       =  1.2;

// ── General fastener sizes ───────────────────────────────────
M2_D        =  2.2;  // M2  clearance hole
M25_D       =  2.7;  // M2.5
M3_D        =  3.2;  // M3
M4_D        =  4.3;  // M4
M6_D        =  6.5;  // M6

M2_HEAD_D   =  4.0;
M3_HEAD_D   =  6.0;
M4_HEAD_D   =  8.0;

// Brass insert outer diameters (heat-set)
INS_M2_OD   =  3.5;
INS_M3_OD   =  4.7;
INS_M4_OD   =  6.3;

// ── Helper modules ───────────────────────────────────────────

// Rounded box
module rbox(size, r=2) {
    x = size[0]; y = size[1]; z = size[2];
    hull() {
        for (xi = [r, x-r]) for (yi = [r, y-r]) {
            translate([xi, yi, 0]) cylinder(h=z, r=r, $fn=FN_CYL);
        }
    }
}

// Countersunk screw hole (from top)
module csk_hole(d, head_d, depth, head_depth=2) {
    cylinder(d=d, h=depth, $fn=FN_CYL);
    translate([0, 0, depth - head_depth])
        cylinder(d1=d, d2=head_d, h=head_depth, $fn=FN_CYL);
}

// PCB standoff pillar with insert hole
module standoff(h, od=6, insert_d=INS_M25_OD, insert_depth=5) {
    difference() {
        cylinder(h=h, d=od, $fn=FN_CYL);
        translate([0, 0, h - insert_depth])
            cylinder(h=insert_depth + 0.1, d=insert_d + TOLERANCE, $fn=FN_CYL);
    }
}

// Cable tie slot
module cable_tie_slot(w=3.5, t=1.5, l=10) {
    translate([-w/2, -l/2, 0])
        cube([w, l, t]);
}
