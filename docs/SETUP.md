# Renaissance Capstone Project — Setup & Bring-Up Plan

Status of this document: written 2026-08-25 against branch `realman_manip` @ `c61409d`,
after a full read of the repo and a probe of the machine it is checked out on
(`/home/iot22/Desktop/Renaissance-Capstone-Project`).

The root `README.md` is **stale** — it describes a different upstream project
(`joshopp/aria_pkg`: ZeroMQ, YOLO `best.pt`, `start_interaction.py`). None of that
matches the current code. Ignore it; use this document instead.

---

## 1. What the system actually is

Three cooperating layers, all talking over **ROS 2 Humble DDS topics** on one host.

```
┌─ Layer A: Perception host (uv venv, python 3.10) ─ src/ ────────────────────┐
│  Project Aria glasses                                                        │
│    ├─ RGB    ──► /aria/rgb_camera/raw, /aria/rgb_camera/undistorted          │
│    ├─ EyeTrk ──► /aria/eye_tracking/gaze_estimate                            │
│    ├─ SLAM   ──► /aria/slam_left|right/raw   ┐ (for OpenVINS, external ws)   │
│    ├─ IMU    ──► /aria/imu                   ┘                               │
│    └─ Audio  ──► faster-whisper ──► Qwen2.5-0.5B ──► /aria/audio/prompt      │
│  SAM3 (3.4 GB ckpt) segments Aria RGB *and* RealSense RGB by that prompt     │
│    └─► /aria/rgb_camera/object_masks , /realman/rgb_camera/object_masks      │
│  LightGlue/SuperPoint cross-matches the two views ──► /aria/.../feature_match│
│  OpenCV visualiser window (q = quit, m = menu)                               │
└──────────────────────────────────────────────────────────────────────────────┘
┌─ Layer B: Grasping (separate conda env `anygrasp`, python 3.10) ────────────┐
│  anygrasp_node.py: RealSense RGB + aligned depth + object mask              │
│    ──► AnyGrasp tracker (licensed .so) ──► /grasp_candidates (top 5)        │
└──────────────────────────────────────────────────────────────────────────────┘
┌─ Layer C: Robot (ros2_robot_ws + deps_ws) ─────────────────────────────────┐
│  rm_driver ─ TCP 192.168.1.18:8080 ─► RealMan RM65 + EG2-4B gripper         │
│  rm_description ─ URDF w/ D435i eye-in-hand on Link6 ─► TF tree             │
│  rm_control ─ trajectory subdivision ─► driver                              │
│  move_group (rm_65_w_gripper_config) + MoveIt Task Constructor (deps_ws)    │
│  grasp_state_machine ─ IDLE→SELECTING→EXECUTING, TF camera→base_link,       │
│                        MTC plan, gripper open/close                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key wiring detail:** Layers A and B are **not connected yet**. `anygrasp_node.py`
subscribes to `TOPIC_MASK = "/PLACEHOLDER/sam/mask"` (a `sensor_msgs/Image`), while
the SAM3 pipeline publishes a pickled `UInt8MultiArray` on
`/realman/rgb_camera/object_masks`. Today the gap is bridged by
`dummy_mask_publisher.py`, which publishes an all-ones mask. See §7.

---

## 2. Hardware inventory & current state

| Item | Expected | Observed on this box (2026-08-25) |
|---|---|---|
| Host OS | Ubuntu 22.04 | ✅ 22.04.5 LTS jammy |
| GPU | CUDA-capable, ≥12 GB for SAM3 | ✅ RTX 4060 Ti 16 GB, driver 575.57.08, CUDA 12.9 |
| CUDA toolkit | 11.x/12.x for MinkowskiEngine | ✅ `/usr/local/cuda-12.8` on PATH |
| RealSense D435i | USB 3 | ✅ `8086:0b3a` on Bus 001 |
| RealMan RM65 | Ethernet, arm `192.168.1.18:8080` | ❌ `enp2s0` is **DOWN**, arm not reachable |
| EG2-4B gripper | driven through the arm controller | (no separate host connection) |
| Project Aria | USB (`aria` netdev) or WiFi | ❌ not on USB right now; certs exist in `~/.aria` |

Two things must change before a hardware run: bring `enp2s0` up with a static IP
(§4.1), and attach/authorise the Aria glasses (§4.2).

---

## 3. Software prerequisites

Everything below is **already present** on this machine. The commands are the
from-scratch recipe for a new box.

### 3.1 Base

```bash
# ROS 2 Humble + MoveIt 2 (scripts shipped in the repo)
cd ros2_robot_ws/src/rm_install/scripts
sudo bash ros2_install.sh
sudo bash moveit2_install.sh

# RealMan C++ driver library -> /usr/local/lib/libapi_cpp.so
cd ../../rm_driver/lib
sudo bash lib_install.sh          # verify: ldconfig -p | grep api_cpp

# RealSense ROS 2 driver
sudo apt install ros-humble-realsense2-camera ros-humble-realsense2-description

# uv (python env manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Confirm `source /opt/ros/humble/setup.bash` is in `~/.bashrc` (it is, line 121).

### 3.2 Perception venv (Layer A)

```bash
cd /home/iot22/Desktop/Renaissance-Capstone-Project
uv sync                     # reads pyproject.toml + uv.lock -> .venv/
```

Pulls three forks from GitHub (`Axemortal/rcp-LightGlue`,
`rcp-projectaria_eyetracking`, `rcp-sam3`) plus `projectaria-client-sdk==1.1.0`
and `faster-whisper`. Already resolvable — verified `import aria.sdk,
projectaria_tools, sam3, lightglue, faster_whisper` succeeds in `.venv`.

### 3.3 AnyGrasp conda env (Layer B)

```bash
conda create -n anygrasp python=3.10 -y && conda activate anygrasp
conda install openblas-devel -c anaconda -y
# PyTorch matching your CUDA, then:
export CUDA_HOME=/usr/local/cuda-12.8
cd grasp_module/dependencies/MinkowskiEngine
python setup.py install --blas_include_dirs=${CONDA_PREFIX}/include \
                        --blas_library_dirs=${CONDA_PREFIX}/lib --blas=openblas
cd ../../src/anygrasp_sdk
pip install -r requirements.txt
cd pointnet2 && python setup.py install
```

The env `anygrasp` already exists here (`~/miniconda3/envs/anygrasp`, py3.10).

### 3.4 MoveIt Task Constructor (Layer C dependency)

Vendored as plain files under `deps_ws/src/moveit_task_constructor` — **not** a git
submodule, so a plain `git clone` of this repo brings it. Built by `install.sh`.

---

## 4. Assets NOT in the repo

`.gitignore` excludes these; they must be fetched or regenerated per machine.

| Asset | Path | How to obtain |
|---|---|---|
| SAM 3 checkpoint (3.4 GB) | `src/models/sam3/sam3.pt` | download from the SAM 3 release; or copy from `~/GitHub/Renaissance-Capstone-Project/src/models/sam3/sam3.pt` |
| AnyGrasp checkpoints | `ros2_robot_ws/src/rm_mtc/src/perception/log/checkpoint_tracking.tar` (and `_detection.tar`) | already present in this checkout; otherwise from the AnyGrasp SDK release |
| ROS/colcon build trees | `deps_ws/{build,install,log}`, `ros2_robot_ws/{build,install,log}` | regenerated by `install.sh` |
| `.venv` | repo root | `uv sync` |

**AnyGrasp license is machine-locked.** `perception/license/Puneet.lic` *is*
committed, but it was issued against one machine's feature id. On a different
machine you must run `grasp_module/src/anygrasp_sdk/license_registration/license_checker -f`,
submit the id to the AnyGrasp form, and drop the new license folder into
`ros2_robot_ws/src/rm_mtc/src/perception/license/`. Allow ~2 working days.
Tracking checkpoint is present here, so on *this* box the existing license applies.

The eye-tracking weights (`src/models/projectaria_eyetracking/weights.pth`, 11 MB)
*are* committed — nothing to do.

---

## 5. Known defects to fix before first run

These are real, reproduced, and will stop a run. Fix them first.

### 5.1 `src/main.py` does not start at all — **blocker**

```
$ cd src && ../.venv/bin/python main.py --help
NameError: name 'Path' is not defined      # main.py:23
```

Two bugs in one file:

1. Line 23 uses `Path(...)` but `pathlib` is never imported.
   → add `from pathlib import Path` to the import block.
2. `parse_arguments()` reads `args.device_ip` (line 306) and `args.profile_name`
   (line 313) but the parser only declares `--mode`, `--recording-path`,
   `--update-iptables`. After fixing (1) you get an `AttributeError`.
   → add the two missing `add_argument` calls:

   ```python
   parser.add_argument("--device-ip", type=str, default=None,
                       help="Aria device IP (omit for USB)")
   parser.add_argument("--profile-name", type=str, default=None,
                       help="Aria streaming profile (default: config AriaConfig)")
   ```

   Defaults fall through to `AriaConfig.ARIA_DEVICE_IP_ADDRESS` (None) and
   `AriaConfig.ARIA_STREAMING_PROFILE_NAME` (`profile15`) in `ApplicationConfig`.

Also note `SCRIPT_DIR` / `PROJECT_ROOT` at lines 23–24 are computed and never used.

### 5.2 Hard-coded `~/GitHub/...` paths — this checkout is on `~/Desktop`

| File | Line | Fix |
|---|---|---|
| `ros2_robot_ws/install.sh` | 4–5 | `DEPS_WS`/`ROBOT_WS` point at `$HOME/GitHub/...`. Make them relative: `ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` |
| `ros2_robot_ws/src/main.py` | `ANYGRASP_DIR` | `/home/iot22/GitHub/.../rm_mtc/src/perception` → derive from `os.path.dirname(__file__)` (the other three node paths already do) |
| `src/services/object_recognition/sam3_model.py` | `__main__` block | two `/home/iot22/GitHub/...` paths; only affects running that file directly |

A second, more advanced clone genuinely exists at
`~/GitHub/Renaissance-Capstone-Project` (branch `combined`, adds `Navigation_Module`).
Decide which one is authoritative before editing — see open questions.

### 5.3 Dead config module

`src/config.py` and the package `src/config/` both exist. Python resolves the
package, so `src/config.py` is unreachable dead code with stale values
(`profile18`, ZMQ settings, SAM2 paths). Delete it to avoid confusion.

### 5.4 Hard-coded values worth knowing

- `object_recognition_pipeline.py`: `PROMPT = "phone"` is the startup default until
  a voice prompt arrives on `/aria/audio/prompt`.
- `anygrasp_node.py`: `FX,FY = 910.7627, 910.3762`, `CX,CY = 657.9279, 375.1953`.
  These are one specific D435i's colour intrinsics. For a different unit, read
  `/camera/camera/color/camera_info` and update, or subscribe to it.
- `anygrasp_node.py`: depth gate is `0 < z < 0.5 m` (the comment says 1.5 m —
  the code says 0.5). Objects beyond 50 cm produce no grasps.
- `mtc_planner.hpp`: `HOME_JOINTS` is a fixed 6-joint pose; `ARM_GROUP = "rm_group"`.
- `arcuo.py`: `TAG_SIZE = 0.15 m`, `DICT_6X6_250`.

---

## 6. Bring-up plan

Do these in order. Stop at the first failure — later stages depend on earlier ones.

### Stage 0 — Fix the defects in §5.1 and §5.2

### Stage 1 — Network

```bash
# 1a. Arm link (RM65 at 192.168.1.18, host must be 192.168.1.10 per rm_65_config.yaml)
sudo ip link set enp2s0 up
sudo ip addr add 192.168.1.10/24 dev enp2s0
ping -c3 192.168.1.18                    # must succeed before Stage 4
```

`udp_ip: 192.168.1.10` in `ros2_robot_ws/src/rm_driver/config/rm_65_config.yaml` is
the address the arm pushes its 5 ms state reports to, so the host IP must match it
exactly. TCP command port 8080, UDP report port 8089.

```bash
# 1b. Aria over USB — device exposes a netdev called `aria`
sudo ip link set aria up
sudo ip addr add 192.168.42.1/24 dev aria
# (main.py does this automatically only when running inside a VM)

# 1b-alt. Aria over WiFi
python main.py --device-ip <aria_wifi_ip> --update-iptables
# --update-iptables opens UDP 7000-8000 for DDS; needs sudo
```

Note `~/cyclone_dds.xml` pins CycloneDDS to `wlo1` with a unicast peer. `RMW_IMPLEMENTATION`
is unset (so FastRTPS is in use) and that file is not referenced by
`CYCLONEDDS_URI` — it is inert. Leave it alone unless you switch RMW; if you do,
adding `enp2s0` will matter.

### Stage 2 — Build the ROS workspaces

```bash
cd ros2_robot_ws
bash install.sh          # after fixing the paths in §5.2
```

`install.sh` builds `deps_ws` (MTC) first if missing, then does a **clean** rebuild
of `ros2_robot_ws` (`rm_ros_interfaces` first so the custom messages —
`GraspCandidate`, `GraspCandidateArray`, `Gripperset`, `Gripperpick`, `Stop` — exist
before the rest compiles). Both trees are already built here; re-run only if you
change C++ or message definitions.

```bash
source deps_ws/install/setup.bash
source ros2_robot_ws/install/setup.bash
```

### Stage 3 — Smoke-test each piece in isolation

```bash
# Camera
ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true pointcloud.enable:=true
ros2 topic hz /camera/camera/color/image_raw
ros2 topic echo --once /camera/camera/color/camera_info    # confirm §5.4 intrinsics

# Arm driver alone (arm powered, in a safe pose, nothing in the workspace)
ros2 launch rm_driver rm_65_driver.launch.py
ros2 topic hz /joint_states                # driver publishes joint_states at the udp_cycle rate

# TF tree — grasp_state_machine needs camera_color_optical_frame -> base_link
ros2 launch rm_description rm_65_display.launch.py
ros2 run tf2_tools view_frames

# MoveIt in simulation only, no hardware
ros2 launch rm_mtc mtc_sim_test.launch.py
```

### Stage 4 — First hardware motion (robot loop, dummy mask)

**Terminal 1 — E-stop. Always start this first and keep a hand on it.**

```bash
source ros2_robot_ws/install/setup.bash
python3 ros2_robot_ws/src/estop.py
#  E = emergency stop   R = resume   S = soft stop   Q = quit
```

**Terminal 2 — the whole robot stack**

```bash
cd ros2_robot_ws/src
python3 main.py
```

That orchestrator launches, in order: RealSense → `rm_mtc/background.launch.py`
(driver + description + control + move_group) → `dummy_mask_publisher` →
`anygrasp_node` under `conda run -n anygrasp` → `grasp_viz` (auto-spawns RViz) →
`grasp_state_machine` (+5 s). Ctrl-C tears all of it down.

On startup `grasp_state_machine` immediately calls `moveToHome()` — **the arm will
move as soon as the state machine comes up.** Clear the workspace first.

With the dummy mask the whole depth frame is treated as the object, so AnyGrasp
returns grasps for whatever is nearest within 50 cm. That is intentional for a first
motion test; it is not the real pipeline.

### Stage 5 — Perception stack (Aria + SAM3 + LightGlue)

```bash
cd src
uv run python main.py --update-iptables
# add --device-ip <ip> for WiFi; omit for USB
```

Expect: an OpenCV window ("RGB Visual Feed"), Aria RGB and gaze overlays, SAM3
loading the 3.4 GB checkpoint (slow first pass), Whisper `small.en` + Qwen2.5-0.5B
on GPU. `q`/`ESC` quits, `m` toggles the menu.

Speak a command → Whisper transcribes → the LLM extracts the object noun → published
on `/aria/audio/prompt` → SAM3 re-segments both camera views with that noun.
Saying "stop"/"end"/"cancel" clears the prompt.

### Stage 6 — Close the loop (see §7)

---

## 7. The one missing link: SAM3 → AnyGrasp

This is the work item that turns two demos into one system.

| | Publisher | Topic | Type |
|---|---|---|---|
| Produced | `object_recognition_pipeline.py` | `/realman/rgb_camera/object_masks` | `std_msgs/UInt8MultiArray` (pickled dict of masks/boxes/scores) |
| Consumed | `anygrasp_node.py` | `/PLACEHOLDER/sam/mask` | `sensor_msgs/Image`, `mono8`, timestamp-synced to depth |

Three ways to bridge it, in increasing order of cleanliness:

1. **Adapter node** (fastest): subscribe to the `UInt8MultiArray`, unpickle, pick the
   mask (gaze-nearest when >1), publish `mono8` `Image` on the placeholder topic with
   the depth message's header copied verbatim — `ApproximateTimeSynchronizer` in
   `anygrasp_node` uses a 50 ms slop, so the stamp must be real, not `now()`.
2. **Change `anygrasp_node`** to subscribe directly to the `UInt8MultiArray` topic and
   do the unpickling itself. Requires the pickle format to be importable in the conda
   env, which it currently is not (it references project classes).
3. **Change the SAM3 pipeline** to also publish a plain `mono8` `Image` mask on a real
   topic name (e.g. `/realman/rgb_camera/object_mask_image`) and point
   `anygrasp_node`/`dummy_mask_publisher` at it. This is the cleanest and keeps the
   conda env free of project imports.

Recommendation: **option 3.** Then `TOPIC_MASK` stops being a placeholder in both
files, and `dummy_mask_publisher` remains a drop-in stand-in on the same topic name
for hardware tests without perception.

Two follow-ups that block real grasping either way:
- The RealSense mask must be spatially registered to the **aligned depth** frame
  (`/camera/camera/aligned_depth_to_color/image_raw`), not the raw depth topic —
  `dummy_mask_publisher` already subscribes to the aligned one; keep that.
- `object_recognition_pipeline.py` has a `TODO: Find the closest mask to the gaze
  point`. With >1 mask it currently keeps all of them. The gaze estimate is already
  published on `/aria/eye_tracking/gaze_estimate` — this is the intended selector.

---

## 8. Other open work found in the code

- `feature_matching.py` cross-matches Aria↔RealSense views with SuperPoint/LightGlue,
  but the result is only visualised; nothing consumes it for pose transfer yet.
  There is a matching `TODO: Perform feature matching to see if there is a valid pair`
  in the object-recognition pipeline.
- **ArUco** (`arcuo.py`, `/aria/aruco_pose`) is computed in `rgb_worker` and the result
  is discarded — `result, frame = detect_aruco(...)` then nothing. `# TODO Implement
  ARUCO Pose Tracking`. This is presumably the intended Aria→robot extrinsic calibration.
- **VIO**: the pose pipeline publishes `/aria/imu` + `/aria/slam_left|right/raw` for
  OpenVINS, and `src/services/aria_device/calibration/` holds the kalibr chains and
  `estimator_config.yaml`. OpenVINS itself lives outside this repo at
  `~/Ros2Workspaces/OpenVINS` (built). `temp.txt` at the repo root is the generated
  calibration dump from `_log_calibration()`. `/aria/vio_pose` has no publisher inside
  this repo.
- **Recording mode** is marked `# TODO: Fix Recording Mode` — `--mode recording` is
  not expected to work.
- `main.py` (repo root) is an unused `uv init` stub.

---

## 9. Fast path for *this* machine

Everything in §3 is already installed and both workspaces are already built.
Minimum to a running system today:

```bash
# 1. fix the two blockers
#    src/main.py       : add `from pathlib import Path` + the two add_argument calls
#    ros2_robot_ws/install.sh + ros2_robot_ws/src/main.py : de-hardcode ~/GitHub paths

# 2. arm network
sudo ip link set enp2s0 up && sudo ip addr add 192.168.1.10/24 dev enp2s0
ping -c3 192.168.1.18

# 3. plug in Aria over USB, then
sudo ip link set aria up && sudo ip addr add 192.168.42.1/24 dev aria

# 4. three terminals
source deps_ws/install/setup.bash && source ros2_robot_ws/install/setup.bash
python3 ros2_robot_ws/src/estop.py            # T1 — first, always
cd ros2_robot_ws/src && python3 main.py       # T2 — robot + grasp loop
cd src && uv run python main.py               # T3 — Aria perception
```

---

## 10. Safety

From the RealMan README, plus what the code does:

- `grasp_state_machine` **moves the arm to home the instant it starts**, before any
  grasp candidate arrives. Clear the workspace before launching Terminal 2.
- Keep `estop.py` running in its own terminal for every hardware session.
  `E` publishes `rm_driver/emergency_stop_cmd state=true`; `R` resumes; `S` stops only
  the current motion.
- Gripper force in `closeGripper()` is `speed=200, force=200` (of 1000). Verify on a
  soft object before anything rigid.
- Check mounting screws before each session; keep people out of the arm's reach;
  power the arm down when not in use.

---

## 11. Open questions

1. **Which checkout is authoritative** — this `~/Desktop` one on `realman_manip`
   (Mar 28), or `~/GitHub/Renaissance-Capstone-Project` on `combined` (Apr 20, adds
   `Navigation_Module`, "Fix pose fusion node", "Add emergency stop")? The hard-coded
   paths in §5.2 all point at the `~/GitHub` one, which suggests it, not this one, was
   the working tree. If `combined` is ahead, some of §5's defects may already be fixed
   there and this plan should be rebased onto it.
2. **Scope of the first bring-up** — robot-only loop with the dummy mask (Stage 4), or
   straight to the full Aria→SAM3→AnyGrasp chain (which needs §7 built first)?
3. **Aria transport** — USB or WiFi? WiFi needs `--device-ip` plus the iptables rule;
   USB needs the `aria` netdev configured manually outside a VM.
4. **Is VIO/OpenVINS in scope now**, or is ArUco (§8) the intended Aria→robot extrinsic
   for this phase? Nothing in this repo publishes `/aria/vio_pose`.
5. **Replication target** — is the goal to reproduce this on a *second* machine? If so
   the AnyGrasp license (§4) has a multi-day lead time and should be requested today.
