#!/usr/bin/env bash
set -euo pipefail

source "$(dirname "$0")/common.sh"

DATASET_DIR="${1:?dataset dir required}"
require_dataset "$DATASET_DIR"

mkdir -p "$DATASET_DIR/tmp"

ODM_ARGS=(
  --project-path /datasets project
  --orthophoto-resolution "$ODM_ORTHOPHOTO_RESOLUTION"
  --mesh-size "$ODM_MESH_SIZE"
  --mesh-octree-depth "$ODM_MESH_OCTREE_DEPTH"
)

if [[ "${ODM_DSM:-0}" == "1" ]]; then
  ODM_ARGS+=(--dsm)
fi

if [[ "${ODM_DTM:-0}" == "1" ]]; then
  ODM_ARGS+=(--dtm)
fi

if [[ -n "${ODM_END_WITH:-}" ]]; then
  ODM_ARGS+=(--end-with "$ODM_END_WITH")
fi

if [[ "${ODM_SKIP_3DMODEL:-0}" == "1" ]]; then
  ODM_ARGS+=(--skip-3dmodel)
fi

if [[ -n "${ODM_EXTRA_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  EXTRA_ARR=($ODM_EXTRA_ARGS)
  ODM_ARGS+=("${EXTRA_ARR[@]}")
fi

echo "Running ODM with args: $(join_args "${ODM_ARGS[@]}")"

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -w "$ODM_WORKDIR" \
  -e TMPDIR="$ODM_TMPDIR" \
  -v "$DATASET_DIR:/datasets/project" \
  "$ODM_IMAGE" \
  "${ODM_ARGS[@]}"

if [[ ! -f "$DATASET_DIR/odm_dem/dsm.tif" && ! -f "$DATASET_DIR/odm_dem/dtm.tif" ]]; then
  echo "ODM did not produce odm_dem/dsm.tif or odm_dem/dtm.tif" >&2
  exit 1
fi

echo "ODM outputs written into $DATASET_DIR"
