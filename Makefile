SHELL := /bin/bash
.DEFAULT_GOAL := world
.DELETE_ON_ERROR:

include Makeconfig

export DATASET_DIR PROJECT_NAME REPO_ROOT
export ROS_DISTRO ROS_DOMAIN_ID ROS_LOCALHOST_ONLY RMW_IMPLEMENTATION GZ_LAUNCH GZ_FALLBACK_CMD
export ODM_IMAGE ODM_ORTHOPHOTO_RESOLUTION ODM_MESH_SIZE ODM_MESH_OCTREE_DEPTH ODM_DSM ODM_DTM ODM_SKIP_3DMODEL ODM_END_WITH ODM_WORKDIR ODM_TMPDIR ODM_EXTRA_ARGS
export HEIGHTMAP_SOURCE HEIGHTMAP_PRIMARY_FORMAT HEIGHTMAP_MAX_SIDE
export WORLD_FILE WORLD_TEMPLATE WORLD_XY_SCALE WORLD_Z_SCALE ADD_MESH
export MESH_X_OFFSET MESH_Y_OFFSET MESH_Z_OFFSET MESH_Z_DELTA Z_ORIGIN_MODE
export CMD_VEL_TOPIC ODOM_TOPIC SCAN_TOPIC IMU_TOPIC TELEOP_TOPIC

ODM_INPUTS := $(if $(strip $(DATASET_DIR)),$(shell find "$(DATASET_DIR)/images" -type f 2>/dev/null),)

.PHONY: odm heightmap world gazebo bridge teleop spawn-robot clean

odm: $(ODM_STAMP)

heightmap: $(HEIGHTMAP_META)

world: $(WORLD_SDF)

gazebo: $(WORLD_SDF)
	./scripts/launch_gazebo.sh "$(DATASET_DIR)" "$(REPO_ROOT)"

bridge:
	./scripts/bridge_ros_gz.sh

teleop:
	./scripts/teleop.sh

spawn-robot:
	./scripts/spawn_robot.sh

$(STAMP_DIR) $(TERRAIN_DIR) $(WORLD_DIR):
	@mkdir -p "$@"

$(ODM_STAMP): scripts/run_odm.sh scripts/common.sh $(ODM_INPUTS) | $(STAMP_DIR)
	./scripts/run_odm.sh "$(DATASET_DIR)"
	@touch "$@"

$(HEIGHTMAP_META): $(HEIGHTMAP_INPUT) scripts/build_heightmap.py | $(TERRAIN_DIR)
	python3 scripts/build_heightmap.py \
		--input "$(HEIGHTMAP_INPUT)" \
		--out-dir "$(TERRAIN_DIR)" \
		--primary-format "$(HEIGHTMAP_PRIMARY_FORMAT)" \
		--max-side "$(HEIGHTMAP_MAX_SIDE)" \
		--flip-y 1

$(WORLD_SDF): $(ODM_STAMP) scripts/build_world.py $(WORLD_TEMPLATE) | $(WORLD_DIR)
	python3 scripts/build_world.py \
		--dataset "$(DATASET_DIR)" \
		--repo-root "$(REPO_ROOT)" \
		--template "$(WORLD_TEMPLATE)" \
		--output "$@" \
		--xy-scale "$(WORLD_XY_SCALE)" \
		--z-scale "$(WORLD_Z_SCALE)" \
		--mesh-x-offset "$(MESH_X_OFFSET)" \
		--mesh-y-offset "$(MESH_Y_OFFSET)" \
		$(if $(strip $(MESH_Z_OFFSET)),--mesh-z-offset "$(MESH_Z_OFFSET)",) \
		--mesh-z-delta "$(MESH_Z_DELTA)" \
		--z-origin-mode "$(Z_ORIGIN_MODE)" \
		--add-mesh "$(ADD_MESH)"

clean:
	rm -rf "$(DATASET_DIR)/.make" \
	       "$(DATASET_DIR)/odm_dem" \
	       "$(DATASET_DIR)/odm_filterpoints" \
	       "$(DATASET_DIR)/odm_georeferencing" \
	       "$(DATASET_DIR)/odm_meshing" \
	       "$(DATASET_DIR)/odm_orthophoto" \
	       "$(DATASET_DIR)/odm_report" \
	       "$(DATASET_DIR)/odm_texturing" \
	       "$(DATASET_DIR)/odm_texturing_25d" \
	       "$(DATASET_DIR)/terrain" \
	       "$(DATASET_DIR)/gazebo_world"
