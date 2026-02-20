std_msgs/Header header

# Status van de actieve persoon-volgmodus (follow-me)
bool    tracking       # True als er actief een target gevolgd wordt

int32   class_id
string  class_name
float32 confidence

# 3D positie van het target in mm (camera coordinaten)
float32 x_mm
float32 y_mm
float32 z_mm

# Horizontale offset in pixels ten opzichte van frame midden
# Positief = target rechts van midden
float32 x_offset_px
