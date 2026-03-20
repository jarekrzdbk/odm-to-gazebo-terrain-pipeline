# ODM → Gazebo World Pipeline

## Scope

The core world-building path is:

1. run OpenDroneMap (ODM) to get orthophoto / DSM / DTM / textured mesh
2. convert DTM or DSM into a Gazebo heightmap
3. generate a Gazebo world that includes:
   - terrain from the heightmap
   - optional visual mesh from ODM
4. launch Gazebo
5. bridge the robot topics to ROS 2
6. drive the robot with teleop

This repo targets **Ubuntu 22.04 + ROS 2 Humble + Gazebo Fortress via `ros-humble-ros-gz`**.

## Configuration model

Defaults live in `Makeconfig`.

### 1. Install local ROS 2 + Gazebo

```bash
./scripts/install_ros_gazebo_ubuntu.sh
```

### 2. Install Python prerequisites

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Build gazebo world

```bash
make world
```

### 4. Launch the simulator

```bash
make gazebo
```

Terminal 2:

```bash
make bridge
```

Terminal 3:

```bash
make teleop
```
