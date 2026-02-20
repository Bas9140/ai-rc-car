"""
avoidance.launch.py  –  Obstakelvermijding

  ros2 launch rc_bringup avoidance.launch.py

Vereist dat sensors.launch.py en perception.launch.py al draaien
(of in hetzelfde all.launch.py worden meegestart).

Topics die deze launch verwacht:
  /camera/obstacle_map      (van rc_perception/depth_node)
  /ultrasonic/distances     (van rc_sensors/ultrasonic_node)

Topics die deze launch publiceert:
  /avoidance/override       geometry_msgs/Twist
  /avoidance/status         std_msgs/String
  /avoidance/active         std_msgs/Bool
"""

from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = PathJoinSubstitution([
        FindPackageShare("rc_bringup"), "config", "params.yaml"
    ])

    return LaunchDescription([
        Node(
            package     = "rc_avoidance",
            executable  = "avoidance_node",
            name        = "avoidance_node",
            parameters  = [params],
            output      = "screen",
            emulate_tty = True,
        ),
    ])
