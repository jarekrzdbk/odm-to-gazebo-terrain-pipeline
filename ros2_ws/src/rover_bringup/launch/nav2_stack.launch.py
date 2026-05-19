from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    use_sim_time = LaunchConfiguration("use_sim_time")
    map_yaml = LaunchConfiguration("map")
    keepout_yaml = LaunchConfiguration("keepout_yaml")
    speed_yaml = LaunchConfiguration("speed_yaml")
    visibility_keepout_yaml = LaunchConfiguration("visibility_keepout_yaml")
    radio_speed_yaml = LaunchConfiguration("radio_speed_yaml")
    params_file = LaunchConfiguration("params_file")
    autostart = LaunchConfiguration("autostart")

    nav2_bringup = PathJoinSubstitution([FindPackageShare("nav2_bringup"), "launch", "bringup_launch.py"])
    nav2 = IncludeLaunchDescription(PythonLaunchDescriptionSource(nav2_bringup),
        launch_arguments={"map": map_yaml, "use_sim_time": use_sim_time, "params_file": params_file, "autostart": autostart}.items())

    filter_nodes = [
        Node(package="nav2_map_server", executable="map_server", name="keepout_filter_mask_server", output="screen",
             parameters=[{"yaml_filename": keepout_yaml, "topic_name": "keepout_filter_mask", "frame_id": "map", "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="costmap_filter_info_server", name="keepout_costmap_filter_info_server", output="screen",
             parameters=[{"type": 0, "filter_info_topic": "keepout_costmap_filter_info", "mask_topic": "keepout_filter_mask", "base": 0.0, "multiplier": 1.0, "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="map_server", name="speed_filter_mask_server", output="screen",
             parameters=[{"yaml_filename": speed_yaml, "topic_name": "speed_filter_mask", "frame_id": "map", "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="costmap_filter_info_server", name="speed_costmap_filter_info_server", output="screen",
             parameters=[{"type": 1, "filter_info_topic": "speed_costmap_filter_info", "mask_topic": "speed_filter_mask", "base": 0.0, "multiplier": 1.0, "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="map_server", name="visibility_keepout_filter_mask_server", output="screen",
             parameters=[{"yaml_filename": visibility_keepout_yaml, "topic_name": "visibility_keepout_filter_mask", "frame_id": "map", "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="costmap_filter_info_server", name="visibility_keepout_costmap_filter_info_server", output="screen",
             parameters=[{"type": 0, "filter_info_topic": "visibility_keepout_costmap_filter_info", "mask_topic": "visibility_keepout_filter_mask", "base": 0.0, "multiplier": 1.0, "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="map_server", name="radio_speed_filter_mask_server", output="screen",
             parameters=[{"yaml_filename": radio_speed_yaml, "topic_name": "radio_speed_filter_mask", "frame_id": "map", "use_sim_time": use_sim_time}]),
        Node(package="nav2_map_server", executable="costmap_filter_info_server", name="radio_speed_costmap_filter_info_server", output="screen",
             parameters=[{"type": 1, "filter_info_topic": "radio_speed_costmap_filter_info", "mask_topic": "radio_speed_filter_mask", "base": 0.0, "multiplier": 1.0, "use_sim_time": use_sim_time}]),
        Node(package="nav2_lifecycle_manager", executable="lifecycle_manager", name="lifecycle_manager_costmap_filters", output="screen",
             parameters=[{"use_sim_time": use_sim_time, "autostart": autostart, "node_names": [
                 "keepout_filter_mask_server","keepout_costmap_filter_info_server","speed_filter_mask_server","speed_costmap_filter_info_server",
                 "visibility_keepout_filter_mask_server","visibility_keepout_costmap_filter_info_server","radio_speed_filter_mask_server","radio_speed_costmap_filter_info_server"]}]),
    ]

    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("autostart", default_value="true"),
        DeclareLaunchArgument("map"),
        DeclareLaunchArgument("keepout_yaml"),
        DeclareLaunchArgument("speed_yaml"),
        DeclareLaunchArgument("visibility_keepout_yaml"),
        DeclareLaunchArgument("radio_speed_yaml"),
        DeclareLaunchArgument("params_file", default_value=PathJoinSubstitution([FindPackageShare("rover_bringup"), "config", "nav2_params.yaml"])),
        nav2, *filter_nodes])
