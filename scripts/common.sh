#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"

: "${ROS_DISTRO:=humble}"
: "${ROS_DOMAIN_ID:=30}"
: "${ROS_LOCALHOST_ONLY:=0}"
: "${RMW_IMPLEMENTATION:=rmw_fastrtps_cpp}"
: "${GZ_LAUNCH:=ros2 launch ros_gz_sim gz_sim.launch.py}"
: "${GZ_FALLBACK_CMD:=ign gazebo}"

: "${ODM_IMAGE:=opendronemap/odm:latest}"

: "${ODM_ORTHOPHOTO_RESOLUTION:=2.5}"
: "${ODM_MESH_SIZE:=400000}"
: "${ODM_MESH_OCTREE_DEPTH:=10}"
: "${ODM_DSM:=1}"
: "${ODM_DTM:=1}"
: "${ODM_EXTRA_ARGS:=}"

: "${HEIGHTMAP_SOURCE:=auto}"
: "${HEIGHTMAP_PNG:=heightmap.png}"
: "${HEIGHTMAP_JSON:=terrain_meta.json}"
: "${WORLD_FILE:=generated_world.sdf}"
: "${ROBOT_MODEL:=simple_bot}"
: "${ROBOT_Z:=20.0}"
: "${WORLD_XY_SCALE:=1.0}"
: "${WORLD_Z_SCALE:=1.0}"
: "${ADD_MESH:=0}"

: "${CMD_VEL_TOPIC:=/cmd_vel}"
: "${ODOM_TOPIC:=/odom}"
: "${SCAN_TOPIC:=/scan}"
: "${IMU_TOPIC:=/imu}"
: "${TELEOP_TOPIC:=/cmd_vel}"

require_ros() {
  # shellcheck disable=SC1091
  set +u
  source "/opt/ros/${ROS_DISTRO}/setup.bash"
  set -u
  export ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION
}

require_dataset() {
  local dataset_dir="${1:?dataset dir required}"
  if [[ ! -d "$dataset_dir/images" ]]; then
    echo "Expected images directory at: $dataset_dir/images" >&2
    exit 1
  fi
}

join_args() {
  local first=1
  for arg in "$@"; do
    if [[ $first -eq 1 ]]; then
      printf '%s' "$arg"
      first=0
    else
      printf ' %s' "$arg"
    fi
  done
}
