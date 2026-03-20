#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
require_ros

ros2 run ros_gz_bridge parameter_bridge \
  ${CMD_VEL_TOPIC}@geometry_msgs/msg/Twist@gz.msgs.Twist \
  ${ODOM_TOPIC}@nav_msgs/msg/Odometry@gz.msgs.Odometry \
  ${SCAN_TOPIC}@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan \
  ${IMU_TOPIC}@sensor_msgs/msg/Imu@gz.msgs.IMU
