"""
sensors.launch.py  –  Start all sensor nodes.

Use this to verify all sensors are working:
  ros2 launch rc_bringup sensors.launch.py

Monitor data:
  ros2 topic echo /gps/fix
  ros2 topic echo /imu/data
  ros2 topic echo /ultrasonic/distances
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
            package    = 'rc_sensors',
            executable = 'gps_node',
            name       = 'gps_node',
            parameters = [params],
            output     = 'screen',
        ),
        Node(
            package    = 'rc_sensors',
            executable = 'imu_node',
            name       = 'imu_node',
            parameters = [params],
            output     = 'screen',
        ),
        Node(
            package    = 'rc_sensors',
            executable = 'ultrasonic_node',
            name       = 'ultrasonic_node',
            parameters = [params],
            output     = 'screen',
        ),
        Node(
            package    = 'rc_sensors',
            executable = 'receiver_node',
            name       = 'receiver_node',
            parameters = [params],
            output     = 'screen',
            emulate_tty = True,
        ),
    ])
