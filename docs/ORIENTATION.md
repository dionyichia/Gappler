# ORIENTATION

**What this is:** the entry point for anyone — human or AI assistant — who has never seen this
repo. It explains what the system is, how the code is laid out, what order to read it in, and
which parts are currently connected versus severed.

**Status:** written 2026-09-09 against branch `main` @ `2d36a89` ("WIP: pre-integration snapshot
of combined branch"), by reading the code only. **No hardware was running.** Every claim tagged
`[code]` was verified by reading the file at the cited line. Claims tagged `[reported]` come from
`RCP_NEW_USER_STARTUP_GUIDE.md` on the `realman_manip` branch, written by someone with the machine
in front of them on 2026-08-25. Claims tagged `[inferred]` are my reading of intent, not fact.
Claims tagged **`[unverified]`** were found mechanically by `bench/` (static analysis of the repo,
no hardware) and **have not been confirmed by a human at the machine.** Treat every one of them as
a question to answer at the next lab session, not as an established fact. When you confirm or
refute one, retag it and say how.

---

## 0. How to use this document

**Doc index:** [`docs/START_HERE.md`](START_HERE.md) — what each document is for and where work stands.

**Companion documents:** [`ARCHITECTURE.md`](ARCHITECTURE.md) has the same information as
diagrams (Mermaid, renders on GitHub) — prose here, pictures there.
[`NEXT_STEPS.md`](NEXT_STEPS.md) is the work register: what we intend to *do*, and in what order.
This file describes reality and stays stable; that one churns.

**If you are a new team member:** read §1, §2, §3. Then follow the reading order in §4 with the
code open. Skip §7–§10 until you actually touch hardware.

**If you are an AI assistant being pointed at this repo:** read this whole file before making
changes. It will save you from re-deriving the topic graph. Two warnings that matter more than the
rest: §6 lists five places where the system is cut apart — do not "fix" them
without reading §6 first, they are the integration seam, not bugs. And §8.1 — code in this repo
moves a real robot arm within seconds of launch.

**Maintaining this doc.** It is meant to grow as we learn. Rules:

- Keep the `[code]` / `[reported]` / `[inferred]` tags honest. If you verify something that was
  `[inferred]`, promote it and say how you verified it.
- Cite `file.py:123` for anything specific. Line numbers drift — if one is wrong, fix it rather
  than deleting the claim.
- Append to §11 (Changelog) when you make a substantive edit.
- If something here turns out to be **wrong**, delete it. A confidently wrong orientation doc is
  worse than no doc.
- **Name things descriptively** — see §0b. It applies to documentation as much as to code: write
  "the mobile base's root frame", not "the base frame".

---

## 0b. Project convention: name things descriptively

**This project has five overlapping subsystems, and several of them have a "base", a "camera", a
"pose" and a "main". Unqualified names are therefore actively dangerous here.** The rule for all
new code, topics, frames, files and docs:

> **A name must say which subsystem it belongs to, without needing context.**

The cautionary example, and it is a real one in this repo `[code]`:

| Name | What it actually is | Better |
|---|---|---|
| `base_link` | the **arm's** root frame | `arm_base_link` |
| `robot_base_link` | the **mobile base's** root frame | `mobile_base_link` |

Two nearly identical names for two different physical objects about half a metre apart, and the
static transform connecting them exists in only one of two launch files (§5). Anyone reading
"base" has to already know which subsystem they are in. That is the failure mode to avoid.

The same problem in other forms:

- **Three files named `main.py`** (repo root, `src/`, `ros2_robot_ws/src/`) plus
  `orchestrator.py` — four entry points, no name telling you which. See §2.
- **"camera"** — could be the Aria RGB camera, the Aria eye-tracking camera, the Aria stereo SLAM
  cameras, or the wrist-mounted RealSense. `/camera/...` topics are the RealSense; `/aria/...`
  are the glasses. That convention only works because the prefix carries the subsystem.
- **`/object_centroid` vs `/object_centroid_2d`** — differ by a suffix, and the `_2d` one is not
  even a normal point (§8.3).

### The full collision inventory `[code]`

A sweep of the repo (excluding vendored trees) found these. Ranked by how likely each is to cause
a real bug, not by how untidy it looks.

| # | Colliding names | What each actually is | Suggested |
|---|---|---|---|
| 1 | `base_link` / `robot_base_link` | arm root / mobile-base root | `arm_base_link` / `mobile_base_link` |
| 2 | `camera_link`, `camera_color_optical_frame`, `camera_rgb` | wrist RealSense mount, its optical frame, and **the Aria glasses' camera** — three unrelated things all called "camera" | prefix each with `arm_` or `aria_` |
| 3 | `/manipulation/*` vs `/manipulator/*` | **the same nav↔arm contract, split across two prefixes differing by one character.** `/manipulation/`: `goal_pose`, `start`, `done`. `/manipulator/`: `release`, `return_to_user` | pick one — `/manipulation/` reads better, these describe the task |
| 4 | `/goal_pose` vs `/manipulation/goal_pose` | "drive here" in the **map** frame vs "the object is here" in the **arm's** frame | qualify the bare one |
| 5 | `/goal_reached` vs `/return_to_user/goal_reached` | outbound leg outcome vs return leg outcome — identical type and values | qualify both legs |
| 6 | `/object_centroid` vs `/object_centroid_2d` | a real 3D point vs pixel-plus-depth (§8.3) | rename the `_2d` one to say what it holds |
| 7 | three × `main.py` + `orchestrator.py` | four entry points. Worse: `ros2_robot_ws/src/main.py:2` describes *itself* as "Main orchestrator", which is the other file's name | name each after what it launches |
| 8 | `rm_65_config` / `rm_65_w_gripper_config` | arm without / with the gripper joints. Ours all use the gripper variant, but the vendor's `rm_bringup` launch files reference the plain one — so copy-pasting a launch snippet loads an arm with no gripper | — (vendor names) |
| 9 | `Navigation_Module/src/base/` | comms packages, **not** the physical base's description (that is `src/urdf/`) | — |

`[code]` **Two of these have already produced defects**, which is the argument for the rule:

- `dummy_mask_publisher.py:14` sets `TOPIC_MASK = "/PLACEHOLDER/sam/mask"` while the other four
  definitions of that same constant name all say `/camera/sam/mask`. The tool broadcasts into the
  void. Its own comment at `:12` says "match these to the placeholders in `anygrasp_node.py`" — but
  that file's value is not a placeholder, it is the real one.
- `goto_glasses.py:35` documents `CAMERA_X_OFFSET = 0.18` as measured "from `base_link` centre" —
  the **arm's** frame name, used to describe the **mobile base's** own geometry, inside the
  navigation subsystem. `object_approach_node.py:51-52` describes the same constant correctly as
  `robot_base_link`. One of the two comments is simply wrong, and the near-identical names are why.

Applying it in practice: prefix topics with the subsystem (`/aria/...`, `/realman/...`), name
frames after the physical thing *and* its subsystem, and never name a file, node or constant
something a reader could reasonably attribute to a different part of the system. When you rename
an existing one, grep for every string occurrence first — frame and topic names are matched as
literal strings, so a rename that misses one fails silently at runtime rather than at build time.

---

## 1. What this system is, in plain English

The goal: **you wear smart glasses, look at an object, say "grab that box", and a mobile robot
drives over, picks it up, and brings it back to you.**

Five subsystems cooperate to do that. They are written in different languages, run in different
Python environments, and in one case on different machines. **The only thing connecting them is
ROS 2.**

### What ROS 2 is, if you have never used it

ROS 2 is not a program you run. It is a **publish/subscribe message bus** — think of it as a set
of named radio channels that any process on the network can broadcast on or listen to.

- A **topic** is a named channel, e.g. `/aria/audio/prompt`. Data flows one way, many-to-many.
- A **node** is any process that publishes or subscribes. One Python script can host several.
- A **message type** is the schema, e.g. `std_msgs/String`, `sensor_msgs/Image`.
- **TF** is a special always-on service tracking where every physical part is relative to every
  other, over time. "Where is the camera lens relative to the robot's base?" is a TF query. It is
  how a pixel becomes a place the arm can reach.
- A **launch file** (`*.launch.py`) is a recipe that starts several nodes at once with parameters.

The practical consequence: **subsystems here are only coupled by topic name and message type.**
Nothing imports anything across the boundary. That is what makes swapping in a different
navigation stack tractable (§10) — and it is also why half the system can be broken while the
other half runs perfectly, which is the situation today (§6).

### The five subsystems

| # | Subsystem | Hardware | Lives in | Runtime |
|---|---|---|---|---|
| A | **Perception** | Project Aria glasses — RGB cam, eye tracker, 7-mic array, IMU, stereo SLAM cams | `src/` | Python 3.10, `uv` venv at repo root |
| B | **Grasp prediction** | none (pure inference on RealSense data) | `grasp_module/`, `ros2_robot_ws/src/rm_mtc/src/perception/` | Python 3.10, **separate conda env `anygrasp`** |
| C | **Arm** | RealMan RM65 6-DOF arm, EG2-4B gripper, RealSense D435i on the wrist | `ros2_robot_ws/` | C++ / ROS 2 Humble |
| D | **Mobile base** | Livox MID-360 LiDAR, differential drive base | `Navigation_Module/` | C++ / Python, ROS 2 Humble |
| E | **Glue** | — | `main.py`, `ros2_robot_ws/src/orchestrator.py` | Python |

**Why two Python environments.** AnyGrasp ships a compiled `.so` built against a specific old
PyTorch/MinkowskiEngine stack. It cannot coexist with SAM3's requirements. So B runs under
`conda run -n anygrasp` and talks to everything else over ROS topics — never by importing. Keep it
that way; any change that makes B import project code will break it.

### The intended end-to-end flow

```
 You say "grab that yellow box"
   │
   ├─ Aria 7-mic array
   │    └─ faster-whisper (small.en) transcribes
   │         └─ Qwen2.5-0.5B-Instruct extracts the noun → "box"
   │              └─ publish  /aria/audio/prompt
   │
   ├─ SAM3 segments BOTH camera views using that word
   │    ├─ Aria RGB view      → /aria/rgb_camera/object_masks
   │    └─ RealSense view     → /realman/rgb_camera/object_masks
   │
   ├─ Your gaze (/aria/eye_tracking/gaze_estimate) disambiguates WHICH mask,
   │    if the word matched several objects
   │
   ├─ LightGlue/SuperPoint feature-matches Aria view ↔ RealSense view to confirm
   │    both cameras are looking at the same physical object
   │
   ├─ Chosen mask + aligned depth → 3D centroid → /manipulation/goal_pose (base_link frame)
   │
   ├─ Nav2 drives the base to within 0.6 m → publishes /manipulation/start
   │
   ├─ grasp_state_machine (C++):
   │    IDLE ──► SELECTING   visual-servo the wrist toward the 2D centroid,
   │    │                    stepping 4 cm at a time until the object is < 0.18 m away
   │    └──►    EXECUTING    AnyGrasp proposes 5 grasp poses; wait for one that is
   │                         stable across 5 frames; move there; close gripper
   │
   ├─ publish /manipulator/return_to_user → Nav2 drives back to your glasses
   │    (found via /aria/fused_pose)
   │
   └─ You say "release" → gripper opens → done
```

**That is the design.** Roughly half of it is not connected in the current code — see §6.

---

## 2. Repo map

Top-level, with an honest note on whether you will ever need to touch each one.

| Path | What it is | Will you edit it? |
|---|---|---|
| `src/` | **Subsystem A.** All Aria glasses code: streaming, eye tracking, ASR, LLM, SAM3, feature matching, pose fusion, OpenCV visualiser. | **Yes, a lot.** |
| `ros2_robot_ws/` | **Subsystem C.** A ROS 2 colcon workspace. Mostly vendor code from RealMan. | Only `src/rm_mtc/` and the loose scripts at `src/`. |
| `ros2_robot_ws/src/rm_mtc/` | **Ours.** The grasp state machine, MoveIt Task Constructor planner, and the perception nodes that bridge to AnyGrasp. | **Yes.** This is the heart of the arm logic. |
| `ros2_robot_ws/src/rm_driver`, `rm_control`, `rm_description`, `rm_moveit2_config`, `rm_gazebo`, `rm_example`, `rm_arm_examples`, `rm_doc`, `rm_install` | RealMan's shipped vendor packages — driver, URDF model, MoveIt config, sim, docs, install scripts. | **No.** Read `rm_description`'s URDF when you need to know where the camera is mounted. |
| `ros2_robot_ws/src/rm_ros_interfaces/` | 79 custom message definitions. Includes ours: `GraspCandidate.msg`, `GraspCandidateArray.msg`. | Only if you add a message. |
| `ros2_robot_ws/src/eg2_4b_description/` | URDF for the gripper. | No. |
| `Navigation_Module/` | **Subsystem D.** A second, separate colcon workspace: Livox driver, SLAM Toolbox + Nav2 config, base drivers, teleop, and the nodes that bridge nav ↔ manipulation. | **Yes** — this is where HiCo-Nav lands. |
| `Navigation_Module/OpenVINS/` | Vendored visual-inertial odometry (upstream, ~3.4 M lines). Estimates the *glasses'* pose from their stereo cams + IMU. | **No.** Treat as a black box; we only consume its output topic. |
| `grasp_module/` | **Subsystem B** source: AnyGrasp SDK + MinkowskiEngine. Build-time only — the runtime `.so` files live in `rm_mtc/src/perception/`. | **No.** Build once per machine, then forget. |
| `deps_ws/` | A third colcon workspace holding **MoveIt Task Constructor** (vendored, not a submodule). A dependency of `rm_mtc`. | **No.** Build it, source it. |
| `shared/config.yaml` | **The single source of truth for Aria-side topic names.** Read by `src/config/ros2.py`, which builds a `ROS2Topics` enum from it at import time. | **Yes**, when adding a topic. |
| `main.py` (root) | Top-level launcher: spawns `orchestrator.py` + the Aria app. | Yes — has hardcoded paths (§8.4). |
| `assets/` | Vendor PDFs (arm + gripper manuals, in Chinese), a test image, gripper serial-debug tools. | No. Manuals are worth a skim. |
| `README.md` (root) | **STALE — ignore it entirely.** It describes a different upstream project (`joshopp/aria_pkg`): ZeroMQ, YOLO `best.pt`, `start_interaction.py`. None of that exists in this code. | Delete it eventually. |
| `pyproject.toml` / `uv.lock` | Subsystem A's Python deps. Three are forks pulled from GitHub: `rcp-LightGlue`, `rcp-projectaria_eyetracking`, `rcp-sam3`. | Rarely. |

### Inside `src/` (subsystem A)

```
src/
├── main.py                    ← ENTRY POINT for everything Aria-side
├── config/                    ← dataclasses of constants; ros2.py reads shared/config.yaml
├── schemas/                   ← plain data containers (ApplicationConfig, GazeEstimate)
├── utils/                     ← logging, iptables, keypress, terminal helpers
├── models/                    ← checkpoints. sam3.pt (3.4 GB) is gitignored; eyetracking weights are committed
├── archive/                   ← dead code, ignore
└── services/                  ← ALL the real logic
    ├── aria_device/           ← talks to the glasses
    │   ├── aria_device_controller.py    connect / start streaming / fetch calibration
    │   ├── aria_stream_client.py        SDK subscriber wrapper
    │   ├── eye_tracking.py              gaze inference
    │   ├── calibration/                 kalibr chains + OpenVINS estimator config
    │   └── stream/                      one "pipeline" per sensor modality
    │       ├── streaming_pipeline.py         starts the device, shares calibration JSON
    │       ├── image_streaming_pipeline.py   RGB + eye-tracking + ArUco  → ROS
    │       ├── audio_streaming_pipeline.py   mic → Whisper → LLM → /aria/audio/prompt
    │       └── pose_streaming_pipeline.py    stereo SLAM cams + IMU → ROS (for OpenVINS)
    ├── object_recognition/    ← SAM3 wrapper + the big cross-camera pipeline
    ├── feature_matching.py    ← SuperPoint + LightGlue, Aria view ↔ RealSense view
    ├── pose_fusion/           ← OpenVINS VIO + ArUco corrections → /aria/fused_pose
    ├── arcuo.py               ← ArUco marker detection (note: filename is misspelled)
    ├── prompt_extractor.py    ← the LLM. Qwen2.5-0.5B, phrase → object noun
    ├── visualizer/            ← OpenCV debug window (keys: 1-6 switch view, m menu, q quit)
    ├── ros/                   ← thin ROS publisher/helper wrappers
    ├── process_manager.py     ← multiprocessing/thread lifecycle + shared quit Event
    └── playback_controller.py ← replay recorded sessions (marked TODO: broken)
```

### Inside `ros2_robot_ws/src/rm_mtc/` (the arm logic we own)

```
rm_mtc/
├── launch/
│   ├── background.launch.py         driver + URDF + control + move_group. NEEDS REAL ARM.
│   ├── grasp_state_machine.launch.py the state machine
│   └── mtc_sim_test.launch.py       ⚠️ `[unverified]` NAMES AN EXECUTABLE THAT IS NOT BUILT — §8.12
├── src/
│   ├── grasp_state_machine.cpp      ★ the arm's brain. IDLE→SELECTING→EXECUTING
│   ├── mtc_planner.cpp / .hpp       MoveIt wrapper: moveToHome, moveCartesianStep, getCurrentPose
│   ├── trivial_mtc.cpp              minimal MTC example
│   └── perception/
│       ├── sam3_ros_node.py         SAM3 on RealSense only, HARDCODED prompt "box"  (see §6)
│       ├── anygrasp_detection_node.py  ★ RGB+depth+mask → /grasp_candidates
│       ├── anygrasp_node.py         older tracking-based variant
│       ├── dummy_mask_publisher.py  all-ones mask, for hardware tests without perception
│       ├── grasp_viz.py             RViz markers for debugging
│       ├── license/                 AnyGrasp licence — MACHINE-LOCKED (§9)
│       └── *.so                     compiled AnyGrasp binaries
```

### Inside `Navigation_Module/src/` (subsystem D)

```
robot_slam/                    ← ours: the nav brain
├── config/  slam_toolbox.yaml, nav2_params.yaml, slam.rviz
├── launch/  slam_mapping.launch.py (build a map), slam_localization.launch.py (use one)
└── scripts/
    ├── object_approach_node.py     ★ object pose → Nav2 goal → /manipulation/start
    ├── goto_glasses.py             ★ navigate to the user; return after grasp
    ├── goal_reached_publisher.py   bridges /goal_pose topic → Nav2 action, reports outcome
    ├── pose_publisher.py           TF map→robot_base_link → /robot_pose
    ├── qos_relay.py                Livox publishes RELIABLE, laserscan needs BEST_EFFORT
    └── aria_image_relay.py         CompressedImage → raw Image so RViz can show it
livox_ros_driver2/, Livox-SDk2/   ← vendor LiDAR driver
base/, drivers/, urdf/            ← vendor base: xpkg_comm, xpkg_msgs, xpkg_vehicle, xpkg_power, URDF
simple_teleop/                    ← keyboard driving, 10 Hz cmd_vel
```

---

## 3. The three workspaces, and why builds are confusing

There are **three separate colcon workspaces** in this repo: `ros2_robot_ws/`, `deps_ws/`,
`Navigation_Module/`. Each has its own `src/` and produces its own `install/setup.bash`.

`[reported]` On the lab machine there were **four** build output directories, only one correct.
The trick that makes it work: run `colcon build` **from the repo root**, so it discovers both
`ros2_robot_ws/src` and `deps_ws/src` and produces one complete overlay. Building from inside
either workspace gives you a partial one that fails at runtime in confusing ways.

`[code]` **`Navigation_Module` has never been built.** There is no `install/` for it anywhere in
this repo, and `RCP_NEW_USER_STARTUP_GUIDE.md` §7 confirms it. Eight packages
(`robot_slam`, `simple_teleop`, `echo_plus_driver`, `xpkg_vehicle`, `xpkg_power`, `xpkg_msgs`,
`xpkg_comm`, `xpkg_urdf_echo_plus`). Building it is a high-value task — **but see §8.6 first: a
package it depends on is missing from this repo.**

`[reported]` Sourcing is load-bearing, not cosmetic. `ros2_robot_ws/src/main.py` launches AnyGrasp
via `conda run`, which inherits `PYTHONPATH` and `AMENT_PREFIX_PATH` from the parent shell. Launch
from an unsourced terminal and that one node dies on import while everything else looks fine.

---

## 4. Reading order

Follow this with the files open. Times are rough.

> **A guided version of this exists.** [`READING_GUIDE.md`](READING_GUIDE.md) walks the same
> rounds file by file, explaining what to notice and why, with check-yourself questions. Use that
> to actually read the code; use the table below as the index.

### Round 1 — the shape of it (~45 min)

| # | File | Why |
|---|---|---|
| 1 | `shared/config.yaml` | 20 lines. Every Aria-side topic name in one place. Read this first — it *is* the interface. |
| 2 | `src/config/ros2.py` | Shows how that YAML becomes the `ROS2Topics` enum used everywhere. |
| 3 | `docs/ORIENTATION.md` §5 | The full topic table below. Skim, don't memorise. |
| 4 | `src/main.py` | The Aria entry point. Focus on `ProcessPipelineBuilder` (lines 30–113): each `add_*` method starts one subsystem. **Note which are commented out at 107–112.** |
| 5 | `ros2_robot_ws/src/main.py` | The robot entry point. A plain sequential launcher — read the numbered comments. |
| 6 | `ros2_robot_ws/src/orchestrator.py` | 146 lines. The highest-level state logic: wait for start → launch → wait for release. Note most subscriptions are commented out. |

You now know what starts what. Stop and make sure that's solid before Round 2.

### Round 2 — the perception path (~1.5 h)

| # | File | Why |
|---|---|---|
| 7 | `src/services/aria_device/stream/streaming_pipeline.py` | 63 lines. How the glasses connect and hand out calibration. |
| 8 | `src/services/aria_device/stream/audio_streaming_pipeline.py` | The one path that definitely works today: mic → Whisper → LLM → topic. |
| 9 | `src/services/prompt_extractor.py` | The LLM. Read the system prompt — it explains the whole voice UX, including the "end"/"stop" kill word. |
| 10 | `src/services/aria_device/stream/image_streaming_pipeline.py` | RGB + gaze + ArUco publishing. |
| 11 | `src/services/object_recognition/object_recognition_pipeline.py` | **718 lines, the biggest and most important file in `src/`.** Read `_setup_ros_node` (all I/O in one place), then `run`, then `_process_aria_frame` / `_process_ros_frame`, then `_find_closest_mask` (this is the gaze→object logic) and `_find_matching_ros_mask` (cross-camera confirmation). |
| 12 | `src/services/feature_matching.py` | How the two camera views get matched. |

### Round 3 — the robot path (~2 h)

| # | File | Why |
|---|---|---|
| 13 | `ros2_robot_ws/src/estop.py` | 90 lines. Read it before anything else in this round — you will need it. |
| 14 | `ros2_robot_ws/src/rm_mtc/src/perception/sam3_ros_node.py` | Short. **Compare it to file 11 and notice they do overlapping jobs differently.** That gap is §6.2. |
| 15 | `ros2_robot_ws/src/rm_mtc/src/perception/anygrasp_detection_node.py` | RGB + depth + mask → grasp poses. Note the `/pipeline_state` gate: it only runs during EXECUTING. |
| 16 | `ros2_robot_ws/src/rm_mtc/include/rm_mtc/mtc_planner.hpp` | 60 lines. The complete arm-motion API — 5 methods. Also the HOME and RETURN joint angles. |
| 17 | `ros2_robot_ws/src/rm_mtc/src/grasp_state_machine.cpp` | **~760 lines, the hardest file here.** Read in this order: constructor (lines 128–161, all I/O), `workerLoop` (590+, the state flow), then `selectingStep` and `executingStep`. Skip the math helpers first pass. |

### Round 4 — navigation (~1 h)

| # | File | Why |
|---|---|---|
| 18 | `Navigation_Module/src/robot_slam/scripts/object_approach_node.py` | Its docstring is the best single description of the nav↔manipulation contract in the repo. |
| 19 | `Navigation_Module/src/robot_slam/scripts/goto_glasses.py` | The "go to the user / come back" behaviour. |
| 20 | `Navigation_Module/src/robot_slam/launch/slam_mapping.launch.py` | The full nav node graph: LiDAR → QoS relay → laserscan → SLAM Toolbox → Nav2. |
| 21 | `Navigation_Module/src/robot_slam/config/nav2_params.yaml` | Where HiCo-Nav will most likely have to plug in. |
| 22 | `src/services/pose_fusion/README.md` + `pose_fusion_node.py` | How the glasses get localised in the robot's map. Needed for "come back to me". |

### Skip entirely on a first pass

`Navigation_Module/OpenVINS/`, `grasp_module/dependencies/MinkowskiEngine/`,
`deps_ws/src/moveit_task_constructor/`, every `rm_*` package except `rm_mtc`, `src/archive/`,
`assets/gripper/`, and the root `README.md`.

---

## 5. The message bus — full topic reference

This is the real interface between subsystems. `[code]` throughout — each entry was read from
source, not from a running system.

### Aria glasses → everything (published by `src/`)

| Topic | Type | Published by |
|---|---|---|
| `/aria/rgb_camera/raw` | `CompressedImage` | `image_streaming_pipeline.py:80` |
| `/aria/rgb_camera/undistorted` | `CompressedImage` | `image_streaming_pipeline.py:85` |
| `/aria/eye_tracking/raw` | `CompressedImage` | `image_streaming_pipeline.py:158` |
| `/aria/eye_tracking/gaze_estimate` | `Point` | `image_streaming_pipeline.py:153` |
| `/aria/aruco_pose` | `PoseStamped` | `image_streaming_pipeline.py:90` |
| `/aria/slam_left/raw`, `/aria/slam_right/raw` | `CompressedImage` | `pose_streaming_pipeline.py:120,126` |
| `/aria/imu` | `Imu` | `pose_streaming_pipeline.py:237` |
| `/aria/audio/prompt` | `String` | `audio_streaming_pipeline.py:49` — **the voice command output** |
| `/aria/fused_pose` | `PoseStamped` — **`robot_base_link` frame, NOT `map`** (`pose_fusion_node.py:229`) | `pose_fusion_node.py:153` — where the user is. ⚠️ See §6.4 — this node does not do what its README says. |
| `/aria/pose_initialized` | `Empty` | `pose_fusion_node.py:154` |

`/aria/vio_pose` is consumed by pose fusion but **has no publisher inside this repo** — it comes
from OpenVINS, launched externally.

### Perception results (pickled `UInt8MultiArray` — visualisation only)

| Topic | Content |
|---|---|
| `/aria/rgb_camera/object_masks` | Aria view + SAM3 masks/scores/boxes |
| `/realman/rgb_camera/object_masks` | RealSense view + SAM3 masks |
| `/combined/object_masks` | Both views + matched keypoints + gaze point |
| `/aria/rgb_camera/feature_match` | LightGlue keypoints and matches |

⚠️ These carry **Python pickle**, so only processes that can import the project's classes can read
them. Never make subsystem B (conda) subscribe to these — see §1.

### Perception → grasping (the real control path)

| Topic | Type | Producer | Consumer |
|---|---|---|---|
| `/camera/sam/mask` | `Image` (mono8) | `sam3_ros_node.py:65` | `anygrasp_detection_node.py:76` |
| `/object_centroid_2d` | `PointStamped` — **x = pixel col, y = pixel row, z = depth in metres** (not a normal 3D point!) | `sam3_ros_node.py:66` | `grasp_state_machine.cpp:146` |
| `/object_centroid` | `PointStamped` | `sam3_ros_node.py:67` | RViz only |
| `/manipulation/goal_pose` | `PoseStamped` (base_link) | `object_recognition_pipeline.py:204` | `object_approach_node.py:75` |

### RealSense camera (vendor driver)

`/camera/camera/color/image_raw`, `/camera/camera/aligned_depth_to_color/image_raw`,
`/camera/camera/color/camera_info`. Always use the **aligned** depth topic — raw depth is not
pixel-registered to colour.

### Grasping → arm

| Topic | Type | Producer | Consumer |
|---|---|---|---|
| `/grasp_candidates` | `GraspCandidateArray` (score, width, depth, pose ×5) | `anygrasp_detection_node.py:81` | `grasp_state_machine.cpp:142` |
| `/pipeline_state` | `String` — `IDLE`/`SELECTING`/`EXECUTING` | `grasp_state_machine.cpp:156` | `anygrasp_detection_node.py:65`, `grasp_viz.py:61` |
| `/rm_driver/set_gripper_position_cmd` | `Gripperset` | state machine + orchestrator | arm driver |
| `/rm_driver/set_gripper_pick_on_cmd` | `Gripperpick` | `grasp_state_machine.cpp:153` | arm driver |
| `/rm_driver/emergency_stop_cmd` | `Stop` | `estop.py` | arm driver |
| `/rm_driver/move_stop_cmd` | `Empty` | `estop.py` | arm driver |

### The nav ↔ manipulation contract ★

**This is the boundary that matters for HiCo-Nav integration.** Everything above is internal to
one subsystem; these six topics are the seams between them.

| Topic | Type | Direction | Meaning |
|---|---|---|---|
| `/manipulation/goal_pose` | `PoseStamped` (base_link) | perception → nav | "the object is here" |
| `/goal_pose` | `PoseStamped` (map) | nav-internal → Nav2 | "drive here" |
| `/manipulation/start` | `Bool` | nav → orchestrator | "in position, go grasp" |
| `/manipulator/return_to_user` | `Bool` | arm → nav | "got it, take me back" |
| `/return_to_user/goal_reached` | `String` `"success"`/`"failed"` | nav → orchestrator | return leg done |
| `/goal_reached` | `String` | nav → approach node | resets the approach guard |
| `/manipulator/release` | `Bool` | voice → orchestrator | "let go" |
| `/manipulation/done` | `Empty` | → approach node | cycle finished |

`[code]` `object_approach_node` subscribes to **five** topics, not the two you would guess:
`/manipulation/goal_pose`, `/goal_reached`, `/aria/audio/prompt`, `/manipulation/done`,
`/manipulator/release` (`object_approach_node.py:74-88`). It listens to the raw voice prompt
directly — so voice reaches navigation even while §6.2 keeps it out of segmentation.

### Nav-internal

`/livox/lidar` (`PointCloud2`, RELIABLE) → `/cloud_relay` (BEST_EFFORT, via `qos_relay.py`) →
`pointcloud_to_laserscan` → SLAM Toolbox → Nav2. Plus `/robot_pose` (`PoseStamped`, map frame,
from TF), `/object_marker`, `/object_map_pose`, `/cmd_vel`.

### TF frames you will meet

```
map → odom → robot_base_link → ... → base_link → Link1..Link6 → camera_link
                                                              → camera_color_optical_frame
```

`base_link` is the **arm's** root frame. `robot_base_link` is the **mobile base's** root frame.
They are different and confusing them is a classic bug. Everything the arm plans happens in
`base_link`; everything Nav2 plans happens in `map` with `robot_base_frame: robot_base_link`.

⚠️ **The static transform bridging them exists in only ONE launch file.** `[code]`
`slam_localization.launch.py:98-103` publishes
`0.18 0 0.48 3.14159 0 0 robot_base_link base_link` — the arm sits 0.18 m forward, 0.48 m up, and
**yawed 180° (it faces backward)**. `slam_mapping.launch.py` does **not** publish it. So during a
mapping run the arm is not connected to the TF tree at all, and anything transforming
`base_link → map` fails silently.

---

## 6. Current state: five severed seams

**The most important section in this document.** These are not bugs to fix casually — they are
where the system was cut apart mid-integration, and understanding *why* is the job.

§6.1–6.3 are deliberate cuts. §6.4 is different: a node whose documentation and code disagree.

### 6.1 The Aria app publishes almost nothing `[code]`

`src/main.py:106–112`:

```python
self.add_streaming(device_ip, profile_name)
# self.add_visualization()          ← OFF
# self.add_object_recognition()     ← OFF
self.add_audio_streaming()
sensors_calib_json_str = self.config_queue.get()
# self.add_image_streaming(...)     ← OFF
# self.add_pose_streaming(...)      ← OFF
```

Four of six stages are commented out. **Today the glasses produce only `/aria/audio/prompt`.** No
RGB, no gaze, no ArUco, no IMU/SLAM frames, no SAM3, no visualiser window.

Consequence: `pose_fusion_node` gets no `/aria/aruco_pose`, so `/aria/fused_pose` never fires, so
`goto_glasses.py` can never find the user. The entire "come back to me" leg is dark.

### 6.2 The gaze-selected mask never reaches the robot `[code]`

`object_recognition_pipeline.py:384` — the one call that turns a chosen mask into a mask-image and
a 3D centroid is commented out:

```python
# self._publish_mask_and_centroid(inference_state, depth, header, ros_image)
```

The method itself (line 405) is complete and looks correct. It is simply not called.

Meanwhile `ros2_robot_ws/src/main.py` launches a **different** node for the same job:
`sam3_ros_node.py`, which has `TEXT_PROMPT = "box"` hardcoded at line 40 and takes no gaze input
at all.

**So the grasping half currently runs on a fixed word, disconnected from your voice and your
eyes.** Everything upstream — Whisper, the LLM, eye tracking, LightGlue cross-matching — is
computed and then thrown away at this seam. `[inferred]` This looks deliberate: a way to test the
arm without depending on the perception stack. But it means the headline demo does not exist yet.
**Closing this seam is what turns two demos into one system.**

### 6.3 The orchestrator's sequencing is disabled `[code]`

`orchestrator.py:57–62` — the subscriptions to `/return_to_user/goal_reached` and
`/manipulator/return_to_user` are commented out, along with their handlers (69–102). What remains:
launch `rm_mtc background` immediately, wait for `/manipulation/start`, launch `main.py`, wait for
`/manipulator/release`, open the gripper, exit. The navigate-back-to-user leg is not wired.

### What this means for planning

You can restore all three by uncommenting — but §6.2 also needs a decision about *which* SAM3 node
is authoritative, and §6.1 will surface whatever bugs made someone disable those stages in the
first place. Budget real debugging time, and do them **one at a time** so you can attribute
failures.

### 6.4 Pose fusion does not do what its README says `[code]`

`src/services/pose_fusion/README.md` describes a node that fuses OpenVINS VIO with ArUco
corrections. **The code does not do that.** Verified line by line:

| README claims | Code actually does |
|---|---|
| Subscribes `/aria/vio_pose` | VIO subscription is **commented out** (`pose_fusion_node.py:135-140`), and so is the whole `_on_vio_pose` handler (243-289). It subscribes to `/robot_pose` instead (147-152) — undocumented. |
| `fused_pose = T_correction @ T_vio_current` | **No VIO term at all.** It computes `T_map_glasses = T_map_marker @ inv(T_camera_marker)` and publishes that directly (231). |
| `T_map_marker` from a known marker position in the map | It is a **fixed offset from the robot**, read from ROS params (126-132). |
| Params `marker_pos_x` etc. | Params are named `marker_offset_x` etc. **The README's example command would silently no-op** — those parameter names do not exist. |
| Published in `map` frame | Published with `frame_id = "robot_base_link"` (229). |
| Publishes `/aria/is_stationary` | **No such publisher exists** anywhere in the code. |

Undocumented extras the code does publish: a TF `robot_base_link → aria_glasses` (213-225), a
`Marker` on `/aria/glasses_marker`, and an `Empty` on `/aria/pose_initialized` on the first fix.

**What it actually is:** a pure ArUco-anchored pose republisher, gated on `/robot_pose` being
available. The drift-correction machinery exists in the file but is dead.

**Why this matters for integration:** `goto_glasses.py` consumes `/aria/fused_pose` and treats it
as a map-frame goal, but it arrives stamped `robot_base_link`. Combined with §6.1 (ArUco is never
published at all, because image streaming is off), the "return to user" leg has **two independent
reasons it cannot work today.**

---

### 6.5 Two nodes do the same segmentation job `[code]`

Structurally part of §6.2, but worth stating separately because it is the thing to fix *before*
restoring that seam.

There is exactly **one** `SAM3Model` class (`src/services/object_recognition/sam3_model.py`).
`sam3_ros_node.py` lives under `ros2_robot_ws/` but **imports it from `src/`** — hence the
`uv run --project <repo root>` + `PYTHONPATH=.../src` launch in `ros2_robot_ws/src/main.py:110-121`.
So the code is shared; the **instances** are not.

Both nodes publish the **same three topics** — `/camera/sam/mask`, `/object_centroid_2d`,
`/object_centroid` (`object_recognition_pipeline.py:34-36`, `sam3_ros_node.py:30-32`). Right now
only one of them actually does, because the pipeline's call site is commented out at `:384`.

⚠️ **Uncommenting `:384` while `sam3_ros_node` runs creates two publishers racing on the same
topics**, with the state machine consuming whichever message lands last. Fix the ownership before
closing the seam — see [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.2 for the comparison table and the
target design.

`[inferred]` `sam3_ros_node.py` looks like a standalone stopgap so the arm could be tested without
the Aria stack, never reconciled with the pipeline it duplicates.

---

## 7. Branches

`[code]` **Corrected 2026-09-10:** `main` and `realman_manip` have **no common ancestor** —
separate root commits (`592bf2f` and `aa5fbb6`, both "Initial commit", both 2025-08-25), and
`git merge-base main origin/realman_manip` returns nothing. The previously stated "72 commits ahead
of each" was `git rev-list --left-right --count` with no merge base, which reports *total commits
per side*, not divergence. There is no shared base, so `git merge` needs
`--allow-unrelated-histories` and per-commit `git cherry-pick` is patch application, not replay.

`[code]` **An audit of all 44 shared non-vendored files found no arm code on `realman_manip` that
`main` lacks.** `main` is later everywhere it matters: `grasp_state_machine.cpp` 802 lines vs 289,
`mtc_planner.cpp` 132 vs 81, `object_recognition_pipeline.py` 718 vs 249, `src/main.py` 442 vs 331.
The 1.5 m depth-filter fix the startup guide describes as applied-and-verified is **already in
`main`** at `anygrasp_node.py:211`. The ~10 files that exist only on `realman_manip` under `src/`
are the pre-reorg flat layout that `main` already reorganised into subpackages
(`src/services/eye_tracking.py` → `src/services/aria_device/eye_tracking.py`, and so on).

⚠️ One file looks like a gain and is not: `rm_65_w_gripper_config/config/sensors_3d.yaml` is
`+25/-1` on `realman_manip`, but the added content is stock MoveIt Setup Assistant boilerplate
pointing at `/head_mount_kinect/depth_registered/image_raw` — a PR2 Kinect topic that does not
exist on this robot. `main`'s `sensors: []` is the correct value for this hardware. **Do not
cherry-pick it.** The underlying *idea* is still worth revisiting: an octomap fed from the D435i is
the "real fix" §8.2 says belongs in the collision scene instead of the z-overwrite hack.

| Branch | What it is | Verdict |
|---|---|---|
| **`main`** | The fuller system. The **only** branch with `Navigation_Module`. | **Work here.** |
| `origin/realman_manip` | Arm + grasp only, and an **older** snapshot of it. Uniquely carries `RCP_NEW_USER_STARTUP_GUIDE.md`, `docs/SETUP.md`, `env.sh` and `calibration.json` (the Aria factory calibration dump for device `1WM10350101291` — `main` has only the derived kalibr chains). | **Take the docs, `env.sh` and `calibration.json`; take no code.** See the audit below. `git show origin/realman_manip:RCP_NEW_USER_STARTUP_GUIDE.md` |
| `origin/legacy/main` | Older snapshot of the same lineage. | Ignore. |
| `origin/legacy/test` | Experiments. | Ignore. |

---

## 8. Known defects and traps

### 8.1 ⚠️ The arm moves within seconds of launch, unprompted `[code]` `[reported]`

`grasp_state_machine.cpp:594–595` — `workerLoop` calls `addSafetyWalls()` then `homeWithRetry()`
**before waiting for anything.** Launching the state machine moves the arm to its home pose
immediately. `homeWithRetry` retries forever until it succeeds (line 342).

`[reported]` As of 2026-08-25 the arm had **never** been commanded to move. Execution is untested.

**Rules:** clear the workspace first; run `estop.py` in its own terminal before anything else;
never launch `grasp_state_machine` or `ros2_robot_ws/src/main.py` while nobody is physically
present. `background.launch.py` alone is safe-ish — `move_group` only plans when asked — but it
does connect to the real arm.

**The orchestrator defers this danger rather than avoiding it.** `[code]` On startup
`orchestrator.py:78` launches only `background.launch.py` — no state machine, the arm does not
move. But it then waits on `/manipulation/start`, and when that `Bool` arrives it launches
`ros2_robot_ws/src/main.py`, which starts the state machine, which homes the arm.

So **the arm can begin moving because a message arrived, not because a human typed a command** — a
stray `ros2 topic pub`, a leftover navigation node, a replayed bag. There is no point in that
sequence where a person confirms. Treat a running orchestrator as a loaded arm.

### 8.2 Self-annotated bugs in the state machine `[code]`

Someone left explicit markers in `grasp_state_machine.cpp`:

- **677, 699** — `LOGICAL ERROR: missing try/catch`. Two `tf_buffer_.transform()` calls in the
  EXECUTING branch are unguarded, unlike the identical calls in `selectingStep()` which are
  wrapped. A TF exception here crashes the worker thread.
- **702** — `HARDCODING BRITTLE FIX`: the goal's z is overwritten with the current z to stop the
  planner driving into the table. A real fix belongs in the collision scene.
- ~~**706** — `LOGICAL ERROR: return value of moveCartesianStep ignored`~~ **`[unverified]`
  Corrected 2026-09-10: the comment at `:706` is stale — the code below it *does* check the return
  value.** The real defect there is different: the failure branch `return`s out of `workerLoop`
  entirely, silently halting the node with only a `WARN`. See [`CODE_AUDIT.md`](CODE_AUDIT.md) §H.

### 8.3 The `/object_centroid_2d` message is not what it looks like `[code]`

It is a `PointStamped`, but `x` and `y` are **pixel coordinates** and `z` is **depth in metres**.
`sam3_ros_node.py:66` publishes it that way; `grasp_state_machine.cpp` back-projects using camera
intrinsics. Treating it as a 3D point will silently produce nonsense.

### 8.4 Hardcoded absolute paths — nothing runs on a fresh clone `[code]`

⚠️ **Surveyed 2026-09-10. Full inventory and the recommended fix are in
[`NEXT_STEPS.md`](NEXT_STEPS.md) §2.5** — it is a 🔴 blocker, not a tidiness item.

Two things the list below does not convey:

1. **The repo was renamed as well as moved.** Paths assume
   `/home/iot22/GitHub/Renaissance-Capstone-Project/`; the working clone is
   `.../Gappler/`. So *every* hardcoded path is broken — even a fresh clone by the original author
   on the original machine would not match. `main.py`, `orchestrator.py`,
   `ros2_robot_ws/src/main.py` and `sam3_ros_node.py` all fail immediately.
2. **One of them is not a path problem at all.** `src/main.py:303-304` launches OpenVINS from
   `~/Ros2Workspaces/OpenVINS/install/` — an external workspace **not in this repo** — while the
   repo vendors OpenVINS source at `Navigation_Module/OpenVINS/` that has **never been built**.
   Which copy is authoritative is an open question, not a rename.

`src/config/base.py` already computes `Settings.PROJECT_ROOT` correctly and `config/models.py:11`
already uses it. The pattern exists; it was just never applied outside `src/`.



Seven files pin `/home/iot22/GitHub/Renaissance-Capstone-Project/...`. They will break on any other
machine or clone path:

`main.py:18` · `ros2_robot_ws/src/orchestrator.py:23` · `ros2_robot_ws/src/main.py:27,34,39,118` ·
`ros2_robot_ws/src/rm_mtc/src/perception/sam3_ros_node.py:38` · `src/main.py:306` ·
`src/services/object_recognition/sam3_model.py:91,96` ·
`Navigation_Module/src/robot_slam/config/slam_toolbox_localization.yaml:14`

### 8.5 Traps that cost a previous session real time `[reported]`

- **Never set `PYTHONNOUSERSITE=1`.** `~/.local`'s torch is the CUDA build; conda's is CPU-only
  with no `libc10_cuda.so`. The pipeline depends on `~/.local` winning `sys.path`. Do not "clean
  up" `~/.local`.
- **AnyGrasp's depth filter** was `z < 0.5` while the bench scene sat at 1.45 m — every point got
  filtered, MinkowskiEngine received an empty tensor and **segfaulted rather than raising**.
  Presents as: node loads fine, then instant segfault on the first frame.
- **`conda run` without `--no-capture-output`** buffers stdout, and the node looks hung.
- **`main.py` reports child deaths as a warning and keeps running.** A dead AnyGrasp node presents
  as "nothing ever happens". Read the terminal.

---

### 8.6 `Navigation_Module` depends on a package that is not in this repo `[code]`

Both SLAM launch files include a launch file from a package called **`xpkg_demo`**
(`bringup_basic_ctrl.launch.py`) — `slam_mapping.launch.py`, `slam_localization.launch.py`, and
declared as an `exec_depend` in `robot_slam/package.xml:12`. **That package's source is nowhere in
this repository.** `[inferred]` it is the vehicle/power/comm bring-up for the Echo Plus base.

Consequence: `colcon build` may well succeed (it is an *exec* dependency, not a build one), but
**launching will fail at runtime** until that package is obtained. Find out where it came from
before planning a bring-up session — this is a question for whoever set up the base.

**Checked on the box 2026-09-11 (as `rcp2026`):** `ros2 pkg prefix xpkg_demo` with only
`/opt/ros/humble` sourced → `Package not found`; no `xpkg_demo*` anywhere under `~/rcp-desktop` or
`~/rcp-github` (depth 7). `/home/iot22` is not readable by `rcp2026`, so a copy in `iot22`'s own
workspaces is still possible — that account is the one place left to look.

### 8.7 Two nodes both claim `/cmd_vel` `[code]`

- `xnode_vehicle` (`xpkg_vehicle`) is the real driver — subscribes `/cmd_vel`, publishes `/odom`
  with `child_frame_id = robot_base_link`.
- `xpkg_power`'s `xnode_power` **also publishes** `/cmd_vel` (`ros2_interface.cpp:155`), but only
  when its `test_mode` param is true (default false) — a slow creep for auto-docking.
- `echo_plus_driver/echo_plus_node.py` is a **third**, work-in-progress SocketCAN driver that also
  subscribes `/cmd_vel`. Its velocity protocol is an explicit placeholder (`echo_plus_node.py:62-64`)
  and it is **not launched by anything**. Do not run it alongside `xnode_vehicle`.

Also note `xpkg_vehicle`'s ROS1 build publishes odom with `child_frame_id = "base_link"` while the
ROS2 build uses `robot_base_link` (`ros1_interface.cpp:186` vs `ros2_interface.cpp:223`). We use
ROS2; just don't copy frame names out of the ROS1 files.

### 8.8 Silent assumptions that will bite you `[code]`

**Gaze is projected onto a plane at a fixed assumed depth.** `project_gaze()` defaults to
`EyeTrackingConfig.DEFAULT_DEPTH_M = 1.5` metres (`eye_tracking.py:150`, `config/eye_tracking.py`).
The eye tracker gives a *direction* (yaw/pitch), not a distance — so the published pixel
coordinate on `/aria/eye_tracking/gaze_estimate` is only correct for objects at ~1.5 m. Closer or
further and the gaze point drifts off-target. Since `_find_closest_mask()` uses that pixel to pick
which object you meant (§6.2), this directly limits how reliably gaze disambiguates objects.

**The camera's optical frames are not defined in this repo.** `rm_65_w_gripper.urdf.xacro:6`
includes `_d435.urdf.xacro` from the external `realsense2_description` package, which is **not
vendored here** (verified: no `_d435*.xacro` anywhere in the tree). So `camera_link →
camera_color_optical_frame` exists only when that package is installed and the RealSense driver is
running. Every grasp transform depends on it. A missing/unlaunched RealSense presents as grasp
candidates being silently skipped.

**`/object_centroid_2d` has no consumer-side staleness check.** The age guard in
`grasp_state_machine.cpp` is commented out (`:637-641`), so SELECTING will keep servoing toward a
centroid that stopped updating.

### 8.9 Dead code and debug leftovers `[code]`

Not bugs, but they mislead readers. Worth a cleanup pass someday:

- `add_feature_matching()` (`main.py:91-96`) is wired into the builder but **never called** by
  either pipeline — the standalone `feature_matching()` process never launches. The `FeatureMatcher`
  *class* is used, directly instantiated inside `ObjectRecognitionPipeline` (`:97`).
- `_log_calibration()` (`pose_streaming_pipeline.py:53-109`) is defined, never called, and writes
  to a hardcoded relative `temp.txt`.
- Raw `print()` instead of `logger` in several places: `object_recognition_pipeline.py:343`
  (`"Success"`), `feature_matching.py:277` (`"HERE!"`), `pose_fusion_node.py:174,238`.
- `MenuOverlay.topics` (`menu_overlay.py:22-32`) lists **5 of the visualizer's 6 view modes** —
  "Combined Visualization" is missing from the on-screen menu but the `6` key still works.
- `object_recognition_pipeline.py:323-324` — a guard is commented out, so Aria frames are
  re-inferred every frame rather than once. `[inferred]` this may be unintentional; SAM3 is the
  most expensive thing in the loop.

### 8.10 Duplicated constants, one already drifted `[code]`

Found by the naming audit (§0b). These are the same value defined independently in several places
— the pattern that produced the `dummy_mask_publisher` defect.

**Already drifted:** `VIDEO_QOS` is defined canonically in `src/config/ros2.py:16-21`, built from
`shared/config.yaml` with `depth: 10`, and imported by five modules. But
`pose_fusion_node.py:62-66` **re-declares it under the same name with `depth=1`**. Editing the
YAML will silently not affect pose fusion. Either import the shared one or rename the local one
`POSE_FUSION_QOS` and say why the shallower queue is wanted.

**Not yet drifted, same risk:**

| Constant | Copies | Note |
|---|---|---|
| `TOPIC_MASK` | 5 | one already wrong — see §0b |
| `DEPTH_SCALE = 0.001` | 4 | the RealSense mm→m conversion |
| `CAMERA_X_OFFSET = 0.18` | 2 scripts + the literal in `slam_localization.launch.py:102` | three independent copies of one physical measurement; change the arm mount and you can update two and miss the third |
| `SAM3_CHECKPOINT` / `SAM3_PATH` | 2, different mechanisms | `sam3_ros_node.py:37` hardcodes an absolute path; `config/models.py:11` derives it from the project root. Same file today, on one machine only |

### 8.11 `/aria/aruco_pose` is stamped with a frame that does not exist `[code]`

`image_streaming_pipeline.py:60` sets `frame_id = "camera_rgb"`. That string appears **exactly
once in the entire repo** — no URDF defines it, and no static or dynamic transform publishes it.
Any TF lookup against it fails, and the name gives no hint that it means the *glasses'* camera
rather than the arm's.

Currently masked by §6.1: image streaming is switched off, so nothing publishes this topic at all.
It will surface the moment that seam is restored.

### 8.11b `[unverified]` A full line-by-line audit exists — see `CODE_AUDIT.md`

45 findings from reading every file we own, publisher to subscriber, on 2026-09-10. Nothing in it
was verified against running hardware. Most relevant to this section:

- **The grasp path cannot work** — `anygrasp_detection_node.py:182` produces candidates only in
  IDLE, `grasp_state_machine.cpp:171` consumes them only in EXECUTING, and `USE_SIMPLE_EXECUTE`
  makes the whole path dead code so neither gate is exercised (§A).
- **`main.py` promises an emergency-stop key that does not exist** (§B1), and `estop.py` may not
  deliver its own message on Ctrl+C (§B2).
- **`HOME_JOINTS` changed** — joint4 by 176° — and §8.1's safety warning quotes the old values (§B4).
- **Undefined behaviour** in the state machine's threading: one condition variable waited on with
  two different mutexes, and the centroid read without its lock (§C1, §C2).
- **`background.launch.py` is launched twice**, giving two `rm_driver` on one arm (§I1).

---

### 8.12 `[code]` `mtc_sim_test.launch.py` names an executable nothing builds

Found by `bench/static.py` (`launch-executables`), not by running anything.

**Checked on the box 2026-09-11:** every built `rm_mtc` on the machine —
`~/rcp-desktop/install/rm_mtc/lib/rm_mtc/` (the hardware-verified overlay) and
`ros2_robot_ws/install/rm_mtc/lib/rm_mtc/` in both clones — contains only `grasp_state_machine`.
The launch file itself was not run.

`rm_mtc/CMakeLists.txt:23` declares exactly one `add_executable` — `grasp_state_machine` — and
`install(TARGETS ...)` at `:43` installs only that. But `launch/mtc_sim_test.launch.py:11` asks for
`Node(package="rm_mtc", executable="mtc_sim_test")`. **There is no `mtc_sim_test` source anywhere in
the tree.** `trivial_mtc.cpp` also exists and is also never built.

Why it matters more than it looks: this launch file is the one thing described as *planning only,
no hardware — safe to run*. It is what a new person would reach for first, and it appears to be the
only way to exercise MoveIt without the arm.

**To check at the machine:** `ros2 launch rm_mtc mtc_sim_test.launch.py` — the prediction is
`executable 'mtc_sim_test' not found on the libexec directory`. If instead it runs, then something
builds it that is not visible in the CMakeLists and this entry is wrong: delete it.

**If confirmed,** the decision is whether `mtc_sim_test` was deleted, renamed (is
`trivial_mtc.cpp` the intended target?), or never written. Wiring `trivial_mtc` into CMakeLists is
cheap and would give the project a hardware-free MoveIt smoke test, which it currently lacks.

---

### 8.13 `[unverified]` The arm and the LiDAR both claim the same NIC, with different host IPs

Found by reading configs; **the two have never been on the network at the same time**, so this has
never had a chance to surface.

**Checked on the box 2026-09-11 (read-only):** `enp2s0` is confirmed as the only wired port
(`ip link`: `lo`, `enp2s0`, `wlo1`, `tailscale0`, `docker0`). It was `NO-CARRIER` at the time,
so nothing was plugged in or powered. Its saved NetworkManager profile, *Wired connection 1*, is
**manual `192.168.1.100/24`** — neither the arm's `.10` nor the LiDAR's `.5`. If that profile is
what comes up when the cable goes in, the arm connects but sends no feedback (the §9 "presents as
a hang" symptom), unless someone adds `.10` by hand each session. The old preflight IP check
would have reported this as PASS: `"192.168.1.10" in "…192.168.1.100/24…"` (TESTBENCH_PLAN §4
P3, now fixed). Whether both devices can coexist is still `[unverified]` — never tried.

| Device | Device IP | Host must be | Source |
|---|---|---|---|
| RM65 arm | `192.168.1.18` | **`192.168.1.10`** | `rm_driver.cpp:4094,4097` (`arm_ip`, `udp_ip`) |
| Livox MID-360 | `192.168.1.3` | **`192.168.1.5`** | `MID360_config.json` — all five `host_net_info` `*_ip` fields |

Both are on `192.168.1.0/24`, and `[reported]` `enp2s0` is *the only physical Ethernet port* on the
workstation. So to run navigation and manipulation together the host must answer to **both**
`.10` and `.5` simultaneously.

`[inferred]` The likely fix is a second address on the same interface —
`sudo ip addr add 192.168.1.5/24 dev enp2s0` alongside the existing `.10` — plus a switch, since
one port cannot physically reach two devices. Neither is in any launch file or setup doc.

Why it was invisible until now: the arm was verified on the `realman_manip` clone, which has no
`Navigation_Module` at all (§7), and `Navigation_Module` has never been built (§3). Each half was
brought up alone.

**To check at the machine:** `ip -4 addr show enp2s0` — does it carry both addresses? Then
`ping 192.168.1.3` and `ping 192.168.1.18` with both devices powered. `bench/preflight.py -g net`
runs exactly this and names the missing alias.

---

### 8.14 `[unverified]` The AnyGrasp node that was verified is not the one `main` launches

**Checked on the box 2026-09-11:** `checkpoint_detection.tar` (296 MB, dated 2 Apr) exists only
in `~/rcp-github` (the `main` checkout); `~/rcp-desktop` has only `checkpoint_tracking.tar`. So
the detection node's weights are on the machine, but it still has no recorded run. Both clones
have the licence files. **New blocker:** the `anygrasp` conda env lived in `iot22`'s
`~/miniconda3`; `rcp2026` has no conda at all, so neither node can currently run as `rcp2026`.

| | Hardware-verified 2026-08-25 | What `main` launches today |
|---|---|---|
| Node | `anygrasp_node.py` | `anygrasp_detection_node.py` |
| Checkpoint | `log/checkpoint_tracking.tar` | `log/checkpoint_detection.tar` |
| Source | `RCP_NEW_USER_STARTUP_GUIDE.md` §4 T6 + "WHAT WORKED" | `ros2_robot_ws/src/main.py:30,34` |

The only AnyGrasp invocation anyone has observed produce `Frame 0: selected 5 seed grasps` used the
**tracking** node and the **tracking** weights. `main`'s launcher uses the detection variant, which
has no recorded successful run. Neither checkpoint is in git (both gitignored), so a fresh clone has
neither.

§2's tree calls `anygrasp_node.py` "older tracking-based variant" — which is accurate, but reads as
though the newer one is the proven one. It is the other way round.

**To check at the machine:** does `log/checkpoint_detection.tar` even exist? Run
`bench/preflight.py -g assets`, which looks for both. Then launch the detection node alone and see
whether it produces candidates.

**Open question for the team:** is `anygrasp_detection_node.py` the intended future and simply
untested, or did the launcher drift off the working configuration? This decides which one the
grasp path should depend on, and it is worth settling before §6.2 is closed.

---

### 8.15 `[code]` `Navigation_Module` has a second build blocker beyond `xpkg_demo`

**Confirmed on the box 2026-09-11:** `~/rcp-github`'s `livox_ros_driver2/` has a `package.xml`
(format 3, `ament_cmake_auto`, dated 20 Apr) that is gitignored — generated locally by
`build.sh:50` — and `package_ROS2.xml`, its source, is on neither the box nor in git. The
predicted case, exactly. The quickest fix is to commit the box's generated file as
`package_ROS2.xml`. Until then, any fresh clone (including a bench build) needs it copied in.

§8.6 records `xpkg_demo` as missing. There is a second, independent one.

`livox_ros_driver2/build.sh:50` generates `package.xml` by copying `package_ROS2.xml`. The repo
contains **only `package_ROS1.xml`**, and `package.xml` is gitignored
(`livox_ros_driver2/.gitignore:3`). So on a fresh clone the package has no manifest at all and
`colcon` will not see it — before any dependency resolution happens.

This matters for planning because `NEXT_STEPS.md` §3.2 describes building `Navigation_Module` as
"pure compile, touches no hardware, safe remotely" — a good remote task. It will not get as far as
compiling.

**To check:** `ls Navigation_Module/src/livox_ros_driver2/package*.xml` on the lab clone. If a
`package.xml` is present there, it was generated locally by `build.sh` and simply never committed —
in which case the fix is to commit `package_ROS2.xml` from upstream. `bench/static.py`
(`generated-manifests`) checks this.

---

## 9. Hardware facts worth knowing before you plan `[reported]`

| Thing | Value |
|---|---|
| Machine | `iot22-Computer`, Ubuntu 22.04.5, ROS 2 Humble, RTX 4060 Ti 16 GB |
| Arm | RealMan RM65-BI at `192.168.1.18:8080`; workstation **must** be `192.168.1.10/24` on `enp2s0` |
| Arm state feedback | UDP to `192.168.1.10:8089`, 5 ms. Wrong host IP → connects fine, zero feedback, presents as a hang. |
| Controller boot | 8080 opens ~60 s after power-on. `Connection refused` before that is normal. |
| Camera | RealSense D435i, **eye-in-hand on `Link6`** |
| LiDAR | Livox MID-360 |
| Aria glasses | paired, device `1WM10350101291`; certs in `~/.aria` |
| AnyGrasp licence | **machine-locked** to that box. New machine ⇒ re-register, ~2 working days. |
| Assets not in git | `src/models/sam3/sam3.pt` (3.4 GB), AnyGrasp checkpoints, all build trees, `.venv` |

**⚠️ There is no base-mounted RGB-D camera on this robot.** The D435i is the only camera and it is
on the moving wrist. `Navigation_Module` is LiDAR-only — no image topics anywhere in it. The
`d455` files under `Navigation_Module/OpenVINS/src/open_vins/config/` are **stock upstream example
configs**, not evidence of hardware. See §10.

---

## 10. HiCo-Nav integration surface

**Target:** replace or augment the current Nav2-based navigation with HiCo-Nav.

> 📄 **The paper has now been read.** Full review, inputs/outputs, design and a first-pass
> port assessment: [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md); visual version:
> [`hico-nav/hico-nav-map.html`](hico-nav/hico-nav-map.html). Two answers change this section:
> HiCo-Nav emits **velocities** (it carries its own A\* planner, trajectory optimiser and
> controller, so adopting it wholesale displaces Nav2 entirely — the report recommends taking only
> the goal-level layer above it), and the **RGB-D requirement is confirmed and load-bearing**. The
> report also surfaces three dependencies not recorded below: FAST-LIVO2 localisation, a
> LiDAR↔camera extrinsic calibration, and a VLM endpoint (cloud API or a local 8B model contending
> with SAM 3 for VRAM).

### Where it plugs in

Everything in §5 under "The nav ↔ manipulation contract" is the boundary. Concretely, HiCo-Nav
must **consume**:

- `/manipulation/goal_pose` (`PoseStamped`, base_link) — where the object is
- `/manipulator/return_to_user` (`Bool`) — grasp finished, go back
- `/aria/fused_pose` (`PoseStamped`, **`robot_base_link` frame** — see §6.4) — where the user is
- `/cloud_relay` (`PointCloud2`) or `/livox/lidar` — the LiDAR stream
- TF `map → odom → robot_base_link`

and **produce**:

- `/manipulation/start` (`Bool`) — arrived, arm may proceed
- `/return_to_user/goal_reached` (`String`) — return leg outcome
- either `/goal_pose` (if it emits goals for a Nav2 controller to execute) **or** `/cmd_vel` (if
  it replaces the controller outright)

**The first question to answer when reading the paper is which of those last two it is.**

`[code]` Concretely, here is what a replacement would displace (`nav2_params.yaml`):

| Role | Current plugin | Line |
|---|---|---|
| Global planner | `nav2_navfn_planner/NavfnPlanner` (`use_astar: false`, `tolerance 0.5`) | 135-140 |
| Local controller | `nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController` (`desired_linear_vel 0.2`, `lookahead 0.6`, `allow_reversing: false`) | 43-65 |
| Local costmap | `voxel_layer` + `inflation_layer`, global_frame `odom` | 72-84 |
| Global costmap | `static_layer` + `inflation_layer`, global_frame `map` | 115-128 |
| Footprint | **circular, `robot_radius: 0.2` m** — no polygon footprint configured | 79, 118 |
| BT navigator | `nav2_bt_navigator::NavigateToPoseNavigator` | 9-21 |

So: **goals** → HiCo-Nav sits beside `goal_reached_publisher.py`, Nav2 and both plugins stay.
**Velocities** → it replaces `RegulatedPurePursuitController` in the `FollowPath` slot, and you
inherit the costmap/TF plumbing as-is.

`[code]` Oddity worth knowing: `local_costmap` defines a `static_layer` block (105-108) that is
**not listed in its `plugins` array** (80), so the local costmap never consumes the static map.
Present but inert — likely unintentional.

Nothing in `/camera/sam/mask`, `/object_centroid_2d`, `/grasp_candidates`, `/pipeline_state`, or
`/rm_driver/*` should be touched by a navigation change. That separation is what makes it possible
to integrate navigation against a half-working grasp stack.

### ⚠️ Open blocker: HiCo-Nav's RGB-D requirement

> ✅ **Confirmed against the paper, 2026-09-10.** Promoted from `[inferred]` to `[paper]`. The
> visual anchors in the memory graph *are* RGB keyframes and depth is what gives objects 3D
> position, so three separate mechanisms depend on the camera. Option 1 (**buy a D455**, not
> another D435i) is the recommendation; option 2 is now rated worse than assumed below — the
> paper's own small-object success rate falls to 65 % from vibration blur on a *rigidly* mounted
> camera; option 3 discards Tier B entirely. See
> [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §6.1.

`[paper]` HiCo-Nav's Cognitive Memory Graph needs a **continuous forward-facing RGB-D stream**. This platform has no such sensor (§9). Three
options, none free:

1. **Buy a base-mounted D455** (~$400 + NTU lead time). Cleanest; procurement lead time makes it
   urgent, not deferrable.
2. **Use the wrist D435i with the arm parked in a fixed observation pose.** Degraded field of view
   and it conflicts with grasping, but zero cost and probably enough for a first integration.
3. **Substitute the 2D LiDAR scan** and adapt the memory graph. Largest deviation from the paper.

**This decision should be made early** — it is the one that costs weeks if it turns out wrong.

---

## 11. Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-10 | Claude (Opus 5) + Dion | Added §8.11b pointing at the new `CODE_AUDIT.md` (45 findings from a line-by-line read of all owned code). **Corrected §8.2**: the `:706` "return value ignored" comment is stale — the code does check it; the real defect is that the failure branch halts the worker loop. |
| 2026-09-10 | Claude (Opus 5) + Dion | Added the `[unverified]` tag and four findings from the new `bench/` static analysis, all awaiting confirmation at the machine: §8.12 `mtc_sim_test` names an unbuilt executable, §8.13 arm and LiDAR both claim `enp2s0` with different host IPs, §8.14 the verified AnyGrasp node is not the one `main` launches, §8.15 a second `Navigation_Module` build blocker (`livox_ros_driver2` has no ROS 2 manifest). **Corrected §7**: `main` and `realman_manip` have no common ancestor, so the "72 commits ahead" figure was meaningless; added the full branch audit — no arm code on `realman_manip` that `main` lacks. |
| 2026-09-10 | Claude (Opus 5) + Dion | Re-scoped §8.4 after a fresh-clone path survey: the repo was renamed as well as moved, so every hardcoded path is broken; and `src/main.py` depends on an external OpenVINS workspace while the repo vendors an unbuilt copy. Full inventory in NEXT_STEPS §2.5. |
| 2026-09-10 | Claude (Opus 5) + Dion | Naming audit folded in: §0b gained the full collision inventory (9 cases, incl. the new `/manipulation/` vs `/manipulator/` contract split); added §8.10 (duplicated constants, `VIDEO_QOS` already drifted 10→1) and §8.11 (`/aria/aruco_pose` stamped with the undefined frame `camera_rgb`). |
| 2026-09-10 | Claude (Opus 5) + Dion | Added §0b, the descriptive-naming convention, prompted by the `base_link` / `robot_base_link` collision. Renamed the docs index to `START_HERE.md` to stop it colliding with the root `README.md`. |
| 2026-09-10 | Claude (Opus 5) + Dion | Added §6.5 (two nodes publish the same segmentation topics — collision hazard), §8.1 addendum (the orchestrator makes arm motion message-triggered, not human-triggered). Linked the new `NEXT_STEPS.md`. |
| 2026-09-11 | Claude (Opus 5) + Dion | Checked findings on the box over SSH, read-only: §8.12 and §8.15 retagged `[code]` (confirmed); §8.6 `xpkg_demo` absent from ROS and both clones (only `iot22`'s home unchecked); §8.13 adds `enp2s0`'s saved profile `192.168.1.100/24`; §8.14 adds that the detection checkpoint exists in `~/rcp-github` and that `rcp2026` has no conda env for AnyGrasp. |
| 2026-09-09 | Claude (Opus 5), from a full read of `main` @ `2d36a89` | Initial version. Structure, reading order, topic map, three severed seams, HiCo-Nav surface. No hardware available; nothing runtime-verified. |
| 2026-09-09 | Claude (Opus 5), from agent-assisted deep pass on `src/` and `Navigation_Module/` | **Corrected** `/aria/fused_pose` frame (`robot_base_link`, not `map`). Added §6.4 (pose fusion README vs code), §8.6 (missing `xpkg_demo`), §8.7 (three `/cmd_vel` claimants), Nav2 plugin table in §10, and the `base_link`/`robot_base_link` static-TF caveat in §5. |
| 2026-09-09 | Claude (Opus 5), folding in the vendor-arm agent pass | Added §8.8 (fixed 1.5 m gaze depth assumption, external `realsense2_description` dependency, missing staleness guard) and §8.9 (dead code / debug leftovers). Expanded the contract table with `object_approach_node`'s full five-topic subscription list. |

### Open questions for the team

1. ~~HiCo-Nav: goals or velocities?~~ **Answered: velocities**, but take only the goal-level layer.
   `hico-nav/PAPER_REPORT.md` §5.1.
2. RGB-D camera — **recommendation is buy a D455**; needs a decision and a purchase order. (§10)
3. Which SAM3 node becomes authoritative, `object_recognition_pipeline.py` or `sam3_ros_node.py`?
   (§6.2)
4. ~~Cherry-pick `env.sh` + the two docs from `realman_manip` onto `main`?~~ **Answered by the
   §7 audit: yes for `RCP_NEW_USER_STARTUP_GUIDE.md`, `docs/SETUP.md`, `env.sh` and
   `calibration.json`; no for any code, and explicitly not `sensors_3d.yaml`.** Not yet done.
6. Is `anygrasp_detection_node.py` the intended future, or did the launcher drift off the working
   configuration? (§8.14) — decides which node the grasp path depends on.
7. How are the arm and the LiDAR meant to share one NIC? (§8.13) — a question for whoever set up
   the base, alongside `xpkg_demo` (§8.6).
5. Do we need §6.1 and §6.3 restored at all for the HiCo-Nav milestone, or only for the thesis
   demo?
