"""
perception.launch.py  –  OAK-D Lite camera + YOLO + tracking + depth

  ros2 launch rc_bringup perception.launch.py
  ros2 launch rc_bringup perception.launch.py mock:=true   # zonder hardware

Launch arguments:
  mock:=true|false     Gebruik mock mode (development zonder OAK-D hardware)
  annotated:=true|false  Publiceer debug overlay topic
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = PathJoinSubstitution([
        FindPackageShare("rc_bringup"), "config", "params.yaml"
    ])

    return LaunchDescription([

        DeclareLaunchArgument(
            "mock", default_value="false",
            description="Mock mode (geen OAK-D hardware vereist)"
        ),
        DeclareLaunchArgument(
            "annotated", default_value="true",
            description="Publiceer geannoteerde debug frames"
        ),

        # ── OAK-D Lite camera + YOLO op Myriad X ────────────────────────
        Node(
            package    = "rc_perception",
            executable = "oak_node",
            name       = "oak_node",
            parameters = [
                params,
                {
                    "mock": LaunchConfiguration("mock"),
                    "publish_annotated": LaunchConfiguration("annotated"),
                },
            ],
            output     = "screen",
            emulate_tty = True,
        ),

        # ── Diepteframe → ObstacleMap ────────────────────────────────────
        Node(
            package    = "rc_perception",
            executable = "depth_node",
            name       = "depth_node",
            parameters = [params],
            output     = "screen",
            emulate_tty = True,
        ),

        # ── Persoon-volgcontroller ────────────────────────────────────────
        Node(
            package    = "rc_perception",
            executable = "tracking_node",
            name       = "tracking_node",
            parameters = [params],
            output     = "screen",
            emulate_tty = True,
        ),
    ])
