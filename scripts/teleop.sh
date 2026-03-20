#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
require_ros
ros2 run teleop_twist_keyboard teleop_twist_keyboard --ros-args -r cmd_vel:=${TELEOP_TOPIC}
