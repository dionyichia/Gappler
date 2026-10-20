source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=177 ROS_LOCALHOST_ONLY=1 ROS2CLI_NO_DAEMON=1
W=~/rcp-Gappler/log/t35e-reloc/stub
export AMENT_PREFIX_PATH=$W/prefix:$AMENT_PREFIX_PATH
echo "domain 177 before: nodes=[$(ros2 node list 2>/dev/null | tr '\n' ' ')]"
for v in with_param control; do
  setsid ros2 launch $W/$v.launch.py > $W/$v.log 2>&1 < /dev/null &
  LP=$!
  for i in $(seq 1 40); do ros2 node list 2>/dev/null | grep -q xnode_vehicle && break; sleep 1; done
  echo "== $v: xnode_vehicle up after ~${i}s; ros2 param get: $(ros2 param get /xnode_vehicle pub_tf 2>&1)"; grep -h "STUB" $W/$v.log
  kill -INT -$LP 2>/dev/null; sleep 3; kill -TERM -$LP 2>/dev/null; sleep 1
done
echo "domain 177 after: nodes=[$(ros2 node list 2>/dev/null | tr '\n' ' ')]"
