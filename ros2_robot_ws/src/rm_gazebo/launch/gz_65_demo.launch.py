import os
import xacro
from launch import LaunchDescription
from launch.actions import ExecuteProcess, RegisterEventHandler
from launch_ros.actions import Node
from launch.event_handlers import OnProcessExit
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    package_name = 'rm_gazebo'
    robot_name_in_model = 'rm_65_description'

    # Locate your robot's URDF (Xacro) file
    pkg_share = get_package_share_directory(package_name)
    print(pkg_share)
    urdf_model_path = os.path.join(pkg_share, 'config', 'gazebo_65_description.urdf.xacro')
    print("---", urdf_model_path)

    # Parse Xacro -> URDF
    doc = xacro.parse(open(urdf_model_path))
    xacro.process_doc(doc)
    robot_description = {'robot_description': doc.toxml()}

    # --- Start Gazebo Fortress (Ignition) ---
    gazebo = ExecuteProcess(
        cmd=['ign', 'gazebo', '-r', 'empty.sdf'],
        output='screen'
    )

    # --- Publish robot_description to ROS ---
    node_robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'use_sim_time': True}, robot_description, {'publish_frequency': 15.0}],
        output='screen'
    )

    # --- Spawn robot into Gazebo Fortress ---
    spawn_entity = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'ros_gz_sim', 'create',
            '-topic', 'robot_description',
            '-name', robot_name_in_model
        ],
        output='screen'
    )

    # --- Load ROS 2 controllers ---
    load_joint_state_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active',
             'joint_state_broadcaster'],
        output='screen'
    )

    load_joint_trajectory_controller = ExecuteProcess(
        cmd=['ros2', 'control', 'load_controller', '--set-state', 'active',
             'rm_group_controller'],
        output='screen'
    )

    # --- Event chaining (spawn → joint_state → trajectory) ---
    evt1 = RegisterEventHandler(
        OnProcessExit(target_action=spawn_entity, on_exit=[load_joint_state_controller])
    )

    evt2 = RegisterEventHandler(
        OnProcessExit(target_action=load_joint_state_controller,
                      on_exit=[load_joint_trajectory_controller])
    )

    return LaunchDescription([
        gazebo,
        node_robot_state_publisher,
        spawn_entity,
        evt1,
        evt2,
    ])
