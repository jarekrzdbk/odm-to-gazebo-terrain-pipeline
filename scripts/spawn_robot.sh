#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
require_ros

WORLD_NAME="${WORLD_NAME:-ortho_world}"
ROBOT_NAME="${ROBOT_NAME:-robot1}"
ROBOT_FILE="${ROBOT_FILE:-$REPO_ROOT/gazebo/models/simple_bot/model.sdf}"
ROBOT_X="${ROBOT_X:-0.0}"
ROBOT_Y="${ROBOT_Y:-0.0}"
ROBOT_Z="${ROBOT_Z:-30.0}"

ros2 run ros_gz_sim create \
  -world "$WORLD_NAME" \
  -name "$ROBOT_NAME" \
  -x "$ROBOT_X" \
  -y "$ROBOT_Y" \
  -z "$ROBOT_Z" \
  -file "$ROBOT_FILE"
