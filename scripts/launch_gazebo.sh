#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

DATASET_DIR="${1:?dataset dir required}"
REPO_ROOT_INPUT="${2:?repo root required}"
WORLD="$DATASET_DIR/gazebo_world/${WORLD_FILE}"

if [[ ! -f "$WORLD" ]]; then
  echo "World not found: $WORLD" >&2
  exit 1
fi

require_ros
export GZ_SIM_RESOURCE_PATH="$REPO_ROOT_INPUT/gazebo/models:${GZ_SIM_RESOURCE_PATH:-}"

echo "Launching world: $WORLD"

if ros2 pkg prefix ros_gz_sim >/dev/null 2>&1; then
  exec ros2 launch ros_gz_sim gz_sim.launch.py gz_args:="-r $WORLD"
fi

if command -v ign >/dev/null 2>&1; then
  exec ign gazebo -r "$WORLD" --render-engine ogre
fi

if command -v gz >/dev/null 2>&1; then
  exec gz sim -r "$WORLD" --render-engine ogre
fi

exit 1
