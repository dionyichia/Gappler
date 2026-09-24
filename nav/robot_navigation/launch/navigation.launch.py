from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch_ros.substitutions import FindPackageShare
import os
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    
    nav_pkg_dir = get_package_share_directory('robot_navigation')
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    
    nav2_params = os.path.join(nav_pkg_dir, 'config', 'nav2_params.yaml')
    map_file = os.path.join(nav_pkg_dir, 'maps', 'my_map.yaml')
    
    use_sim_time = LaunchConfiguration('use_sim_time')
    map_arg = LaunchConfiguration('map')
    
    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false'
    )
    
    declare_map = DeclareLaunchArgument(
        'map',
        default_value=map_file
    )
    
    echo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('xpkg_demo'),
                'demo_vehicle/ROS2/launch',
                'bringup_basic_ctrl.launch.py'
            ])
        ])
    )
    
    livox_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare('livox_ros_driver2'),
                'launch',
                'msg_MID360_launch.py'
            ])
        ])
    )
    
    pointcloud_to_laserscan = Node(
        package='pointcloud_to_laserscan',
        executable='pointcloud_to_laserscan_node',
        name='pointcloud_to_laserscan',
        parameters=[{
            'target_frame': 'livox_frame',
            'transform_tolerance': 0.01,
            'min_height': -0.5,
            'max_height': 2.0,
            'angle_min': -3.14159,
            'angle_max': 3.14159,
            'angle_increment': 0.0087,
            'scan_time': 0.1,
            'range_min': 0.5,
            'range_max': 30.0,
            'use_inf': True,
            'inf_epsilon': 1.0,
        }],
        remappings=[
            ('cloud_in', '/livox/lidar'),
            ('scan', '/livox/lidar_2d')
        ]
    )
    
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')
        ]),
        launch_arguments={
            'map': map_arg,
            'use_sim_time': use_sim_time,
            'params_file': nav2_params
        }.items()
    )
    
    return LaunchDescription([
        declare_use_sim_time,
        declare_map,
        echo_launch,
        livox_launch,
        pointcloud_to_laserscan,
        nav2_launch,
    ])
