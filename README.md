# ODM → Gazebo → ROS 2 / Nav2 Terrain Pipeline

A pipeline for converting drone image datasets into Gazebo simulation worlds and optional ROS 2 / Nav2 navigation assets.

## Overview

This project uses OpenDroneMap outputs such as orthophotos, DTM/DSM elevation models, point clouds, and textured meshes to build simulated terrain for robot experiments.

The main workflow is:

1. process drone images with OpenDroneMap;
2. convert a DTM or DSM raster into a Gazebo heightmap;
3. generate a Gazebo SDF world;
4. use the heightmap as the robot collision surface;
5. optionally use the ODM textured mesh as the visual terrain;
6. bridge Gazebo topics to ROS 2;
7. drive a simulated robot;
8. optionally generate Nav2, semantic, and visibility masks.

## Target stack

```text
Ubuntu 22.04
ROS 2 Humble
Gazebo Fortress / Ignition Gazebo 6
OpenDroneMap
Docker
Python
Make
Bash
```

## Development note

This project were developed with help from a large language model, ChatGPT.

## Features

- Run OpenDroneMap on drone image datasets.
- Generate Gazebo terrain from DTM or DSM rasters.
- Use ODM textured meshes as visual terrain.
- Launch Gazebo worlds from generated SDF files.
- Bridge Gazebo topics to ROS 2.
- Drive a simple differential-drive robot with keyboard teleoperation.
- Generate Nav2 maps from slope and roughness.
- Generate semantic keepout and speed masks.
- Generate visibility and radio-quality masks from DEM line-of-sight analysis.

## Dataset layout

The input dataset should contain an `images` directory:

```text
/path/to/dataset/
└── images/
    ├── image_001.jpg
    ├── image_002.jpg
    └── ...
```

After ODM processing, the dataset can contain:

```text
/path/to/dataset/
├── images/
├── odm_dem/
├── odm_georeferencing/
├── odm_meshing/
├── odm_orthophoto/
├── odm_texturing/
├── odm_texturing_25d/
├── terrain/
└── gazebo_world/
```

Important ODM outputs used by this project:

```text
odm_orthophoto/odm_orthophoto.tif
odm_dem/dtm.tif
odm_dem/dsm.tif
odm_texturing/odm_textured_model_geo.obj
odm_texturing_25d/odm_textured_model_geo.obj
odm_georeferencing/odm_georeferenced_model.laz
odm_meshing/odm_mesh.ply
```

## Installation

Install ROS 2 and Gazebo:

```bash
./scripts/install_ros_gazebo_ubuntu.sh
```

Create and activate a Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration

Edit `Makeconfig`.

Core paths:

```make
DATASET_DIR ?= /path/to/dataset
PROJECT_NAME ?= project
REPO_ROOT ?= $(CURDIR)
```

ROS / Gazebo:

```make
ROS_DISTRO ?= humble
ROS_DOMAIN_ID ?= 30
ROS_LOCALHOST_ONLY ?= 0
RMW_IMPLEMENTATION ?= rmw_fastrtps_cpp
```

ODM:

```make
ODM_IMAGE ?= opendronemap/odm:latest
ODM_ORTHOPHOTO_RESOLUTION ?= 2.5
ODM_MESH_SIZE ?= 100000
ODM_MESH_OCTREE_DEPTH ?= 8
ODM_DSM ?= 1
ODM_DTM ?= 1
```

Terrain and world:

```make
HEIGHTMAP_SOURCE ?= dtm
HEIGHTMAP_PRIMARY_FORMAT ?= 8
HEIGHTMAP_MAX_SIDE ?= 2049

WORLD_FILE ?= generated_world.sdf
WORLD_TEMPLATE ?= templates/world.sdf.in

ADD_MESH ?= 1
WORLD_XY_SCALE ?= 1.0
WORLD_Z_SCALE ?= 1.0
Z_ORIGIN_MODE ?= center
MESH_X_OFFSET ?= 0.0
MESH_Y_OFFSET ?= 0.0
MESH_Z_DELTA ?= 0.0
```

Semantic and visibility analysis:

```make
SEMANTIC_MODEL_ID ?= optimum/segformer-b0-finetuned-ade-512-512
SEMANTIC_ALPHA ?= 0.35

OBS_X_M ?= 0.0
OBS_Y_M ?= 0.0
OBS_HEIGHT_M ?= 2.0
TARGET_HEIGHT_M ?= 0.5
MAX_VIS_RANGE_M ?= 300.0
```

## Quickstart

Build the Gazebo world:

```bash
make world
```

Launch Gazebo:

```bash
make gazebo
```

Start the ROS 2 bridge in another terminal:

```bash
make bridge
```

Drive the robot in another terminal:

```bash
make teleop
```

Make sure the Gazebo simulation is unpaused.

## Main Make targets

Dataset and configuration:

```bash
make print-config
make dataset-check
```

ODM processing:

```bash
make odm
make odm-ortho
make odm-dem
make odm-mesh
```

Terrain and Gazebo world generation:

```bash
make heightmap
make world
make gazebo
```

ROS 2 bridge and robot control:

```bash
make bridge
make teleop
make spawn-robot
make laser-tf
```

Nav2 assets:

```bash
make nav-assets
make nav-debug
make localization
make navigation
make rviz
```

Semantic assets:

```bash
make semantic
make semantic-class-map
make semantic-masks
```

Visibility and radio masks:

```bash
make visibility-masks
```

Cleaning:

```bash
make clean-odm
make clean-heightmap
make clean-semantic
make clean-nav-assets
make clean-semantic-masks
make clean-visibility
make clean-world
make clean-all
```

## Generated outputs

Typical terrain outputs:

```text
terrain/heightmap.png
terrain/heightmap8.png
terrain/heightmap16.png
terrain/terrain_meta.json
```

Typical Gazebo output:

```text
gazebo_world/generated_world.sdf
```

Typical Nav2 outputs:

```text
terrain/nav2_map.pgm
terrain/nav2_map.yaml
terrain/traversability.png
terrain/slope.png
terrain/roughness.png
terrain/nav_debug_overlay.png
```

Typical semantic outputs:

```text
terrain/semantic_class_ids.png
terrain/semantic_class_overlay.png
terrain/keepout_mask.pgm
terrain/keepout_mask.yaml
terrain/speed_mask.pgm
terrain/speed_mask.yaml
```

Typical visibility outputs:

```text
terrain/visibility_keepout_mask.pgm
terrain/visibility_keepout_mask.yaml
terrain/radio_speed_mask.pgm
terrain/radio_speed_mask.yaml
terrain/visibility_overlay.png
```

## Terrain strategy

The recommended simulation setup is:

```text
heightmap = collision surface
ODM mesh  = visual surface
```

This is usually more stable than using the full photogrammetry mesh as collision geometry.

Recommended driving configuration:

```make
HEIGHTMAP_SOURCE := dtm
ADD_MESH := 1
WORLD_XY_SCALE := 1.0
WORLD_Z_SCALE := 1.0
Z_ORIGIN_MODE := center
MESH_Z_DELTA := 0.0
```

Use `dtm` for smoother ground driving.

Use `dsm` when above-ground objects such as trees or buildings should influence the elevation surface.

## Mesh visual strategy

The visual mesh is selected in this preferred order:

```text
odm_texturing_25d/odm_textured_model_geo.obj
odm_texturing_25d/odm_textured_model.obj
odm_texturing/odm_textured_model_geo.obj
odm_texturing/odm_textured_model.obj
```

The 2.5D mesh is usually smoother for terrain-like worlds.

The full 3D mesh can look more photogrammetric, but it may contain holes, vertical artifacts, and vegetation artifacts.

## Robot model

The default robot is stored in:

```text
gazebo/models/simple_bot/model.sdf
```

It is a simple differential-drive robot with:

- `base_link`;
- left and right wheel joints;
- caster wheel;
- lidar sensor;
- `/cmd_vel` input;
- `/odom` output;
- `/scan` output;
- `/tf` output.

## Viewing outputs

View ODM mesh:

```bash
meshlab odm_texturing/odm_textured_model_geo.obj
```

View ODM point cloud:

```bash
cloudcompare odm_georeferencing/odm_georeferenced_model.laz
```

Launch the generated Gazebo world directly:

```bash
ign gazebo -v 4 -r "$DATASET_DIR/gazebo_world/generated_world.sdf"
```

## Limitations

This project is experimental.

Known limitations:

- photogrammetry meshes may contain holes and artifacts;
- mesh visuals and heightmap collision surfaces may not align perfectly;
- DTM is smoother for driving but may not match the visual mesh exactly;
- DSM can include trees and buildings, which can make driving rough;
- full mesh collision can be slow or unstable;
- semantic segmentation quality depends on the model and orthophoto quality;
- visibility masks are approximate and DEM-dependent;
- Gazebo performance depends on GPU, mesh size, and heightmap size.
