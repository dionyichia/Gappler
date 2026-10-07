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

## Record Template

```markdown
## [YYYY-MM-DD] T<id> | Short title

- Evidence: [`T<id>_TOPIC.md`](T<id>_TOPIC.md)
- Verified:
- Outcome:
- Next:
```
