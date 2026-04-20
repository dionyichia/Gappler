from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    power_ini_path = PathJoinSubstitution([
        FindPackageShare("xpkg_power"),
        "ini",
        "device_id_list.ini"
    ])
 
    xnode_comm = Node(
        name="xnode_comm",
        package="xpkg_comm",
        executable="xnode_comm",
        output="screen",
        parameters=[{
            "dev_list": True,
            "com_enable": True,
            "com_channel_common": False,
            "com_channel_xstd": True,
        }]
    )
 
    xnode_power = Node(
        name="xnode_power",
        package="xpkg_power",
        executable="xnode_power",
        output="screen",
        parameters=[{
            "ini_path": power_ini_path,
            "test_mode": False,
            "manu_enable": False,
            "manu_state": True,
            "beep_enable": True,
            "rec_votage": 1.0,
            "min_current": 0.2,
        }]
    )
    
    launch_description = LaunchDescription([xnode_comm, xnode_power])
    
    return launch_description
