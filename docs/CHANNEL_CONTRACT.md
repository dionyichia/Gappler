# CHANNEL CONTRACT

> **Paths moved 2026-09-21 (reorg).** Many cites below use the old layout (`src/`, `ros2_robot_ws/`,
> `Navigation_Module/`). Look up the new path in [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.15,
> "Where things moved". Line numbers inside moved files did not change with the move.


**What this is.** The one place that says which subsystem owns which message channel, and what
passes between subsystems. It is task `T0.7` in [`PROJECT_PLAN.md`](PROJECT_PLAN.md), settled by
Dion on 2026-09-20.

**Who this is for.** Dion, Zongzhe and Sherman. If you are about to rename a topic, change a message
type, change a frame, or add a channel that another subsystem reads, this file says whether that is
yours to change and who you have to tell.

**This file is the single source.** [`ORIENTATION.md`](ORIENTATION.md) §5, `PROJECT_PLAN` §3.5,
[`task-tree.html`](task-tree.html) and [`wiring-map.html`](wiring-map.html) used to carry
their own copies of the handover list. They now point here.

**Provenance tags** are the same as the rest of `docs/`: `[code]` read from source, `[reported]` a
person said it, `[inferred]` reasoning, `[unverified]` static finding not confirmed at the machine.
Nothing in this file has been checked on the robot.

---

## 1. The four subsystems and who owns them

| Subsystem | What it is | Lives in | Owner |
|---|---|---|---|
| **Aria** | The glasses: voice, gaze, images, pose | `src/services/` | Dion |
| **Grasp** | Segmentation and grasp prediction: SAM 3, AnyGrasp | `ros2_robot_ws/src/rm_mtc/src/perception/`, `src/services/object_recognition/` | Dion |
| **Bot** | The RM65 arm: driver, MoveIt, the grasp state machine, the orchestrator, the e-stop | `ros2_robot_ws/` | Dion |
| **Nav** | The mobile base: LiDAR, SLAM, Nav2, the bridge nodes, later the memory graph | `Navigation_Module/` | Split, see below |

**Nav has two owners, and the line between them is the goal.** Sherman owns everything that gets the
robot to a commanded point. Zongzhe owns everything that decides which point.

| | Sherman: motion and sensing | Zongzhe: goals and algorithms |
|---|---|---|
| Owns | Base driver, Livox, `qos_relay.py`, SLAM and Nav2 configuration and parameters, the static transforms, mapping and localisation, the base camera driver, the pose-source and FAST-LIVO2 study, `/cmd_vel`, the Nav2 `navigate_to_pose` server | The memory graph, goal ordering, the node that emits drive goals, the graph query service, `object_approach_node.py` and `goal_reached_publisher.py` |

This replaces the old three streams named after people's subsystems. The streams are kinds of work,
not subsystems: **arm and perception** (Dion), **algorithms and graph** (Zongzhe), **platform and
experiments** (Sherman).

---

## 2. Rules

1. **One owner per channel.** The owner is whoever owns the publishing side. Changing a channel's
   name, message type, frame or meaning is the owner's call, and the owner tells the consumers
   before it lands.
2. **One publisher per channel.** Two publishers on one topic is a defect, not a feature. Three
   exist today and are marked below.
3. **One client per action server.** Two clients on `navigate_to_pose` is `CODE_AUDIT` E5.
4. **Every handover states its QoS.** ROS silently drops messages when a publisher and a subscriber
   disagree about delivery settings. Unless a row says otherwise, a handover is `RELIABLE`, depth
   10, which is the ROS 2 default `[code]`. Image and point-cloud channels are `BEST_EFFORT`.
5. **Run the bench before and after any change here.** `./bench/run.sh` fails when a name in this
   contract moves. Re-baseline deliberately with `python3 bench/contracts.py snapshot`.
6. **Names change in one pass, not opportunistically.** Today's names are frozen here. The target
   names are in §7. See [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.4.

---

## 3. Handover points, in the code today

These cross a subsystem boundary. They are the contract.

| # | Channel | Type and frame | From | To | Owner | State |
|---|---|---|---|---|---|---|
| H1 | `/aria/audio/prompt` | `String`, the object word | Aria, `audio_streaming_pipeline.py:49` | Nav, `object_approach_node.py:80` and `goto_glasses.py:59` | Dion | works. Two nav consumers race for Nav2 (E5). Segmentation never listens (L1) |
| H2 | `/manipulation/goal_pose` | `PoseStamped`, `base_link` | Grasp, `object_recognition_pipeline.py:204` | Nav, `object_approach_node.py:74` | Dion | works. From M7 the graph writes it through `T7.1` |
| H3 | `/manipulation/start` | `Bool` | Nav, `object_approach_node.py:97` | Bot, `orchestrator.py:56` | Zongzhe | works. Today it launches a process. Becomes an arm and disarm gate, see B-4 in §6 |
| H4 | `/goal_pose` | `PoseStamped`, `map` | Nav, `object_approach_node.py:90` | Nav2, via `goal_reached_publisher.py:29` | Zongzhe | works. Becomes a handover when the frontier layer writes it (M9) |
| H5 | `/object_centroid_2d` | `PointStamped`, but x = pixel column, y = pixel row, z = depth in metres | Grasp, `sam3_ros_node.py:66` **and** `object_recognition_pipeline.py:192` | Bot, `grasp_state_machine.cpp:146` | Dion | works. Two publishers. Rename pending, §7 |
| H6 | `/grasp_candidates` | `GraspCandidateArray` | Grasp, `anygrasp_detection_node.py:81` **and** `anygrasp_node.py:71` | Bot, `grasp_state_machine.cpp:142` | Dion | works. Two publishers. Nothing reaches the arm today, `CODE_AUDIT` A1 to A3 |
| H7 | `/pipeline_state` | `String`: `IDLE`, `SELECTING`, `EXECUTING` | Bot, `grasp_state_machine.cpp:156` | Grasp, `anygrasp_detection_node.py:65`, `anygrasp_node.py:55`, `grasp_viz.py:61` | Dion | works. The gate that reads it is inverted, see G-4 in §6 |
| H8 | `/camera/camera/color/image_raw`, `/camera/camera/aligned_depth_to_color/image_raw`, `/camera/camera/color/camera_info` | `Image`, `Image`, `CameraInfo`. `BEST_EFFORT` | Wrist RealSense driver | Grasp, 5 nodes. Bot, `grasp_state_machine.cpp:138` | Dion | the wrist D435i is faulty. Replacement decided, T-3 in §6 |
| H9 | `/manipulation/done` | `Empty` | **nobody** | Nav, `object_approach_node.py:83` | Dion | broken. The approach node stays latched without it (F1, observed) |
| H10 | `/manipulator/release` | `Bool` | **nobody** | Nav, `object_approach_node.py:86`. Bot, `orchestrator.py:65` | Dion | broken. Aria will publish it, see A-1 in §6 |
| H11 | `/aria/eye_tracking/gaze_estimate` | `Point` | Aria, `image_streaming_pipeline.py:153` | Grasp, the recognition pipeline | Dion | switched off. M2 and M8 need it, `T2.2` |
| H12 | `/aria/rgb_camera/undistorted` | `CompressedImage`, `BEST_EFFORT` | Aria, `image_streaming_pipeline.py:85` | Nav, `aria_image_relay.py:27`, which decompresses to `/aria/rgb_camera/view` for viewing | Dion | switched off. The relay is kept, see A-4 in §6 |

`[code]` The glasses image does **not** need to reach the arm workspace. Cross-camera matching
happens inside `object_recognition_pipeline.py`, which subscribes to both cameras itself
(Aria at `:130`, the synchronised RealSense pair at `:137-143`) and holds the feature matcher at
`:117`.

### Out of scope: the return-to-user leg

`PROJECT_PLAN` §4 puts the return leg and the pose fusion node out of scope. These four channels
therefore have **no owner** until that changes. They are not deleted, they are parked.

| # | Channel | From | To | Note |
|---|---|---|---|---|
| H13 | `/aria/fused_pose` | Aria, `pose_fusion_node.py:153` | Nav, `goto_glasses.py:47` | Frame mismatch, E1 and E2. Pose fusion may return if gaze in 3D needs the glasses transform |
| H14 | `/robot_pose` | Nav, `pose_publisher.py:12` | Aria, `pose_fusion_node.py:147` | Only feeds pose fusion |
| H15 | `/manipulator/return_to_user` | Bot, `grasp_state_machine.cpp:159` | Nav, `goto_glasses.py:63` | Still fires on every successful grasp |
| H16 | `/return_to_user/goal_reached` | Nav, `goto_glasses.py:68` | nobody, `orchestrator.py:57-59` commented out | |

---

## 4. Handover points not built yet

| # | What passes | From | To | Owner | Decided |
|---|---|---|---|---|---|
| P1 | Base camera stream, `/base_camera/...` | D455 driver on the base | Nav, the memory graph. Dion, calibration | Dion | Dion brings it up first for the calibration in `T5.5`. Sherman owns the mount and the hardware |
| P2 | Graph query: sentence in, object position out | Nav, the memory graph, `T6.8` | Dion's C++ node, `T7.1`, which then writes H2 | Zongzhe | A ROS service, see N-3 in §6 |
| P3 | Gaze image feature into the graph query | Aria, `T8.1` | Nav, the graph query, `T8.2` | Dion | Can ride inside P2's request |
| P4 | Segmentation trigger | Phase logic | Grasp, the one segmentation service | Dion | Dion owns the service and the trigger, see G-5 in §6 |

---

## 5. Measurements

One subsystem writes these down and the others depend on them. Sherman owns the measuring.

| # | Measurement | Where it is written today | Owner |
|---|---|---|---|
| M1 | Arm on the base, `robot_base_link` → `base_link`: 0.18 m forward, 0.48 m up, yawed 180° | `slam_localization.launch.py:98-103`, missing from `slam_mapping.launch.py` (`T3.3`) | Sherman |
| M2 | LiDAR on the base, `robot_base_link` → `livox_frame`: 0.18 m forward, 0.2 m up | both SLAM launch files | Sherman |
| M3 | Forward offset `CAMERA_X_OFFSET = 0.18` | `object_approach_node.py:51`, `goto_glasses.py:35`, and the robot model. `T5.4` makes it one source | Sherman |
| M4 | Base camera pose relative to the LiDAR | not measured. `T5.5` | Dion, with Sherman's rig |
| M5 | Footprint radius: 0.20 m configured, 0.265 m in the chassis manual | `nav2_params.yaml` | Sherman |

⚠️ **M5 is an explicit open check, not a closed decision.** The configured radius is smaller than
the manufacturer's stated turning radius. Do not change it until the integrated robot is measured,
and do not treat the current value as verified.

---

## 6. Decisions settled 2026-09-20

All of these were decided by Dion. Each names where the detail lives.

### Aria

- **A-1. Aria publishes `/manipulator/release`** when the spoken word is "release". With the return
  leg out of scope, the order is: the grasp finishes, the state machine publishes
  `/manipulation/done`, then release is accepted. Closes `CODE_AUDIT` open question 4.
- **A-2. The return leg is out of scope.** H13 to H16 have no owner. Pose fusion is parked rather
  than dropped, because a later gaze-in-3D method would want the glasses transform. This settles
  `CODE_AUDIT` open question 6: `/aria/fused_pose`'s frame is not fixed now.
- **A-3. Gaze by geometry** is not planned in. Build the appearance baseline in M2 first, then decide
  on the evidence. `PROJECT_PLAN` D9, `NEXT_STEPS` §2.13.
- **A-4. Keep `aria_image_relay.py` as is.** It is a decompressor for viewing, not a duplicate
  publisher, and it is useful when stubbing the glasses with a recorded video.

### Grasp

- **G-1. Retire `sam3_ros_node.py`.** The pipeline already subscribes to both cameras and publishes
  the same channels, so retiring the node loses nothing and saves a second 3.21 GB copy of SAM 3.
  Detail and the VRAM argument in `NEXT_STEPS` §2.2 and §2.14.
- **G-2. Folder layout: four top-level folders, one folder per node inside each.** `aria`, `grasp`,
  `arm`, `nav`, and within each, a folder per node holding its code, launch file, config and tests.
  The segmentation service goes in `grasp`, since that is where its model and its consumers are. A
  caller in another subsystem reaches it over ROS. This is also the layout `T0.11` needs, so CI can
  run one test suite per subsystem.
- **G-3. Which AnyGrasp program is authoritative stays open** until the box check of
  `anygrasp_node.sh` in `T0.0`. The two differ in method, tracker against detector, not only in
  checkpoint.
- **G-4. The inverted gate is a typo. AnyGrasp runs during `EXECUTING`.** `CODE_AUDIT` A1 is the
  bug, A2 is correct. `[code]` The sequence is: `SELECTING` steps the arm toward the segmentation
  centroid 4 cm at a time until the object is closer than 0.18 m, then `EXECUTING` starts, AnyGrasp
  proposes candidates, the state machine waits for one stable across 5 frames, and only then plans
  and executes the final move (`grasp_state_machine.cpp:625-716`). So grasp candidates are computed
  after the object is identified and approached, and before the final planned move, which is what
  the fix should preserve. Precomputing candidates while the arm is idle is not useful: they are in
  the camera frame and the wrist camera moves during the approach.
- **G-5. Dion owns both the segmentation service and its trigger** (`T2.4` and `T6.5`). `T6.5`
  shrinks to publishing the trigger. The trigger channel is P4 above.
- **G-6. Rename `/object_centroid_2d`** in the one naming pass, not now. §7.

### Bot

- **B-1. `USE_SIMPLE_EXECUTE` stays `true` for bring-up.** Treated as deliberate, step by step.
  Answers `CODE_AUDIT` open question 1. It hides A1 and A2, so both are fixed before it is flipped.
- **B-2. Use the `realman_manip` home pose values**, the ones the safety document describes.
  ⚠️ **Do not trust either set.** Recalibrate and validate on the simulated arm before any powered
  run. Answers `CODE_AUDIT` open question 2.
- **B-3. `ros2_robot_ws/src/main.py` owns `background.launch.py`.** Delete the launch in
  `orchestrator.py:69-74`. Already recorded in `CODE_AUDIT` open question 5.
- **B-4. "Arrived" stops launching processes.** The arm stack is already running and the state
  machine subscribes to `/manipulation/start` as an arm and disarm gate. Closes `CODE_AUDIT` B6.
  The larger design is `NEXT_STEPS` §2.14.
- **B-5. The state machine publishes `/manipulation/done`** at the end of each cycle, in `T1.8` or
  `T1.9`. Closes H9 and the F1 latch.
- **B-6. Today's names are frozen, target names recorded.** One rename pass later. §7.

### Nav

- **N-1. `goto_glasses` comes out of the launch file, commented out with the reason**, not deleted.
  The same applies to every other out-of-scope item: comment with a note saying it was scoped out,
  so it can come back. Removes the `navigate_to_pose` race, `CODE_AUDIT` E5.
- **N-2. The graph answers queries. It does not drive.** Dion's `T7.1` node writes H2. The frontier
  layer, if M9 happens, writes H4. Answers `NEXT_STEPS` §1.3 for the contract topics.
- **N-3. The graph query is a ROS service.** Request and response, called once per task.
- **N-4. The base camera is `/base_camera/...`.** The wrist camera becomes `/arm_camera/...` in the
  naming pass. Neither keeps the driver default, which is the same for both cameras.
- **N-5. FAST-LIVO2 is in scope, staged.** Build up to it rather than starting with it: the existing
  2D localisation first, then `T5.7`'s error study, then FAST-LIVO2 if the evidence says 2D
  localisation is the limit. Sherman owns the study. This answers `PROJECT_PLAN` D4 and turns
  stretch goal S4 into planned work.
- **N-6. Qualify `/goal_pose` and `/goal_reached`** in the naming pass. §7.
- **N-7. The footprint radius waits for the integrated measurement**, and the check is explicit in
  M5 above so it is not forgotten.

### Team

- **T-1. Sherman takes nav bring-up plus the pose-source and FAST-LIVO2 study.** Zongzhe keeps the
  memory graph, goal ordering and the bridge nodes. The line is §1.
- **T-2. Dion keeps `T5.5` to `T5.7`**, the calibration and localisation-error work. Answers
  `PROJECT_PLAN` D2.
- **T-3. Buy a replacement wrist camera** if the D435i does not survive a replug. Replacements are
  available `[reported]`. Answers `PROJECT_PLAN` D8. **Not needed so far:** the D435i survived the
  replug on 2026-09-22, colour and depth at 15 Hz `[observed]` (T0.12).
- **T-4. Config: one tree per subsystem, with a shared constants package underneath.**
  `NEXT_STEPS` §2.10.
- **T-5. This file is the single source** for the contract.

### The phase table

When each camera's detection runs. This is the trigger policy `T2.4` needed, and it lines up with
the phase-gated model residency in `NEXT_STEPS` §2.14.

| Phase | Glasses | Base camera | Wrist camera |
|---|---|---|---|
| 1, navigating | yes | yes | no |
| 2, grasping | yes today, probably no once the graph carries the instance | no | yes |

---

## 7. Names: today's and the target

Frozen today, renamed in one pass later (`NEXT_STEPS` §2.4). ROS matches names as plain text at run
time, so a rename that misses one place fails silently on the robot.

| Today | Target | Why |
|---|---|---|
| `/manipulation/*` and `/manipulator/*` | one prefix, `/manipulation/*` | One contract split across two prefixes that differ by one letter |
| `/goal_pose` | qualified, for example `/nav/goal_pose` | Sits next to `/manipulation/goal_pose` and means something different |
| `/goal_reached` | qualified by leg | Sits next to `/return_to_user/goal_reached` |
| `/object_centroid_2d` | a name saying pixel plus depth | It is not a 3D point |
| `/camera/camera/*` (wrist) | `/arm_camera/*` | Collides with the base camera's driver default |
| `base_link` | `arm_base_link` | It is the arm's root frame |
| `robot_base_link` | `mobile_base_link` | It is the base's root frame |

⚠️ The frame renames touch URDFs, launch files, C++ and Python, and they are the only ones that can
break motion planning. Do them last, with someone at the robot.

---

## 8. Hidden channels

Channels that a topic list does not show. Each says whether it is assigned.

| # | Channel | Assigned | Owner | Rule |
|---|---|---|---|---|
| X1 | `navigate_to_pose` action, Nav2 | Yes | Sherman owns the server | Exactly one client. The client node is Zongzhe's `goal_reached_publisher.py`. `goto_glasses.py` is the second client today, removed by N-1 |
| X2 | `/cmd_vel` | Yes | Sherman | Only Nav2 publishes it. On the safety list in `CLAUDE.md` |
| X3 | TF tree | Yes, per edge | see below | One publisher per edge |
| X4 | MoveIt `move_group` action and services | Yes, as one block | Dion | Internal to the bot, not a handover. `mtc_planner.cpp:16` plans for `rm_group` |
| X5 | Process launches | Yes | Dion | One launcher per program. `main.py` owns `background.launch.py` (B-3). Launching stops being an interlock (B-4) |
| X6 | Vendor driver topics | Owner per driver, not per topic | `rm_driver` and the wrist camera: Dion. Livox, the base driver and the base camera: Sherman | The vendor owns the names. `/rm_driver/*` is the driver's API, not ours |
| X7 | ROS parameters, 201 of them | Per file | Nav and SLAM YAML: Sherman. MoveIt config: Dion. `shared/global_config.yaml`: Dion | Assigning individual parameters is not useful |
| X8 | QoS | Written into this contract | Dion | Rule 4 in §2 |
| X9 | Visualisation and debug topics | No | whoever publishes them | `/debug/*`, the markers, `/object_marker`, `/object_map_pose`, `/aria/glasses_marker`, and the pickled mask topics. The pickled ones go when `T2.1` lands |
| X10 | OpenVINS and `/aria/vio_pose` | No, out of scope | none | Launched from `src/main.py:309`, no publisher in this repo, only feeds pose fusion |
| X11 | `/goto_glasses/trigger`, `/goto_glasses/cancel` | No, out of scope | none | Subscribed, never published. Return leg only |

### The TF tree, one owner per edge

| Edge | Published by | Owner |
|---|---|---|
| `map` → `odom` | SLAM Toolbox | Sherman |
| `odom` → `robot_base_link` | base driver, `ros2_interface.cpp:165` | Sherman |
| `robot_base_link` → `base_link` | static, `slam_localization.launch.py:98-103` only | Sherman |
| `robot_base_link` → `livox_frame` | static, both SLAM launch files | Sherman |
| `base_link` → `Link1…Link6` → `camera_link` | the arm's robot model | Dion |
| `camera_link` → `camera_color_optical_frame` | the RealSense driver at run time | Dion |
| `robot_base_link` → `aria_glasses` | `pose_fusion_node.py:215-229` | out of scope |

⚠️ `[code]` Two frames are used but defined nowhere in the repository: `camera_rgb`, which stamps
`/aria/aruco_pose`, and `camera_color_optical_frame`, which exists only if the camera driver is
running. Every TF lookup against a missing frame fails silently.

⚠️ `[code]` The `robot_base_link` → `base_link` edge exists in the localisation launch file and not
in the mapping one, so during a mapping run the arm is not attached to the tree at all. `T3.3`.

---

## 9. Internal channels

Everything that stays inside one subsystem belongs to that subsystem's owner. They do not each need
naming here. The full list, with publishers and subscribers, comes from the bench:

```bash
./bench/run.sh report      # every channel, plus the ones with no publisher or no subscriber
```

Known problems inside subsystems, so they are not lost:

| Subsystem | Problem |
|---|---|
| Grasp | `/PLACEHOLDER/sam/mask` in `dummy_mask_publisher.py:14` should be `/camera/sam/mask`. The tool broadcasts into the void |
| Grasp | `/camera/sam/mask` has two publishers, `sam3_ros_node.py:65` and `object_recognition_pipeline.py:189`. G-1 removes one |
| Bot | `/rm_driver/set_gripper_position_cmd` has two publishers, `grasp_state_machine.cpp:150` and `orchestrator.py:51` |
| Bot | ~~`estop.py` ignores the Ctrl+C key, `CODE_AUDIT` B2a, observed~~ Fixed 2026-09-21 (T1.2) |
| Aria | Every glasses channel except the spoken word is switched off, `ORIENTATION` §6.1 |

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-20 | Claude (Opus 5) + Dion | Created. `T0.7`. Twelve live handovers, four parked with the return leg, four planned, five measurements, eleven hidden channels and the TF edge table. Twenty-eight decisions recorded, including the nav split between Sherman and Zongzhe, FAST-LIVO2 staged into scope, the phase table, and the target names for the rename pass. |
| 2026-09-20 | Claude (Opus 5) + Dion | `next-steps-map.html` republished with the new ownership section, the owner changes and T0.7 marked done. `wiring-map.html` §8 gained a pointer to this file and was republished (version 5). ⚠️ Its share pin still points at the old version, so viewers see the previous page until the pin is moved from the page's Share menu. |
| 2026-09-21 | Claude (Opus 5) + Dion | `estop.py` fixed (CODE_AUDIT B2, B2a, B2c, task T1.2): the description of it updated to match. |
| 2026-09-21 | Claude (Opus 5) + Dion | X7: `shared/config.yaml` renamed to `shared/global_config.yaml` (reorg step 2). |
| 2026-09-21 | Claude (Opus 5) + Dion | Pointer at the top to the old-to-new path table in `NEXT_STEPS` §2.15, after the reorg moved our code. |
| 2026-09-22 | Claude (Opus 5) + Dion | T-3: the wrist D435i survived the replug (T0.12), so no replacement is needed so far. Same camera update in `testbench-map.html` and the task tree's 14 September note. |
