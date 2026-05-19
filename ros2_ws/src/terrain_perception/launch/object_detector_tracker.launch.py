from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("use_sim_time", default_value="true"),
        DeclareLaunchArgument("image_topic", default_value="/camera/image_raw"),
        DeclareLaunchArgument("model_path", default_value=""),
        Node(package="terrain_perception", executable="object_detector_tracker", name="object_detector_tracker",
             parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time"), "image_topic": LaunchConfiguration("image_topic"), "model_path": LaunchConfiguration("model_path")}],
             output="screen"),
    ])
