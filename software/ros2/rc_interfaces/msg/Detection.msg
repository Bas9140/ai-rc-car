std_msgs/Header header

# YOLO detectie met 3D ruimtelijke informatie (OAK-D Lite Myriad X)
int32   class_id
string  class_name
float32 confidence

# Bounding box in pixels (relatief aan camera frame resolutie)
int32 xmin
int32 ymin
int32 xmax
int32 ymax

# 3D positie in mm (camerafrane: +X rechts, +Y omlaag, +Z vooruit)
float32 x_mm
float32 y_mm
float32 z_mm

# Classificatie hulpvlaggen
bool is_obstacle
bool is_person
