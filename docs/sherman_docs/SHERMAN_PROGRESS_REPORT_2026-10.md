# Sherman: progress report, joining the project to 2026-10-23

This is a full information dump of Sherman's work on Gappler, from the first task on 2026-09-16 to
2026-10-23. It will be merged with Dion's and Zongzhe's reports for the team progress presentation
(interim assessment, planned 2026-10-28), then cut down. So it errs on the side of too much detail.
Cut freely. Slide layout is not handled here.

Sherman's part of the system: getting the mobile base to know where it is and where the user is. That
means the base and its LiDAR, the camera mount on the base, mapping and localisation (first SLAM
Toolbox, then FAST-LIVO2), handing the pose and obstacles to Nav2, the calibration rigs, and the
recordings the memory graph (Zongzhe) is built from.

**How to read the evidence.** Task IDs (T3.5d, T5.4) are rows in `docs/task-tree.html`. Run records are
in `docs/bench-runs/` (22 files are Sherman's). Longer write-ups are in `docs/sherman_docs/`. Pictures
and videos are in `docs/sherman_docs/local/report_media/` (gitignored, on Sherman's Mac only). Tags:
`[measured]` from a run, a log or a bag. `[code]` read from source. `[inferred]` reasoning not yet
tested. `[reported]` said by Sherman or another person, with no log behind it. `[unverified]` still to
confirm. A skipped check is written as skipped. Note for the merge: the request lists only four tags.
`[reported]` is added here, and its meaning differs from the repo `CLAUDE.md`, which uses it for claims
from the 2026-08-25 hardware session.

The section numbers here differ from the order in the request, because every stage of the work gets its
own section. Challenges are section 15, next steps 16, visualisation options 17, media inventory 18,
open questions 19.

---

## 0. Summary

| Stage | Where it stands on 2026-10-23 | Headline number |
|---|---|---|
| Groundwork on the shared hardware (T0.1, T0.2, T0.5, T0.9, T1.2 to T1.5) | Done | 23,043 arm joint-feedback packets, 0 dropped (T1.5). D455 about 30 Hz for 60 s (T0.1) |
| Camera mount and geometry (T5.1 to T5.4) | Done for geometry, not calibrated | 12 geometry and navigation unit checks pass. Mount fit PASS `[reported]` (T5.3, T5.4) |
| Base and LiDAR bring-up (T3.4) | Keyboard driving and LiDAR done. No stopping test | Odometry 50.002 Hz, LiDAR 10.0014 Hz, battery 25.1 V (T3.4) |
| Mapping, first try with SLAM Toolbox (T3.5 early, T3.9) | Held on 2026-10-15, all evidence synthetic | 12 synthetic scan cases, 10 of 10 scans each, exact map reload |
| FAST-LIVO2 on a public recording (T3.5a) | Done | 663 valid coloured clouds, 0 invalid, clean exit |
| Own recording (T3.5b) | Done | 74.03 s, 19,987 messages, zero backwards timestamps |
| FAST-LIVO2 on our recording (T3.5c) | Done with residuals | Two PASS replays, LiDAR 747 of 747, 0 invalid outputs |
| Live mapping, hand-pushed (T3.5d) | Done with residuals | 26 m path, returned to start within 12 mm |
| Handing the pose to Nav2 (T3.5f) | Done with residuals. Nav2 itself not run on it | Mid-route error 6.7 cm at most, against a reference that has about 7 cm of its own error |
| Restart inside a saved map (T3.5e) | Deferred to stretch S10 | 3D prototype 7 cm from the tape, SLAM Toolbox reload 25 to 35 cm |
| Camera to LiDAR calibration (T5.5) | Not built. Rig and target are Sherman's, procedure is Dion's | Mount rotation is eye-estimated zeros |
| Drive to a point ten times (T3.6) | Not started. Three prerequisites open | None yet |

**No automatic driving yet.** Every drive so far was manual. T3.4 was keyboard driving with a person at
the base. T3.5d and T3.5f were pushed by hand with the wheel driver off. The name `handdriven1` means
that. Nav2 has never driven the base to a goal. That is T3.6.

Totals `[measured]` on 2026-10-23: 217 commits by Sherman on all branches (git authors `weejingjie24`
and `samwee24`). 18 merged pull requests (#12 to #118), 2 closed (#18, #21), 1 open (#126). Task rows:
22 owned by Sherman alone (14 DONE, 8 open or deferred). 4 more shared rows where Sherman is listed
first or with Zongzhe (T0.2, T0.5, T3.5, T5.4, all DONE). 12 rows list Sherman as second owner after Dion.
Sherman's part is in T1.6 and T1.7, the rest are Dion's (section 3.4). Task T3.5 itself was marked DONE on 2026-10-22. The work log
`docs/sherman_docs/WORK_LOG.md` runs to 2026-10-20. The T3.5f work from 2026-10-21 and 10-22 is
recorded only in the `docs/sherman_docs/t3.5f/` notes.

---

## 1. Context: how this part fits the project

### 1.1 The two papers

Gappler joins two research systems and adds something neither has.

| | FAM-HRI | HiCo-Nav |
|---|---|---|
| What it is | Human-robot interaction with Meta Aria glasses. The user's gaze and speech tell a robot arm which object to pick | Zero-shot language navigation. A robot explores an unseen room and builds a cognitive memory graph of the objects it sees, each with 3D points and a CLIP feature |
| Where it comes in | The original authors of this repo were recreating it. Dion's glasses and grasp work is that recreation | Zongzhe (memory graph) and Sherman (navigation) integrate it |
| Gap we fill | FAM-HRI assumes the object is already in front of the arm | HiCo-Nav finds a class ("a box"), not the instance the user looked at |

The research claim, from Dion's report: carry a gaze-cropped image feature into the memory graph query,
so the robot finds the specific object the user looked at, then drives to it and grasps it.

**What the base has to give the rest of the system.** Sherman's navigation gives the memory graph two
things. A camera pose for every frame, so object points can be stored in one world frame. And a way to
drive to a goal. HiCo-Nav needs an RGB-D camera on the base with a time-synchronised pose (T5.7 and
T5.9 task text, `PAPER_REPORT.md`). FAST-LIVO2 was picked because it gives a LiDAR, inertial and
camera pose with colour in one estimator.

Navigation is split `[code]` (CHANNEL_CONTRACT, decided 2026-09-20): Sherman owns the base, the map,
localisation and driving to a point. Zongzhe owns the graph, goal ordering and the bridge nodes.

### 1.2 Open-source parts built on

We are building something new from existing open-source systems, not tuning one old workflow.

| Open-source part | What it gives us | What Sherman added or changed |
|---|---|---|
| FAST-LIVO2 (HKU MARS lab, `hku-mars/FAST-LIVO2`) through the ROS 2 port `U-AMC/FAST-LIVO2-ROS2`, pinned at commit `a09599a` | LiDAR, inertial and visual odometry that also paints a coloured 3D map | Container recipe and replay harness. Two memory-safety fixes. A repair of the visual map (behind-camera seeds, voxel key mismatch). A restored range gate (`blind_sqr`). A found sign error in the LiDAR to IMU offset. A config checker. The bridge that turns its pose into `odom` for Nav2 |
| SLAM Toolbox | A 2D occupancy map from a 2D scan and an odom pose | An owned map saver with manifest and checksums. A start-pose gate. A mapping-only config with scan matching and loop closing off (`slam_toolbox_fastlivo.yaml`) |
| Nav2 and `pointcloud_to_laserscan` | Planning, driving, 2D scan from a cloud | Params left unchanged on purpose. Added a CustomMsg to PointCloud2 converter for the scan path |
| Livox ROS Driver 2 and Livox SDK2 (Mid-360) | LiDAR points and timing | Native CustomMsg mode for point timing. An owned LiDAR-only launch |
| Intel RealSense ROS driver (D455) | Colour and depth | Started by serial number at 640x480x30, colour only for the mapper |
| Hexman ECHO-PLUS base driver (`xpkg_*`, vendor) | Wheel odometry and velocity commands | Kept as is. Its odom TF is switched off in FAST-LIVO2 mode without editing vendor code |
| ROS 2 Humble, rosbag2 | Messages, recording, replay | Strict bag audit and bag identity tools |

Where HiCo-Nav comes in for Sherman's part: the hand-driven bag `handdriven1` is the stand-in drive
that Zongzhe's graph tasks run on (T6.2 note, T6.3, T6.4, T6.4e). It has colour, LiDAR and poses. It
has no depth topic and the camera to LiDAR rotation is not calibrated, which keeps T6.2 open.

---

## 2. What existed when I started, and what I changed

### 2.1 When I started (September 2026)

`[code]` from `docs/ORIENTATION.md` unless noted.

- The navigation code in the repo had never been built. A package it depends on (`xpkg_demo`) was not
  in the repo. The stack that really ran on the base came from another user's workspace on the lab box
  (ORIENTATION 8.6, 8.15).
- The base was only ever run with a vendor launch. There was no record of the base's own size, the
  camera on it, or where each sensor sat.
- The arm offset 0.18 m was copied in three places, so changing the arm mount could update two and miss
  one (ORIENTATION 8.x, `CAMERA_X_OFFSET`).
- Both SLAM launches flushed the Ethernet address and put back only `.5`, which could drop the arm link
  `.10` (T3.9 text).
- The arm and the LiDAR could not be on the same network port at once (T0.2).
- No camera on the base. No map of the lab. No localisation in a map.
- Navigation was 2D only, from a wheel odometry plus a 2D scan. No image topics anywhere in it.

### 2.2 What I changed, in the order it happened

| Date | Change | Task | Evidence |
|---|---|---|---|
| 2026-09-16 | Switch wired so arm and LiDAR answer together | T0.2 | `setup/T0.2_SESSION.md` |
| 2026-09-16 | Base identified: ECHO-PLUS 460 x 380 x 140 mm, rotation radius 265 mm | T0.9 | `setup/T0.9_BASE_FOOTPRINT.md` |
| 2026-09-22 | D455 validated on USB 3, three streams at about 30 Hz | T0.1 | `setup/T0.1_D455_VALIDATION.md` |
| 2026-09-21 to 09-24 | Fresh clone on the Mac passes L0 to L2 | T0.5 | `bench-runs/2026-09-24-sherman-mac-t0.5-fresh-clone.txt` |
| 2026-09-22 | Three arm safety fixes before any power | T1.2 | `setup/T1.2_SAFETY_FIXES.md` |
| 2026-09-23 | Home pose decided and checked in simulation. Physical setup visit | T1.3, T1.4 | `setup/T1.3_HOME_POSE.md`, `setup/T1.4_PHYSICAL_SETUP.md` |
| 2026-09-26 | Mapping launch joins the arm to the base TF tree | T3.3 | `nav/robot_slam/launch/slam_mapping.launch.py:117-122` |
| 2026-09-16 to 10-06 | D455 mount designed, fitted, geometry single-sourced | T5.1 to T5.4 | `t5/` |
| 2026-10-06 to 10-13 | Base and LiDAR bring-up, bounded keyboard control | T3.4 | `t3.4/` |
| 2026-10-07 to 10-13 | SLAM Toolbox launch and map-save work, all synthetic | T3.5 early, T3.9 | `t3.5/` |
| 2026-10-13 | Arm driver bring-up runbook validated | T1.5 | `bench-runs/2026-10-13-labbox-t1.5-validation.txt` |
| 2026-10-15 | Switch to FAST-LIVO2, task split into T3.5a to T3.5f | T3.5 | WORK_LOG 2026-10-15 |
| 2026-10-16 to 10-19 | Public replay, own capture, own replay, three fork repairs | T3.5a to T3.5c | `t3.5/`, `t3.5c/` |
| 2026-10-20 | Live mapping session | T3.5d | `t3.5d/T3.5d_ATTENDED_RESULT_20261020.md` |
| 2026-10-20 to 10-22 | Bridge, converter, launch switch, drift investigation | T3.5f | `t3.5f/` |
| 2026-10-20 | Restart-in-map work stopped and deferred | T3.5e | `t3.5e/` |

### 2.3 Tests and bench checks added with the changes

No change ships without a covering check. Named from the work log `[code]`.

| Check | What it covers | Task |
|---|---|---|
| L0 `arm-bringup-single-launch` | The arm driver is launched once. Red with 2 sites, green with 1 | T1.2 |
| L0 `joint-poses-within-limits`, `home-joints-decided` | Hard-coded joint rows stay inside URDF limits | T1.3 |
| `bench/test_geometry.py`, `bench/test_camera_navigation.py` | Fixed mounts and the D455 reference for both navigation legs | T5.4 |
| `bench/test_navigation_launches.py` | The launches change no network setting | T3.9 |
| `bench/nodes/test_cloud_scan_pipeline.py` | LiDAR cloud to scan path, L4 simulation | T3.5, T3.5g |
| L0 `FAST-LIVO capture tools` (86 tests), `FAST-LIVO replay harness` (55 tests) | Capture and replay tooling | T3.5c |
| `bench/test_fastlivo_odom_bridge.py` (6 tests, L0) | The bridge transform, with four deliberately broken versions that must fail | T3.5f |
| L4 TF ownership check | Exactly one publisher of `odom` to `robot_base_link` | T3.5f |
| Contract baseline re-snapshot `e531095` | Channel contract after the new nodes | T3.5f |

---

## 3. Stage 1: groundwork on the shared hardware (T0.1, T0.2, T0.5, T0.9, T1.2 to T1.5)

Some of these are arm tasks. Dion's report covers the arm. They are listed here because Sherman did
the work.

### 3.1 What each did

1. **Network (T0.2).** One switch. Workstation on port 1, LiDAR on port 2, arm on port 3.
   NetworkManager keeps three addresses on the box port: `.100`, `.10` (arm) and `.5` (LiDAR). After a
   connection cycle the RM65 at `.18` answered from `.10` and the MID-360 at `.3` answered from `.5`
   `[measured]`.
2. **D455 (T0.1).** Moved to a USB 3 port after a port and cable swap. A 60 s bag of colour, depth and
   aligned depth recorded 2,117, 2,273 and 2,117 messages, about 30 Hz sustained `[measured]`. The
   earlier rate swings were a measurement artefact of `ros2 topic hz`.
3. **Base identity (T0.9).** The Hexman ECHO-PLUS manual gives 460 x 380 x 140 mm and a 265 mm rotation
   radius. Nav2 used a 0.20 m radius, so it was 0.065 m too small `[measured]` from the manual. The
   footprint was taped at the robot on 2026-09-23 as 0.380 x 0.460 m (T1.4).
4. **Fresh clone (T0.5).** An isolated clone of `dev` on the Mac passed L0 to L2. L3 to L6 were skipped
   because the Mac has no ROS 2 or NVIDIA card. Joined with Zongzhe's half in PR #29.
5. **Arm safety fixes (T1.2).** The stop program now stops on Ctrl+C, kill and a closed terminal. The
   launcher no longer promises a stop key that does not exist. The second arm-driver launch in the
   orchestrator was deleted behind a new failing-first check (red with 2 launch sites, green with 1).
6. **Home pose (T1.3).** The existing home row stayed. In simulation it passed 2 of 2 full cycles. The
   alternative from `realman_manip` failed the final approach 5 of 5 times, joint 4 reaching -3.092
   against a -3.1 limit. Purpose-built candidates were checked against forward kinematics, and the
   variant matrix passed 3 of 3 (baseline, 80 px sideways, shortened 0.22 m).
7. **Arm bring-up runbook (T1.5).** Validated in an attended session on 2026-10-13, Sherman operating
   and Dion at the power button. 23,043 packets on the wire, 0 drops, joint rate about 200 Hz, no
   motion `[measured]`.

### 3.2 Problems found

| Problem | Fix or state | Task |
|---|---|---|
| Two operator notes disagreed about the same arm pose | Original row kept, rejected alternative documented | T1.3 |
| Return pose test used a stale constant (2.3562 against fixed 2.3000) | Test-only fix | T1.3 |
| ROS hz shows a late wobble 140 to 171 on the joint topic | Open, ROS side, candidate for T4.3 | T1.5 |

### 3.3 Still open

- T1.4 cell measurements are blocked until a table exists. The reach figure D3 needs a written
  transcription (T1.4 residual).
- The arm controller rejects the hardware e-stop, so the stop is software only (Dion's T1.42).

### 3.4 Arm and grasp rows shared with Dion (owner DS)

The task tree lists 12 rows as Dion first, Sherman second. Most are Dion's work and are in Dion's report.
This report claims only what Sherman's own docs record or Sherman confirmed on 2026-10-23.

| Task | Sherman's part | Source |
|---|---|---|
| T1.6 | Wrote the driver-only runbook (T1.5) and the no-motion handshake procedure for the first powered arm session on 2026-09-23. The session result is in Dion's report | `WORK_LOG.md` (T1.6 procedure entry) |
| T1.7 | Dion ran the first commanded arm motion to HOME on 2026-09-23. Sherman checked the arm's joint readings against the HOME row `[reported]`. Every joint ended within 0.02 degrees of the row `[measured]`. This confirmed on the real arm the pose Sherman chose and checked in simulation in T1.3 | task row T1.7, `bench-runs/2026-09-23-labbox-t1.7-home-joint-states.txt` |

Sherman watched the T1.22 gripper tests.
Not claimed here, Dion's work: T1.11, T1.12, T1.22, T1.24 (done) and T1.18, T1.20, T2.5, T8.3
(open). T3.7 (navigation to arm handover) and T5.5 (camera to LiDAR calibration) are also DS rows. They
are covered in sections 13 and 16 for Sherman's side only.

---

## 4. Stage 2: the camera mount and the geometry (T5.1 to T5.4, T3.3)

### 4.1 What it does

The D455 sits on the front of the base on a 20 x 20 mm aluminium extrusion (190 mm long). Navigation
uses its depth origin as the reference point for both the approach and the return leg. Everything else
on the base (arm, LiDAR, camera) has one fixed position in one config file.

Step by step:

1. CAD and measurements for the mount (T5.2, v1 2026-09-16). Version 2 on 2026-09-24 changed the plate
   stack to a 3 mm middle plate and a 5 mm top platform, so the camera sits higher, per Dion's request
   for navigation.
2. Fabricate and fit (T5.3, 2026-10-06). Sherman reported rigidity, arm clearance, cable route and
   navigation view all PASS `[reported]`. Both RGB and depth endpoints delivered live frames for serial
   146222253541 `[measured]`.
3. Measure as-fitted geometry (T5.4). Bottom screw at (0.208, 0, 0.528) m, axle height 65 mm, axle in
   line with the chassis midpoint `[reported]`.
4. Compose the chain (T5.4). Intel's macro gives the screw to the camera link offset (0.01115, 0.0475,
   0.0145) m, then the colour sensor offset and the optical frame flip. Exactly two static publishers
   cover the mount and the sensor frames `[measured]` (T5.4 doc).
5. Navigation uses it. Approach stops 0.6 m and return stops 0.5 m from the target, planar, measured
   from the D455 depth origin by TF, not from the old 180 mm figure.
6. Single-source (T5.4). One YAML (`shared/global_config.yaml`) holds the arm, LiDAR and camera mounts.
   Both SLAM launches read it. The mapping launch also joins the arm tree: `robot_base_link` to
   `base_link` at (0.18, 0, 0.48) m, yaw 180 degrees (T3.3). A live `tf2_echo` returned exactly that
   `[measured]`.

### 4.2 Results

| Check | Result | Tag | Source |
|---|---|---|---|
| Geometry, model and camera-navigation unit checks | 12 pass | `[measured]` | T5.4 |
| Mock navigation controls | 9 pass, 4 known expected-fail | `[measured]` | `bench-runs/2026-10-06-sherman-t5.4-full.txt` |
| Builds on the box | 24 arm and grasp packages, 18 nav packages, exit 0 | `[measured]` | same |
| Planar distance check, 10,000 random cases | maximum error about 5e-15 m | `[measured]` | `t5/T5.4_D455_TF.md` |
| Whole box suite | FAIL, exit 1 | `[measured]` | same |

The whole-suite failure is not a geometry fault. The state machine simulation refused to start because
the real arm was reachable, which is by design. And the L5 robot check failed because the Aria glasses
were unplugged. No safety guard was bypassed.

### 4.3 Problems found and fixed

| Problem | Fix | Task |
|---|---|---|
| Three separate copies of the 0.18 m arm offset | One config, checked by test | T5.4 |
| "180 mm" turned out to mean the camera, not the robot front | New rule: D455 depth origin for both legs | T5.4 |
| Installed Intel macro gave x = 0.01115, not the 0.0158 first used | Corrected from the installed package | T5.4 |
| A missing camera TF would have produced a wrong goal | No goal or start is sent, return retries when TF appears | T5.4 |

### 4.4 Still open

- Mount rotations (roll, pitch, yaw) are visually estimated zeros with no uncertainty. Calibration is
  T5.5.
- Photo archival of the fitted mount, angular uncertainty and the clearance method (T5.3 residuals).
- A cached TF is not proof the camera is alive (T5.4 residual).
- Physical stopping accuracy is unproven (T3.6).

---

## 5. Stage 3: base and LiDAR bring-up (T3.4)

### 5.1 What it does

The ECHO-PLUS base takes velocity commands and reports odometry. The Livox MID-360 gives scans. T3.4
proved both talk to the box, and that a person can drive the base slowly with the keyboard through a
bounded speed limiter, with a single path from keyboard to driver.

Path: keyboard teleop, then the Nav2 velocity smoother, then the vendor base driver. Teleop sends
nothing for 0.25 s of silence then stops. The smoother bounds forward and reverse speed and returns to
zero after the input stops. A fail-closed guard refuses to start on the wrong ROS domain.

### 5.2 Results

| Check | Result | Tag | Source |
|---|---|---|---|
| LiDAR PointCloud2 rate | 10.0014 Hz, one publisher | `[measured]` | `2026-10-13-sherman-t3.4-stationary.txt` |
| Base odometry rate | 50.002 Hz, zero reported motion at rest | `[measured]` | same |
| Battery | 25.1 to 25.2 V, both battery flags clear (19.3 V on the chassis display on 2026-10-07 triggered a hold) | `[measured]` and `[reported]` | same, `...t3.4-attended-hold.txt` |
| Limiter on private test topics | Output back to zero 0.500 s after input stops | `[measured]` | `...t3.4-excerpts.txt` |
| Pipeline silence | Zero observed in 0.457 to 0.603 s | `[measured]` | `...t3.4-remote.txt` |
| Attended driving | W forward, S reverse, A and D turn, X stop all confirmed, Q exits, chassis powered off | `[reported]` | `t3.4/T3.4_BASE_BRINGUP.md` |
| Five-minute read-only recorder | 2,079 raw and 4,162 final commands, 15,000 odometry and 15,000 status messages | `[measured]` | `...t3.4-stationary.txt` |
| Keyboard and smoother bench, private domain | PASS (after one harness fix) | `[measured]` | `...t3.4-pr-checks.txt` |

### 5.3 Problems found and fixed

| Problem | Fix | Task |
|---|---|---|
| Keyboard bench failed at idle publication. First message came at 1.944 s, only 7 fit the fixed window | Harness readiness fix, test first (4 red then green). Keyboard behaviour unchanged | T3.4 |
| Burst keyboard input could pile up | Non-blocking teleop with a burst correction | T3.4 |
| Missing hand remote raised a "remote controller lost" flag | Explained, not a lost-CAN stopping behaviour | T3.4 |
| Handover claimed all processes stopped, an inspection showed the earlier drivers still running | Cleanup authorised, drivers already gone, recorded | T3.4 |
| The SLAM launches flushed the Ethernet address and put back only `.5`, which could drop the arm link | Launches no longer touch Ethernet | T3.9 |

### 5.4 Still open

- No stopping distance, braking or watchdog measurement. The power button is reported to stop the base
  immediately, with no timed result and no emergency-stop rating (T3.4 text).
- Odometry accuracy of the wheels was never measured.
- A timed physical-stop test is a prerequisite of T3.6 and is not yet written.
- Installed overlay still differs from source (3 drift, 1 missing). Reviewed deployment and a live
  network coexistence check are owed (T3.9).

---

## 6. Stage 4: mapping, first attempt with SLAM Toolbox (T3.5 early, 2026-10-07 to 10-13)

### 6.1 What it does and what was built

The original route: LiDAR, then a QoS relay, then a 2D laser scan, then SLAM Toolbox builds a map, then
Nav2 plans on it. The work in this stage made that route safe and testable without any robot motion.

1. Remove the network changes from both SLAM launches (T3.9).
2. Use one owned PointCloud2 wrapper for all three navigation entry points.
3. Bench the cloud to scan conversion on synthetic scans.
4. Add gates before localisation starts: the saved map must exist and be non-empty, a start pose must be
   given (`GAPPLER_MAP_START_POSE=x,y,theta`), and a manifest file with SHA256 over the snapshot must
   verify. Any failure refuses to start before any hardware action.
5. An owned saver for new map snapshots, with manifest, mapping-mode check, a pause and restore of
   measurement, and an explicit "robot is stationary" acknowledgement.

### 6.2 Results (all synthetic, no live LiDAR)

| Check | Result | Tag | Source |
|---|---|---|---|
| Cloud to scan conversion, 12 cases | 10 of 10 distinct scans each | `[measured]` | `2026-10-07-sherman-t3.5-cloud-scan.txt` |
| Focused tests on the box | 29 pass (47 later, after the T3.4 merge) | `[measured]` | `2026-10-13-sherman-t3.5-phase2.txt`, `...resolved-dev.txt` |
| Real installed mapper save, then fresh localiser reload | Exact map raster recovered | `[measured]` | `2026-10-07-sherman-t3.5-slam-persistence.txt` |
| Three known poses with biased odometry | Error 0.000 to 0.001 m, 0.001 rad | `[measured]`, ideal synthetic | `...phase2.txt` |
| Reseed through `/initialpose` | 0.000 m | `[measured]` | `...init-pose.txt` |
| Startup trials, control against treatment (relocated scans) | Control 1.440 m wrong, treatment 0.080 m recovered | `[measured]` | `2026-10-15-sherman-t3.5-targetfix.txt` |
| A map from another user's folder (545 x 390 cells at 0.05 m) | Loads cleanly | `[measured]` | `2026-10-15-sherman-t3.5-historical-map.txt` |

### 6.3 Problems found

| Problem | State | Task |
|---|---|---|
| A corrupt graph aborts the localiser (`std::length_error`) with no safe rejection | Open, vendor behaviour | T3.5 |
| A missing deserialise reply leaves no usable map | Open | T3.5 |
| Upstream image saver breaks on paths with spaces | Direct argv saver used | T3.5 |
| First fair-control test compared against the wrong place (replay start, not end) | Test expectation fixed | T3.5 |

### 6.4 Why it was held

On 2026-10-15 Sherman chose FAST-LIVO2 as the implementation. SLAM Toolbox work was held, not deleted.
Branch `t3.5-launch-prep` stays as the verified software record. The decision was about getting a
coloured, camera-fused pose for HiCo-Nav, and all of the above evidence is synthetic. It proves
plumbing and gating, not map or localisation quality.

---

## 7. Stage 5: FAST-LIVO2 offline on a public recording (T3.5a)

### 7.1 What it does

FAST-LIVO2 takes LiDAR scans, 200 Hz inertial data and camera images. It matches each scan to a voxel
map to estimate the pose, then also uses image patches to refine it and paints each map point with the
image colour. Output: a pose about 20 times a second (frame `camera_init` to `aft_mapped`) and
`/cloud_registered`, the coloured points in the world frame.

Steps in T3.5a:

1. Pin the fork (`a09599a`) and build it inside a container with no network, 2 CPUs, 8 GiB.
2. Convert the authors' public recording to a ROS 2 bag (14,850 messages, originals untouched).
3. Replay it into the mapper at 0.25 speed through a harness that counts every input, every output and
   refuses to call a run good if any count is off.

### 7.2 Results `[measured]`

| What | Result | Source |
|---|---|---|
| Conversion | 14,850 of 14,850 messages | `T3.5_FASTLIVO_REPLAY.md` |
| Final PASS run `t59-replay-20261016T175305Z-433728` | Supervisor and all processes exit 0 | same |
| Input coverage | 667 LiDAR, 668 camera, 13,511 IMU plus 4 before start (allowance 21) | same |
| Outputs | 665 odometry, 663 valid clouds (9.18 M points), 618 RGB, 0 invalid | same |
| Visual retrievals | 663 | same |

### 7.3 Problems found and fixed

| Problem | Effect | Fix | Task |
|---|---|---|---|
| One-byte image over-read at `vio.cpp:1679` (found by AddressSanitizer) | Memory error during replay | Sampling guard in the fork | T3.5a |
| Mapper crash at shutdown | Run could not end cleanly | Root cause: `-march=native` (32-byte Eigen alignment) against a prebuilt PCL (16-byte). Alignment cap added in the recipe | T3.5a |
| First claim "empty LIO clouds are intended design" | Wrong wording | Withdrawn. They are source-observed heartbeats, not proven intent | T3.5a |
| One mislabeled ASan image | Wasted run | Guard added: an overridden image needs explicit flags | T3.5a |
| Mixed ASan binary abort | Run aborted | `T35_LD_PRELOAD` | T3.5a |

### 7.4 Still open

No accuracy, live-sensor or Nav2 claim comes from T3.5a. The replay shows that the mapper runs
correctly on someone else's data.

---

## 8. Stage 6: our own recording (T3.5b and the capture day)

### 8.1 What it does

Record real data from the real sensors on the base, then check every message before trusting it.

Steps: start the Livox driver in native CustomMsg mode (the only format with per-point time offsets),
start the D455 colour stream only (640x480 at 30 Hz), record with `ros2 bag record`, then audit the
file with `rosbag2_py` (no hand-rolled message decoding).

### 8.2 Results `[measured]`

| Recording | What | Source |
|---|---|---|
| `t35b_proof3` (2026-10-17) | 74.03 s, 19,987 messages, 2.2 GiB. LiDAR 10 Hz CustomMsg, IMU 200.0 Hz, colour 30 Hz, zero backwards timestamps, zero USB overflow warnings | `T3.5_SENSOR_CAPTURE.md` |
| Audit of the same bag | 740 scans, 14,807 IMU, 2,220 images, 14,799,936 LiDAR points, 51.84 % zero-range, max LiDAR gap 106.095 ms | `T3.5_VERIFICATION_20261017.md` |
| `t35c_standoff` (2026-10-17) | 746 scans, 2,238 images, same near-surface picture as `t35b_proof3` | `T3.5_CONSUMER_CONTRACT.md` |
| D455 depth probe | Depth value on 3.2 % of raw pixels (3.0 % aligned), scattered speckle, no coherent surface | work log 2026-10-17 |
| `stationary02` (2026-10-19) | 74.648 s, 747 LiDAR, 14,931 IMU, 2,179 images and 2,179 CameraInfo. Rates 10.00, 200.00 and 29.19 Hz. 14,940,000 LiDAR points, 35.92 % zero-range | `T3.5_CAPTURE_AUDIT_20261019.md` |
| Four projections across `stationary02` | 2,459 to 2,569 LiDAR points land in the camera image at 1.19 to 8.57 m | same |

![LiDAR points drawn on the camera image at the start of stationary02](local/report_media/nav_lidar_on_camera_overlay_stationary02_t0s_2026-10-19.png)
*Each dot is a LiDAR return placed in the colour image with the nominal camera to LiDAR transform.
Colour shows depth. Recording stationary02, scan 0. Shows the shared coverage and that the transform is
roughly right, not that it is calibrated. (T3.5c capture audit)*

![Earlier recording with foam mats close to the sensor](local/report_media/nav_lidar_on_camera_overlay_foam_mats_standoff_t32s_2026-10-17.png)
*The 2026-10-17 standoff recording. All in-frame LiDAR returns sit at 0.16 to 0.24 m in a thin band at
the bottom. A low foam surface was in the way, so this scene could not test the camera to LiDAR
rotation. It is why the capture was redone on 2026-10-19. (T3.5c)*

### 8.3 Problems found

| Problem | Effect | Fix or state | Task |
|---|---|---|---|
| First recording `t35b_proof` had no LiDAR topic (recorder missed the overlay) | Unusable | Kept, marked unusable | T3.5b |
| Scene was foam mats resting on a bench, not a barrier. The first reading of the scene was wrong | Wrong claim in a document | Withdrawn and recorded | T3.5c |
| Reported depth probe figure was 0.03 %, true 3.2 % | Wrong claim | Corrected 2026-10-18. The "inside min-Z" reading was withdrawn | T3.5c |
| LiDAR did not answer ping or ARP on 2026-10-19 morning | Capture would have been wasted | Actual config targets `.3` with host `.5`, not the probed `.12` | T3.5c |
| `ROS_DOMAIN_ID` pinned nowhere on the box, so a fresh pane silently runs on domain 0 | Empty graph | Explicit export gate in the plan | T3.5c |
| `stationary01` had unequal image and CameraInfo counts and background walking | Not selected | Kept as record | T3.5c |
| Accelerometer in g, not m/s squared (0.990 at rest as published) | Needs care downstream | Flagged for the consumer, bag untouched | T3.5b |
| Per-scan point offsets unsorted | Motion deskew path never sorts | Reported, not rewritten | T3.5b |
| LiDAR driver exits with SIGBUS after SDK shutdown (inside libspdlog) | Unclean driver stop | Open, parked, bag replay does not use the live driver | T3.5c |
| Image-to-LiDAR lag measured 31.7 ms | Needed in the consumer contract | Recorded | T3.5 |

---

## 9. Stage 7: FAST-LIVO2 on our recording (T3.5c)

### 9.1 What it does

Replay our own recordings through the mapper, twice per bag. Run A has the image off (`img_en: 0`,
LiDAR and inertial only). Run B has the image on (`img_en: 1`, adds the visual update and colour). The
two configs differ in that one line and nothing else (checked by `diff`).

### 9.2 Results `[measured]`

| Run | Config | Result | Source |
|---|---|---|---|
| `t35b_proof3` A (2026-10-18) | image off | PASS | `T3.5c_REPLAY_20261018.html` |
| `t35b_proof3` B (2026-10-18) | image on | FAIL: 419 typed-empty clouds, no positive retrieval in 1,469 attempts | same |
| Public bag on the repaired image | image on | PASS, 663 retrievals, 0 invalid | `T3.5c_PUBLIC_REGRESSION_20261019.md` |
| `stationary02` A `t59-replay-20261019T151612Z-21456` | image off | PASS. LiDAR 747 of 747, IMU 14,923 of 14,931 (8 before start, allowance 21). 743 odometry over 74.21 s, 432 clouds (5,530,694 points), 0 invalid | `T3.5c_STATIONARY02_REPLAY_PREP.md`, work log |
| `stationary02` B2 `t59-replay-20261019T164028Z-25771` | image on | PASS. Camera 2,179 of 2,179, 1,303 visual retrievals, 0 invalid, 118 zero-point coloured clouds recorded and matched to the mapper's own count of 118 | same |

### 9.3 What the work found in the mapper (the interesting part)

Each item was checked against source and by experiment before it was accepted. No finding was accepted
on one line of evidence.

| Finding | Evidence | Effect |
|---|---|---|
| **Behind-camera visual seeds.** Visual map generation checked pixel bounds but not positive depth. Seeds could be stored behind the camera | Counters: 3,604,174 stored-point checks all rejected as behind the camera. A visibility guard cuts appended seed points 22,016 to 5,558 on the public scene `[measured]` | On the old bag, run B stayed failing after the guard. That scene (foam, near surface) gave no usable seeds. The repairs were proven on the public bag |
| **Voxel key mismatch.** Insertion and retrieval used different arithmetic for negative coordinates (`vio.cpp:228-238` against `380-398`) | Buggy control: key hits 1,392,458 against 1,878,707 shadow hits. With the fix they match: 1,855,269 equals 1,855,269 `[measured]` | Retrieval missed real map points. Accepted retrieval points rose 112,980 to 128,385 |
| **LiDAR to IMU offset has the wrong sign (F3).** The fork's Mid-360 profile uses the manual's IMU position unnegated but applies it with a rule that needs the negation (`IMU_Processing.cpp:85-92`) | Four independent lines agree: code rule, the Livox manual (IMU at +11.0, +23.29, -44.12 mm), the fork's own Avia entry, upstream FAST-LIVO. `[code]` | About 10.2 cm of geometric inconsistency in every replay before 2026-10-19. Qualitative verdicts unaffected. New configs carry (-0.011, -0.02329, 0.04412) m |
| **Range gate cannot act (F2).** `blind_sqr` is declared with no value and never assigned, because the port dropped upstream's line `blind_sqr = blind * blind` | Control run: median 19,968 points per scan, the full packet count. Patched image: median 9,607 (9,411 to 9,875). Ratio 0.4811 per scan against a predicted 0.48. Removed fraction 0.5206 against the audited 51.84 % zero-range `[measured]` | The gate dropped nothing on `t35b_proof3`. On the public bag the patched gate changes only 0.5 % of points (24,008.5 to 23,885.5 median source points) |
| **F1.** `lio.max_iterations` is read by nothing. The code reads `lio.min_iterations` | `grep` returns zero hits | No numeric change today, but raising it in a config would do nothing |
| Config sweep of 42 parameters | Five findings, none changes a number in our staged pair | `T3.5_CONFIG_SWEEP_20261019.md` |
| Zero-point coloured clouds (118 of 1,482 frames on `stationary02`) | The stock publish path still publishes a fielded cloud with zero points when nothing projects into the image. Deterministic across two runs `[code]` | Harness records them only when its count equals the mapper's count |

### 9.4 Harness work (so the verdicts mean something)

The replay harness refuses to pass a run with any unexplained miss. Three bounded allowances were added,
each test first, each re-frozen with new file hashes, each strict:

| Allowance | Rule | Why |
|---|---|---|
| One lost terminal message | Only the last stamp of a non-LiDAR topic, strictly after the last LiDAR callback, exactly one message | 4 of 6 public runs on 2026-10-19 lost the final camera frame at bag end. The loss is image-independent. No VIO frame can use that message |
| Zero-point coloured clouds | Harness count must equal the mapper's own `coloured_points=0` count, in visual mode, every such frame had source points | Stock behaviour |
| RGB count | Restated as validity plus a bound (monitor cannot see more than the mapper published). No count is a target | The same image scored 606 RGB on 2026-10-18 and 389 on 2026-10-19. The mapper publishes `/rgb_img` with queue size 1 to a best-effort monitor |

Provenance rule: every run carries its image ID by immutable hash (`ac276ad7...` is the combined image),
a manifest of about 20 to 95 files, and the exact harness bytes.

### 9.5 Still open (T3.5c residuals, from the task row)

- Offline smoke on a 74.6 s stationary recording. Not map quality, not calibrated geometry.
- Why 118 scans have nothing in the camera view is not shown.
- The mount rotation is eye-estimated zeros, and the extrinsic sign is documented, not measured in the
  field (T5.5 is the calibration gate).
- The added RGB bound check has not been exercised in a live replay.
- The LiDAR driver SIGBUS at shutdown.

---

## 10. Stage 8: live mapping, hand-pushed (T3.5d)

### 10.1 What it does

The real sensors feed the real mapper while a person pushes the base by hand. No wheel driver runs and
nothing is commanded.

1. Lab box rebooted by hand first (a silent hang at 06:19 on 2026-10-20, same signature as 2026-10-06,
   cause unknown).
2. Native Livox and D455 drivers run on the box. The mapper image `ac276ad7` runs in a container on the
   host network (no devices, no extra capabilities, domain 174, localhost only). No native FAST-LIVO2
   build exists on the box (Sophus and vikit are absent).
3. A sensor-free dry run first. `stationary02` played from the host into the container reproduced run B2
   (747 LiDAR, 2,179 images, 118 zero-point frames at the same positions, 1,303 retrievals), but not bit
   for bit (418 of 1,482 coloured counts differ, median 0.1 %).
4. Stationary start, then a hand-driven loop, then two slow spins.

### 10.2 Results `[measured]` (`t3.5d/T3.5d_ATTENDED_RESULT_20261020.md`)

| What | Result |
|---|---|
| Stationary 24 s, first launch | Pose moved 0.8 mm. Odometry 20.0 Hz, cloud 40.0 Hz |
| Stationary 30 s after restart | Max displacement 5.7 mm |
| `handdriven1` bag | 117.9 s, 43,610 messages, 4.5 GB |
| Odometry | 2,356 messages, 0 invalid, no backwards stamps, longest gap 0.098 s, largest step 5 cm |
| Coloured clouds | 2,186 with points (median 1,157), 170 zero-point frames (7.2 %), 2,356 default-empty heartbeats, 0 invalid |
| Path | 26.05 m horizontal (29.9 m in 3D, the extra is height jitter inside a 9.4 cm range), farthest 3.47 m from start |
| Return to start | Mapper 12 mm horizontal, 4 mm vertical, 2.4 degrees yaw. Sherman by eye: about 1 cm from the tape mark |
| LiDAR-only check of the same return (T3.5f) | 4 mm. So the odometry error is 7 mm, or 0.03 % of the path |
| Map | Coherent per Sherman, except the glass and mirror section |
| Compute | Mapper is CPU only (no CUDA anywhere in the pinned source). Per-frame LIO plus VIO median 11 to 14 ms against a 100 ms scan period, 95th percentile 55 to 72 ms in the heavier logs, maximum 116 ms (`t3.5e/T3.5e_COMPUTE_STEP0_20261020.md`) |

![Coloured 3D map of the lab, orange hand-driven path](local/report_media/nav_fastlivo_map_iso_handdriven1_2026-10-20.png)
*FAST-LIVO2 coloured map from the 118 s hand-driven run, seen from above at an angle. The ceiling and
far ghost points from glass are cropped. People in the lab appear in the colours. (T3.5d)*

![Hand-driven path from above with a zoom on the start and end](local/report_media/nav_fastlivo_trajectory_closure_handdriven1_2026-10-20.png)
*The path coloured by time over the 2D occupancy view. The inset is 10 cm by 10 cm around the start
(green) and the end (square). Raw odometry closes 12 mm and the checked end-point error is 7 mm.
End-point accuracy only. (T3.5d, T3.5f)*

### 10.3 Problems found

| Problem | Effect | State | Task |
|---|---|---|---|
| Box Ethernet lost carrier several times (13:48:19 to 13:48:51) while the Orin cable was unplugged | Mapper logged IMU time jumps of 8.1 s and 15.1 s and 9 empty-cloud errors, then reset | Recorded, link stable after. Stationary evidence predates it | T3.5d |
| Mapper teardown aborts (`RCLError`, context invalid) | 2 of 4 stops aborted. The other 2 had unknown exit codes | Open | T3.5d |
| Spin test cannot decide the LiDAR to IMU sign | Reported pose follows the extrinsic it is given. The two spins differ by (-0.018, -0.042) m against 2 x T = (-0.022, -0.047) m `[inferred]` | The sign stays documented from the manual and code, not measured | T3.5d |
| Visual-mode odometry is 20 Hz, not the 10 Hz in the runbook | Wiring review used 10 Hz | Corrected | T3.5d |
| Fixed sleep raced the camera parameter server in the probe script | Mapper aborted with "Camera model not correctly specified" | Script fixed, run kept as evidence | T3.5d |

### 10.4 Still open

No absolute accuracy. No calibration. The bridge constant should come from the same extrinsic the mapper
ran with, so the sign question does not move the base pose (T3.5d note). Live runs are not
reproducible bit for bit.

---

## 11. Stage 9: handing the pose to Nav2 (T3.5f)

### 11.1 What it does

Design decided on 2026-10-20 (called option 2):

1. FAST-LIVO2 gives the pose. `fastlivo_odom_bridge` turns `/aft_mapped_to_init` into the TF edge
   `odom` to `robot_base_link`: `T_odom_base(t) = Tb * P0^-1 * P(t) * Tb^-1`. `P0` is the first pose, so
   odom is the base at start-up. `Tb` is the offset (0.191, 0.02329, 0.15588) m from the mapper's IMU
   body to the base.
2. A converter, `livox_custom_to_cloud`, turns the Livox CustomMsg into a normal point cloud for the 2D
   scan. A normal Python subscription takes 110.6 ms to decode one 19,968-point message, longer than the
   100 ms scan period. A raw subscription with numpy takes 0.38 ms and matches field for field on 60
   test messages `[measured]` (`t3.5e/T3.5e_RELOCALISATION_START_20261020.md`).
3. SLAM Toolbox runs in mapping mode every session, with its own scan matching and loop closing off. It
   supplies `map` to `odom` and the `/map` grid that Nav2 needs. FAST-LIVO2 cannot make a grid.
4. The wheel driver stays the source of `/odom` velocity (the mapper pose has zero twist) but its TF is
   switched off with `pub_tf: False`.
5. One launch switch: `odom_source:=wheel|fastlivo`, default `wheel`, so existing behaviour is unchanged.

![How the pieces connect from sensors to a map the robot can use](local/report_media/nav_pipeline_fastlivo_to_nav2_2026-10-22.png)
*Wiring of the FAST-LIVO2 path. Solid links were checked live on 2026-10-21 (T3.5f). Nav2 (dashed) was
not run on it.*

### 11.2 Checks done `[measured]` unless tagged

| Check | Result | Source |
|---|---|---|
| Bridge unit tests (L0) | 6 pass. Offset arithmetic, first sample is identity, straight drive follows the base forward even when started 30 degrees turned, turn in place about the centre leaves the base still, a 0.73 and -0.4 degree tilt of the start frame cancels, wrong frame names refused. Four deliberately broken versions all fail | `bench/test_fastlivo_odom_bridge.py` |
| Wheel TF off | `GroupAction` plus `SetParameter` reaches the driver only if the group is unscoped. A scoped group left `pub_tf` True | `tools/fastlivo/bridge_checks/` |
| Launch switches | Four argument sets evaluated, "ALL SWITCH EXPECTATIONS HOLD" | `tools/fastlivo/live/evidence_dry_check_20261021.txt` |
| Live wiring checks, 2026-10-21 | PASS `[reported]` in the task row. Per-check output sits in the box session folder `t35f-live-20261021/logs`, not in a repo run record | task row T3.5f |
| `bench/run.sh quick` | 9 pass, 0 fail, 13 skipped (no venv, PyYAML or ROS on the Mac). `contracts check` PASS | PR #117 |
| PR #117, merged 2026-10-21 | 46,579 lines added, 239 removed, 416 files changed (mostly evidence tooling) | `gh pr view 117` |
| PR #118, merged 2026-10-22 | Test-only fix for a flaky L4 test (`cloud_scan`). Merged at Sherman's request before the 20-run loop on the box | `gh pr view 118` |

### 11.3 The closure investigation (an honest detour)

Two live runs on 2026-10-21 each ended 0.32 m from where they began, in opposite directions. The first
reading was drift of about 2 % of the path. It turned out to be placement.

| Reading | Result `[measured]` | Source |
|---|---|---|
| Odometry first to last, run 1 and run 2 | 0.318 m and 0.312 m | `T3.5f_ROUTE_ANALYSIS_20261021.md` |
| LiDAR-only first to last (no odometry, no map) | 0.319 m and 0.321 m | same |
| Closure after subtracting the LiDAR-only value | 1 mm (run 1), 9 mm (run 2) | `T3.5f_DRIFT_CAUSE_20261021.md` |
| Run 2 start onto run 1 end, cross-run LiDAR fit | 1.2 cm | same |
| Run 2 end onto run 1 start | 1.4 cm | same |
| Sherman's recollection | Run 1 started on the taped mark A. Run 2 started where run 1 ended | `[reported]` |

So the base was put down at two places 0.32 m apart and the two runs are the same trip in opposite
directions. FAST-LIVO2 itself closed to about 1 cm. The earlier ranking ("favourable outlier", "run 2
attitude", "marks distorted") was withdrawn in the same document. Not tape-measured, so the tape check
is still owed (see 11.5). The retest of this reading has not happened. Sherman decided on 2026-10-23
to present the results as they stand.

![Error of FAST-LIVO2 against the hand-driven reference along both runs](local/report_media/nav_t35f_drift_step3_error_vs_time_2026-10-21.png)
*Blue is the error with the pose at the scan stamp. Orange is the error with the pose shifted 0.15 s.
The grey band is the reference's own error, about 7 cm. The error follows speed and falls back to zero
at rest, which is the signature of a timestamp offset and not drift. (T3.5f, drift note)*

### 11.4 Mid-route accuracy and the stamp lag `[measured]`

- Against the `handdriven1` map as an independent reference, with the 0.15 s lag removed, FAST-LIVO2 stays
  within 6.7 cm in run 1 and 6.5 cm in run 2 for the whole route. Without the correction 12.7 and 11.3 cm.
  Median 8 mm and 15 mm. The reference carries about 7 cm of its own error, so 6.7 cm is at the floor
  (`T3.5f_DRIFT_LOCATE_20261021.md`).
- The mapper stamps its pose at publish time, about 0.15 s after the scan it describes. Three
  independent readings agree: the pose-time sweep (best delta +0.15 s on all three bags), the reference
  track, and the spin sharpness test (wall thickness 13.5 mm at 0.15 s). The cause of the lag itself is
  `[inferred]`, from reading the source.
- Effect: surfaces smear by speed times 0.15 s, about 4 cm at 0.28 m/s, for anything that pairs a scan
  with a transform by stamp.
- Fix prepared, off by default: `stamp_offset_s` in the bridge (default 0.0), proposed -0.15. A mapper
  patch to stamp measurement time would make -0.15 wrong, so the two must change together.
- Weak directions in the room are mild (smallest horizontal eigenvalue median 0.128, ratio to the middle
  one about 1.3). The error does not line up with them.
- Spins: translation drift 0.081 m (corrected extrinsic) against 0.124 m (pre-correction), but each is
  one spin and the pre-correction one was faster, so this is not decisive.

### 11.5 Floor marks (ground truth that did not close)

Marks A, B and C taped on the floor. Tape: AB 2.00 m, AC 2.00 m, BC about 2.80 m, plus or minus 0.05 m,
arms drawn parallel so headings are 0 by construction `[reported]`. Odometry at the marks (run 1, odom
frame): B (2.262, -0.124), C (-0.045, 1.991), A again (0.247, -0.202) `[measured]`.

With the start on A, mark C fits (-0.008 m) and mark B does not (AB +0.264 m). B to C is 3.130 m against
2.80 m, so 0.33 m too long. The three readings do not isolate the cause. Candidates: mark placement,
tape reading, or the pose chain during the mark tour (13 and 92 "HARD time lag" self-syncs before the B
and C readings). These are residuals for the fixture (T5.8), not for the estimator.

### 11.6 Replay A, B, C and D (staged, not run)

Four replays were staged to separate visual-update, glass and compute causes. After the placement result
they are expected to reproduce about 0.3 m by construction, so they were not run. Replay D (handdriven1
at 0.3 speed) would still test whether the 12 mm closure reproduces with four times the time budget.
The pose dump and a rate cap raised to 0.3 are in the harness (`T3.5f_REPLAY_AB_20261021.md`).

### 11.7 Problems found

| Problem | Effect | Fix or state | Task |
|---|---|---|---|
| Mapper frames are `camera_init` and `aft_mapped`, not `map` and `body`. Its TF cannot be switched off | Wrong assumption in the review | Remap `/tf` to `/fastlivo/tf` in the container | T3.5f |
| Mapper odometry rate 20 Hz in visual mode, not 10 Hz | Review wrong | Corrected | T3.5f |
| Pinned fork has no map load or relocalise path (writes a PCD only) | Restart in a saved map needs something extra | See stage 10 | T3.5e |
| Camera model abort on first mapper start (run 1) | Cause not isolated, second start worked. Guess: discovery race | `[unverified]` | T3.5f |
| Initial tilt of `camera_init` differs by about 1.2 to 1.5 degrees per launch (accelerometer gravity estimate) | Start frame slightly tilted | Bridge uses the full first pose as `P0` and refuses to publish above 2 degrees start tilt (measured 0.73) | T3.5f |
| Base driver publishes its own odom TF by default | Two publishers on one edge | Unscoped `GroupAction` sets `pub_tf: False`. A rate-based check proves exactly one publisher | T3.5f |

### 11.8 Still open

- `stamp_offset_s` is unset. Set -0.15 only after recording `/tf` with it on and rerunning the offset
  sweep (expect best delta near 0), and a SLAM Toolbox pairing with no extrapolation errors.
- Nav2 has not followed the resulting `map` frame.
- `navigation.launch.py:70` reads `/livox/lidar` as PointCloud2. In fastlivo mode that topic carries
  CustomMsg, so the scan silently gets nothing. Likely fix: read `/cloud_relay`, with a launch wiring
  test (T3.6 prerequisite).
- A tape-measured start and end, to turn the placement result from LiDAR geometry plus recollection
  into a tape reading.
- Mapper teardown abort. PR #118's 20-run loop on the box is owed (the box checkout was dirty when it was written).
- The mid-route result is at the reference floor, not better.

---

## 12. Stage 10: restart inside a saved map (T3.5e), deferred

### 12.1 What was done

The pinned fork only writes a PCD at shutdown and never reads one. So "start the robot inside a saved
map" needs something outside the mapper. Sherman decided on 2026-10-20: version 1 starts near a known
pose, a person gives a guess, registration refines it. Start anywhere is out of scope.

A numpy prototype (`tools/fastlivo/reloc/`, frozen 2026-10-20, runs 1 to 31) registered the first 3 s of
a second launch against a map built from `handdriven1`. Then the option 2 design (SLAM Toolbox map and
reload) was tested offline.

### 12.2 Results `[measured]`

| Test | Result |
|---|---|
| Second start relative to the first, 3D prototype | (1.94, 1.19) m, yaw within 1 degree, 2.3 m in plan. Three variants agree within 1.5 cm |
| Against tape measure (2.00, 1.16) m, plus or minus 5 cm | Plan error 0.067 to 0.074 m. One pose pair, not an accuracy statistic |
| Inlier gate | True fits 0.959 to 0.975. Wrong local fits 0.73 to 0.75. Provisional threshold 0.9 sits in a gap of about 0.2 |
| Operator-style guess, 8 corners of plus or minus 0.5 m and 15 degrees | 7 of 8 converged within 0.4 cm and 0.2 degrees. The eighth (0.713 inliers) was refused by the gate |
| Planarity filter | 0.5 is the default. Switching it off regressed the self-test from about 0.2 cm to 8.2 cm |
| SLAM Toolbox reload, same bags | 0.25 to 0.30 m from the tape in the default setup (5 identical sessions, so systematic). Other variants 0.16 to 0.47 m |
| A map from FAST-LIVO2 poses only, plain matcher | 0.148 m, about three times better than the scan-matched map (0.498 m) |
| 3D prototype for comparison | 0.070 m |

The SLAM Toolbox map was warped against FAST-LIVO2's own cloud (per-tile shifts 0 to 0.5 m). The poses-only
map agrees much better (66 % at 0.10 m, against 60 %), and SLAM Toolbox cannot reload that graph at all (it
segfaults on it). `[inferred]` The map is the dominant factor, not the matcher.

### 12.3 Decision and state

Deferred to stretch S10 by Sherman on 2026-10-20. Reason: every session now builds its SLAM map and its
memory graph from start-up, so no restart-in-map is needed for M3 to M8. The evidence stays for S10.
A stamp re-stamping patch (emulated) did not clearly help and was not approved. The three-floor-mark
recovery check was never done, so T3.5e is not met.

### 12.4 Still open

All of T3.5e. Candidates not yet tried: Nav2 AMCL on a poses-only map image, `lidar_localization_ros2`
(Humble supported, needs a build of about 30 minutes, not on the box), the Orin (compute never measured
there).

---

## 13. Stage 11: calibration rigs (T5.5, not built)

### 13.1 What exists

M5 needs LiDAR points projected into the camera image to land on the right objects, with the camera pose
error written down as a number. Dion owns the procedure and the numbers. Sherman owns the rig and the
target. Neither has been built.

What is there as a stand-in:

- A nominal camera to LiDAR transform composed from the measured mount: `Rcl = [0,-1,0, 0,0,-1, 1,0,0]`,
  `Pcl = (-0.0115, 0.3425, -0.03915) m`. Labelled nominal, not calibrated. `[code]` (T3.5 consumer
  contract, section 4).
- A projection pre-check tool (`project_scan.py`, 26 tests) that draws LiDAR points on the image with that
  transform.
- A sensitivity figure: rotation is the weak axis, about 6.7 pixels per degree at this camera `[code]`.
- `live_preview.py`: a read-only live view with the overlay, rates and freshness, shown in a browser over
  an SSH tunnel. It found that a Python subscription to the LiDAR saturates one core (4.4 Hz intake at 99 %
  CPU) and that fix was made.

### 13.2 What this does not prove

Overlays on `stationary02` show about 2,500 points landing in the image over a shelf, a chair and the
floor at 1.19 to 8.57 m. They look right by eye. They are not a measurement of rotation error, because
glass and reflections are in view and there is no known target.

### 13.3 Open

Build the target and rig, run the procedure with Dion, record the number (T5.5). Then verify (T5.6, Dion).
The calibration gates T6.2's depth recording and HiCo-Nav's use of depth.

---

## 14. The recordings collected and what came out of them

### 14.1 Recordings on the lab box (Sherman's)

| Recording | Date | What | Size | Used for |
|---|---|---|---|---|
| `t35b_proof3` and `proof2` | 2026-10-17 | Stationary, near foam mats | 74.03 s, 19,987 messages, 2.2 GiB | T3.5b, T3.5c old-bag tests |
| `t35c_standoff` | 2026-10-17 | Stationary, retreated 1.5 to 3 m | 746 scans, 2,238 images | Projection pre-check |
| depth probe | 2026-10-17 | D455 depth and aligned depth | 1.73 GB, 9,419 messages | Showed depth is unusable in that setup |
| `stationary02` | 2026-10-19 | Stationary, shelf and chair scene | 74.648 s, 20,036 messages | T3.5c A and B2 |
| `handdriven1` | 2026-10-20 | Hand-pushed loop | 117.9 s, 43,610 messages, 4.5 GB | T3.5d, T3.5e, Zongzhe's graph |
| `spin-corrected`, `spin-precorrection` | 2026-10-20 | One slow turn each | 408 LiDAR messages in the first | Sign test, T3.5e |
| T3.5f run 1 | 2026-10-21 | Hand-pushed loop with floor marks | 32,615 messages, 2.49 GB | T3.5f |
| T3.5f run 2 | 2026-10-21 | Same, started at the end of run 1 | 34,159 messages, about 2.5 GB | T3.5f |

The T3.5f message counts are from the bag `metadata.yaml` files on the box, read on 2026-10-23
(`~/rcp-Gappler/log/t59-fastlivo/log/t35f-live-20261021/bag` and `.../run2/bag`) `[measured]`.

All are rosbag2 in sqlite, original bytes untouched, hashes in `tools/fastlivo/EVIDENCE_*.sha256`.

### 14.2 What was made from them

| Output | Numbers | Where |
|---|---|---|
| Coloured map of `handdriven1` | 2,186 non-empty clouds, 2,873,812 raw coloured points, 945,543 at 2 cm, 228,709 at 5 cm | `local/presentation/data/handdriven1.npz` |
| PCD from the recorded cloud, for the relocaliser | 228,709 points at 5 cm, frame `camera_init` | box, under the acceptance run output (exact path not checked) |
| Maps (2D) | 5 cm cells. Hand-driven map 730 x 390 with 5,980 occupied cells | `tools/fastlivo/acceptance/results_run1/` |
| T3.5f map | `final_map.pgm` and `.yaml` | box, `t35f-live-20261021/maps` |
| 12 objects of ground truth on the hand-driven drive | Zongzhe (T6.4e) | PR #110 |
| Graph run on the whole drive | Zongzhe (T6.4 step 1) | PR #112 |

### 14.3 Gaps (T6.2)

`handdriven1` has no depth topic. Depth has to be made by projecting the LiDAR into the colour camera, and
that fills 2 to 13 % of the image. The camera to LiDAR rotation is not calibrated. T6.2 stays open until a
recording with the D455 aligned depth on is made, after T5.6 (Zongzhe's note, T6.2 row).

Faces of lab visitors and students are in the colour frames and in the coloured map. Check before any
external showing.

---

## 15. Challenges

1. **A shared robot and one box.** Three people and a CI runner use the same box. Several runs stopped
   at a custody check. The box hung silently twice (2026-10-06 and 2026-10-20) and needed a power cycle.
   Cause unknown. `/home` is 89 % full (36 GB free on 2026-10-23). Lab box access works over Tailscale,
   on 2026-10-19 and 2026-10-21 the campus route timed out.
2. **A port that was missing a line.** The ROS 2 port of FAST-LIVO2 had three silent defects we found:
   a range gate that never took a value (F2), a LiDAR to IMU sign error (F3), and a negative-coordinate
   key mismatch in the visual map. Each needed source reading, a control run and a repair image. None of
   it shows in a normal "it runs" test.
3. **Honest reporting under pressure.** At least five earlier statements in the work log had to be
   withdrawn in writing: the foam "barrier" reading, the depth probe percentage, the 5 cm map thickness, the
   "empty clouds are intended" claim, and the "favourable outlier" drift ranking. The writing rule is
   that a withdrawn claim stays in the record with the correction.
4. **No ground truth.** Tape marks on the floor disagreed by 0.26 to 0.33 m with themselves. The
   reference map has about 7 cm of error. The tape on the start and end was a recollection. A fixture
   with a fixed outline for the base is the fix (T5.8).
5. **Timing.** The mapper stamps its pose 0.15 s late. Speech, glasses and wrist camera have their own
   delays (Dion). A time offset looks like drift until you check that it vanishes at rest.
6. **Glass and mirrors.** The lab room is glass-walled. About 42 % of 5 cm points lie outside the glass
   box (`glass_ghost_points` image, figure from `local/presentation/README.md`) and cannot be told apart from real objects outside. The map was
   coherent except the glass and mirror section.
7. **Replay is not live.** Replay hides timing and network faults. The Ethernet flap in T3.5d showed it.
8. **Mapper stops abort 2 of 4 times** and the LiDAR driver exits with SIGBUS after shutdown. Neither
   corrupts the data written before it, neither is fixed.
9. **Compute on the target machine.** The mapper is light on the box (11 to 14 ms median). The Orin was
   never measured.
10. **Robot safety evidence is thin.** No stopping distance, no timed stop, no hardware e-stop rating on
    the base. The only proof is Sherman's report that the power button stops it at once.

---

## 16. Next steps, in order

| Order | Step | Task |
|---|---|---|
| 0 | Run the box verification that PR #117 skipped (L0 to L4 on the T3.5 changes), and the 20-run `cloud_scan` loop for PR #118 | PR #117, PR #118 |
| 1 | Decide and set `stamp_offset_s` (-0.15 proposed), with the two checks listed in the drift note | T3.5f residual, T3.6 prerequisite |
| 2 | Fix `navigation.launch.py:70` to read the converted cloud, with a launch wiring test | T3.6 prerequisite |
| 3 | Write and run a timed physical-stop test, then record the stopping distance | T3.6 prerequisite, T3.4 |
| 4 | Build the trial fixture: fixed outline for the base, marked start and goal points, one written centring rule | T5.8 |
| 5 | Drive to a commanded point ten times, record the error each time (the M3 acceptance) | T3.6 |
| 6 | A reviewed install of the navigation overlay and a live network coexistence check | T3.9 |
| 7 | Build the calibration rig and target, run with Dion, write the error as a number | T5.5, then T5.6 |
| 8 | Record again with the D455 aligned depth on, after T5.6 | T6.2 |
| 9 | Navigation to arm handover on hardware, with Dion and Zongzhe | T3.7 (needs T3.8) |
| 10 | Time every stage and report the 99th percentile | T4.2 |
| 11 | Pose-source accuracy study (drift and duplicate-object rate) on the new route | T5.7, T5.9 |
| 12 | Restart in a saved map, picking up the frozen 3D prototype or AMCL | T3.5e, stretch S10 |
| 13 | Check the lab photo policy for off-site models | T6.11 |

---

## 17. Visualisation options for the navigation section

One judge is a visualisation professor. Ranked by impact for the effort. Pick two or three. Each says
which data already exists and how much work remains.

| # | Visual | Data exists | Work left |
|---|---|---|---|
| 1 | **Coloured 3D map, orbiting, with the path** (opener). A viewer sees the lab appear, with the colours coming from the camera | Yes. `nav_fastlivo_map_orbit_handdriven1_2026-10-20.gif` and `.mp4`, three stills | None. Re-render to remove people from the colours if used externally |
| 2 | **Map build-up with the camera picture in the corner.** The map grows as scans arrive, the robot is a marker, the live D455 image plays bottom right | Yes. `map_buildup` GIF and MP4 | None |
| 3 | **Closure zoom.** The path draws itself, then the camera zooms into 10 cm around start and end | Yes. `trajectory_draw` GIF, stills | None. State the 7 mm and 12 mm wording the same way everywhere |
| 4 | **Error against time with and without the 0.15 s correction.** Shows how we found a time offset hiding as drift, and that the error vanishes at rest | Yes. `nav_t35f_drift_step3_error_vs_time` | About 2 hours. Cut to two panels, larger text. Depends on the placement retest (question 1) |
| 5 | **Interactive 3D viewer in a browser.** The audience rotates the coloured map. A slider for time shows the map as it grew | Yes. 945,543 points at 2 cm, 228,709 at 5 cm | About half a day (a small three.js page, the 5 cm cloud is web-sized) |
| 6 | **Photo beside the map as seen from that camera pose**, then a moving side-by-side | Partly. Two stills exist (`camera_vs_map_shelf`, `camera_vs_map_chair`), frames at 5 Hz exist | About half a day for 20 s of video. Alignment is limited by the eye-estimated rotation, so caption it that way |
| 7 | **LiDAR points on the camera image before and after calibration.** Best single figure for M5. It goes in the paper (T5.6) | Before-calibration overlays exist | Needs the T5.5 session first, then one render |
| 8 | **Ten drives to a point, scatter of landing errors around the target with a circle at 10 cm** | No. T3.6 is planned after 2026-10-28, so this cannot exist for the presentation | Needs T3.6. Highest value for M3. One robot session plus a plotting script |
| 9 | **Three bugs found in the port as before and after bars** (19,968 against 9,607 points, 1,392,458 against 1,878,707 key hits, 22,016 against 5,558 seeds) | Yes, all numbers are in run records | About 1 to 2 hours. Low value for a general audience, good for a methods slide |
| 10 | **Phone video of the base being pushed, beside the map being built** | No. No media was taken | Not possible without a new session |

The pipeline diagram (`pipeline`) and the timeline of T3.5 (`timeline`) already exist as clear slides. The
stats card has six numbers and one footnote on what is not claimed.

---

## 18. Media inventory

All in `docs/sherman_docs/local/report_media/` (gitignored, never committed). Copies, not moves. The
originals are in `docs/sherman_docs/local/presentation/out/`, in `tools/fastlivo/`, and on the lab box.

| File | Shows | Task | Section |
|---|---|---|---|
| `nav_fastlivo_map_iso_handdriven1_2026-10-20.png` | Coloured map, three-quarter view, with path | T3.5d | 10 |
| `nav_fastlivo_map_top_handdriven1_2026-10-20.png` | Same map straight down | T3.5d | 10 |
| `nav_fastlivo_map_inside_handdriven1_2026-10-20.png` | Same map at eye height | T3.5d | 10 |
| `nav_fastlivo_map_orbit_handdriven1_2026-10-20.gif` and `.mp4` | Camera orbits the coloured map, 14 s, GIF 800x450, MP4 1920x1080 (71 MB) | T3.5d | 10, 17 |
| `nav_fastlivo_map_buildup_handdriven1_2026-10-20.gif` and `.mp4` | Map grows as clouds arrive, camera image in the corner | T3.5d | 10, 17 |
| `nav_fastlivo_trajectory_closure_handdriven1_2026-10-20.png` | Path from above, 10 cm zoom on start and end | T3.5d, T3.5f | 10 |
| `nav_fastlivo_trajectory_draw_handdriven1_2026-10-20.gif` | The path drawing itself | T3.5d | 17 |
| `nav_camera_vs_map_shelf_handdriven1_2026-10-20.png`, `nav_camera_vs_map_chair_...png` | Photo, coloured map from that pose, LiDAR-only grey | T3.5d | 10, 17 |
| `nav_glass_ghost_points_handdriven1_2026-10-20.png` | Ghost points behind glass in red | T3.5d | 15 |
| `nav_pipeline_fastlivo_to_nav2_2026-10-22.png` | Wiring from sensors to a usable map | T3.5f | 11 |
| `nav_extrinsic_sign_fix_diagram_2026-10-18.png` | The LiDAR to IMU offset sign fix | T3.5c | 9 |
| `nav_t35_timeline_2026-10-22.png` | T3.5 progress, 15 to 22 October | T3.5 | 0 |
| `nav_stats_card_handdriven1_2026-10-22.png` | Six headline numbers | T3.5d | 0 |
| `nav_lidar_on_camera_overlay_stationary02_t0s_2026-10-19.png`, `..._t74s_...png` | LiDAR points on the colour image, start and end of the recording | T3.5c | 8, 13 |
| `nav_lidar_on_camera_overlay_foam_mats_standoff_t32s_2026-10-17.png` | The failed scene with foam near the sensor | T3.5c | 8 |
| `nav_d455_colour_mid_frame_depth_probe_2026-10-17.png`, `nav_d455_raw_depth_sparse_speckle_2026-10-17.png` | Colour and raw depth of the depth probe | T3.5c | 8 |
| `nav_live_preview_overlay_capture_day_2026-10-19.png` | The live preview overlay during capture | T3.5c | 13 |
| `nav_t35f_drift_step1_track_overlay_2026-10-21.png` | Run 1, run 2 and `handdriven1` tracks in one frame | T3.5f | 11 |
| `nav_t35f_drift_step3_error_vs_time_2026-10-21.png` | Error against time, with and without 0.15 s | T3.5f | 11 |
| `nav_t35f_drift_step3_error_on_map_2026-10-21.png` | The same error drawn on the map | T3.5f | 11 |
| `nav_t35f_drift_step4_weak_directions_2026-10-21.png` | Weak directions along the route | T3.5f | 11 |
| `nav_t35f_route_report_stamp_corrected_2026-10-21.png` | Route report with the stamp correction | T3.5f | 11 |
| `nav_t35f_first_last_frames_2026-10-21.png` | First and last camera frames of each run | T3.5f | 11 |
| `nav_camera_frames_along_t35f_run1_2026-10-21.jpg` | 16 camera frames along run 1 | T3.5f | 11 |
| `nav_topdown_density_three_recordings_2026-10-21.png` | LiDAR density, three recordings, top down | T3.5f | 11 |
| `nav_glass_box_vs_paths_2026-10-21.png` | The estimated glass box against each path | T3.5f | 15 |
| `nav_slamtoolbox_reload_maps_side_by_side_2026-10-20.png` | 2D maps A, B, C from the option 2 reload test | T3.5e | 12 |
| `nav_reloc_first_frame_handdriven1_start_2026-10-20.png`, `nav_reloc_first_frame_spin_start_2026-10-20.png` | The two start views, same scene, different place | T3.5e | 12 |
| `nav_reloc_y_fit_profile_2026-10-20.png` | Fit quality along y for the placement result | T3.5e | 12 |

**VIDEO STUBS** (not on this machine or still to record):

| Planned file | What it should show | Status |
|---|---|---|
| **VIDEO STUB** `nav_handdriven_phone_video_2026-10-20.mp4` | Phone video of the base being pushed by hand during T3.5d, to sit beside the map build-up | No media was taken. Nothing to copy. Record next session or drop |
| **VIDEO STUB** `nav_keyboard_driving_t3.4_2026-10-13.mp4` | Attended keyboard driving, W S A D and the X stop | No media was taken. Nothing to copy |
| **VIDEO STUB** `nav_floor_marks_tape_layout_2026-10-21.jpg` (photo) | Tape marks A, B, C and the base on its outline | No media was taken. Take one at the next lab visit, needed for T5.8 |
| **VIDEO STUB** `nav_d455_mount_fitted_2026-10-06.jpg` (photo) | The fitted D455 mount, front and side | No media was taken. T5.3 says photo archival is owed |
| **VIDEO STUB** `nav_nav2_drive_to_point_<date>.mp4` | The base driving to a goal on the map with RViz beside it | To record when T3.6 runs, planned after 2026-10-28 |
| **VIDEO STUB** `nav_calibration_rig_<date>.mp4` | The calibration target and the overlay snapping onto it | To record at T5.5 |

---

## 19. Open questions for Sherman

Answered on 2026-10-23 (all questions):

1. **Placement retest.** Not done. Decision: present the results as they are. The T3.5f numbers stay in
   the report with the cross-run LiDAR fits as the measured part and the recollection as `[reported]`.
2. **Box verification for PR #117.** Not run, confirmed by Sherman on 2026-10-23. The PR was merged
   without it. PR #118 also merged before its 20-run loop, and the work has no T3.5g row in the task tree.
3. **Privacy.** Fine to show the coloured map and camera frames as they are.
4. **Closure number.** Report all of it: raw odometry 12 mm, LiDAR-only 4 mm, odometry error 7 mm.
5. **Dion's tasks.** Keep T1.2, T1.3 and T1.5 in this report. Two people can be on the same task.

6. **Photos and videos.** None were taken. The VIDEO STUB rows in section 18 stay as notes of what to
   record next.
7. **Hardware stop.** None on the base. The only stop is the power button.
8. **Ten drives.** T3.6 is planned after 2026-10-28. Visual 8 in section 17 cannot exist for the
   presentation.
9. **Credits.** Approved as listed: HKU MARS lab (`hku-mars/FAST-LIVO2`), the port
   `U-AMC/FAST-LIVO2-ROS2`, SLAM Toolbox, Nav2, Livox, RealSense, Hexman Robotics.
10. **Lab box hang.** Ignore. Stays as a challenge line only.

11. **Shared rows with Dion.** Sherman chose and checked the HOME pose in simulation (T1.3). Dion ran
    it on the real arm and Sherman checked the joints against the HOME row (T1.7). T1.11, T1.12, T1.22
    and T1.24 are Dion's work, Sherman only watched. Claimed: T1.6 runbook and procedure, T1.7 check.

No questions left open. The PR #117 box check is queued as next step 0.

---

## 20. Sources

- Task rows: `docs/task-tree.html` (T0.x, T1.2 to T1.7, T3.x, T4.2, T5.x, T6.2, T6.11).
- Work log: `docs/sherman_docs/WORK_LOG.md` (2026-09-16 to 2026-10-20).
- Evidence write-ups: `docs/sherman_docs/setup/`, `t3.4/`, `t3.5/`, `t3.5c/`, `t3.5d/`, `t3.5e/`, `t3.5f/`, `t5/`.
- Run records in `docs/bench-runs/` (Sherman's 22): `2026-09-24-sherman-mac-t0.5-fresh-clone.txt`,
  `2026-10-06-sherman-t3.4-excerpts.txt`, `...t3.4-remote.txt`, `...t5.4-full.txt`,
  `2026-10-07-sherman-t3.4-attended-hold.txt`, `...t3.5-cloud-scan.txt`, `...t3.5-init-pose.txt`,
  `...t3.5-launch-prep.txt`, `...t3.5-map-prerequisites.txt`, `...t3.5-owned-map-saver.txt`,
  `...t3.5-runbook-ownership-drift.txt`, `...t3.5-slam-persistence.txt`, `...t3.5-snapshot-manifest.txt`,
  `2026-10-13-sherman-t3.4-pr-checks.txt`, `...t3.4-stationary.txt`, `...t3.5-dev-sync.txt`,
  `...t3.5-phase2.txt`, `...t3.5-resolved-dev.txt`, `...t3.5-startup-prep.txt`,
  `2026-10-15-sherman-t3.5-historical-map.txt`, `...t3.5-startup-control.txt`, `...t3.5-targetfix.txt`.
  Also `2026-10-13-labbox-t1.5-validation.txt`. The FAST-LIVO2 runs (T3.5a to T3.5f) are recorded as
  hash manifests, `docs/sherman_docs/tools/fastlivo/EVIDENCE_*.sha256` (33 files), with raw logs on the
  box under `~/rcp-Gappler/log/t59-fastlivo/log/`.
- Pull requests by Sherman (GitHub `samwee24`): #12, #13, #17, #19, #20, #22, #24, #27, #29, #30, #31,
  #32, #38, #39, #61, #69, #117, #118. Closed: #18, #21. Open: #126 (FAST-LIVO visual-fix test skips
  when the host compiler cannot build `<cmath>`, opened 2026-10-23).
- Design context: `docs/ORIENTATION.md`, `docs/CHANNEL_CONTRACT.md`, `docs/hico-nav/PAPER_REPORT.md`,
  `docs/dion_docs/DION_PROGRESS_REPORT_2026-10.md` (for shape).
- Box read-only checks on 2026-10-23: uptime, disk, listing of recordings and images, floor-mark files,
  bag metadata. Nothing started, nothing changed. Seven images were copied with scp.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-10-23 | Claude (Sonnet 5.5) + Sherman | Created from the task tree, work log, evidence write-ups, run records, git history, pull requests and a read-only look at the lab box, for the team progress presentation. Media copied to `local/report_media/`. |
| 2026-10-23 | Claude (Opus 5.5) + Sherman | Review pass. Added section 3.4 for the 12 rows co-owned with Dion. Commit count 217, PR #126 listed. Removed the repeated PR #118 loop from next step 6. Fixed the 5e-15 citation, cited the 110.6 ms, 0.38 ms and 42 % figures, added T3.5f bag message counts from the box. Noted the `[reported]` tag difference and the work log end date. Open question 11 added. |
| 2026-10-23 | Claude (Opus 5.5) + Sherman | Question 11 answered: the shared grasp rows are Dion's work. Section 3.4 cut to T1.6 only, the one shared row Sherman's docs record. Summary row for shared rows removed. T1.7 added: Dion ran the HOME motion, Sherman checked the joints against the HOME row. Sherman also did the T1.3 simulation check. |
