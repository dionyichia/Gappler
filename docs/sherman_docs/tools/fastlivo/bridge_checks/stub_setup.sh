set -e
W=~/rcp-Gappler/log/t35e-reloc/stub; rm -rf $W; mkdir -p $W
P=$W/prefix
for pkg in xpkg_comm xpkg_vehicle xpkg_demo; do mkdir -p $P/share/ament_index/resource_index/packages $P/share/$pkg; : > $P/share/ament_index/resource_index/packages/$pkg; done
mkdir -p $P/share/xpkg_vehicle/ini $P/share/xpkg_demo/demo_vehicle/ROS2/launch $P/share/xpkg_demo/demo_vehicle/ROS2/config $P/lib/xpkg_comm $P/lib/xpkg_vehicle
: > $P/share/xpkg_vehicle/ini/device_id_list.ini
cp ~/rcp-Gappler/nav/vendor/demo/demo_general_chassis/demo_vehicle/ROS2/launch/bringup_basic_ctrl.launch.py $P/share/xpkg_demo/demo_vehicle/ROS2/launch/
cat > $P/lib/xpkg_vehicle/xnode_vehicle <<PY
#!/usr/bin/env python3
# stub: declares pub_tf the way the real driver does (ros2_interface.cpp:128, default true), reads it once, then idles. Sends nothing.
import rclpy
from rclpy.node import Node
rclpy.init()
n = Node("xnode_vehicle")
n.declare_parameter("pub_tf", True)
print("STUB xnode_vehicle read pub_tf =", n.get_parameter("pub_tf").value, flush=True)
rclpy.spin(n)
PY
cat > $P/lib/xpkg_comm/xnode_comm <<PY
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
rclpy.init()
n = Node("xnode_comm")
rclpy.spin(n)
PY
chmod +x $P/lib/xpkg_vehicle/xnode_vehicle $P/lib/xpkg_comm/xnode_comm
cat > $W/with_param.launch.py <<PY
from launch import LaunchDescription
from launch.actions import GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import SetParameter
from launch_ros.substitutions import FindPackageShare
inc = IncludeLaunchDescription(PythonLaunchDescriptionSource([PathJoinSubstitution([FindPackageShare("xpkg_demo"), "demo_vehicle/ROS2/launch", "bringup_basic_ctrl.launch.py"])]))
def generate_launch_description():
    return LaunchDescription([GroupAction(actions=[SetParameter(name="pub_tf", value=False), inc])])
PY
sed 's/SetParameter(name="pub_tf", value=False), //' $W/with_param.launch.py > $W/control.launch.py
echo staged
