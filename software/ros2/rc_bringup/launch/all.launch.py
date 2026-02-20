"""
all.launch.py  –  Start the complete AI RC Car stack.

  ros2 launch rc_bringup all.launch.py

Launch arguments:
  mode:=idle|manual|autonomous|follow_me   (default: manual)

Example: start in manual mode
  ros2 launch rc_bringup all.launch.py mode:=manual
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = PathJoinSubstitution([
        FindPackageShare('rc_bringup'), 'config', 'params.yaml'
    ])

    pkg_bringup = FindPackageShare('rc_bringup')

    return LaunchDescription([

        # ── Launch arguments ──────────────────────────────────────────
        DeclareLaunchArgument(
            'mode', default_value='manual',
            description='Initial driving mode (idle/manual/autonomous/follow_me)'
        ),

        # ── Include sub-launches ──────────────────────────────────────
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([pkg_bringup, 'launch', 'vehicle.launch.py'])
            ])
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([pkg_bringup, 'launch', 'sensors.launch.py'])
            ])
        ),

        # ── Perception (OAK-D Lite + YOLO + tracking + depth) ────────
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([pkg_bringup, 'launch', 'perception.launch.py'])
            ])
        ),

        # ── Avoidance (sensor fusie + uitwijklogica) ──────────────────
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([pkg_bringup, 'launch', 'avoidance.launch.py'])
            ])
        ),

        # ── Navigation (GPS waypoints + pure pursuit) ────────────────
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                PathJoinSubstitution([pkg_bringup, 'launch', 'navigation.launch.py'])
            ])
        ),

        # ── Mission node ──────────────────────────────────────────────
        Node(
            package    = 'rc_mission',
            executable = 'mission_node',
            name       = 'mission_node',
            parameters = [params],
            output     = 'screen',
            emulate_tty = True,
        ),
    ])
