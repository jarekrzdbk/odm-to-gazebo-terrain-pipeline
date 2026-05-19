#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
require_ros

: "${CMD_VEL_TOPIC:=/cmd_vel}"
: "${ODOM_TOPIC:=/odom}"
: "${SCAN_TOPIC:=/scan}"
: "${IMU_TOPIC:=/imu}"
: "${TF_TOPIC:=/tf}"
: "${CLOCK_TOPIC:=/clock}"

ros2 run ros_gz_bridge parameter_bridge \
  ${CMD_VEL_TOPIC}@geometry_msgs/msg/Twist@gz.msgs.Twist \
  ${ODOM_TOPIC}@nav_msgs/msg/Odometry@gz.msgs.Odometry \
  ${SCAN_TOPIC}@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan \
  ${TF_TOPIC}@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V \
  ${CLOCK_TOPIC}@rosgraph_msgs/msg/Clock[gz.msgs.Clock
