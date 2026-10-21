#!/bin/bash
# usage: run_box.sh SCRIPT [args]  -- syncs this dir to the box work dir and runs SCRIPT niced there, detached (nohup), ROS Humble sourced. Log: out/SCRIPT.log
# BOXSSH overrides the route (default: Tailscale, which worked when the campus route timed out).
D=$(cd "$(dirname "$0")" && pwd); H=rcp2026@100.87.133.60; W=rcp-Gappler/log/t59-fastlivo/log/t35f-drift
SSHO="-o HostKeyAlias=10.91.242.76 -o ConnectTimeout=15"
scp -q $SSHO "$D"/*.py "$D"/../t35f_route/route_common.py $H:$W/ || exit 1
ssh $SSHO $H "cd $W && source /opt/ros/humble/setup.bash && export T35_CONVERTER=\$HOME/rcp-Gappler/log/t59-fastlivo/log/t35f-live-stage/src/robot_slam/scripts/livox_custom_to_cloud.py MPLBACKEND=Agg OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 && nohup env $BOXENV nice -n 15 python3 $* > out/${1%.py}${LOGSUF}.log 2>&1 < /dev/null & echo started $1"
