std_msgs/Header header

# Zone-gebaseerde obstakekkaart afgeleid van diepteframe (OAK-D Lite)
# Zones zijn horizontale strips van het camera gezichtsveld

# Zone status constanten
uint8 STATUS_CLEAR   = 0   # Vrij (> warn_dist_mm)
uint8 STATUS_WARNING = 1   # Naderend obstakel (< warn_dist_mm)
uint8 STATUS_BLOCKED = 2   # Geblokkeerd (< stop_dist_mm)

int32    num_zones            # Aantal zones (standaard 5)
string[] zone_names           # ["far_left","left","center","right","far_right"]
float32[] zone_distances_mm   # Mediaan afstand per zone in mm (-1 = geen meting)
uint8[]  zone_statuses        # STATUS_CLEAR / WARNING / BLOCKED per zone

# Ultrasoon (HC-SR04) aanvulling – backward compatible
float32 front_m
float32 rear_m
float32 left_m
float32 right_m
string  source                # "depth" of "ultrasonic" of "combined"
