# Aria stream on the lab box: why no data arrives, and the fix to build

Dion, 2026-10-13. Task: **T2.12** (fix), blocks **T2.2**. Branch `t2.2-aria-stream`.

## The answer

The glasses stop sending when the receiving computer has more than **2 IPv4 addresses besides the
glasses' USB link**. The box has 6 (`enp2s0` x3, `wlo1`, `tailscale0`, `docker0`), so the stream starts,
the glasses and the box find each other, and then no data arrives at all. Not images, not audio, not IMU.
`[observed]`

The box cannot drop to 2: the arm needs `192.168.1.10`, the LiDAR needs `192.168.1.5`, and we reach the
box over `wlo1` and Tailscale. So removing addresses is not a fix.

**The fix to build (T2.12):** run the Aria receiver in its own Linux network namespace, an isolated
network view that contains only the USB link plus one link back to the box for ROS. That is at most
2 other addresses, inside the limit.

## Evidence

All on 2026-10-13, glasses `1WM10350101291` (Gen 1), SDK `projectaria_client_sdk` 1.1.0.

| Test | Result |
|---|---|
| Box, normal setup (6 other addresses) | `Streaming` state, glasses log `DDS participant discovered: AriaSdk`, 0 messages of any type `[observed]` |
| Meta's own sample `streaming_subscribe` on the box | Black window `[observed]` |
| Firewall | Not the cause. INPUT policy ACCEPT, `ufw` inactive `[observed]` |
| Fresh pairing approved in the Companion app, glasses OS updated (clock was 5 min fast, now synced) | Still 0 on the box `[observed]` |
| Dion's Mac (2 other addresses), hotspot or campus Wi-Fi, Tailscale on or off | 77 frames per camera in 8 s `[observed]` |
| Box, receiver in a network namespace with only the USB link | 100 frames per camera in 10 s, plus audio, IMU, baro, magnetometer `[observed]` |
| Box, namespace with the USB link plus N fake addresses | N = 0, 1, 2 all data. N = 3 to 6 nothing `[observed]` |

Why 2 is the limit is `[inferred]`: the SDK bundles Fast DDS (the DDS library ROS 2 also uses). Fast
DDS keeps at most 4 unicast addresses per remote participant by default. If the glasses' copy does the
same and counts loopback, the USB address falls off the list once the box announces more than 3 others.
The SDK ignores `FASTRTPS_DEFAULT_PROFILES_FILE` (a loopback-only profile on the Mac changed nothing), so
we cannot trim the address list from config.

## How to repeat the test

Glasses on the box's USB, then:

```
source ~/rcp-Gappler/global_env.sh
aria streaming start --interface usb --profile profile18 --use-ephemeral-certs
sudo docs/dion_docs/aria_stream_box/aria_stream_address_limit_test.sh
aria streaming stop
```

The script needs `sudo` because it creates network namespaces. It moves only the `aria` link and puts
it back each round.

## What T2.12 has to solve

1. **The launcher.** Wait for the `aria` link to appear after `aria streaming start` (the glasses
   recreate it on every start), move it into a namespace, give it an address, start the receiver there.
2. **ROS back to the box.** `aria_app/main.py` publishes ROS topics. Inside the namespace it cannot
   reach the rest of ROS on domain 91. A veth pair (a virtual cable between the namespace and the box)
   gives it one more address, which is still within the limit. Check that `ROS_LOCALHOST_ONLY=1`
   does not block this, since the veth is not loopback.
3. **No password prompt.** A sudoers rule limited to the launcher, so `quickstart_terminals.sh aria`
   can start it. Needs agreement from the others who use `rcp2026`.
4. **Starting the stream.** `start_aria_stream` in `aria/aria_app/services/aria_device/stream/streaming_pipeline.py`
   starts the stream and waits for the glasses on `192.168.42.129`. That step can stay outside the
   namespace if the receiver only subscribes.

Until then, the Mac streams fine and two recordings cover offline work (below).

## Recordings for offline work

On Dion's Mac in `~/aria-recordings/` (not in git, 1.1 GB). Copy to the box when needed.

| File | What | Notes |
|---|---|---|
| `9f28219c-2540-4d2b-ac8a-cfbd48c2f01d.vrs` | Seated, looking at the box, with a stretch looking away on purpose | 94 s. Use the window in `.trim.json` (drops the first 30 s and last 15 s) |
| `c2cbafe8-ebc9-4279-8782-8cdaeb81b99b.vrs` | Standing, 4 still stops at different distances, for T2.3 | 118 s. Stops and measurements in `.stops.json` |

Both use `profile0`: every sensor, calibration included, but **RGB at 1 frame per second** (eye tracking
and SLAM at 10). Voice in the second one is soft, about 12 dB over room noise.

The 4 stops, with eye height 160 cm, box 5.5 x 14 x 7.5 cm on a 67 cm table, distances along the floor
from toes to box, ±10 cm:

| Stop | Seconds | Floor distance | Eye to box, approx. |
|---|---|---|---|
| 1 | 14-29 | 110 cm | 140 cm |
| 2 | 38-53 | 138 cm | 163 cm |
| 3 | 62-79 | 226 cm | 242 cm |
| 4 | 87-101 | 158 cm | 180 cm |

## Other things found on the way

- **Two pairs of glasses.** `1WM10350101291` matches `aria_factory_calibration.json`, so the T0.0 serial
  check passes for that pair. `1WM093701N1197` is a second pair with no calibration file in the repo.
- **These are Gen 1 glasses.** Use SDK 1.x. `pip install projectaria_client_sdk` now installs 2.x, which
  is for Gen 2.
- **The box `~/.aria` certs** were copied from Zongzhe's `~/Gappler/.aria-auth-cache`, then replaced by
  a fresh pairing approved in the Companion app.
- **The glasses' Wi-Fi** has an NTUSECURE login stored. Remove it with
  `aria device wifi forget --ssid NTUSECURE`.
