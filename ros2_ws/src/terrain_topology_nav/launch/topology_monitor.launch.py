from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("map_topic", default_value="/map"),
        Node(package="terrain_topology_nav", executable="topology_monitor", name="topology_monitor",
             parameters=[{"map_topic": LaunchConfiguration("map_topic"), "use_sim_time": LaunchConfiguration("use_sim_time")}],
             output="screen"),
    ])
