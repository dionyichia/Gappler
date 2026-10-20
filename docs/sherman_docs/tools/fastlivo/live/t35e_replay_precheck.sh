#!/usr/bin/env bash
# T3.5e replay pre-check. READ-ONLY: lists who and what is using the box and says BLOCKED or CLEAR. Needs no sudo, stops nothing.
# T35_MY_TMUX=<name> excludes your own tmux session from the "attached" test. Exit 0 = CLEAR, 1 = BLOCKED.
set -u
MINE=${T35_MY_TMUX:-}
blocked=0; why() { echo "BLOCKED: $*"; blocked=1; }
echo "== time, load, memory"; date; uptime; free -h | sed -n 1,2p
echo; echo "== logins (all share the rcp2026 account; remote host shown where ssh)"; who
echo; echo "== processes by user other than rcp2026 (not system daemons)"
ps -eo user:14,pid,etime,pcpu,pmem,args --sort=-pcpu | awk 'NR==1 || ($1!="rcp2026" && $1!="root" && $1!~/^(systemd|messagebus|avahi|colord|rtkit|gdm|syslog|polkitd|_chrony|nvidia-persistenced|whoopsie|kernoops|dnsmasq|cups-browsed|www-data|nobody)/)' | cut -c1-150 | head -15
echo; echo "== top CPU processes (all users)"; ps -eo user:12,pid,etime,pcpu,pmem,args --sort=-pcpu | cut -c1-150 | head -12
echo; echo "== hardware-using or robot processes (CLAUDE.md check)"
hits=$(ps -eo pid,user,etime,args | grep -iE "[r]ealsense|[r]s_launch|[r]os2 launch|[b]ench/run.sh|[R]unner.Worker|[r]m_driver|[f]astlivo_mapping|[x]node_vehicle|[l]ivox_ros_driver2_node|[d]ocker run|[c]ontainerd-shim" | cut -c1-160)
if [ -n "$hits" ]; then echo "$hits"; why "robot, camera, mapper, CI or container processes are running (list above)"; else echo "(none)"; fi
echo; echo "== camera / lidar device users"; fuser -v /dev/video* 2>&1 | head -5
echo; echo "== GPU"; nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader
# the remote-desktop capture daemon and the desktop compositor show up here but are not someone's compute job
gp=$(nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader 2>/dev/null | grep -vE "gnome-remote-desktop|Xorg|gnome-shell")
if [ -n "$gp" ]; then echo "$gp"; why "GPU compute processes are running (list above)"; else echo "(no GPU compute processes)"; fi
echo; echo "== tmux sessions and attached clients"
tmux ls -F '#{session_name}: windows=#{session_windows} attached_clients=#{session_attached}' 2>&1
tmux list-clients -F '#{client_session} on #{client_tty} idle=#{client_activity_string}' 2>&1 | head -12
while IFS=' ' read -r name n; do
  [ -z "$name" ] && continue; [ "$name" = "$MINE" ] && continue; [ "$name" = "gh-runner" ] && continue
  [ "${n:-0}" -gt 0 ] && why "tmux session '$name' has $n attached client(s)"
done < <(tmux ls -F '#{session_name} #{session_attached}' 2>/dev/null)
if tmux has-session -t '=t134viz' 2>/dev/null; then
  [ "$(tmux display -p -t '=t134viz' '#{session_attached}')" -gt 0 ] && why "t134viz is in use"
fi
echo; echo "== ROS domain 174 (the replay's domain) must be empty"
d174=$(ROS_DOMAIN_ID=174 ROS_LOCALHOST_ONLY=1 ROS2CLI_NO_DAEMON=1 timeout 15 bash -c 'source /opt/ros/humble/setup.bash; ros2 node list 2>&1 | head -5; ros2 topic list 2>&1 | grep -vE "^/(parameter_events|rosout)$" | head -5')
if [ -n "$d174" ]; then echo "$d174"; why "ROS domain 174 is not empty"; else echo "(empty)"; fi
echo; echo "== disk"; df -h ~ | tail -1
echo; echo "load check: 1-minute load average $(cut -d' ' -f1 /proc/loadavg) on $(nproc) logical CPUs"
awk -v l="$(cut -d' ' -f1 /proc/loadavg)" 'BEGIN{ if (l > 4) exit 1 }' || why "1-minute load average above 4"
echo; if [ $blocked -eq 0 ]; then echo "CLEAR, as far as this scan can tell (it cannot see docker containers without sudo; it cannot tell who is at a shared-account terminal)."; exit 0; else echo "Do not start the replay."; exit 1; fi
