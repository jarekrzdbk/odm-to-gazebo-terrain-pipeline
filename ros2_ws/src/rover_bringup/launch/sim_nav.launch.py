from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    pkg_share = FindPackageShare("rover_bringup")
    use_sim_time = LaunchConfiguration("use_sim_time")
    bridge_config = LaunchConfiguration("bridge_config")
    map_yaml = LaunchConfiguration("map")
    keepout_yaml = LaunchConfiguration("keepout_yaml")
    speed_yaml = LaunchConfiguration("speed_yaml")
    visibility_keepout_yaml = LaunchConfiguration("visibility_keepout_yaml")
    radio_speed_yaml = LaunchConfiguration("radio_speed_yaml")
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([pkg_share, "launch", "nav2_stack.launch.py"])),
        launch_arguments={"use_sim_time": use_sim_time, "map": map_yaml, "keepout_yaml": keepout_yaml, "speed_yaml": speed_yaml,
                          "visibility_keepout_yaml": visibility_keepout_yaml, "radio_speed_yaml": radio_speed_yaml}.items())
    bridge = ExecuteProcess(cmd=["ros2","run","ros_gz_bridge","parameter_bridge","--ros-args","-p",["config_file:=", bridge_config]], shell=False, output="screen")
    ekf = Node(package="robot_localization", executable="ekf_node", name="ekf_filter_node", output="screen",
               parameters=[PathJoinSubstitution([pkg_share, "config", "ekf.yaml"]), {"use_sim_time": use_sim_time}])
    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("map"),
        DeclareLaunchArgument("keepout_yaml"),
        DeclareLaunchArgument("speed_yaml"),
        DeclareLaunchArgument("visibility_keepout_yaml"),
        DeclareLaunchArgument("radio_speed_yaml"),
        DeclareLaunchArgument("bridge_config", default_value=PathJoinSubstitution([pkg_share, "config", "bridge.yaml"])),
        bridge, ekf, nav2_launch])
