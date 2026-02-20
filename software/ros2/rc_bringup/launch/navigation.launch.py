"""
navigation.launch.py  –  GPS waypoint navigatie

  ros2 launch rc_bringup navigation.launch.py

  # Met robot_localization EKF (optioneel, vereist ros-humble-robot-localization):
  ros2 launch rc_bringup navigation.launch.py ekf:=true

Vereist dat sensors.launch.py al draait (gps_node + imu_node).

Topics die deze launch verwacht:
  /gps/fix          sensor_msgs/NavSatFix
  /imu/data         sensor_msgs/Imu
  /mission/mode     std_msgs/String

Topics die deze launch publiceert:
  /navigation/cmd_vel         geometry_msgs/Twist
  /navigation/status          std_msgs/String
  /navigation/distance_m      std_msgs/Float32
  /navigation/heading_deg     std_msgs/Float32

Services:
  /navigation/add_waypoint    rc_interfaces/srv/AddWaypoint
  /navigation/start           std_srvs/srv/Trigger
  /navigation/pause           std_srvs/srv/Trigger
  /navigation/resume          std_srvs/srv/Trigger
  /navigation/clear           std_srvs/srv/Trigger

Action:
  /navigation/navigate_to     rc_interfaces/action/NavigateTo
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params = PathJoinSubstitution([
        FindPackageShare("rc_bringup"), "config", "params.yaml"
    ])
    ekf_params = PathJoinSubstitution([
        FindPackageShare("rc_navigation"), "config", "ekf_params.yaml"
    ])

    return LaunchDescription([

        DeclareLaunchArgument(
            "ekf", default_value="false",
            description="Start robot_localization EKF node (optioneel)"
        ),

        # ── Navigation node (GPS + IMU → waypoint navigatie) ─────────────
        Node(
            package     = "rc_navigation",
            executable  = "navigation_node",
            name        = "navigation_node",
            parameters  = [params],
            output      = "screen",
            emulate_tty = True,
        ),

        # ── EKF (optioneel, voor rviz2 / Nav2 integratie) ────────────────
        Node(
            package     = "robot_localization",
            executable  = "ekf_node",
            name        = "ekf_filter_node",
            parameters  = [ekf_params],
            output      = "screen",
            condition   = IfCondition(LaunchConfiguration("ekf")),
            remappings  = [("odometry/filtered", "/odom")],
        ),
        Node(
            package     = "robot_localization",
            executable  = "navsat_transform_node",
            name        = "navsat_transform_node",
            parameters  = [ekf_params],
            output      = "screen",
            condition   = IfCondition(LaunchConfiguration("ekf")),
            remappings  = [
                ("gps/fix",           "/gps/fix"),
                ("odometry/filtered", "/odom"),
            ],
        ),
    ])
