> **Historical record, archived 2026-09-19 (T0.0).** Copied unchanged from the `realman_manip`
> branch (commit `55a2815`). It records the 2026-08-25 session that brought up the arm driver,
> camera, MoveIt and AnyGrasp on the old `~/Desktop` clone. **Paths, IPs, the network setup and
> the "no base camera" finding are out of date.** For the current setup, read
> [`../START_HERE.md`](../START_HERE.md) and [`../TESTBENCH_PLAN.md`](../TESTBENCH_PLAN.md).
> It is kept because other docs and `bench/` cite it by section number.
>
> **Correction 2026-09-23 (T1.3):** §7 quotes the `realman_manip` home row. That row is
> rejected (5/5 final-approach sim FAILs, joint4 at its limit); the final home row is the
> MAIN row `[0, 0, 0.7854, 0, 1.5708, 1.5708]`. The §7 text below is unchanged history.

# RCP — New User Start-Up Guide

**Machine:** `iot22-Computer` — i5-13400F, RTX 4060 Ti 16 GB (driver 575.57.08), Ubuntu 22.04.5, ROS 2 Humble
**Clone this guide was verified on:** `~/Desktop/Renaissance-Capstone-Project` (branch `realman_manip`)
**Last validated:** 2026-08-25

**Status:** driver, camera, TF, MoveIt/MTC and AnyGrasp all brought up successfully in a prior
session. **The arm has never been commanded to move.** Execution is untested — see §7.

> **Validation note.** Every command, path, version and IP below was re-checked against the live
> machine on 2026-08-25 by read-only inspection. Two things are marked `[unverified this pass]`
> because confirming them requires launching the driver, which was deliberately not done.

---

## 1. Machine facts

| Thing | Value |
|---|---|
| Wired NIC (to arm) | `enp2s0` — the only physical Ethernet port |
| Workstation IP on arm subnet | `192.168.1.10/24` (required, see §3.2) |
| RM65 arm | `192.168.1.18`, TCP 8080 |
| Arm sends UDP state to | `192.168.1.10:8089`, 5 ms cycle |
| Arm model | `RM65-BI`, controller v3 |
| RealSense D435i | eye-in-hand, on `Link6` |
| Aria glasses | paired — device `1WM10350101291` |
| AnyGrasp licence | machine-locked to this box (`.../perception/license/Puneet.lic`). **Do not migrate hardware.** |
| SSH | `100.93.102.19` (tailscale0), `10.91.155.97` (wlo1, NTU DHCP — will move) |

### Two clones exist and they differ

| Path | Branch | Contents |
|---|---|---|
| `~/Desktop/Renaissance-Capstone-Project` | `realman_manip` | arm + grasp only — **everything here was verified on this one** |
| `~/GitHub/Renaissance-Capstone-Project` | `combined` | arm + grasp + `Navigation_Module` + Aria relay |

The branches have diverged: `realman_manip` is **51 commits ahead / 71 behind** `origin/combined`.
`combined` is the fuller system (`31763e8 Add Navigation_Module`). Merging them is outstanding work.

---

## 2. Environment — one command per terminal

```bash
source ~/Desktop/Renaissance-Capstone-Project/env.sh
```

It sources, in order:

1. `/opt/ros/humble/setup.bash`
2. `$REPO_ROOT/install/setup.bash`
3. `$REPO_ROOT/.venv/bin/activate`

### Which overlay is the right one

There are **four** install spaces on disk. Only one is correct:

| Path | State |
|---|---|
| `install/` | 2026-08-25, complete: rm_* + MTC + pointnet2 — **use this** |
| `ros2_robot_ws/install/` | 2026-03-28, rm_* only, **no MTC** |
| `ros2_robot_ws/src/install/` | stray nested build, carries `COLCON_IGNORE` |
| `deps_ws/install/` | duplicate copy of the same five MTC packages |

The repo-root `install/` is a single complete overlay because the colcon run was launched **from the
repo root**, so it discovered both `ros2_robot_ws/src` and `deps_ws/src`. **Do not also source
`deps_ws/install/setup.bash`** — it puts a second copy of every MTC `.so` on the library path.

`~/.bashrc` sources only `/opt/ros/humble/setup.bash`. A fresh shell therefore finds **no** project
packages and fails with `Package 'rm_gazebo' not found ... searching: ['/opt/ros/humble']`.

### Rebuilding it

Only if `install/` is wiped. Run from the **repo root** — that is what makes the overlay complete;
building inside `ros2_robot_ws` or `deps_ws` gives a partial one:

```bash
cd ~/Desktop/Renaissance-Capstone-Project
source /opt/ros/humble/setup.bash        # only this — a stale overlay poisons the build
colcon build
```

~6 min for all 24 packages. Colcon then reports stderr for six
(`moveit_task_constructor_capabilities`, `_core`, `_demo`, `_visualization`, `rviz_marker_tools`,
`pointnet2`). **All benign, zero errors:** five are the one-line
`You did not request a specific build type: Choosing 'Release' for maximum performance`, and
`pointnet2` is 65 torch `Tensor.data<T>() is deprecated` warnings.

Sourcing is load-bearing, not cosmetic: `main.py` launches the AnyGrasp node via `conda run`, which
inherits `PYTHONPATH` and `AMENT_PREFIX_PATH` from the parent shell. Launch from an unsourced
terminal and that node dies on import while everything else looks fine.

**The `.venv` activation is deliberate.** Do not `deactivate` before running the pipeline.

### GUI over SSH

`~/.bashrc:147-149` hardcodes `export DISPLAY=:1` — the machine's **physical** monitor. Over SSH,
RViz and Gazebo do launch, but the window opens on the workstation's own screen. Use a remote
desktop into `:1`; X11-forwarding also needs those `DISPLAY` lines removed, and Gazebo over
forwarded GLX is unusably slow.

---

## 3. Bring-up

### 3.1 Physical

- Ethernet into `enp2s0`, other end into the RM65 **control box**
- Control box powered on

```bash
ip addr show enp2s0        # NO-CARRIER = nothing electrically connected; no software fixes this
sudo dmesg -w              # watch the link come up while plugging in
```

### 3.2 Network

A NetworkManager profile already exists — `enp2s0`, `ipv4.method manual`, `192.168.1.10/24` — but
with **`connection.autoconnect: no`**, so it does not come up on boot. Do not create a new profile;
bring the existing one up:

```bash
sudo nmcli con up enp2s0
ping -c 3 192.168.1.18
```

To make it automatic: `sudo nmcli con mod enp2s0 connection.autoconnect yes`

Manual equivalent, if you prefer not to touch NetworkManager:

```bash
sudo ip link set enp2s0 up
sudo ip addr add 192.168.1.10/24 dev enp2s0
```

`.10` is **not arbitrary** — the driver tells the arm to send UDP joint state to that exact address.
Wrong address = connects fine, zero feedback, presents as a hang.

### 3.3 Confirm the arm's control server

```bash
nc -zv 192.168.1.18 8080
```

**The controller takes ~60 s after power-on before 8080 opens.** `Connection refused` right after
power-up is normal — wait and retry. Refused ≠ timeout: refused means the host is up and rejecting,
so the network is fine.

Optional full picture: `nmap -p 1-10000 192.168.1.18` — expect 22, 80, 111, 502, 515, 3000, 8060,
**8080**, 8090. `http://192.168.1.18` is a useful read-only view of arm state.

---

## 4. Launch — six terminals

Every terminal starts with `source ~/Desktop/Renaissance-Capstone-Project/env.sh`.

### T1 — E-stop (open first, every time)

```bash
python3 ~/Desktop/Renaissance-Capstone-Project/ros2_robot_ws/src/estop.py
```

`E` emergency · `R` resume · `S` soft stop · `Q` quit. Keystrokes register only in the **focused** window.

### T2 — Arm driver

```bash
ros2 launch rm_driver rm_65_driver.launch.py
```

Expect:

```
[rm_driver]: RM_65_driver is running
[rm_driver]: product_version = RM65-BI
[rm_driver]: controller version : 3
[rm_driver]: UDP_Configuration is cycle:5ms,port:8089,...,ip:192.168.1.10,...
```

`product_version` came back *from the arm* — that line is proof the TCP handshake worked.

### T3 — Camera

```bash
ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true pointcloud.enable:=true
ros2 topic hz /camera/camera/color/image_raw
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw
```

Both ≈ **13–14 Hz**. `[unverified this pass]`

### T4 — MoveIt + robot_state_publisher

```bash
ros2 launch rm_mtc background.launch.py
```

Wait for `You can start planning now!`. This does **not** move the arm — `move_group` only plans when asked.

### T5 — TF check (the usual failure point)

```bash
ros2 run tf2_ros tf2_echo base_link camera_color_optical_frame
```

Expect translation ≈ `[-0.100, -0.049, 0.728]`, rotation near-identity. `[unverified this pass]`

Chain: `base_link → … → Link6 → camera_link → camera_color_optical_frame`. Arm side from the URDF,
optical side from the RealSense node's TF publisher — **both must be running** or every grasp
candidate is silently skipped.

### T6 — AnyGrasp

```bash
source ~/Desktop/Renaissance-Capstone-Project/env.sh
python3 ros2_robot_ws/src/rm_mtc/src/perception/dummy_mask_publisher.py &
cd ros2_robot_ws/src/rm_mtc/src/perception
conda run --no-capture-output -n anygrasp python anygrasp_node.py \
    --checkpoint_path log/checkpoint_tracking.tar --filter oneeuro
```

Expect:

```
license passed: True, state: FvrLicenseState.PASSED
[anygrasp_node]: AnyGrasp model loaded
[anygrasp_node]: AnyGrasp node ready, waiting for synchronized frames...
[anygrasp_node]: Frame 0: selected 5 seed grasps
```

`--no-capture-output` matters — plain `conda run` buffers stdout and the node looks hung.

---

## 5. Two traps that cost real time

### 5.1 Depth filter silently empties the point cloud → segfault

`anygrasp_node.py:155` filtered to `z < 0.5` while the comment above it said `0 < z < 1.5m`. The
bench scene sits at **~1.45 m**, so the filter discarded every point, MinkowskiEngine got an empty
sparse tensor, and **segfaulted instead of raising**.

Symptom: node loads cleanly, logs `waiting for synchronized frames`, then `Segmentation fault (core dumped)`
on the first frame.

**Fix is applied and verified in the working tree** (`anygrasp_node.py:155`, backup at `anygrasp_node.py.bak`):

```python
depth_mask = (points_full[:, :, 2] > 0) & (points_full[:, :, 2] < 1.5)
```

Confirming scene depth:

```bash
ros2 topic echo /camera/camera/aligned_depth_to_color/image_raw --field data --once | head -c 500
```

Little-endian uint16 millimetres — `[198, 5]` = 198 + 5×256 = 1478 mm.

**Caveat:** AnyGrasp quality degrades with distance. It no longer crashes at 1.45 m; whether the
grasps are *usable* at that range is untested. Working nearer 0.5 m may be the intended setup.

### 5.2 Never set `PYTHONNOUSERSITE=1`

| Location | Version |
|---|---|
| `~/.local/lib/python3.10/site-packages/torch` | **2.10.0+cu128**, `cuda.is_available() == True` ← the one that gets used |
| `~/miniconda3/envs/anygrasp/.../torch` | 2.7.0, **CPU-only — no `libc10_cuda.so` on disk** |

`~/.local` precedes conda on `sys.path`, so `conda run` picks up the CUDA build.
`PYTHONNOUSERSITE=1` forces conda's CPU-only torch → `ImportError: libc10_cuda.so: cannot open shared object file`.

**Do not "clean up" `~/.local`.** The pipeline depends on it winning.

---

## 6. Aria glasses

Already paired — no phone-app or credential work needed:

```bash
source ~/Desktop/Renaissance-Capstone-Project/.venv/bin/activate
aria auth check      # → SDK is authenticated with device 1WM10350101291
```

Subcommands are `pair` / `check` / `unpair` / `remove-certs`. There is no `list`. Certs live in
`~/.aria` and `~/streaming-certs` (home dir, so they survive venv rebuilds). A NetworkManager
profile `Aria` exists for the `aria` USB interface.

**Corrections to earlier notes:**

- The Desktop `.venv` is **fine** — its shebangs point at
  `/home/iot22/Desktop/.../.venv/bin/python`, not the GitHub clone. No rebuild needed.
- `setuptools` is **80.10.2** and `pkg_resources` imports successfully. The `<81` constraint is
  already satisfied; it is still worth pinning in `pyproject.toml` so a future `uv sync` cannot
  break the Aria CLI.

**Not yet working:** `src/main.py` (the Aria entry point) does not run at HEAD:

- `Path` is used at `src/main.py:23` but never imported
- `run()` and `parse_arguments` take `device_ip` / `profile_name`, but the parser only declares
  `--mode`, `--recording-path`, `--update-iptables`

---

## 7. Not verified / not done

- **Execution — the arm has never moved.** `grasp_state_machine.cpp:111` calls `moveToHome()` on
  startup, unprompted, within seconds of launch. Home is
  `{-0.0175, -0.1745, 0.7854, -3.0718, -1.6930, -1.6057}` rad
  (`include/rm_mtc/mtc_planner.hpp:40`), executed at 0.1 velocity/accel scaling. Clear the arm's
  path, keep the physical e-stop in reach, and do the first run with someone who has operated this arm.
- **`Navigation_Module`** has no `install/setup.bash` — never built in the `combined` clone.
- **`rqt_image_view` / RViz Qt tooling.** PyQt5 **is** installed system-wide (`/usr/bin/python3 -c
  "import PyQt5"` succeeds); it is missing **only inside the project `.venv`**. So these tools fail
  in any terminal that sourced `env.sh`. Run them from a separate shell that sources only
  `/opt/ros/humble/setup.bash` + `install/setup.bash`, or `uv pip install PyQt5` into the venv.

---

## 8. Finding relevant to the FYP

**There is no base-mounted RGB-D camera on this robot.**

- Only one camera in the stack — the D435i, included via `sensor_d435 parent="Link6"` in
  `rm_description/urdf/rm_65_w_gripper.urdf.xacro:23`. Eye-in-hand.
- `Navigation_Module` is Livox MID-360 → `pointcloud_to_laserscan` → 2D LaserScan → SLAM Toolbox /
  Nav2. No image topics.
- The `d455` references under `Navigation_Module/OpenVINS/src/open_vins/config/` are **stock
  upstream example configs**, not evidence of installed hardware.

HiCo-Nav's Cognitive Memory Graph needs a continuous RGB-D stream, and nothing on this robot
provides one. This is a procurement item (a D455 is ~$400 with NTU lead time), not a software
problem — worth raising with Dr. Yuan promptly.

---

## 9. Shutdown

Ctrl+C each terminal in reverse launch order. `main.py` tears down its children on Ctrl+C, but it
reports child deaths as `WARNING: '<label>' exited with code N` and **keeps running** — a dead
AnyGrasp node presents as "nothing ever happens".

Drop the arm network config: `sudo nmcli con down enp2s0`
(or `sudo ip addr del 192.168.1.10/24 dev enp2s0` if you configured it by hand).

---

# WHAT WORKED — quick reference

```bash
# --- physical: cable in enp2s0, arm control box powered on ---

# --- once per boot ---
sudo nmcli con up enp2s0          # profile exists, autoconnect is off
ping -c 3 192.168.1.18
nc -zv 192.168.1.18 8080          # wait ~60s after power-on if refused

# --- every terminal ---
source ~/Desktop/Renaissance-Capstone-Project/env.sh

# T1  e-stop
python3 ~/Desktop/Renaissance-Capstone-Project/ros2_robot_ws/src/estop.py

# T2  arm driver          → expect "product_version = RM65-BI"
ros2 launch rm_driver rm_65_driver.launch.py

# T3  camera              → expect 13–14 Hz
ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true pointcloud.enable:=true

# T4  moveit + rsp        → expect "You can start planning now!"
ros2 launch rm_mtc background.launch.py

# T5  tf check            → expect translation ≈ [-0.100, -0.049, 0.728]
ros2 run tf2_ros tf2_echo base_link camera_color_optical_frame

# T6  anygrasp            → expect "Frame 0: selected 5 seed grasps"
python3 ros2_robot_ws/src/rm_mtc/src/perception/dummy_mask_publisher.py &
cd ros2_robot_ws/src/rm_mtc/src/perception
conda run --no-capture-output -n anygrasp python anygrasp_node.py \
    --checkpoint_path log/checkpoint_tracking.tar --filter oneeuro
```

## Rules that are not optional

1. `source env.sh` in **every** terminal. Skipping it kills the AnyGrasp node silently.
2. Source the repo-root `install/` — **never** `deps_ws/install/` on top of it, and never
   `ros2_robot_ws/install/` (no MTC).
3. **Never** set `PYTHONNOUSERSITE=1`. Conda's torch is CPU-only; `~/.local`'s is the CUDA one.
4. `anygrasp_node.py:155` must be `< 1.5`, not `< 0.5`, for a scene at ~1.45 m. Otherwise: empty
   cloud → MinkowskiEngine segfault.
5. Do **not** `deactivate` the `.venv`. `env.sh` activates it on purpose. (Exception: Qt tools — §7.)
6. `grasp_state_machine` and `main.py` move the arm within seconds of launch, unprompted.

---

## Next session

Work moves to `~/GitHub/Renaissance-Capstone-Project` (branch `combined`) for the Navigation_Module
and Aria relay. Expect to redo parts of this bring-up there: paths, `env.sh`, and whether a
repo-root `install/` overlay exists are all clone-specific and **unverified** on that side. That
clone currently has only `ros2_robot_ws/install/` from 2026-04-09.
