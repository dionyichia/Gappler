#!/usr/bin/env bash
# Stage this branch's T3.5f files on the lab box without touching its checkout or its install_nav overlay. Run from the repo root on the Mac:
#   bash docs/sherman_docs/tools/fastlivo/live/stage_t35f_live.sh
# Copies (ssh, no sudo): the robot_slam package source, the mapper container script, the two corrected YAMLs, the TF checker and the
# pre-check into STAGE, installs robot_slam into STAGE/prefix with cmake (ament_cmake, no compile, no colcon), and writes a sha256 manifest.
# Safe to repeat: the stage directory is rebuilt.
set -euo pipefail
BOX=${T35_BOX:-rcp2026@10.91.242.76}
# Tailscale route (campus route down): T35_BOX=rcp2026@100.87.133.60 T35_SSH_OPTS="-o HostKeyAlias=10.91.242.76"
SSH_OPTS=${T35_SSH_OPTS:-}
STAGE=${T35_STAGE:-rcp-Gappler/log/t59-fastlivo/log/t35f-live-stage}   # relative to the box home
LIVE=docs/sherman_docs/tools/fastlivo/live
[ -f "$LIVE/t35e_mapper_container.sh" ] || { echo "run from the repo root"; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/stage/src" "$tmp/stage/config"
cp -R nav/robot_slam "$tmp/stage/src/robot_slam"; find "$tmp/stage" -name __pycache__ -prune -exec rm -rf {} +
cp "$LIVE/t35e_mapper_container.sh" "$LIVE/tf_edge_check.py" "$LIVE/t35e_replay_precheck.sh" "$LIVE/launch_switch_check.py" "$tmp/stage/"
cp "$LIVE/config/t35c_stationary02_20261019_visual.yaml" "$LIVE/config/t35c_stationary02_20261019_camera.yaml" "$tmp/stage/config/"
tar -C "$tmp" -czf "$tmp/stage.tgz" stage
ssh $SSH_OPTS "$BOX" "rm -rf ~/$STAGE && mkdir -p ~/$STAGE"
scp -q $SSH_OPTS "$tmp/stage.tgz" "$BOX:$STAGE.tgz"
ssh $SSH_OPTS "$BOX" bash -s <<REMOTE
set -euo pipefail
cd ~ && tar -xzf $STAGE.tgz -C ~/$STAGE --strip-components=1 && rm $STAGE.tgz
cd ~/$STAGE && chmod +x t35e_mapper_container.sh tf_edge_check.py t35e_replay_precheck.sh
set +u; source /opt/ros/humble/setup.bash; set -u
cmake -S src/robot_slam -B build_robot_slam -DCMAKE_INSTALL_PREFIX=\$PWD/prefix > build_robot_slam.log 2>&1
cmake --install build_robot_slam >> build_robot_slam.log 2>&1
find . -type f -not -path './build_robot_slam/*' -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256
echo "staged in ~/$STAGE: \$(wc -l < MANIFEST.sha256) files, robot_slam installed in prefix/"
ls prefix/share/robot_slam/launch prefix/lib/robot_slam
REMOTE
