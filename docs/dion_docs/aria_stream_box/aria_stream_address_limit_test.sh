#!/bin/bash
# Find how many IPv4 addresses besides the glasses' USB link the Aria receiver can have
# before the glasses stop sending (found 2026-10-13: 2 work, 3 do not).
# Each round builds an isolated network space with N fake addresses plus the `aria` USB link,
# listens for 10 s, then puts the link back. Nothing shared on the box is touched.
#
# Usage, with the glasses already streaming over USB (`aria streaming start --interface usb ...`):
#   sudo docs/dion_docs/aria_stream_box/aria_stream_address_limit_test.sh
# Then stop the stream with `aria streaming stop`.
DIR="$(dirname "$(readlink -f "$0")")"
PY="$DIR/../../../.venv/bin/python"   # the repo .venv
USER_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
for N in 0 1 2 3 4 5 6; do
  ip netns add arialim
  ip netns exec arialim ip link set lo up
  ip netns exec arialim ip link add dummy0 type dummy
  ip netns exec arialim ip link set dummy0 up
  for i in $(seq 1 "$N"); do ip netns exec arialim ip addr add "10.200.$i.1/24" dev dummy0; done
  ip link set aria netns arialim
  ip netns exec arialim ip link set aria up
  ip netns exec arialim ip addr add 192.168.42.2/24 dev aria
  R=$(ip netns exec arialim sudo -u "$SUDO_USER" env HOME="$USER_HOME" PYTHONWARNINGS=ignore \
      timeout 30 "$PY" "$DIR/aria_stream_probe_all_types.py" 2>&1 | grep received)
  echo "extra addresses $N: $R"
  ip netns exec arialim ip link set aria netns 1
  ip netns del arialim
done
