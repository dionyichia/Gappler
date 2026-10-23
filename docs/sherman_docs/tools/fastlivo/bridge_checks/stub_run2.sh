W=~/rcp-Gappler/log/t35e-reloc/stub
cat > $W/immediate.launch.py <<PY
from launch import LaunchDescription
from launch.actions import GroupAction
from launch_ros.actions import Node, SetParameter
def generate_launch_description():
    # positive control: same SetParameter, but the node starts at once (no TimerAction)
    return LaunchDescription([GroupAction(actions=[SetParameter(name="pub_tf", value=False), Node(package="xpkg_vehicle", executable="xnode_vehicle", name="xnode_vehicle", output="screen")])])
PY
sed 's/GroupAction(actions=\[SetParameter/GroupAction(scoped=False, actions=[SetParameter/' $W/with_param.launch.py > $W/unscoped.launch.py
grep -c "scoped=False" $W/unscoped.launch.py
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=177 ROS_LOCALHOST_ONLY=1 ROS2CLI_NO_DAEMON=1 AMENT_PREFIX_PATH=$W/prefix:$AMENT_PREFIX_PATH
for v in immediate unscoped; do
  setsid ros2 launch $W/$v.launch.py > $W/$v.log 2>&1 < /dev/null &
  LP=$!
  for i in $(seq 1 40); do ros2 node list 2>/dev/null | grep -q xnode_vehicle && break; sleep 1; done
  echo "== $v: xnode_vehicle up after ~${i}s; ros2 param get: $(ros2 param get /xnode_vehicle pub_tf 2>&1)"; grep -h "STUB" $W/$v.log
  kill -INT -$LP 2>/dev/null; sleep 3; kill -TERM -$LP 2>/dev/null; sleep 1
done
echo "domain 177 after: nodes=[$(ros2 node list 2>/dev/null | tr '\n' ' ')]"
