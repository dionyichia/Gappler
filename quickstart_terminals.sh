#!/usr/bin/env bash
# Opens a tmux session for a robot session on the lab box: one pane per process, every pane set up
# the T1.6 way (its subsystem's env file, ROS domain 91, localhost only).
#
#   ./quickstart_terminals.sh gripper|arm|grasp|nav|aria|full [--dry] [--print] [--anygrasp]
#
# Drivers, the e-stop, cameras and monitors start on their own. Anything that moves the arm or the
# base is typed into its pane but not sent: press Enter there yourself.
#   --dry    type every command, start nothing (to look before you run)
#   --print  list the panes and exit, no tmux
#   --anygrasp  grasp and full: also start the AnyGrasp detector (step 7, T1.17). Off by default:
#               it takes the GPU, and nothing reads it while use_simple_execute is true
# Refuses to start (except --dry) if what it would start, or a bench run, is already up on the box.
# The session is named after the layout. Detach: Ctrl-b d. Run again to reattach.
# Close: tmux kill-session -t <layout>.
set -u
# tmux matches -t by name prefix, so "grasp" would find someone's "grasp_t1_24". "=" makes it exact.
R="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS="export ROS_DOMAIN_ID=91 ROS_LOCALHOST_ONLY=1"
LAYOUT="${1:-}"
DRY=0 PRINT=0 ANYGRASP=0
for a in "${@:2}"; do
  case "$a" in --dry) DRY=1 ;; --print) PRINT=1 ;; --anygrasp) ANYGRASP=1 ;; *) echo "unknown option: $a" >&2; exit 2 ;; esac
done

WINDOWS=() PANES=() ENV_OVERRIDE=""
win() { WIN=$1; WINDOWS+=("$1"); }
# pane auto|typed <subsystem whose env file to source> <command>
pane() { PANES+=("$WIN"$'\t'"$1"$'\t'"${ENV_OVERRIDE:-$2}"$'\t'"$3"); }

ESTOP="python3 $R/arm/estop/estop.py"
JOINT_RATE="ros2 topic hz -w 10 /joint_states"

lay_gripper() {
  win gripper
  pane auto arm "$ESTOP"
  pane auto arm "ros2 launch rm_driver rm_65_driver.launch.py"
  pane auto arm "$JOINT_RATE"
  pane typed arm 'ros2 topic pub --once /rm_driver/set_gripper_position_cmd rm_ros_interfaces/msg/Gripperset "{position: 1000, block: false, timeout: 0}"'
}

lay_arm() {
  win arm
  pane auto arm "$ESTOP"
  pane auto arm "ros2 launch arm_bringup arm_bringup.launch.py"
  pane auto arm "$JOINT_RATE"
  pane typed arm ""
}

# The T1.25 order (GRASP_BRINGUP_STEPS): the state machine last, by hand. Segmentation (T2.1) is
# the segmentation service plus the grasp client. The service refuses to start if one already runs
# on this channel, and the client then uses that one. "nomask" leaves segmentation out.
lay_grasp() {
  local serial
  serial=$(PYTHONPATH="$R/shared" python3 -c 'from gappler_common import camera_serial; print(camera_serial("wrist_camera"))') \
    || { echo "could not read the wrist camera serial from config" >&2; exit 1; }
  win grasp
  pane auto arm "$ESTOP"
  pane auto grasp "ros2 launch arm_bringup arm_bringup.launch.py"
  # The leading _ makes the launch file read the serial as text, as the grasp launcher does.
  # 640x480x15: SAM 3 is ~40 % faster a call than at the driver default 1280x720, and the driver
  # uses a third of the CPU (T2.11). No point cloud: only grasp_viz's RViz display reads it.
  pane auto arm "ros2 launch realsense2_camera rs_launch.py \"serial_no:='_$serial'\" align_depth.enable:=true rgb_camera.color_profile:=640x480x15 depth_module.depth_profile:=640x480x15"
  if [ "${1:-}" != nomask ]; then
    pane auto shared_services "python $R/shared_services/segmentation/segmentation_service.py"
    pane auto grasp "python $R/grasp/grasp_segmentation_client/grasp_segmentation_client.py"
  fi
  # Its own venv (T1.10). Run from its folder: the checkpoint path is relative
  ((ANYGRASP)) && pane auto grasp "cd $R/grasp/anygrasp_node && $R/grasp/anygrasp_venv/.venv/bin/python anygrasp_detection_node.py --checkpoint_path log/checkpoint_detection.tar"
  pane auto arm "ros2 topic echo /pipeline_state"
  # RViz on the box monitor (T1.34): the arm, AnyGrasp's points and the candidates
  pane auto grasp "python3 $R/grasp/grasp_viz/grasp_viz.py"
  pane auto grasp "DISPLAY=\${DISPLAY:-:1} rviz2 -d $R/grasp/grasp_viz/rviz_config.rviz"
  pane typed grasp "ros2 launch grasp_state_machine grasp_state_machine.launch.py"
  # One attempt per request (T1.25). Send once IDLE shows and the client is publishing a centroid
  pane typed grasp "ros2 topic pub --once /manipulator/grasp_request std_msgs/msg/Empty"
}

lay_nav() {
  win nav
  pane auto nav "ros2 launch robot_slam slam_localization.launch.py"
  pane auto nav "ros2 topic hz -w 10 /livox/lidar"
  pane typed nav "ros2 run simple_teleop teleop"
}

lay_aria() {
  win aria
  pane auto aria "python $R/aria/aria_app/main.py"
  pane auto aria "python $R/aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py"
}

lay_full() {
  ENV_OVERRIDE=global
  lay_grasp
  lay_aria
  echo "full: nav left out. slam_localization.launch.py resets enp2s0 to 192.168.1.5 only,"
  echo "which would most likely cut the arm's 192.168.1.10 link (T3.9). Run nav on its own."
}

# What each layout must not find already running.
ARM_BUSY='rm_driver|arm_bringup|grasp_state_machine|start_camera_arm_grasp|grasp_orchestrator'
CAMERA_BUSY='realsense2_camera|rs_launch|anygrasp_detection_node'
NAV_BUSY='livox|slam_toolbox|slam_localization|slam_mapping|nav2|xpkg|echo_plus|simple_teleop|goto_glasses'
ARIA_BUSY='aria_app/main.py'
case "$LAYOUT" in
  gripper|arm) BUSY="$ARM_BUSY" ;;
  grasp)       BUSY="$ARM_BUSY|$CAMERA_BUSY" ;;
  nav)         BUSY="$NAV_BUSY" ;;
  aria)        BUSY="$ARIA_BUSY" ;;
  full)        BUSY="$ARM_BUSY|$CAMERA_BUSY|$ARIA_BUSY" ;;
  *) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
"lay_$LAYOUT"

if ((PRINT)); then
  for p in "${PANES[@]}"; do
    IFS=$'\t' read -r w mode env cmd <<<"$p"
    printf '%-8s %-5s %-6s %s\n' "$w" "$mode" "$env" "$cmd"
  done
  exit 0
fi

if ! tmux has-session -t "=$LAYOUT" 2>/dev/null; then
  found="" cams="" gpu=""
  ((DRY)) || found=$(ps -eo pid,user,etime,args | grep -iE "$BUSY|Runner.Worker|bench/run.sh" | grep -v grep)
  ((DRY)) || case "$LAYOUT" in grasp|full) cams=$(fuser /dev/video* 2>/dev/null) ;; esac
  ((DRY)) || case "$LAYOUT" in grasp|aria|full) gpu=$(nvidia-smi --query-compute-apps=pid,process_name --format=csv,noheader 2>/dev/null \
    | grep -v gnome-remote-desktop) ;; esac   # the remote desktop always holds ~120 MiB
  if [ -n "$found$cams$gpu" ]; then
    echo "Not starting. Already in use:"
    [ -n "$found" ] && echo "$found"
    [ -n "$cams" ] && echo "cameras held by pids:$cams"
    [ -n "$gpu" ] && echo "GPU: $gpu"
    exit 1
  fi

  declare -A FIRST=()
  for w in "${WINDOWS[@]}"; do
    if [ "$w" = "${WINDOWS[0]}" ]; then
      FIRST[$w]=$(tmux new-session -d -s "$LAYOUT" -n "$w" -c "$R" -P -F '#{pane_id}' bash)
    else
      FIRST[$w]=$(tmux new-window -t "=$LAYOUT:" -n "$w" -c "$R" -P -F '#{pane_id}' bash)
    fi
  done

  TYPED=()
  for p in "${PANES[@]}"; do
    IFS=$'\t' read -r w mode env cmd <<<"$p"
    if [ -n "${FIRST[$w]}" ]; then
      id=${FIRST[$w]}; FIRST[$w]=""
    else
      id=$(tmux split-window -t "=$LAYOUT:$w" -c "$R" -P -F '#{pane_id}' bash)
      tmux select-layout -t "=$LAYOUT:$w" tiled >/dev/null
    fi
    if [ "$env" = global ]; then envfile="$R/global_env.sh"; else envfile="$R/$env/${env}_env.sh"; fi
    setup="source $envfile && $ROS"
    if [ "$mode" = auto ] && ((!DRY)); then
      tmux send-keys -t "$id" "$setup && $cmd" Enter
    else
      tmux send-keys -t "$id" "$setup" Enter
      [ -n "$cmd" ] && TYPED+=("$id"$'\t'"$cmd")
    fi
  done
  # Type the waiting commands once the env has loaded, so they land on a fresh prompt.
  sleep 3
  for t in "${TYPED[@]}"; do
    IFS=$'\t' read -r id cmd <<<"$t"
    tmux send-keys -t "$id" -l "$cmd"
  done
  tmux set -t "=$LAYOUT" mouse on >/dev/null
  tmux select-window -t "=$LAYOUT:${WINDOWS[0]}"
fi

if [ -n "${TMUX:-}" ]; then tmux switch-client -t "=$LAYOUT"; else tmux attach -t "=$LAYOUT"; fi
