SHELL := /bin/bash
.DEFAULT_GOAL := world
.DELETE_ON_ERROR:

include Makeconfig

REPO_ROOT ?= $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
DATASET_DIR ?=
ROS2_WS ?= $(REPO_ROOT)/ros2_ws

export DATASET_DIR PROJECT_NAME REPO_ROOT ROS2_WS
export ROS_DISTRO ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION GZ_LAUNCH GZ_FALLBACK_CMD
export ODM_IMAGE ODM_ORTHOPHOTO_RESOLUTION ODM_MESH_SIZE ODM_MESH_OCTREE_DEPTH ODM_DSM ODM_DTM ODM_SKIP_3DMODEL ODM_END_WITH ODM_WORKDIR ODM_TMPDIR ODM_EXTRA_ARGS
export HEIGHTMAP_SOURCE HEIGHTMAP_PRIMARY_FORMAT HEIGHTMAP_MAX_SIDE
export WORLD_FILE WORLD_XY_SCALE WORLD_Z_SCALE ADD_MESH
export MESH_X_OFFSET MESH_Y_OFFSET MESH_Z_OFFSET MESH_Z_DELTA Z_ORIGIN_MODE
export CMD_VEL_TOPIC ODOM_TOPIC SCAN_TOPIC IMU_TOPIC TELEOP_TOPIC

STAMP_DIR ?= $(DATASET_DIR)/.make
TERRAIN_DIR ?= $(DATASET_DIR)/terrain
WORLD_DIR ?= $(DATASET_DIR)/gazebo_world

ODM_STAMP := $(STAMP_DIR)/odm.done
ODM_ORTHO_READY := $(STAMP_DIR)/odm_ortho.ready
ODM_DEM_READY := $(STAMP_DIR)/odm_dem.ready
ODM_MESH_READY := $(STAMP_DIR)/odm_mesh.ready

ODM_ORTHO := $(DATASET_DIR)/odm_orthophoto/odm_orthophoto.tif
ODM_DTM_TIF := $(DATASET_DIR)/odm_dem/dtm.tif
ODM_DSM_TIF := $(DATASET_DIR)/odm_dem/dsm.tif

NAV2_SOURCE ?= $(or $(HEIGHTMAP_SOURCE),dtm)
ifeq ($(NAV2_SOURCE),dtm)
NAV_DEM := $(ODM_DTM_TIF)
else ifeq ($(NAV2_SOURCE),dsm)
NAV_DEM := $(ODM_DSM_TIF)
else
$(error NAV2_SOURCE must be dtm or dsm)
endif

HEIGHTMAP_META ?= $(TERRAIN_DIR)/terrain_meta.json

ORTHO_IMAGE ?= $(ODM_ORTHO)
SEMANTIC_SCHEMA_JSON ?= $(REPO_ROOT)/configs/semantics/semantic_target_schema.json
SEMANTIC_MODEL_ID ?= optimum/segformer-b0-finetuned-ade-512-512
CLASSES_JSON ?= $(REPO_ROOT)/configs/examples/classes.json

BUILD_SEMANTIC_PRIOR ?= 1
USE_SIM_TIME ?= true

OBS_X_M ?= 0.0
OBS_Y_M ?= 0.0
OBS_HEIGHT_M ?= 2.0
TARGET_HEIGHT_M ?= 0.5
MAX_VIS_RANGE_M ?= 300.0

WORLD_FILE ?= generated_world.sdf
WORLD_SDF := $(WORLD_DIR)/$(WORLD_FILE)

NAV2_MAP_PGM := $(TERRAIN_DIR)/nav2_map.pgm
NAV2_MAP_YAML := $(TERRAIN_DIR)/nav2_map.yaml
TRAVERSABILITY_PNG := $(TERRAIN_DIR)/traversability.png
SLOPE_PNG := $(TERRAIN_DIR)/slope.png
ROUGHNESS_PNG := $(TERRAIN_DIR)/roughness.png
TOPOLOGY_SUMMARY := $(TERRAIN_DIR)/topology_summary.json
TERRAIN_FRAME := $(TERRAIN_DIR)/terrain_frame.json
NAV_DEBUG_OVERLAY := $(TERRAIN_DIR)/nav_debug_overlay.png

SEMANTIC_CLASS_MAP := $(TERRAIN_DIR)/semantic_class_ids.png
SEMANTIC_CLASS_OVERLAY := $(TERRAIN_DIR)/semantic_class_overlay.png
SEMANTIC_METADATA := $(TERRAIN_DIR)/semantic_class_map.json

KEEPOUT_PGM := $(TERRAIN_DIR)/keepout_mask.pgm
KEEP_OUT_YAML := $(TERRAIN_DIR)/keepout_mask.yaml
SPEED_PGM := $(TERRAIN_DIR)/speed_mask.pgm
SPEED_YAML := $(TERRAIN_DIR)/speed_mask.yaml
SEMANTIC_NAV_OVERLAY := $(TERRAIN_DIR)/semantic_overlay.png

VIS_KEEPOUT_PGM := $(TERRAIN_DIR)/visibility_keepout_mask.pgm
VIS_KEEP_OUT_YAML := $(TERRAIN_DIR)/visibility_keepout_mask.yaml
RADIO_SPEED_PGM := $(TERRAIN_DIR)/radio_speed_mask.pgm
RADIO_SPEED_YAML := $(TERRAIN_DIR)/radio_speed_mask.yaml
VISIBILITY_OVERLAY := $(TERRAIN_DIR)/visibility_overlay.png

ROS2_BUILD_STAMP := $(ROS2_WS)/install/.portfolio_build.stamp
ROS2_SOURCES := $(shell test -d "$(ROS2_WS)/src" && find "$(ROS2_WS)/src" -type f \( -name '*.py' -o -name '*.xml' -o -name '*.yaml' -o -name '*.launch.py' -o -name 'CMakeLists.txt' \) || true)

ODM_INPUTS := $(if $(strip $(DATASET_DIR)),$(shell find "$(DATASET_DIR)/images" -type f 2>/dev/null),)

SEMANTIC_PRIOR_ENABLED := $(filter 1 true yes,$(BUILD_SEMANTIC_PRIOR))
NAV_ASSET_SEM_DEPS := $(if $(SEMANTIC_PRIOR_ENABLED),$(SEMANTIC_CLASS_MAP),)
NAV_ASSET_SEM_ARG := $(if $(SEMANTIC_PRIOR_ENABLED),--semantic-class-map "$(SEMANTIC_CLASS_MAP)",)

.PHONY: help sync-ros2 \
        odm odm-ortho odm-dem odm-mesh \
        heightmap \
        semantic semantic-class-map semantic-masks \
        nav-assets nav-debug visibility-masks \
        world gazebo bridge teleop spawn-robot laser-tf \
        ros2-clean ros2-build localization navigation rviz \
        clean portfolio-clean

sync-ros2:
	@test -d "$(ROS2_WS)/src" || (echo "Missing $(ROS2_WS)/src. This Makefile does not generate ros2_ws/src; create or sync it first."; exit 1)

$(STAMP_DIR) $(TERRAIN_DIR) $(WORLD_DIR):
	@mkdir -p "$@"

odm: $(ODM_STAMP)
odm-ortho: $(ODM_ORTHO_READY)
odm-dem: $(ODM_DEM_READY)
odm-mesh: $(ODM_MESH_READY)

$(ODM_STAMP): scripts/run_odm.sh scripts/common.sh $(ODM_INPUTS) | $(STAMP_DIR)
	@test -n "$(DATASET_DIR)" || (echo "Set DATASET_DIR"; exit 1)
	./scripts/run_odm.sh "$(DATASET_DIR)"
	@touch "$@"

$(ODM_ORTHO_READY): scripts/run_odm.sh scripts/common.sh $(ODM_INPUTS) | $(STAMP_DIR)
	@test -n "$(DATASET_DIR)" || (echo "Set DATASET_DIR"; exit 1)
	@if [ ! -f "$(ODM_ORTHO)" ]; then \
		./scripts/run_odm.sh "$(DATASET_DIR)"; \
	fi
	@test -f "$(ODM_ORTHO)" || (echo "Expected ODM orthophoto not found: $(ODM_ORTHO)"; exit 1)
	@touch "$@"

$(ODM_DEM_READY): scripts/run_odm.sh scripts/common.sh $(ODM_INPUTS) | $(STAMP_DIR)
	@test -n "$(DATASET_DIR)" || (echo "Set DATASET_DIR"; exit 1)
	@if [ ! -f "$(NAV_DEM)" ]; then \
		./scripts/run_odm.sh "$(DATASET_DIR)"; \
	fi
	@test -f "$(ODM_DTM_TIF)" -o -f "$(ODM_DSM_TIF)" || (echo "Expected ODM DEM output not found in $(DATASET_DIR)/odm_dem"; exit 1)
	@test -f "$(NAV_DEM)" || (echo "Configured NAV2_SOURCE=$(NAV2_SOURCE) but file not found: $(NAV_DEM)"; exit 1)
	@touch "$@"

$(ODM_MESH_READY): scripts/run_odm.sh scripts/common.sh $(ODM_INPUTS) | $(STAMP_DIR)
	@test -n "$(DATASET_DIR)" || (echo "Set DATASET_DIR"; exit 1)
	@mesh="$$( \
	  for p in \
	    "$(DATASET_DIR)/odm_texturing_25d/odm_textured_model_geo.obj" \
	    "$(DATASET_DIR)/odm_texturing_25d/odm_textured_model.obj" \
	    "$(DATASET_DIR)/odm_texturing/odm_textured_model_geo.obj" \
	    "$(DATASET_DIR)/odm_texturing/odm_textured_model.obj" ; do \
	      [ -f "$$p" ] && { printf '%s\n' "$$p"; break; }; \
	  done \
	)"; \
	if [ -z "$$mesh" ]; then \
	  ./scripts/run_odm.sh "$(DATASET_DIR)"; \
	  mesh="$$( \
	    for p in \
	      "$(DATASET_DIR)/odm_texturing_25d/odm_textured_model_geo.obj" \
	      "$(DATASET_DIR)/odm_texturing_25d/odm_textured_model.obj" \
	      "$(DATASET_DIR)/odm_texturing/odm_textured_model_geo.obj" \
	      "$(DATASET_DIR)/odm_texturing/odm_textured_model.obj" ; do \
	        [ -f "$$p" ] && { printf '%s\n' "$$p"; break; }; \
	    done \
	  )"; \
	fi; \
	test -n "$$mesh" || (echo "Missing ODM textured OBJ mesh."; exit 1); \
	printf '%s\n' "$$mesh" > "$@"

heightmap: $(HEIGHTMAP_META)

$(HEIGHTMAP_META): $(ODM_DEM_READY) scripts/build_heightmap.py | $(TERRAIN_DIR)
	python3 scripts/build_heightmap.py \
		--input "$(NAV_DEM)" \
		--out-dir "$(TERRAIN_DIR)" \
		--primary-format "$(HEIGHTMAP_PRIMARY_FORMAT)" \
		--max-side "$(HEIGHTMAP_MAX_SIDE)" \
		--flip-y 1

semantic: semantic-class-map
semantic-class-map: $(SEMANTIC_CLASS_MAP)

$(SEMANTIC_CLASS_MAP) $(SEMANTIC_CLASS_OVERLAY) $(SEMANTIC_BLEND_PNG) $(SEMANTIC_METADATA) &: \
	scripts/build_semantic_class_map.py $(SEMANTIC_SCHEMA_JSON) $(ODM_ORTHO_READY) | $(TERRAIN_DIR)
	python3 scripts/build_semantic_class_map.py \
		--image "$(ODM_ORTHO)" \
		--model-id "$(SEMANTIC_MODEL_ID)" \
		--schema-json "$(SEMANTIC_SCHEMA_JSON)" \
		--out-class-map "$(SEMANTIC_CLASS_MAP)" \
		--out-overlay "$(SEMANTIC_CLASS_OVERLAY)" \
		--out-blend "$(SEMANTIC_BLEND_PNG)" \
		--out-metadata "$(SEMANTIC_METADATA)" \
		--blend-alpha "$(SEMANTIC_ALPHA)" \
		--tile-size 768 \
		--overlap 128 \
		--providers CPUExecutionProvider

nav-assets: $(NAV2_MAP_YAML) $(TOPOLOGY_SUMMARY) $(TERRAIN_FRAME) $(NAV_DEBUG_OVERLAY)
nav-debug: $(NAV_DEBUG_OVERLAY)

$(NAV2_MAP_PGM) $(NAV2_MAP_YAML) $(TRAVERSABILITY_PNG) $(SLOPE_PNG) $(ROUGHNESS_PNG) $(TOPOLOGY_SUMMARY) $(TERRAIN_FRAME) $(NAV_DEBUG_OVERLAY) &: \
	scripts/build_nav2_assets.py $(ODM_DEM_READY) $(ODM_ORTHO_READY) $(NAV_ASSET_SEM_DEPS) | $(TERRAIN_DIR)
	python3 scripts/build_nav2_assets.py \
		--dataset "$(DATASET_DIR)" \
		--source "$(NAV2_SOURCE)" \
		$(NAV_ASSET_SEM_ARG) \
		--orthophoto "$(ODM_ORTHO)" \
		--inflate-radius-m 0.45 \
		--min-free-region-px 150 \
		--hole-fill-px 500

semantic-masks: $(KEEP_OUT_YAML) $(SPEED_YAML)

$(KEEPOUT_PGM) $(KEEP_OUT_YAML) $(SPEED_PGM) $(SPEED_YAML) $(SEMANTIC_NAV_OVERLAY) &: \
	scripts/build_semantic_masks.py $(NAV2_MAP_YAML) $(SEMANTIC_CLASS_MAP) $(CLASSES_JSON) | $(TERRAIN_DIR)
	python3 scripts/build_semantic_masks.py \
		--class-map "$(SEMANTIC_CLASS_MAP)" \
		--map-yaml "$(NAV2_MAP_YAML)" \
		--out-dir "$(TERRAIN_DIR)" \
		--classes-json "$$(cat "$(CLASSES_JSON)")"

visibility-masks: $(VIS_KEEP_OUT_YAML) $(RADIO_SPEED_YAML)

$(VIS_KEEPOUT_PGM) $(VIS_KEEP_OUT_YAML) $(RADIO_SPEED_PGM) $(RADIO_SPEED_YAML) $(VISIBILITY_OVERLAY) &: \
	scripts/build_visibility_masks_fast.py $(ODM_DEM_READY) $(NAV2_MAP_YAML) | $(TERRAIN_DIR)
	python3 scripts/build_visibility_masks_fast.py \
		--dem "$(NAV_DEM)" \
		--obs-x-m "$(OBS_X_M)" \
		--obs-y-m "$(OBS_Y_M)" \
		--obs-height-m "$(OBS_HEIGHT_M)" \
		--target-height-m "$(TARGET_HEIGHT_M)" \
		--max-range-m "$(MAX_VIS_RANGE_M)" \
		--map-yaml "$(NAV2_MAP_YAML)" \
		--out-dir "$(TERRAIN_DIR)" \
		--work-resolution-m 2.0

world: $(WORLD_SDF)

$(WORLD_SDF): scripts/build_world.py $(WORLD_TEMPLATE) $(ODM_MESH_READY) | $(WORLD_DIR)
	python3 scripts/build_world.py \
		--dataset "$(DATASET_DIR)" \
		--repo-root "$(REPO_ROOT)" \
		--template "$(WORLD_TEMPLATE)" \
		--world-file "$(notdir $@)" \
		--xy-scale "$(WORLD_XY_SCALE)" \
		--z-scale "$(WORLD_Z_SCALE)" \
		--add-mesh "$(ADD_MESH)" \
		--mesh-x-offset "$(MESH_X_OFFSET)" \
		--mesh-y-offset "$(MESH_Y_OFFSET)" \
		$(if $(strip $(MESH_Z_OFFSET)),--mesh-z-offset "$(MESH_Z_OFFSET)",) \
		--mesh-z-delta "$(MESH_Z_DELTA)" \
		--z-origin-mode "$(Z_ORIGIN_MODE)" \
		--visual-mode rgb

gazebo: $(WORLD_SDF)
	WORLD_FILE="$(notdir $(WORLD_SDF))" ./scripts/launch_gazebo.sh "$(DATASET_DIR)" "$(REPO_ROOT)"

bridge:
	./scripts/bridge_ros_gz.sh

teleop:
	./scripts/teleop.sh

spawn-robot:
	./scripts/spawn_robot.sh

laser-tf:
	. /opt/ros/$$ROS_DISTRO/setup.sh && \
	ros2 run tf2_ros static_transform_publisher \
	  --x 0 --y 0 --z 0.35 \
	  --roll 0 --pitch 0 --yaw 0 \
	  --frame-id base_link --child-frame-id laser_frame

ros2-clean:
	rm -rf "$(ROS2_WS)/build" "$(ROS2_WS)/install" "$(ROS2_WS)/log"

ros2-build: $(ROS2_BUILD_STAMP)

$(ROS2_BUILD_STAMP): sync-ros2 $(ROS2_SOURCES)
	cd "$(ROS2_WS)" && . /opt/ros/$$ROS_DISTRO/setup.sh && colcon build --symlink-install
	@mkdir -p "$(dir $@)"
	@touch "$@"

localization: ros2-build $(NAV2_MAP_YAML)
	cd "$(ROS2_WS)" && . /opt/ros/$$ROS_DISTRO/setup.sh && . install/setup.sh && \
	ros2 launch nav2_bringup localization_launch.py \
		map:="$(NAV2_MAP_YAML)" \
		use_sim_time:=$(USE_SIM_TIME) \
		params_file:="$(ROS2_WS)/src/rover_bringup/config/nav2_params.yaml"

navigation: ros2-build
	cd "$(ROS2_WS)" && . /opt/ros/$$ROS_DISTRO/setup.sh && . install/setup.sh && \
	ros2 launch nav2_bringup navigation_launch.py \
		use_sim_time:=$(USE_SIM_TIME) \
		params_file:="$(ROS2_WS)/src/rover_bringup/config/nav2_params.yaml"

rviz:
	. /opt/ros/$$ROS_DISTRO/setup.sh && \
	ros2 launch nav2_bringup rviz_launch.py use_sim_time:=$(USE_SIM_TIME)

clean-odm:
	rm -rf "$(DATASET_DIR)/.make" \
	       "$(DATASET_DIR)/odm_dem" \
	       "$(DATASET_DIR)/odm_filterpoints" \
	       "$(DATASET_DIR)/odm_georeferencing" \
	       "$(DATASET_DIR)/odm_meshing" \
	       "$(DATASET_DIR)/odm_orthophoto" \
	       "$(DATASET_DIR)/odm_report" \
	       "$(DATASET_DIR)/odm_texturing" \
	       "$(DATASET_DIR)/odm_texturing_25d"

clean-heightmap:
	rm -f "$(HEIGHTMAP_META)" \
	      "$(TERRAIN_DIR)/heightmap.png" \
	      "$(TERRAIN_DIR)/heightmap8.png" \
	      "$(TERRAIN_DIR)/heightmap16.png"

clean-semantic:
	rm -f "$(SEMANTIC_CLASS_MAP)" \
	      "$(SEMANTIC_CLASS_OVERLAY)" \
	      "$(SEMANTIC_METADATA)"

clean-nav-assets:
	rm -f "$(NAV2_MAP_PGM)" "$(NAV2_MAP_YAML)" \
	      "$(TRAVERSABILITY_PNG)" "$(SLOPE_PNG)" "$(ROUGHNESS_PNG)" \
	      "$(TOPOLOGY_SUMMARY)" "$(TERRAIN_FRAME)" "$(NAV_DEBUG_OVERLAY)"

clean-semantic-masks:
	rm -f "$(KEEPOUT_PGM)" "$(KEEP_OUT_YAML)" \
	      "$(SPEED_PGM)" "$(SPEED_YAML)" "$(SEMANTIC_NAV_OVERLAY)"

clean-visibility:
	rm -f "$(VIS_KEEPOUT_PGM)" "$(VIS_KEEP_OUT_YAML)" \
	      "$(RADIO_SPEED_PGM)" "$(RADIO_SPEED_YAML)" "$(VISIBILITY_OVERLAY)"

clean-world:
	rm -rf "$(DATASET_DIR)/gazebo_world"

clean-all: clean-odm clean-heightmap clean-semantic clean-nav-assets clean-semantic-masks clean-visibility clean-world ros2-clean
	rm -rf "$(TERRAIN_DIR)"
