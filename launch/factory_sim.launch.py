"""Launch Gazebo Classic with three factory machines + TurtleBot3.

Requires: gazebo_ros, turtlebot3_gazebo (and TURTLEBOT3_MODEL set, e.g. burger).
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    AppendEnvironmentVariable,
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
def generate_launch_description():
    # spawn_turtlebot3.launch.py reads this from os.environ at parse time
    os.environ.setdefault("TURTLEBOT3_MODEL", "burger")

    pkg_share = get_package_share_directory("voice_robot_control")
    pkg_gazebo_ros = get_package_share_directory("gazebo_ros")
    pkg_tb3_gazebo = get_package_share_directory("turtlebot3_gazebo")

    world_path = os.path.join(pkg_share, "worlds", "factory_machines.world")
    models_path = os.path.join(pkg_share, "models")
    tb3_models = os.path.join(pkg_tb3_gazebo, "models")

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")
    x_pose = LaunchConfiguration("x_pose", default="0.0")
    y_pose = LaunchConfiguration("y_pose", default="0.0")

    # Ensure our machine models + TurtleBot3 models are findable
    set_model_path = AppendEnvironmentVariable(
        "GAZEBO_MODEL_PATH",
        models_path + os.pathsep + tb3_models,
    )

    set_tb3_model = SetEnvironmentVariable(
        name="TURTLEBOT3_MODEL",
        value=os.environ["TURTLEBOT3_MODEL"],
    )

    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gzserver.launch.py")
        ),
        launch_arguments={"world": world_path}.items(),
    )

    gzclient = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, "launch", "gzclient.launch.py")
        ),
    )

    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_tb3_gazebo, "launch", "robot_state_publisher.launch.py")
        ),
        launch_arguments={"use_sim_time": use_sim_time}.items(),
    )

    spawn_turtlebot = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_tb3_gazebo, "launch", "spawn_turtlebot3.launch.py")
        ),
        launch_arguments={
            "x_pose": x_pose,
            "y_pose": y_pose,
        }.items(),
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("x_pose", default_value="0.0"),
            DeclareLaunchArgument("y_pose", default_value="0.0"),
            set_tb3_model,
            set_model_path,
            gzserver,
            gzclient,
            robot_state_publisher,
            spawn_turtlebot,
        ]
    )
