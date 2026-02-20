"""
vehicle.launch.py  –  Start only the vehicle control node.

Use this for initial hardware testing:
  ros2 launch rc_bringup vehicle.launch.py

Then send a test command:
  ros2 topic pub /vehicle/cmd_vel geometry_msgs/Twist \
    "{linear: {x: 0.1}, angular: {z: 0.0}}" --once
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = PathJoinSubstitution([
        FindPackageShare('rc_bringup'), 'config', 'params.yaml'
    ])

    return LaunchDescription([
        Node(
            package    = 'rc_vehicle',
            executable = 'vehicle_node',
            name       = 'vehicle_node',
            parameters = [params],
            output     = 'screen',
            emulate_tty = True,
        ),
    ])
