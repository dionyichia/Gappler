# Sherman's Work Log

This is an append-only index of Sherman's Gappler work. Team task status, scheduling, and ownership
remain in [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md).

## [2026-09-16] T0.2 | Network switch proof

- Evidence: [`T0.2_SESSION.md`](T0.2_SESSION.md)
- Verified: RM65 at `192.168.1.18` replied from host address `192.168.1.10`; MID-360 at
  `192.168.1.3` replied from host address `192.168.1.5`; both checks passed after a NetworkManager
  connection cycle.
- Outcome: Evidence supports closing shared-plan task T0.2, pending shared-doc review.
- Next: Send this evidence record to the Dion documentation owner.

## [2026-09-16] T0.9 | Base identity recorded

- Evidence: [`T0.9_BASE_FOOTPRINT.md`](T0.9_BASE_FOOTPRINT.md)
- Verified: The supplied Hexman Robotics ECHO Series Product Manual v1.8.7 identifies the chassis as
  ECHO-PLUS, `460 x 380 x 140 mm`, with a `265 mm` stated rotation radius.
- Outcome: The manual's rotation radius exceeds the current `0.20 m` Nav2 radius by `0.065 m`.
  Physical integrated-robot measurement remains required before changing the navigation footprint.
- Next: Photograph the manufacturer/model label and measure the footprint with a tape measure.

## [2026-09-16] T5.2 | D455 mobile-base mount constraints

- Evidence: [`T5.2_D455_MOUNT.md`](T5.2_D455_MOUNT.md)
- Verified: The planned D455 base mount uses `20 x 20 mm` aluminum extrusion, with a required
  `190 mm` extrusion length.
- Outcome: Mount CAD and dimensions are reported complete. The provided D455 still needs USB 3 and
  live-stream verification; fabrication, anchor-point geometry, and arm-clearance measurement remain open.
- Next: Test the D455 under T0.1, then validate the completed design against the physical base before
  fabrication.

## [2026-09-21] T0.5 | Fresh Mac clone bench

- Evidence: [`T0.5_FRESH_CLONE.md`](T0.5_FRESH_CLONE.md)
- Verified: An isolated clone at `9bbb26a` passed L0 static checks, L1 contracts, and L2 preflight.
  L3-L4 skipped as expected because the Mac has no ROS 2 Humble or NVIDIA environment.
- Outcome: Sherman's clean-clone evidence is complete. The independent-clone half of T0.5 remains open.
- Next: Resolve the Orin-to-GitHub transfer failure, create a new clean Orin clone, and record its
  bench result before closing T0.5.

## [2026-09-24] T0.5 | Refreshed on current dev, both halves on one branch

- Evidence: [`T0.5_FRESH_CLONE.md`](T0.5_FRESH_CLONE.md), [`../bench-runs/2026-09-24-sherman-mac-t0.5-fresh-clone.txt`](../bench-runs/2026-09-24-sherman-mac-t0.5-fresh-clone.txt)
- Verified: fresh clone of `dev` @ `787f2cc` on this Mac, `./bench/run.sh quick` PASS (L0-L2, 10/0/0/13; L3-L6 SKIPPED off-box as expected). Merged Sherman evidence with Zongzhe's `origin/t0.5` log onto the shared `t0.5` line; brought to current `dev` (stale plan/table touches resolved to current content).
- Outcome: single T0.5 branch carrying both halves, PR to `dev` unmerged. T0.5 task flip needs owner sign-off (Zongzhe's half is his Sep-21 run).
- Next: PR review + merge word; delete probe clone `~/fresh-clone-t05` after merge.

## [2026-09-24] T0.5 | Flipped DONE in PR #29 (merge pending)

- Evidence: same as above; task-tree T0.5 → DONE with both-halves rationale + finding disposition.
- Verified: full-run evidence current (Sherman @ `787f2cc`); Zongzhe's Sep-21 log stands per task letter (no version pin); anygrasp-env finding non-blocking, tracked under T1.10.
- Outcome: T0.5 DONE on the branch. PR #29 still unmerged — merge needs the merge word (Zongzhe sign-off requested in PR text).
- Next: merge PR #29 on word; then delete `~/fresh-clone-t05`, the `t0.5-sherman-evidence` feeder, and the remote `t0.5` post-merge.

## [2026-09-22] T0.1 | D455 ROS-driver validation

- Evidence: [`T0.1_D455_VALIDATION.md`](T0.1_D455_VALIDATION.md)
- Verified: D455 on USB 3 (5000M, serial `146222253541`) after a port/cable swap; ROS driver delivered
  color, depth, and aligned depth at ~30 Hz sustained over a 60 s three-topic bag (2117/2273/2117 msgs).
  Earlier `hz` swings were a measurement artifact. D435i moved to its own direct USB 3 port.
- Outcome: T0.1 stream/USB gaps closed. Box left clean, no ROS processes running.
- Next: T5.3 mount fabrication, then T5.5 LiDAR-camera calibration.

## [2026-09-22] T1.2 | Remaining safety fixes done

- Evidence: [`T1.2_SAFETY_FIXES.md`](T1.2_SAFETY_FIXES.md)
- Verified: B1 launcher wording corrected (2 lines, zero behavior change; no phantom `q` promise left).
  I1 orchestrator double-launch copy deleted behind a new failing-first L0 check
  (`arm-bringup-single-launch`): RED with 2 sites, GREEN with 1. Full L0 (11 checks), L1, and
  `./bench/run.sh quick` PASS.
- Outcome: T1.2 complete. T1.6 still needs T1.4 and the solo Ctrl-C discipline.
- Box 2026-09-22: isolated `~/rcp-t1.2` worktree — L3 build PASS, sim_moveit PASS, estop_delivery
  PASS (plus Sherman direct run), nav_nodes PASS on re-run after one flake; state_machine_sim refused
  by design with the arm powered. Weights linked per repo precedent; worktree removed after.
- Next: Push + PR, then T1.4 physical setup at the box.

## [2026-09-22] T1.3 | Home pose decided row applied (code, Mac side)

- Evidence: [`T1.3_HOME_POSE.md`](T1.3_HOME_POSE.md)
- Verified (Mac): new L0 check `home-joints-decided` RED (5 joints differ) before the header edit,
  GREEN after; full L0 (12 checks) clean. Sim expectation flipped to the decided row (runs on the
  box only). Baseline banked in the evidence note; stale-warning verified absent; trivial_mtc copy
  untouched per scope.
- Outcome: Code change complete locally. Unpushed. Box rebuild + sim re-runs still owed.
- Next: Push, box worktree rebuild, sim_moveit + state_machine_sim vs baseline, then PR.

## [2026-09-22] T1.3 | Final evidence only; original home row retained

- Evidence: [`T1.3_HOME_POSE.md`](T1.3_HOME_POSE.md)
- Verified: original row has 2/2 full simulated-cycle PASSes; `realman_manip` has 5/5 final-approach FAILs; joint4 reached `-3.092`, only `0.008` rad from `-3.1`.
- Outcome: `dev` keeps the original row. The decided-row change remains only in unmerged `t1.3-home-pose` / PR #18. Task-tree T1.3 is PROGRESS, not DONE.
- Next: T1.4 physical setup, then a purpose-built candidate with joint-limit margin; replacement PR only after sim validation.

## [2026-09-22] T1.4 | Measurement plan recorded on t1.4-physical-setup

- Evidence: [`T1.4_PHYSICAL_SETUP.md`](T1.4_PHYSICAL_SETUP.md)
- Verified: plan only; no physical visit, no arm motion, no table/cell.
- Outcome: exact A–F sheet recorded (base verification, static envelope, extrusion/mount, safety setup, camera identity, blockers). Task-tree T1.4 status untouched.
- Next: lab visit for T1.4-now measurements; T1.4-cell stays blocked until a table exists.

## [2026-09-23] T1.4 | Visit closed, DONE (power-on ready, no motion)

- Evidence: [`T1.4_PHYSICAL_SETUP.md`](T1.4_PHYSICAL_SETUP.md)
- Verified: A taped (0.380 x 0.460). B2/B4/C4/C5 measured-closed, single readings. B1 verdicts + C6-C9 reported with itemizations waived. D cleared as reported (D1 figures waived, D2 deleted, D3 verbal confirm with transcription owed, D4 no hazards). E serial 243222074878 matches banked wrist default. F blockers confirmed. Unpowered throughout, no motion commanded.
- Outcome: T1.4 DONE locally on t1.4-physical-setup. Unpushed. Residuals: D3 figure transcription, T1.4-cell blocked until a table exists.
- Next: Push + PR to dev on Sherman's word, then T1.3 purpose-built candidate from latest origin/dev.

## [2026-09-23] T1.5 | Driver-only bring-up draft

- Draft: [`../ARM_BRINGUP.md`](../ARM_BRINGUP.md) (shared procedure; not yet validated)
- Verified: source and earlier records only. No controller power-on, driver launch, or joint-feedback
  observation was performed for this draft.
- Outcome: no-motion handshake procedure prepared for Dion and Sherman's T1.6 session. T1.5 and
  T1.6 remain open until its attended session results are recorded.
- Next: T1.4's no-motion power-on verdict was merged in PR #22. Review the procedure with Dion,
  carry forward its accepted 0.03 m back-edge overhang and D3 reach figure still owed, then validate
  the commands and outcomes during T1.6.
- 2026-09-23: moved the draft to shared docs and required independent UDP packet observation
  alongside ROS joint feedback. No hardware run performed for this update.

## [2026-09-23] T1.3 | MAIN row adopted final, branch to dev

- Evidence: [`T1.3_HOME_POSE.md`](T1.3_HOME_POSE.md)
- Verified: Round A 4/4 reachable + TF placement mm-matches FK (C1 wins: lowest grasp 0.922, 44-deg view). Round B on C1: approach + close PASS (rejected row's killer step); return FAIL 0.0563 attributed to stale test RETURN (2.3562 vs fixed 2.3000, delta 0.0562), fixed test-only. C2 probe reverted. Archive guide bannered (was quoting rejected row). No production-code change: HOME_JOINTS already MAIN.
- Outcome: verdict MAIN final (sim-validated + documented) on t1.3-home-pose-select. Residuals: variant matrix not run, T1.1 supersession owed (Dion), box green re-run owed, live validation T1.7.
- Next: PR to dev, CI green, box verification, merge on Sherman's word. Task-tree T1.3 DONE at merge.

## [2026-09-24] T1.3 | Variant matrix green, scenario residual closed

- Evidence: [`T1.3_HOME_POSE.md`](T1.3_HOME_POSE.md) (matrix rows in verdict section)
- Verified: `SM_CY`/`SM_FAR` knobs added test-only on `t1.3-variant-matrix` (defaults = baseline); box sim 3/3 PASS (baseline, lateral +80px, shortened 0.22m) with gripper close in all, return 0.0001 rad, C7 XFAIL as designed. Box left clean, channel empty. Fixed stale "unvalidated on the real arm" test string (T1.7 validated 2026-09-23).
- Outcome: MAIN survives off-center and shortened geometries. Remaining residuals: T1.1 supersession owed (Dion), live validation T1.7, D3 transcription, table frame.
- Next: PR `t1.3-variant-matrix` to `dev` on Sherman's word (CI + merge word; box already verified).

## [2026-09-24] T5.4 | D455 TF determination opened (CAD + package sources)

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md)
- Verified (Mac, no lab access): replacement-mount CAD inputs recorded (hole origin, platform edge −13.05/+29.50 mm, y = 0 centered, 3 mm middle plate vs 5 mm top platform — all design-intent, unverified as-built); D455 package facts read from Intel URDF (origin = bottom screw, color y −0.059, baseline 95 mm, fixed optical flip, driver overwrites fine extrinsics live).
- Outcome: chain derived with one UNKNOWN (platform↔base placement); frame-collision flag to Dion/T5.5; October taping list referenced under T5.4-after-T5.3-fit. No PR; T5.4 stays OPEN.

## [2026-09-24] T5.2 | v2 plate revision DONE

- Evidence: [`T5.2_D455_MOUNT.md`](T5.2_D455_MOUNT.md) (v2 section + changelog)
- Verified: same mount, revised plate stack (3 mm middle, 5 mm top platform current); requirement recorded (Dion via Sherman: camera higher to see higher for navigation); positions carry over from verified v1 geometry. Task-tree T5.2 → DONE (v2).
- Outcome: v2 design closed remotely (no lab access). Physical fit + view verification remain T5.3 (Oct 5+); geometry measurement remains T5.4.
- Next: PR `t5.2-mount-v2` to `dev` (docs-only: CI + merge word, no box needed).

## [2026-09-26] T3.3 | Mapping launch arm TF DONE

- Evidence: `nav/robot_slam/launch/slam_mapping.launch.py:117-122` (`robot_base_to_arm`), mirroring `nav/robot_slam/launch/slam_localization.launch.py:107-112`; task-tree T3.3 → DONE.
- Verified: Mac `./bench/run.sh quick` PASS (L0/L1/L2; L3-L6 skipped off-box). Box (isolated domain, publisher stopped after): py_compile OK, exactly 1 `robot_base_to_arm` definition, exact args `0.18 0 0.48 3.14159 0 0 robot_base_link base_link`; live `tf2_echo` → Translation `[0.180, 0.000, 0.480]`, quaternion `[0, 0, 1, 0]`, yaw 180°. Branch rebased onto `dev` via merge (clean), pushed @ `f1f1a47` + close-out.
- Outcome: mapping launch now joins the arm tree during mapping runs. Residuals: 0.18/0.48 values duplicated across both SLAM launches (plus `bench/nodes/test_nav_nodes.py` fixture) until T5.4 single-sources them; full mapping-launch TF tree untested (no base bring-up remote).
- Next: PR `t3.3-mapping-tf` to `dev`; Zongzhe review; merge on Sherman's word (robot-adjacent: CI + box evidence + word).

## [2026-10-06] T5.3 | Revised D455 mount fit PASS

- Evidence: [`T5.3_D455_FIT.md`](T5.3_D455_FIT.md).
- Verified: serial 146222253541 selected explicitly; RGB and depth browser endpoints delivered JPEG frames, and Sherman confirmed live views. Rigidity, fasteners, cable route, arm clearance and navigation-view suitability are Sherman-reported PASS, not independently certified by automation.
- Outcome: task-tree T5.3 marked DONE. No runtime TF or robot motion commands added. Geometry integration remains T5.4 and camera–LiDAR calibration remains T5.5; photo archival, angular uncertainty and detailed clearance-method evidence remain residuals.
- Branch checks: `git diff --check` and Mac `./bench/run.sh quick` PASS; L3–L6 skipped. These checks validate repository consistency, not physical fit.
- Next: branch verification and review; merge requires CI, box evidence and Sherman's explicit merge word. Task-tree artifact republish is owed (no publishing tool available in this session).

## [2026-10-06] T5.4 | As-fitted screw geometry recorded

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md); T5.3 merged PR #38.
- Verified: Sherman reported platform/screw measurements, 65 mm axle height and axle alignment with the chassis midpoint. Derived provisional bottom-screw xyz `(0.208, 0, 0.528) m`; zero rpy visually estimated, uncertainty unknown. Serial corrected to 146222253541. Mac quick bench and `git diff --check` PASS (L3–L6 skipped).
- Outcome: measured placement recorded; T5.4 remains OPEN. No live TF changed. Preserved both work-log histories when merging latest `origin/dev` into the existing pushed T5.4 branch.
- Next: distinguish arm, LiDAR, camera and return-clearance offsets before single-source integration; inspect installed camera package/frame chain, then focused tests and isolated box verification. Do not replace every 0.18 with the camera screw x=0.208.

## [2026-10-06] T5.4 | Shared fixed geometry, behavior preserved

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md), `shared/global_config.yaml`, `bench/test_geometry.py`.
- Verified: Mac quick checks PASS with geometry runtime explicitly SKIPPED (PyYAML absent); box six geometry tests PASS; mock-nav six controls PASS/four existing XFAIL; isolated TF lookups matched arm/LiDAR/provisional screw config and publishers were stopped. Contract scanner extended/tested without baseline reset.
- Outcome: both SLAM launches read shared mount definitions; approach/return legacy references remain separately 0.18 and marker height reads arm geometry. No stopping behavior changed. D455 screw stored, not deployed as a camera/optical transform. Review findings addressed: malformed-config errors and accurate runtime skip reporting.
- Next: T5.4 remains PROGRESS pending D455 package/frame chain and Dion's navigation-reference decisions. No PR or merge yet. Task-tree artifact republish remains owed.

## [2026-10-06] T5.4 | D455 sensor-frame chain verified

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md), `nav/robot_slam/launch/base_camera.launch.py`, `nav/robot_slam/urdf/base_d455.urdf.xacro`.
- Verified: installed Intel macro gives screw-to-link `(0.01115, 0.0475, 0.0145) m` (corrects earlier x=0.0158); driver serial 146222253541; RGB/depth frame headers resolve to robot_base_link. Exactly two static publishers with disjoint mount/body versus sensor children. Eight box geometry/model tests PASS; Mac quick PASS with runtime/model checks explicitly SKIPPED. Read-only code review found no important issues.
- Outcome: opt-in camera-only source launch integrated and verified in private domain 176, no arm/base driver or stopping-behavior change. Our camera-only browser preview remains running. Installed-package deployment/full-system operation/calibration not proven; no build performed.
- Decision reported by Sherman: 180 mm refers to camera, not robot front. Which camera/frame and whether both navigation legs use it remain to be confirmed; fitted D455 screw/depth x are 208/219.15 mm. T5.4 stays PROGRESS. Task-tree artifact republish owed.

## [2026-10-06] T5.4 | Both navigation legs reference D455 depth origin

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md), `shared/nav_geometry.py`, `bench/test_camera_navigation.py`, mock-nav log `bench_nav_nodes_2026-10-06_1642.txt` on the box.
- Decision: Sherman explicitly selected the new base D455 for both approach and return. Distances are planar: 0.6/0.5 m, using actual TF sensor origin rather than old 180 mm or screw position. Separate arm/LiDAR geometry unchanged.
- Verified: four new camera-reference mock cases failed old code; after implementation full mock-nav nine controls PASS/four existing XFAIL. Pure geometry/arrival-gate tests PASS; arrival map-TF loss regression failed before its guard fix. Box eight geometry/model tests and initial three pure geometry tests PASS. Missing camera TF produces no goal/start and return can retry when TF appears.
- Outcome: legacy reference scalars removed. Camera launch must run on navigation's domain; private preview does not provide production TF. Full L0–L5 lab testing requested and pending, with real-arm-unreachable simulation guard intact; no real motion automated. Task remains PROGRESS until verification is reconciled.

## [2026-10-06] T5.4 | Evidence reconciliation before close-out

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md), candidate `12d784c`, isolated box `log/t54-full-suite.txt` and arm build log.
- Verified: current box L0–L2 checks passed, including eight geometry/model tests and four camera-navigation tests. Arm/grasp build finished all 24 packages with exit 0 in 5 min 10 s. Mac quick bench passed executed checks; ROS-dependent checks skipped explicitly. Additional 10,000-case planar check passed (maximum error about 5e-15 m).
- Clarified: initial CAD/no-runtime statements are historical; mount orientation remains visually estimated. Latest-available/cached TF is not fresh localisation or live camera health. Arrival still trusts nav success; calibration and physical stopping accuracy remain unproven. Original measurement-plan checks not evidenced are now labelled residuals.
- Outcome: documentation prerequisite work progressed while the box suite runs. Navigation build and final-code mock navigation still pending at this entry. Existing environments/weights reused; fresh-machine reproducibility not claimed. T5.4 stays PROGRESS, no PR yet, merge approval withdrawn until results are reviewed and Sherman approves again.

## [2026-10-06] T5.4 | Final box evidence and geometry/software close-out

- Evidence: [`T5.4_D455_TF.md`](T5.4_D455_TF.md), [`full box output`](../bench-runs/2026-10-06-sherman-t5.4-full.txt), candidate code `12d784c` (subsequent commits documentation-only).
- Verified: L0–L2 PASS; both builds PASS (24 arm/grasp, 18 nav); final-code mock navigation nine controls PASS/four known XFAIL. MoveIt, e-stop and AnyGrasp environment PASS; recorded-image replay controls PASS/known A1 XFAIL.
- Whole-suite disposition: FAIL, exit 1. State-machine simulation safely refused before launch with arm reachable; L5 failed because Aria USB absent, with six private-domain graph checks skipped. No guards bypassed and no real motion commanded. Unchanged vendor-driver compiler warnings recorded, not dismissed as proof of hardware safety.
- Outcome: T5.4 marked DONE for geometry/software integration in task-tree, not calibration or real driving acceptance. Visual mount angles/measurement uncertainty, cached-TF health limitations, known defects and physical stopping accuracy remain explicit residuals. PR/CI next; no active merge approval. Hosted task-tree Artifact republish owed.

## [2026-10-06] T3.4 | LiDAR and base feedback, driving still open

- Evidence: [`T3.4_BASE_BRINGUP.md`](T3.4_BASE_BRINGUP.md), [session excerpts](../bench-runs/2026-10-06-sherman-t3.4-excerpts.txt).
- Verified: Sherman-run Livox PointCloud2 stream approximately 10 Hz; ECHO_PLUS driver initialized and odometry approximately 50 Hz. Incoming chassis frames decoded CAN mode and low battery (latest 20.5 V). Isolated Nav2 limiter on private test topics bounded forward/reverse outputs and returned to zero in 0.500 s after input stopped.
- Outcome: T3.4 PROGRESS, not DONE. No runtime code/config change, keyboard-driving acceptance, physical stop proof, odometry accuracy measurement or fresh-build provenance claimed. Gripper and personal desktop work excluded from this task record.
- Handoff: 21:01 read-only process check still showed communications-only xnode_comm, no vehicle/teleop/LiDAR/arm drivers. Chassis power, charging and custody not independently confirmed; no user process stopped by OpenCode.
- Next: charge and verify hardware stop/transport setup, maintain the isolated control-path check, fix Livox-format/network-startup gaps with tests, then attended driving and stopping evidence. Hosted task-tree Artifact republish owed.

## [2026-10-06] T3.4 | Maintained remote control preparation

- Evidence: [`T3.4_REMOTE_CHECKS.md`](T3.4_REMOTE_CHECKS.md), [reviewed box results](../bench-runs/2026-10-06-sherman-t3.4-remote.txt), matching Mac/box SHA256 for six control/launch sources.
- Changed: fail-closed fixed-domain guard, maintained keyboard/smoother bench, nonblocking teleop with 0.25 s inactivity timeout and burst-input correction, LiDAR-only PointCloud2 launch, focused static CMake executable resolution. Vendor files and full SLAM launches unchanged.
- Verified: Mac quick bench PASS with declared skips; box private-domain suite PASS including hidden-node refusal, roughly 10 Hz keyboard publication, raw exit zeros, terminal restoration and surviving-smoother response to teleop crash. Pipeline silence zero observed in 0.457-0.603 s. Real LiDAR launch constructed without executing any action. Read-only review follow-up found no remaining important defects.
- Whole quick-bench disposition on box: FAIL, exit 1. L0/L1 passed; L2 lacked three model-weight files in the separate test checkout. No guard bypass, asset duplication, full build or whole-stack PASS claimed.
- Handoff: no hardware driver launched or motion commanded. Original lab checkout/untracked work preserved; user-started communications-only node remains untouched. Power/charging/custody unconfirmed. T3.4 PROGRESS; attended driving/physical stopping remain open, no completion PR or merge. Hosted task-tree Artifact republish owed.

## [2026-10-07] T3.5 | Navigation launch preparation, not deployed

- Evidence: [`T3.5_LAUNCH_PREP.md`](T3.5_LAUNCH_PREP.md), [box/source results](../bench-runs/2026-10-07-sherman-t3.5-launch-prep.txt).
- Changed on `t3.5-launch-prep`, stacked on T3.4 `3c4038c`: removed Ethernet mutation from both SLAM launches; all three owned navigation entry points use the owned PointCloud2 LiDAR wrapper. No vendor/config/map/scan/frame changes.
- Verified: five original subcase failures reproduced before fixes; updated stdlib tests, Mac quick bench and focused box static/contracts passed. All three real ROS descriptions/includes constructed with temporary source-backed shares, returned LiDAR action and wrapper parameters verified; no actions executed. Review's omitted-return coverage gap corrected and mutation-tested.
- Residuals: installed box overlay unchanged; no build/live LiDAR/scan/navigation acceptance or whole box suite claimed. Prior separate-checkout weight preflight gaps unchanged. Map route and save/load alignment still open; T3.4 physical stop/driving acceptance still open.
- Handoff: original checkout/untracked logs, Ethernet addresses and user-started communications node preserved. T3.5 PROGRESS; no PR/merge. Hosted task-tree Artifact republish owed.

## [2026-10-07] T3.5 | Synthetic point-cloud conversion

- Evidence: [`T3.5_CLOUD_SCAN.md`](T3.5_CLOUD_SCAN.md), [reviewed 12-case box output](../bench-runs/2026-10-07-sherman-t3.5-cloud-scan.txt), five matching source hashes.
- Changed: maintained domain-127 synthetic bench and L0 fixture/source-contract tests; no production node/configuration change. Actual source parameters/routes used, including relay paths for SLAM and direct cloud input for AMCL.
- Verified: all 12 box cases received 10/10 distinct scans; known geometry/nearest beam, height/range limits, invalid/empty clouds, frame/timestamps and full relay metadata/payload checked. Input/output reliability and durability observed; history/depth declared/use-checked because DDS introspection reports UNKNOWN/0. Final domain empty. Five stdlib tests and available Mac quick levels passed; explicit skips retained.
- Review: timeout cleanup grace, source routing/returned actions, full QoS contract, duplicate-frame rejection and full metadata checks strengthened. Follow-up found no remaining blockers. Interim unavailable depth/history assertion failure recorded, not hidden or fixed by altering production QoS.
- Residuals: no full box suite/build/load test, live LiDAR/physical TF, obstacle safety or map/localization acceptance. Existing preflight weight gaps unchanged. Original lab checkout/overlay and user-started communications node preserved. T3.5 PROGRESS; no PR or merge.

## [2026-10-07] T3.5 | Map availability before localization actions

- Added source-only readable/nonempty serialized-file gate before hardware action construction.
- Four focused tests and real ROS construction/refusal checks passed on the box; available Mac quick checks passed. Evidence: [`T3.5_MAP_PREP.md`](T3.5_MAP_PREP.md) and [raw results](../bench-runs/2026-10-07-sherman-t3.5-map-prerequisites.txt).
- Map audit and Sherman-selected SLAM baseline documented; teammate coordination pending.
- No installed changes/actions/hardware. Graph serialization, corrupt-map refusal before hardware, initial pose and actual restart/reload remain outstanding. T3.5 PROGRESS.

## [2026-10-07] T3.5 | Installed synthetic SLAM persistence

- Real installed mapper saved graph/data and YAML/image; fresh localizer recovered exact map raster and three known poses with biased odometry. No sensor/driver/controller or hardware commands.
- Missing deserialize replies expose no usable map; malformed graph aborts localizer with std::length_error. Preserved failure evidence, then restarted for valid case. No vendor fix/safe rejection claimed.
- Direct argv image saver handles spaces, avoiding upstream service's unquoted shell; candidate saving procedure remains unchanged. Old-node departure gate addresses observed restart discovery race.
- Evidence/limits: [`T3.5_SLAM_PERSISTENCE.md`](T3.5_SLAM_PERSISTENCE.md). T3.5 PROGRESS; saving/readiness integration, initialization runbook, deployment and physical acceptance remain open.

## [2026-10-07] T3.5 | Explicit snapshot saving

- Added owned saver for new graph/image snapshots with manifest/checksums, mapping/topic checks, refreshed-raster subscription, measurement pause/restore and explicit stationary acknowledgment. This never stops wheels.
- Synthetic box test invokes actual saver, advances graph with no map subscribers, verifies fresh map timestamp, reloads exact owned raster and checks fresh poses after normal/SIGINT/SIGTERM completion. Localization saving is refused before writes.
- Review found stale-raster and interrupted-cleanup gaps; addressed and rerun, including repeated-signal regression. All five tests run on box; Mac PyYAML-dependent validation explicitly skipped.
- Evidence: [`T3.5_MAP_SAVING.md`](T3.5_MAP_SAVING.md). No build/install/deploy, automatic graph saves or historical overwrite. Corrupt-localizer abort/readiness, initialization and minimal control runbook remain open. T3.5 PROGRESS.

## [2026-10-07] T3.5 | Explicit localization start pose

- Added `require_initial_pose` (finite `GAPPLER_MAP_START_POSE=x,y,theta`); localization launch now refuses silent-origin startup and passes `map_start_pose` before any hardware actions.
- Verified: 6 map tests + construction refusals (map + pose) pass on Mac and box; synthetic `/initialpose` reseeding 0.000 m with biased odometry. Evidence: [`T3.5_MAP_PREP.md`](T3.5_MAP_PREP.md), [init-pose results](../bench-runs/2026-10-07-sherman-t3.5-init-pose.txt).
- Review: PASS no blockers. Readiness gates, minimal manual-control runbook, install evidence and physical acceptance remain open. T3.5 PROGRESS.

## [2026-10-07] T3.5 | Snapshot manifest gate

- Added `require_snapshot_manifest` (manifest JSON, frame/geometry sanity, SHA256 over all four snapshot files); localization launch verifies it third, before any hardware actions.
- Verified: 8 map tests + all three refusal checks (map/pose/manifest) pass on Mac and box with zero Node/Include calls on refusal. Evidence: [manifest results](../bench-runs/2026-10-07-sherman-t3.5-snapshot-manifest.txt).
- Review: PASS no blockers. Manual-control runbook, install evidence and physical acceptance remain open. T3.5 PROGRESS.

## [2026-10-07] T3.5 | Minimal manual-control runbook (unvalidated)

- Evidence: [`T3.5_MANUAL_CONTROL.md`](T3.5_MANUAL_CONTROL.md)
- Verified: docs only; no hardware, SSH/ROS, build or install performed. Sources re-read for citations: teleop defaults/behavior (`teleop_node.py:35-42,62-88,106-134`), tested smoother bounds (T3.4 doc), driver `/cmd_vel` subscription and `xnode_power` second publisher (vendor `ros2_interface.cpp:177` / `:154`), tested input/output wiring (`bench/nodes/test_velocity_smoother.py:85`), wider committed `nav2_params.yaml:190-203` defaults flagged as a T4 verify-and-override gate.
- Outcome: T1-T6 terminals, single keyboard-to-driver path with `ros2` ownership checks, per-maneuver record sheet, halt-on-gate-failure rules and shutdown/custody checklist recorded. Explicit limits: arm driver off, no Nav2 goals, 1.0 s software bound is not a physical criterion, no kill/network experiments on moving hardware. Procedure unvalidated; driver-feed wiring, hardware-stop procedure and stopping criteria still owed at the attended session. T3.5 PROGRESS.
- Next: attended-session review with the lab operator; fill in wiring/stop-procedure gaps; no PR/merge until validated.
## [2026-10-13] T1.5 | Runbook validated, DONE

- Evidence: [`../bench-runs/2026-10-13-labbox-t1.5-validation.txt`](../bench-runs/2026-10-13-labbox-t1.5-validation.txt); runbook [`../ARM_BRINGUP.md`](../ARM_BRINGUP.md) (banner validated, observed rate note, changelog).
- Verified: attended session, Sherman operating, Dion at the rear power button. Box `dev` `49d80f7`, overlay rebuilt same day, domain 91 empty. Handshake RM65-BI/controller-3/UDP-5ms-8089; 23,043 wire packets ~14:55:07–14:57:03 (0 drops) spanning echo stamp `1791874553` (joint1–6 finite); `hz` opens ~200 steady; stop path 1 pub + 1 sub; ping 0% loss, 8080 open; no motion commanded or observed. Shutdown: driver exited, estop closed, controller off by Sherman, ping DOWN 15:08:59.
- Outcome: the cached-readings gap is closed; T1.5 DONE in task-tree with residuals. Supersedes stale branch `t1.5-runbook-followup` (never PR'd, 96 behind).
- Residuals: ROS-hz late-watch wobble 140–171 (ROS-side, T4.3 candidate); velocity/effort empty (known). Hosted task-tree Artifact republish owed.
- Next: PR `t1.5-closeout` to `dev`; CI green + merge word.

## [2026-10-07] T3.4 | Attended LiDAR recheck, battery hold

- Evidence: [`T3.4_BASE_BRINGUP.md`](T3.4_BASE_BRINGUP.md#2026-10-07-attended-follow-up-lidar-passed-battery-hold), [selected excerpts](../bench-runs/2026-10-07-sherman-t3.4-attended-hold.txt).
- Verified: lab `dev` at `3dde592`; network addresses/USB adapter present; owned source LiDAR initialized, one PointCloud2 publisher, 9.999-10.002 Hz. Unsupported hidden-node flag failed first, then corrected Humble `--all` observation succeeded. Candidate source hashes matched; no installed-overlay change.
- Outcome: Sherman reported chassis display **19.3 V**; no fresh ROS battery/alarm reading. Session halted before base driver, keyboard, smoother or activation; T3.4 stays PROGRESS. No movement/stopping acceptance or mapping.
- Handoff: user-started LiDAR still running at last inspection; physical power-off, charging and custody not confirmed. No user process terminated by automation.
- Next: verify manufacturer charger/nameplate compatibility, charge with supervision, establish battery and physical-stop readiness, then resume stationary feedback and attended driving/stop gates. Hosted task-tree Artifact republish owed.
- Close-out verification: Mac quick bench passed executed levels with explicit ROS/PyYAML skips; evidence links/anchors, task-tree syntax/status assertion and diff checks passed. Read-only documentation review found no blockers. Documentation-only change on existing stacked `t3.5-launch-prep`; no completion PR or merge.

## [2026-10-13] T3.5 | Merge current dev, runtime verification held

- Evidence: [dev-sync results](../bench-runs/2026-10-13-sherman-t3.5-dev-sync.txt).
- Combined `dev` at `49d80f7` with existing shared `t3.5-launch-prep`, without rewriting history. Resolved bench lists/README/task-tree changelogs by preserving both sides; added failing-first L0 suite-coverage check. Updated renamed arm-launcher warning; T3.9 records existing source fix, not deployment.
- Verified: Mac quick available checks PASS with explicit skips/disk warning. Fresh box snapshot tree exactly matched local candidate; static/contracts, focused tests, real launch construction and prerequisite refusals passed. Installed comparison still reports 3 drift/1 missing (exit 1), not installed readiness.
- Held: runtime guard found another user's real arm driver and refused before any software pipeline. PIDs subsequently exited, but shared-box custody requires coordination before retry. No process killed or hardware commanded; original checkouts and installed overlay untouched.
- Review: read-only merge-resolution/evidence review PASS. Push this verified source checkpoint for visibility, not as whole-suite or deployment acceptance; runtime verification remains held.
- Next: coordinate idle-box window, then serial isolated runtime benches before requesting deployment. T3.4/T3.5/T3.9 remain PROGRESS; no build/deployment, completion PR or dev/main merge. Hosted task-tree Artifact republish owed.

## [2026-10-13] T3.5 | Follow-up dev advance

- Evidence: [dev-sync results, follow-up section](../bench-runs/2026-10-13-sherman-t3.5-dev-sync.txt).
- After pushing checkpoint `3bac347`, the ancestry check found newer `dev` at `4cbb56e`; incorporated it with a second merge, without conflicts or history rewriting.
- Imported the newer task statuses, Orin backup notes/script and grasp-layout camera settings. Navigation/shared/bench implementation unchanged in this delta. No backup setup script or robot launcher executed.
- Verified locally: quick checks exit 0 with explicit environment/subtest skips, imported shell syntax and task-tree syntax/status checks. Earlier box evidence remains pinned to its recorded tree, not the new whole-source revision. Runtime custody hold and installed drift remain unresolved; no deployment or hardware acceptance.

## [2026-10-13] T3.4 | Stationary feedback and software-startup diagnosis

- Evidence: [stationary results](../bench-runs/2026-10-13-sherman-t3.4-stationary.txt).
- Sherman started hardware communications, vehicle driver and candidate LiDAR source after readiness acknowledgment; OpenCode only inspected feedback and ran private software tests. Original overlays and other users' processes untouched.
- Observed: fresh ROS 25.1-25.2 V, both battery flags clear; odometry 50.002 Hz and zero reported motion; reliable PointCloud2 recheck 10.0014 Hz, one publisher. No real velocity publishers. Missing handset explains the documented remote-controller-lost flag, not lost-CAN stopping behavior.
- First complete private keyboard/smoother bench FAILED at idle publication, despite 12 smoother cases passing. Diagnostic reproduced late startup: first message 1.944 s, seven messages in the original fixed window, steady 9.994 Hz. All test processes cleaned up, domain 127 clear.
- Harness-only readiness fix: four focused tests RED then GREEN (five keyboard tests total), ownership tests and local quick available checks PASS, review PASS. Exact-tree box candidate verified; complete private keyboard/smoother rerun PASS, final domain empty. No keyboard behavior, remapping or stop-limit relaxation.
- Attended driving: live ACTIVE smoother parameters and exactly-one keyboard -> smoother -> driver ownership verified. Sherman confirms W/S/A/D physical directions and complete X-stop, then Q exit and chassis power-off. Power button reported to stop immediately; no timed stop or emergency-stop rating claimed. Five-minute read-only recorder saved 2079 raw/4162 final commands and 15000 each odometry/status messages.
- Shutdown: initial inspection contradicted the all-processes-stopped report (earlier stationary-window drivers remained). Sherman authorized cleanup; by inspection all tracked driver PIDs were already gone, so no driver signal sent. Final 17:31 process/graph check PASS: session nodes gone, zero publishers on both command topics, odometry and LiDAR; all session panes at Bash, tmux retained. Physical power-off reported by Sherman.
- Outcome: T3.4 keyboard-driving/LiDAR scope DONE in task tree; hosted Artifact republish owed. Source provenance/installed drift and unmeasured braking/watchdog/calibration/charging gaps explicit; no mapping/deployment/full-suite acceptance implied. Charger custody not independently established.

## [2026-10-13] T3.5 | Phase 1 source-only (parallel to T3.4 merge resolution)

- Evidence: [`T3.5_MANUAL_CONTROL.md`](T3.5_MANUAL_CONTROL.md) (reconciliation table), [`T3.5_MAP_PREP.md`](T3.5_MAP_PREP.md) (route memo + G2–G4 proposal).
- Verified: working tree clean at phase start; local `t3.5-launch-prep` @ `ac1addf` in sync with origin; T3.4 resolution isolated in its own worktree/branch (`t3.4-bringup-evidence`), untouched. No T3.4-owned files modified. Mac `git diff --check` clean; `./bench/run.sh quick` PASS for executed checks, with explicit environment/subtest skips and L3-L6 not run.
- Outcome: driving-sheet rows 1–4, 6–7 reconciled with T3.4 DONE with reported/observed limits; silence timing, timed stop, braking, watchdog, calibration, charger custody, mapping and localization remain open. SLAM baseline stands, team sign-off owed. G2 dry-load / G3 re-verify / G4 corrupt-graph procedure proposed, not implemented. T3.5 stays PROGRESS; no PR/merge.
- Next: Phase 2 isolated box benches after T3.4 merge lands + idle-box window coordinated; Phase 3 live mapping only after deployment review.

## [2026-10-13] T3.5 | Phase 2 isolated software verification

- Evidence: [Phase 2 box results](../bench-runs/2026-10-13-sherman-t3.5-phase2.txt), tested commit `9c098dc`, exact tree `d9f55d45dfb8f992d409014ea2ee60185a080896`.
- Verified: 29 focused tests, construction-only launches, 12 synthetic cloud/scan cases (10/10 scans each) and installed SLAM save/restart/reload passed. Explicit saver pause restoration after normal/SIGINT/SIGTERM completion and localization-mode refusal passed. Exact raster reload and three synthetic pose errors 0.000–0.001 m / 0.001 rad; `/initialpose` reseeding passed. Final domain 127 empty, no matching driver/test processes.
- Limits: corrupt graph still aborts the localizer; installed comparison exit 1 (3 drift/1 missing), unchanged before/after. No build, deployment, hardware, historical graph load, full suite or parameter-startup localization proof. G2–G4 remain proposals. T3.5/T3.9 remain PROGRESS.
- Handoff: another session briefly began a dev merge in this checkout during testing; its conflicts were left untouched. After Sherman's merge confirmation, inspection found T3.4 PR #69 merged into dev but T3.5 still at the tested `9c098dc`, with no merge in progress. Commit this pinned evidence before a shared-safe dev update; verify the resulting source separately before requesting deployment.
## [2026-10-13] T3.4 | Isolated PR branch and fresh critical-source verification

- Evidence: [PR checks](../bench-runs/2026-10-13-sherman-t3.4-pr-checks.txt).
- Existing T3.4 branch merged current dev without rewriting history; cherry-picked T3.4 evidence/readiness and only the cited stable ownership test. Unfinished T3.5 implementation excluded; all dev task data and shared-service suites preserved.
- Available local quick checks PASS with explicit skips; runner coverage RED then GREEN, 18 focused tests/review PASS. Six critical sources matched the box candidate exactly; fresh complete private keyboard/smoother check PASS, final private domain empty. LiDAR constructor failed without nav overlay, then passed with the documented environment; no launch actions executed.
- Sherman authorized PR into dev and merge commit only after review/CI/box gates pass. PR/CI pending at this entry; no merge or main change claimed. Hosted Artifact republish owed.

## [2026-10-13] T3.5 | Resolved T3.4 dev merge and parallel readiness audits

- Evidence: [resolved-source verification](../bench-runs/2026-10-13-sherman-t3.5-resolved-dev.txt), exact frozen tree `06b89328ff29385df6b98183b72c64fea5e5c625`; feature `aa21483` plus merged T3.4 dev `fdd6061`. Both prior histories and both bench suites retained; 119 task records preserved. Navigation source unchanged from tested `9c098dc`.
- Parallelized read-only launch audit, readiness design and merge/documentation review; one exclusive box verifier ran serially. Lead remained sole Git/source/docs writer. No competing domain-127 jobs, hardware or builds.
- Verified: 47 focused tests, construction-only checks, 12 scan cases and synthetic save/reload passed. Final private graph empty. Original checkout at externally advanced dev `0bf552e`, its existing untracked logs, overlay and network remained unchanged during the resumed run. Evidence hashes verified after transfer.
- Close-out: final available Mac quick checks exit 0 with explicit environment/one-saver-subtest skips; no owned static findings, two vendor findings and two imported contract endpoint warnings. Both coverage checks and read-only evidence/documentation review passed. L3–L6/full-suite acceptance not claimed.
- Audits: native components with explicit candidate YAML avoid new launch infrastructure. Full SLAM launches/quickstart nav include hardware/Nav2/goal actions and are excluded from manual mapping. Updated existing checklist with fresh scan/TF and sole-map-owner gates, reload-only same-byte staging proposal and independent physical-reference sheet. Source construction does not prove parameter startup; the post-seed pose observation does not prove reseed causality.
- Limits: installed comparison still exit 1 (4 match/3 drift/1 missing/1 skip); corrupt graph still aborts. Automatic startup/reseed-control tests, staging/dry-load G2–G4 implementation, team sign-off, attended readiness and live acceptance remain open. These documentation corrections do not implement gates. T3.5/T3.9 stay PROGRESS; no completion PR or deployment.
- Next: bank/push this reviewed checkpoint, then catch up the later `0bf552e` docs-only dev advance before further source work. Implement focused startup/reseed controls and reviewed component-only provenance/gates before requesting attended live work. Hosted task-tree Artifact republish remains owed.

## [2026-10-13] T3.5 | Later docs-only dev catch-up

- Integrated dev `0bf552e` into the existing T3.5 branch with a merge, not history rewriting. Imported the teammate's voice-trigger documentation, restart evidence and task notes unchanged. No runtime source changed from the separately box-tested checkpoint.
- Verification: available Mac quick checks passed with explicit environment/subtest skips; no build, deployment or hardware action. T3.5 remains PROGRESS. Next: automatic-startup and matched reseed-control fixture tests.

## [2026-10-13] T3.5 | Startup/reseed fixtures prepared; box verification blocked

- Evidence: [test preparation](../bench-runs/2026-10-13-sherman-t3.5-startup-prep.txt), frozen runtime-source tree `0eb9f3fc6c977329c5c31da88bdeebdc6952f3da`.
- Added failing-first parameter/odometry/TF helpers and nine passing local fixture checks. Existing persistence bench now has fresh automatic-startup trials using localization YAML, saved-raster comparison and scan-derived pose/TF; matched control/treatment keeps odometry fixed while relocating scans. No production driver changes. Read-only design review incorporated before transfer attempt.
- Available Mac quick checks passed with explicit environment/subtest skips. Both lab-access routes failed before transfer; no box job, graph check, hardware action or deployment occurred. Runtime assertions, discriminating negative control and parameter-startup efficacy remain UNVERIFIED. T3.5 stays PROGRESS.
- Next: restore lab access, verify fresh idle conditions and exact candidate tree, run serial isolated regressions and review evidence before any live-work proposal. Push this preparation for visibility, not as runtime acceptance.

## [2026-10-15] T3.5 | FAST-LIVO2 selected; SLAM Toolbox work held

- Decision (Sherman): FAST-LIVO2 is the T3.5 implementation from here on.
  SLAM Toolbox-specific development is held; nothing is discarded or merged.
  Branch `t3.5-launch-prep`, all pushed evidence, and box snapshots are preserved
  as the verified software record, reusable for comparison.
- FAST-LIVO2 evaluation runs on `t5.9-fastlivo-feasibility` (other agent):
  ROS 2 bag conversion verified (14,850 messages, originals untouched),
  isolated container replay next, off domain 127. No action from this session
  until replay review lands; coordinate the window when called.
- Remaining T3.5 tasks reframe around FAST-LIVO2: real-data check replays the
  shared converted bag; live session maps/localizes with FAST-LIVO2 once its
  replay is reviewed. Overlay rebuild and reuse-vs-remap calls stay open,
  now against the FAST-LIVO2 path. T3.5 stays PROGRESS; no completion PR.

## [2026-10-15] T3.5 | Fair-control fix prepared; box verification next

- Fix (test-first, box-untested): map readiness polls up to 15 s for the expected raster with absent/unequal/frame diagnostics; mapper settles 1 s before shutdown and a `karto::Exception` fails fast with a log pointer; relocation trials replay identical 2 cm-step motion in scan and odometry worlds so the movement gate admits scans in both; pose/TF agreement uses per-stamp odometry and reports TF numerical change separately. No thresholds, config defaults, vendor code, or production drivers changed. Eleven fixture tests pass after RED.
- Fair-control box run: control correctly stayed wrong (1.707 m off), treatment moved with the replay but the witness compared against the replay start instead of its end (0.500 m off start ≈ on track). Expectation bug, not a localizer failure: the replay advances 0.58 m, so the target is now the replay end. Box-untested.
- Evidence: [startup/control results](../bench-runs/2026-10-15-sherman-t3.5-startup-control.txt), exact tree `0eb9f3fc6c977329c5c31da88bdeebdc6952f3da`. Single verifier, serial private-domain tests; original teammate grasp checkout and both overlays preserved.
- Verified: 32 focused unit tests and seven construction observations passed. Saver/interruption/graph/image checks passed; fresh localizer automatically loaded the owned snapshot with exact raster plus fresh scan-derived pose/TF, without deserialize request.
- Stopped: no-reseed relocation control lacked current pose or TF observations; combined assertion cannot distinguish which. Suite exit1, treatment/subsequent stages not reached, cloud skipped. No causal reseeding proof. Installed drift unchanged; domain127 empty after owned-process cleanup.
- Diagnostic: one fresh exact-tree `2652fb69` run with counters failed earlier at raster equality, so counts are unavailable. Mapper shutdown also logged `karto::Exception`/Aborted, not the corrupt-map stage. No root cause established, no retry. Original work/overlays preserved and private domain empty again. First startup pass is not repeatability proof.
- Targetfix FULL PASS exact-tree `f36b3ba7`: 34 focused unit tests, 7 construction observations, persistence exit0 (automatic startup both trials, control 1.440 m correctly wrong, treatment 0.080 m recovered), cloud 12/12 exit0. Installed drift byte-identical exit1; corrupt abort re-observed as limitation. Original checkout/overlays preserved; domain127 empty. Matched reseed efficacy demonstrated on fixture; live/physical acceptance still open.
- Staging: added `stage_snapshot` (test-first, 10 fixture tests pass) copying verified snapshots into independent private files and hashing the copies. Historical `~iot22/maps` compatibility still untested; check next read-only without touching the source.
- Historical map: isolated installed-localizer check LOADABLE -- clean deserialization, 545x390 @0.05 m raster served, no abort; source hashes unchanged, checkout/overlays preserved, domain127 empty. [Evidence](../bench-runs/2026-10-15-sherman-t3.5-historical-map.txt). Lab-match, accuracy, and reuse-vs-remap decision still open.
- Next: investigate shutdown abort and startup readiness before changing control behavior. Upstream stationary scan gating is a hypothesis, not installed-runtime proof. No relaxed thresholds, vendor changes, hardware or deployment. T3.5 stays PROGRESS.
- Close-out: final available Mac quick checks exit0 with explicit skips; source diff only expands two diagnostic messages. Read-only evidence review passed; preservation manifests independently compared identical. Box suite remains failed/inconclusive, not a green runtime checkpoint. No completion PR.

## [2026-10-15] T3.5 | Split into T3.5a-f, FAST-LIVO2 replay record

- Evidence: [`T3.5_FASTLIVO_REPLAY.md`](T3.5_FASTLIVO_REPLAY.md)
- Verified: task-tree T3.5 split into six subtasks (public replay, sensor
  capture, our-data replay, live mapping, persistent localization, Nav2
  handover); T3.6 repointed to T3.5f; T5.9 reframed (FAST-LIVO2 implements
  T3.5 directly, staged 2D-first gate superseded). T3.5a progressed: U-AMC
  fork builds in isolation, authors' bag converts 14,850/14,850 and replays
  to EOF with 664 odom, 663 valid clouds, 600 images, 0 invalid; empty LIO
  clouds are upstream design (heartbeats). Nominal mount values kept as
  labelled working estimates pending T5.5; unaltered setup means no new drift.
- Outcome: T3.5/T3.5a-f PROGRESS in task-tree; hosted Artifact republish owed.
  One mapper teardown crash open (GDB: heap dispose under ~LIVMapper; ASan
  rebuild staged). No hardware touched; MID-360 answers ping, drivers unrun.
- Next: ASan backtrace, minimal fork patch, normal rebuild, PASS rerun; then
  T3.5b attended capture. No PR (task open).

## [2026-10-16] T3.5a | Heartbeat gate, ASan runs staged

- Evidence: [`T3.5_FASTLIVO_REPLAY.md`](T3.5_FASTLIVO_REPLAY.md) (findings 3, 6)
- Verified: LIO empty clouds proven upstream design from pinned source and
  counted as heartbeats (664 heartbeats, 663 valid clouds, 0 invalid on
  rerun). ASan image built with verified linkage after one mislabeled build
  (guard added: overridden image requires flags). Mixed-binary abort fixed
  with `T35_LD_PRELOAD`. Recipe 8/8, replay 32/32 tests pass on the box.
- Outcome: data side fully clean; only the mapper teardown crash still FAILs
  the run. No hardware touched.
- Next: instrumented replay, then patch from the ASan report.

## [2026-10-16] T3.5a | Audit reset and ASan image-read finding

- Evidence: [`T3.5_FASTLIVO_REPLAY.md`](T3.5_FASTLIVO_REPLAY.md), runs
  `t59-replay-20261016T070324Z-414486` and `t59-replay-20261016T070602Z-414943`.
- Correction to the earlier entry: empty LIO clouds are source-observed behavior,
  not proven intentional design. ASan-only preload did not fix startup; ASan plus
  the C++ runtime completed a paused diagnostic. Linkage does not prove uniform
  instrumentation. The data side was not fully reconciled: normal replay missed
  ten initial IMU callback logs; ASan replay had a large trailing backlog.
- Verified: separate harness candidate, 44/44 lab pure tests, normal paused
  diagnostic clean. Full ASan replay at 0.2 aborted during callback drain, before
  cleanup, on a one-byte image overread in pinned `vio.cpp:1679`. A standalone
  candidate regression reproduces the unsafe footprint and tests a guard.
- Outcome: actionable memory finding, not task completion. Original destructor
  crash is not explained. No mapper rebuild, robot command or deployment change.
- Next: review the minimal guard, compile the full patched mapper, then perform
  attended patched ASan and normal replay checks. No PR or merge yet.

## [2026-10-16] T3.5a | Destructor root-caused to Eigen/PCL alignment

- Evidence: [`T3.5_FASTLIVO_REPLAY.md`](T3.5_FASTLIVO_REPLAY.md), patched ASan
  image `56f183c4`, run `t59-replay-20261016T083645Z-421664`.
- Verified: sampling guard held for the full recording (no vio report; 331
  valid clouds, 0 invalid). ASan diagnosed the original crash site:
  `handmade_aligned_free` on a PCL-`malloc`'d VoxelGrid buffer —
  `-march=native` (AVX2, 32-byte Eigen alignment) vs prebuilt PCL (16-byte).
  Alignment fix staged in recipe: 10/10 tests pass both sides, real-file dry
  run clean on both pinned CMakeLists. Recipe hashes match Mac↔lab.
- Outcome: root cause identified with a staged fix, not yet proven by a clean
  normal replay. No robot command or deployment change.
- Next: patched normal-image rebuild, then full normal replay expecting clean
  shutdown. No PR or merge yet.

## [2026-10-17] T3.5a | DONE — PASS replay, clean shutdown

- Evidence: [`T3.5_FASTLIVO_REPLAY.md`](T3.5_FASTLIVO_REPLAY.md), patched
  normal image `d0dcfa8a`, run `t59-replay-20261016T175305Z-433728`.
- Verified: verdict PASS, supervisor exit 0, all processes exit 0; EOF with
  reconciled coverage (667/668/13,511+4 prestart, allowance 21); 665 odom,
  663 valid clouds (9.18 M points), 618 RGB, 0 invalid, 663 visual retrievals.
- Outcome: T3.5a done criteria met. Task-tree T3.5a flipped DONE on
  `t3.5-launch-prep`; no merge until all of T3.5 completes. No accuracy,
  live-sensor or Nav2 claims.
- Next: T3.5b attended stationary capture on the same branch.

## [2026-10-17] T3.5b | Stationary capture preparation

- Plan: [`T3.5_SENSOR_CAPTURE.md`](T3.5_SENSOR_CAPTURE.md).
- Verified read-only: both cameras enumerated on 5000M USB links, 54 GiB free,
  required host Ethernet addresses retained, no matching hardware/bench/replay
  jobs or video holders reported. These checks do not establish custody or
  sensor streaming. No driver startup, recording, network edit or motion command.
- Outcome: T3.5b PROGRESS on the existing T3.5 branch. Native Livox CustomMsg
  is required for point timing; existing PointCloud2-only and full robot launch
  paths are unsuitable. Shared lab checkout's unrelated changes left untouched.
- Next: confirm operator attendance and an agreed sensor window, then inspect
  exact installed driver settings and perform staged operator-run capture.

## [2026-10-17] T3.5b | DONE — stationary capture recorded and characterised

- Evidence: [`T3.5_SENSOR_CAPTURE.md`](T3.5_SENSOR_CAPTURE.md); primary bag
  `t35b_proof3` (74.03 s, 19,987 msgs, 2.2 GiB) plus `t35b_proof2` backup on
  the lab box at `log/t59-fastlivo/log/t35b-capture.R0fVks/`; analysis
  `analyze_proof3_ros.py` (`rosbag2_py` + `rclpy` deserialisation, no
  hand-rolled CDR).
- Verified: native CustomMsg (10 Hz, `timebase` == header, ns offsets spanning
  each ~100 ms scan, all finite, lines 0–3); IMU 200.0 Hz, zero non-finite,
  stationary gyro, accel |a| = 0.990 as-published (g-scale vs m/s² flagged for
  the T3.5c consumer, bag untouched); colour-only 640x480 rgb8 @30 Hz with
  1:1 matching stable CameraInfo (zero stamp mismatches); first headers
  aligned within ~20 ms; zero backwards stamps on all streams; colour-only
  log shows zero USB overflow warnings; provenance (driver/firmware/serial/
  SHAs/commands) recorded; shutdown verified (no LiDAR/camera/recorder/daemon
  processes, only pre-existing `gh-runner` remains).
- Outcome: T3.5b done criteria met. Task-tree T3.5b flipped DONE on
  `t3.5-launch-prep`; no merge until all of T3.5 completes. The first
  `t35b_proof` bag lacks LiDAR (recorder missed the overlay) and is retained
  as unusable. Stationary data proves delivery, not physical sync, delay
  calibration or extrinsics.
- Next: T3.5c replay of `t35b_proof3` through FAST-LIVO2 offline (gated also
  on T5.5 nominal mount transform).

## [2026-10-17] T3.5 | Verification audit, no hardware restart

- Evidence: [verification report](T3.5_VERIFICATION_20261017.md).
- Fresh: full primary bag deserialisation/integrity, all-point finite/count/time
  checks, exact calibration pairing; Mac available bench PASS; lab recipe 10,
  harness 45 and sampling 7 tests PASS. Retained T3.5a result rechecked, not rerun.
- Findings: zero-range returns ~51.8%, corrected image lag 31.7 ms, analyser unit
  bugs, incomplete runtime provenance, clock-domain uncertainty and untracked
  build tooling. Previous universal guard/allocator claims qualified.
- Outcome: T3.5 overall remains PROGRESS; capture characterisation stands with
  explicit limits. No physical synchronisation, calibrated fusion or Nav2 claim.

## [2026-10-17] T3.5 | Phase A: tooling preserved, strict bag audit

- Evidence: [freeze record](T3.5_INPUT_FREEZE_20261017.md),
  [verification report](T3.5_VERIFICATION_20261017.md).
- Fresh: strict `analyze_bag.py` on `t35b_proof3` — `ANALYSIS_OK`, exit 0, every
  audit number reproduced (740/14,807/2,220/2,220; 14,799,936 points, 51.84%
  zero-range; 106.095 ms max LiDAR gap; one calibration variant). Synthetic
  mini-bag tests 6/6: backwards/duplicate stamps, missing CameraInfo,
  non-finite point and `point_num` lie all fail as intended.
- Preserved: recipe (10 files) and replay harness (16 files) copied
  byte-identical into `docs/sherman_docs/tools/fastlivo/` with
  `MANIFEST.sha256`; strict analyser + tests added; bag and replay-evidence
  hashes frozen.
- Outcome: Phase A complete; T3.5 remains PROGRESS. Phase B (consumer contract)
  next; T3.5c stays gated on T5.5.

## [2026-10-17] T3.5 | Phase B: consumer contract, config pair, checker

- Evidence: [consumer contract](T3.5_CONSUMER_CONTRACT.md).
- Fresh: pinned source read at exact commits (FAST-LIVO2 `a09599a`, vikit
  `6f213c7`): routing, preprocess clamp/blind/sampling, IMU init and
  normalisation, image cv_bridge path, remote camera loader, all 79 declared
  parameters. Staged the `t35b_proof3` replay pair plus
  `check_replay_configs.py`; box run `CONFIG_OK`, 33/33 unit tests, and two
  mutations each failing with exactly their intended single failure. All six
  repo copies byte-identical to the box manifest
  `EVIDENCE_t35c-config-check.sha256`; sample statistics pinned (0.216% clamp
  rewrites; inversions <= 458 us).
- Findings: recording-driver messages identical to pinned-driver messages
  (CDR-safe); the CustomMsg path requires `lidar_type: 1` (8 would subscribe
  PointCloud2 and receive nothing); the IMU deskew path never sorts while our
  scans are unsorted (stationary-inert, unproven for motion); k3 not
  representable in the pinned camera loader; camera values must be served by
  `parameter_blackboard` before mapper start.
- Outcome: Phase B complete; T3.5 remains PROGRESS. T3.5c visual acceptance
  stays gated on T5.5. Phase C (LiDAR-IMU diagnostic replay of the unchanged
  bag) next; no PR or merge until all of T3.5 completes.
- Next: Phase C diagnostic replay run on the lab box, then resolve T5.5 with
  Dion for T3.5c.

## [2026-10-17] T3.5 | Phase B revision: nominal visual config, mode-aware checker

- Evidence: [consumer contract](T3.5_CONSUMER_CONTRACT.md) (status, §4, §7, §8, R1).
- Fresh: review found Phase B declared the visual leg blocked on missing
  T5.5 numbers, but Sherman's as-fitted camera measurements (T5.4 chain) compose
  into a nominal camera-LiDAR transform, and T3.5c's own framing ("nominal mount
  transform is the starting estimate") is the authority for staging the visual
  leg ahead of T5.5. New `t35b_proof3_visual.yaml` (img_en=1) carries the
  full-chain composition: T_base<-livox (M2 retained mount) composed with
  T_base<-colour_optical (T5.4: screw 0.208/0/0.528 + Intel body
  +0.01115/+0.0475/+0.0145 + colour y -0.059 + optical rpy -pi/2, 0, -pi/2)
  -> Rcl [0,-1,0, 0,0,-1, 1,0,0], Pcl (-0.0115, 0.3425, -0.03915) m;
  provenance-labelled nominal, explicitly not calibrated. Checker gained a mode
  contract: img_en 0 = diagnostic (non-empty placeholder), img_en 1 = visual
  (Rcl/Pcl must equal the reviewed composition), anything else fails; unit test
  recomposes the chain from documented inputs and pins the constants; 42 tests
  (37 run on Mac, 5 PyYAML-gated). Diagnostic pair byte-unchanged.
- Findings: direction/frame questions resolved from pinned source — p_cam =
  Rcl*p_lidar + Pcl (vio.cpp:38-39, 58-59), camera = D455 colour optical frame
  (the bag's image frame); no online extrinsic refinement exists (image
  time-delay estimator only, disabled). A wrong-axis or mirrored closure fails
  the recomposition test. Rotation is the weak axis (~6.7 px/deg at fx 385):
  the pre-fusion projection check is the next build item, before any visual
  replay or fusion claim.
- Outcome: staged and pushed; T3.5 remains PROGRESS. Visual-mode box round owed
  (unit tests + both checker runs + truncated-Pcl and img_en mutations). No
  mapper run, no hardware, no bag modification; no PR or merge.
- Next: build the projection pre-check tool against the existing bag with the
  nominal extrinsic, then the T3.5c visual replay runner; resolve T5.5 numbers
  with Dion.

## [2026-10-17] T3.5 | T3.5c: visual-config box round (revision's owed evidence)

- Evidence: [consumer contract](T3.5_CONSUMER_CONTRACT.md) (§8 visual-config
  round), [round manifest](tools/fastlivo/EVIDENCE_t35c-visual-config-20261017.sha256);
  box dir `~/rcp-Gappler/log/t59-fastlivo/log/t35c-visual-config` at commit
  `47a9b2e`.
- Fresh: 42/42 unit tests on the box; diagnostic file `MODE diagnostic` +
  `CONFIG_OK` (pair byte-unchanged, `05f849d0`/`977b6db9` in the manifest);
  visual file `MODE visual` + `EXTRINSICS` + `CONFIG_OK`; `Pcl[1]` and
  `img_en: 2` mutations each exactly one failure; manifest 19/19 verified.
- Findings: mode contract holds end to end on the box; checker outputs are
  run-stable byte-for-byte except rosbag2's bag-open timestamp log line.
- Outcome: revision's owed round closed; T3.5 remains PROGRESS. No mapper
  run, no hardware, no bag modification.
- Next: projection pre-check tool and first round on the same bag.

## [2026-10-17] T3.5 | T3.5c: projection pre-check tool + first box round

- Evidence: [consumer contract](T3.5_CONSUMER_CONTRACT.md) (§8 projection
  block, R1), [box manifest](tools/fastlivo/EVIDENCE_t35c-projection-20261017.sha256);
  box dir `~/rcp-Gappler/log/t59-fastlivo/log/t35c-projection.zD3Wie` at commit
  `2c9abff`.
- Fresh: `project_scan.py` (+26 stdlib tests, commit `2c9abff`) projects
  sampled scans onto nearest-in-time images with the staged nominal `Rcl/Pcl`
  and refuses the diagnostic config. Box round: 68/68 unit tests (26 tool +
  42 checker), 8 overlays, manifest 16/16 verified; repo tool copies
  hash-match the box manifest.
- Findings: in-frame LiDAR returns are 170–241 of 19,968 points per sampled
  scan, all at 0.16–0.23 m camera depth in a bottom band — `t35b_proof3`
  faces an acoustic-foam barrier ~0.2 m ahead of the sensor head; the LiDAR
  (max elevation 52°) cannot see over its top edge (61° needed), so only the
  top fan rings graze the bottom of the camera view. Scene-consistent with the
  nominal composition (band and depths where the geometry predicts, nothing
  elsewhere) but no rotation or far-field leverage — not an alignment check.
  No existing recording qualifies: `t35b_proof` has no LiDAR topic;
  `t35b_proof2/3` are the same scene; Bright_Screen_Wall used a different
  camera (`/left_camera/*`, 1280×1024, fx ≈ 1293.6).
- Outcome: T3.5 remains PROGRESS. Visual acceptance needs a fresh
  depth-bearing recording (standoff ≈ 1.5–3 m); no mapper run, no fusion
  claim, no PR or merge.
- Next: record the new scene bag on the box; re-run `project_scan.py` on it;
  then the T3.5c visual replay runner; resolve T5.5 numbers with Dion.

## [2026-10-17] T3.5 | T3.5c: standoff re-capture, depth probe, scene correction

- Evidence: [consumer contract](T3.5_CONSUMER_CONTRACT.md) (§8 correction
  block, R1); box dirs `t35c-projection-standoff.DxdNlI` (round 2) and
  `t35c-depth-check` (depth probe).
- Verified: the pre-check re-run on the standoff bag `t35c_standoff` (746
  scans / 2238 images, 8 overlays, 68/68 unit tests) draws 127–230 of
  ≈20,000 points per sampled scan in frame, all at 0.16–0.24 m camera depth in
  the bottom band — the same picture as `t35b_proof3` (162–241, 0.16–0.23 m;
  the round-1 block's "170–241" was a one-sample error). A deliberate 1.5–3 m
  retreat from the mats does not move the in-frame returns off the near
  surface.
- Fresh: D455 depth probe of the same setup (depth + aligned depth + factory
  `extrinsics/depth_to_color`; 1.73 GB, 9,419 messages): 582 raw and 582
  aligned frames, a value on 3.2 % of raw pixels (3.0 % aligned) — scattered
  speckle, none at the frame centre in any frame, no coherent surface anywhere.
  No distance measurement obtained, and this data cannot separate surfaces
  inside the 0.35 m blind zone (848×480) from a degraded depth stream. Side
  finding: the camera pair's factory extrinsic (5.91 cm along the optical x,
  rotation within 0.2° of identity) agrees with the URDF's 5.9 cm
  colour↔depth offset — a constraint on the camera pair's own geometry, not on
  its mounting to the LiDAR.
- Corrected 2026-10-18: this entry and the contract first reported the depth
  probe as "0.03 % of pixels valid … consistent with the near surface inside
  min-Z". The measured means are 0.0323 (raw) and 0.0298 (aligned), i.e. 3.2 %
  and 3.0 %, and the min-Z attribution is withdrawn: blind-zone returns and a
  degraded stream are indistinguishable in the probe's data.
- Probe provenance: the reader is preserved with the bag on the box
  (`t35c-depth-check/t35c_depth_read.py`, outputs in `analysis/`), not as repo
  tooling — it is a one-off probe with no unit tests and depends on the box's
  numpy/cv2/rosbag2_py.
- Correction: §8 read the scene as an "acoustic-foam barrier ~0.2 m ahead" with
  a "61°-top-edge" argument; both were inference from the image alone and are
  withdrawn. The scene is interlocking foam mats resting on a cushioned bench
  (operator, on site) — a low compliant surface, flat across its middle,
  curving away at the edge. The withdrawn claims never entered the tooling,
  the configs or the bag evidence; no data artifact changes.
- Outcome: T3.5 remains PROGRESS. Both projection rounds are consistent with the
  nominal composition and neither is evidence against it, but they exercise no
  rotation or far-field translation, so they are not an alignment verification;
  T5.5 remains the calibration owner and T3.5c's formal dependency on it stands.
- Next: fold the corrected scene reading into T3.5c's write-up; if a
  rotation-discriminating check is wanted, stage a scene the LiDAR sees beyond
  the near surface. No mapper run, no fusion claim, no PR or merge.
- Ops: all T3.5c processes stopped and the three task tmux sessions (`t35c`,
  `t35c-depth`, `t35c-rec`) closed; both bags and the repo working tree
  untouched.

## [2026-10-18] T3.5c | Own-data replay: LIO PASS, visual FAIL

- Evidence: [two-round report](T3.5c_REPLAY_20261018.html),
  `tools/fastlivo/EVIDENCE_t35c-replay-20261018.sha256` (14 files).
- Verified: Sherman ran frozen `t35b_proof3` in both modes from staged bundle
  `bfdd444`. A `20261018T062144Z-511887` PASS; B `20261018T064017Z-512716`
  FAIL (419 typed-empty clouds, no positive retrievals in 1,469 attempts).
  Both EOF, reconciled input callbacks, clean mapper exit. No new replay started
  during the read-only investigation; tmux retained.
- Source finding: inconsistent negative-coordinate visual voxel keys at pinned
  `vio.cpp:228–238` vs `380–398`. Arithmetic mismatch reproduced; actual rejecting
  stage still unknown. Geometry-only raw-scan proxy retains some reachable bins,
  so this is not a proven complete explanation for zero matches.
- Outcome: T3.5c stays PROGRESS; no calibration tuning or gate relaxation.
- Next: separately reviewed instrumentation-only build/replay, initiated by Sherman,
  to count key hits and later visual rejection stages. No PR or merge.

## [2026-10-18] T3.5c | Counters-only diagnostic candidate staged

- Evidence: [report §7](T3.5c_REPLAY_20261018.html), recipe README;
  box bundle `log/t59-fastlivo/log/vio-diagnostic.VSnwsS`.
- Implementation: SHA-gated additions-only source instrumentation, shadow key
  queries never used for selection; incremental mapper-only build from the exact
  accepted image into a separate fixed tag, with network none and existing
  custody/lock/resource checks. Existing replay gates unchanged.
- Verified: first new tests failed before implementation; 10 recipe + 5 diagnostic
  tests pass on Mac and box, including real pinned-source byte restoration;
  29/29 staged manifest entries checked. Separate review caught a Docker tag-alias
  loophole; failing-first negative test added, guard restricted to fixed diagnostic
  tag, re-review reports no remaining significant findings in that change.
- Next: Sherman initiates the prepared pane-2 build and supplies custody/sudo;
  review build/actual image before staging a separate replay. No build, new mapper
  replay or hardware command has been started. Generated C++ compilation remains
  unverified; T3.5c remains PROGRESS.

## [2026-10-18] T3.5c | Diagnostic build/replay completed: negative-depth rejection

- Evidence: [report §8](T3.5c_REPLAY_20261018.html),
  `tools/fastlivo/EVIDENCE_t35c-diagnostic-20261018.sha256` (14 files).
- Verified: user-run build `build-logs.tMfThU` exits 0, generates diagnostic
  image `3cd781a6`; source diff/hashes and binary marker checks pass.
  User-run replay `20261018T080001Z-515864` FAIL, normal EOF, 419 typed-empty
  clouds, no positive retrievals, clean mapper shutdown and reconciled callbacks.
- Counters: 75,024 current-key hits; 143,998 shadow-key hits (never selected).
  All 3,604,174 stored-point checks reached behind-camera rejection; no candidate
  reached pixel projection, grid selection or photometric matching. These are
  repeated checks, not unique points. One empty-map startup call is separate.
- Source finding: visual-map generation checks projected pixel bounds but omits
  positive camera-depth validation; retrieval rejects negative depth. The unchecked
  seed path can store behind-camera points. Why no usable front-facing seed survives
  remains unproven. `mat_out.txt` byte-identical to original B.
- Next: focused visibility regression/candidate, keeping voxel repair separate.
  No fix, tuning or further run started. T3.5c PROGRESS; tmux/evidence retained.

## [2026-10-18] T3.5c | Visual source candidates and next lab recording plan

- Source changes: SHA-gated `patch_visual_fixes.py` + stdlib-only C++ visibility
  predicate. `visibility` guards all three seed paths; `visibility-voxel` adds
  consistent current/raycast keys without reindexing insertion/reference maps.
  Each has a fixed separate experimental image tag, opt-in only; original accepted
  mapper, calibration and replay gates unchanged.
- Tests: new regressions observed failing first. Original source-extracted C++
  voxel expressions reproduce the mismatch; fixed expressions match at negative,
  boundary and float-rounding inputs. 10 recipe + 5 diagnostic + 4 visual-fix
  tests pass on Mac and box (real sources/compiler enabled). Separate review found
  no significant issue; guard-order assertions strengthened from its feedback.
- Staged: `log/t59-fastlivo/log/visual-repair.xIOr2o`, manifest 32/32 checked;
  visibility-only build command prepared in pane 2, not executed. Full mapper
  candidate compilation and replay remain unverified.
- Lab plan: [19 October capture](T3.5c_CAPTURE_PLAN_20261019.html), 15 s pilot
  with audited overlap GO before a 75 s stationary bag. No hardware started;
  new scene/data is separate from software validation. T3.5b stays DONE,
  T3.5c remains PROGRESS. No PR or merge.

## [2026-10-18] T3.5c | Visibility-only replay reviewed; no visual seeds survive

- Build `build-logs.LQAloY` exit 0, exact image `ba66a419`; source/header hashes,
  reviewed diff, accepted base and container policy verified.
- Replay `20261018T090909Z-518313`: FAIL, normal EOF/quiet drain, reconciled
  callbacks and clean mapper exit. Zero visual points appended, visual map empty
  on all 1,470 retrieval calls; 419 typed-empty clouds persist. Numerical
  `mat_out.txt` byte-identical to original B and counters-only diagnostic.
- Outcome: old invalid seed population prevented, but this data/configuration
  supplies no seed surviving the corrected path. Not a passing visual result.
- Evidence: [report §10](T3.5c_REPLAY_20261018.html), 13-file visibility manifest.
- Next: cumulative visibility/voxel build prepared in pane 2; user executes.
  Then public-bag regression to exercise usable visual features. No new build or
  further replay started. New scene pilot remains planned for 19 October.

## [2026-10-18] T3.5c | Public regression PASS, key mismatch proven active, custody prompts removed

- Cumulative image `2fa9f264` public run `20261018T092811Z-520005`: PASS, zero
  invalid, 663 positive retrievals; counters show retrieval `key_hits` equal to
  insertion-convention `shadow_key_hits` (1,855,269 over 2.79 M queries).
- Buggy counters control `20261018T094059Z-520924` (image `3cd781a6`): mismatch
  active on the public scene (1,392,458 vs 1,878,707). With the fix, accepted
  retrieval points rise 112,980 → 128,385; the visibility guard cuts appended
  seed points 22,016 → 5,558; verdict and retrieval-row count unchanged.
  `mat_out` differences across all run pairs are dominated by run-to-run input
  delivery; no byte-identity or fix-attribution claim.
- Operator decision: typed `IDLE`/`CUSTODY AGREED` prompts removed from the
  build/replay tools (commit `c3c7d60`); entering the command is the
  confirmation. Programmatic lock/conflict/hold/resource checks unchanged.
  Bundle `visual-repair.xIOr2o` re-synced, manifest 32/32, 74 tests green on Mac
  and box, bench quick PASS. Evidence `EVIDENCE_t35c-public-20261018.sha256`.
- T3.5c remains PROGRESS; the 19 October pilot-gated capture is the next data step.

## [2026-10-18] T3.5c | Read-only live preview tool, L0 coverage, box preflight baseline

- New `live_preview.py` for the capture kit: read-only subscribers write the
  newest colour frame, a LiDAR-on-camera overlay (provisional nominal Rcl/Pcl),
  a stats block (arrival rates, stamp ages, depth bands, 3×3 region grid) and a
  self-refreshing `preview.html`. 18 unit tests (`test_live_preview.py`).
- A box smoke run found a real shutdown defect (SIGTERM → rclpy
  `ExternalShutdownException` → double `rclpy.shutdown()` traceback); fixed and
  re-smoked clean (`f528af3`, `cabd7f3`).
- Bench L0 now covers `FAST-LIVO capture tools` (86 tests) and `FAST-LIVO replay
  harness` (55 tests); `test_analyze_bag.py` stays box-only (`rosbag2_py`).
  Bench quick PASS.
- Kit `t35c-capture-kit.UTtxiL` staged and verified: manifest 32/32, box tests
  86 + 55 green with zero skips, Mac↔box file hashes identical,
  `preflight-baseline.txt` (box up 5 days, 44 GiB free, no ROS processes, D455 +
  435i on USB, MID-360 absent, native CustomMsg in `install_nav`) and
  `preview-smoke.txt` preserved.
- Capture plan updated (`2556bed`): preview pane allowed and specified, RViz
  stays off, viewing via the Mac browser over an `ssh -L 8099` tunnel; the
  offline pilot audit remains the GO gate. No hardware ran; the preview
  publishes nothing.
- T3.5c remains PROGRESS; the 19 October pilot-gated capture is the next data step.

## [2026-10-18] T3.5c | Preview dry run: rclpy CustomMsg cost found and fixed

- Dry run: `t35b_proof3` replayed (`ros2 bag play --loop`) into the preview on
  domain 174, in a new tmux session `t35preview` (the `t35c` session untouched).
  First result: every topic throttled to ~3 Hz at 106% CPU.
- Root cause, isolated with the new `probe_topic.py`: rclpy converts one
  20k-point `CustomMsg` in ~127 ms, so a normal Python subscription to
  `/livox/lidar` saturates a core at 10 Hz (4.4 Hz intake, 99% CPU) and starves
  the node; images (30 Hz, 15%) and IMU (200 Hz, 16%) are cheap. `ros2 topic hz`
  reads true rates only because reliable+deep CLI subscriptions keep up on their
  own process.
- Fixes (`8f29425`): scan subscribed raw and deserialized once per render;
  arrival-based scan freshness (`since=`; image/IMU keep stamp `age=`); QoS depth
  100 (the sensor preset's 5 overflowed every render); image subscribed
  reliable+volatile as the mapper does (fragmented 921 kB images lose whole
  samples best-effort); `write_png` gained a `level` parameter, default
  byte-pinned by test, preview uses level 1.
- After the fix: 10.2 / 30.7 / 205.7 Hz shown, LiDAR freshness 0.09 s, 47% of
  one core. The overlay reproduces the old scene's known failure exactly
  (drawn ~200, depths 0.16–0.24 m, `regions row2` only), which is the signal the
  new recording must clear. Replay stamps make `age=` read `STALE`; that is
  offline-only.
- Tools and tests green on Mac and box (90 tool tests, 55 harness tests), bench
  quick PASS. Capture plan updated with the dry-run numbers.
- `t35preview` stays up until Sherman agrees to close it.

## [2026-10-18] T3.5f | Read-only integration review: FAST-LIVO2 → the current stack

- Evidence: [`T3.5f_INTEGRATION_REVIEW_20261018.html`](T3.5f_INTEGRATION_REVIEW_20261018.html)
- Reviewed read-only (no box, no hardware, no file changed outside this doc):
  mapper output contract, current TF ownership, Nav2's inputs, bench assertions.
- New facts, previously unrecorded: the mapper's output frames are
  `camera_init` (world) → `aft_mapped` (body) at pinned `LIVMapper.cpp:1555–1576`
  — not `map`/`body` as assumed; its TF cannot be switched off (remap `-r
  /tf:=...` is the way); odometry is ≈10 Hz, not 50 Hz; and the pinned fork has
  no map-load or relocalisation path at all (pcd save only), which is what
  T3.5e must actually solve.
- Proposed wiring: one new bridge node owns `map → odom` (the edge SLAM Toolbox
  owns today), base driver keeps `odom → robot_base_link`, every consumer keeps
  its hardcoded frames, Nav2 params unchanged. Rejected: bridge on the
  `odom → robot_base_link` edge (would move the local costmap into `map`), and
  renaming consumers to `camera_init`.
- Identified gap: Nav2's global costmap needs `/map` (OccupancyGrid); FAST-LIVO2
  produces point clouds only. Recommended: offline SLAM Toolbox map build reused
  by `nav2_map_server`. Local obstacles need no change (`/scan` from the raw
  cloud stays in `livox_frame`, local costmap stays in `odom`).
- Five decisions listed for Sherman (live run form, localizer ownership, `/map`
  source, 10 Hz tolerance, body offset ownership). Nothing implemented; T3.5f
  still sits behind T3.5c → T3.5d → T3.5e.
- Next: pilot-gated capture on 19 October per `T3.5c_CAPTURE_PLAN_20261019.html`.

## [2026-10-18] T3.5f | LiDAR→IMU extrinsic: pinned fork's Mid-360 profile has the sign inverted

- Evidence: [`T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md`](T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md)
- Found while answering "do we have every transform the bridge needs?": the pinned
  fork's Mid-360 `extrin_calib.extrinsic_T` is the Livox manual's IMU-position
  numbers **unnegated**, while its own code applies them verbatim as
  `p_imu = extrinsic_R·p_lidar + extrinsic_T` (`IMU_Processing.cpp:85–92`, used at
  `:528`), which needs the negation.
- Four independent lines agree: the code rule; the Livox Mid-360 manual ("IMU Data",
  p.15, read from the operator's copy with `pdftotext`) placing the IMU chip at
  (+11.0, +23.29, −44.12) mm in the point-cloud coordinates with axes parallel to
  that frame; the fork's **own** Avia entry using the negated manual value (same
  file, same code path — so one of the two is a slip); and upstream FAST-LIO's
  `mid360.yaml`. The fork's README says Mid-360 support was added later, and its
  git history is two commits, so the newer entry is the suspect.
- Verified our `livox_frame` really is the manual's frame: driver copies point
  x/y/z through unchanged (`lddc.cpp:322–324`), its only transform path is the
  config's `extrinsic_parameter`, which is all-zero in the vendored
  `MID360_config.json` and is pushed to the device as its install attitude
  (`livox_lidar_callback.cpp:93–101`); SDK2 has no axis remap on the point path.
- Consequences recorded: the fork has **no online extrinsic estimation**
  (`extrinsic_est_en` absent from its source), so the wrong sign is never corrected
  at runtime — ~10.2 cm of geometric inconsistency inside every replay so far,
  which bounds the T3.5a/T3.5c evidence against absolute-geometry claims (their
  qualitative verdicts are unaffected). The integration bridge's body constant
  becomes (0.191, 0.023, 0.156) m instead of (0.169, −0.023, 0.244) m.
- Actions: reviewed value `[-0.011, -0.02329, 0.04412]`/identity goes into the new
  checked config pair for the 19 October recording; both frozen t35b pairs stay
  byte-unchanged and `check_replay_configs.py` now enforces the corrected value in
  every mode while `PRECORRECTION_PAIRS` reports their known sign as a note.
  Tests: `test_check_replay_configs.py` 42 → 50 (TDD, red first); Mac run 50 OK
  (6 staged-pair tests skip without PyYAML, as before). Contract §7/R2/changelog
  and the 19 October capture plan updated.
- Owed: a box round for the checker revision (50/50, both modes `CONFIG_OK`, one
  retained-sign `NOTE` per pair, one sign-mutation negative control), and the
  T3.5d in-place rotation test that decides the sign empirically — a wrong body
  constant makes the reconstructed base position walk a 10.2 cm circle at the
  rotation frequency, while a correct one leaves it stationary.
- Correction to an earlier statement of mine this session: a constant body
  translation does **not** cancel in pose deltas in general — it cancels only while
  the orientation is unchanged. Rotating is therefore the discriminating motion.
- Next: with Sherman's word, commit the t3.5-launch-prep documentation and checker
  changes; capture day follows the plan unchanged.

## Record Template


```markdown
## [YYYY-MM-DD] T<id> | Short title

- Evidence: [`T<id>_TOPIC.md`](T<id>_TOPIC.md)
- Verified:
- Outcome:
- Next:
```
