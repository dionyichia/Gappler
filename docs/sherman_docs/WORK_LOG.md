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
- **Revision 2026-10-18 (same day):** the body constant this entry quotes from
  the fork's Mid-360 profile was wrong by a sign — corrected to
  (0.191, 0.023, 0.156) m, identity rotation, per the entry below and
  [`T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md`](T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md).
  Decision 5 is settled for the pinned sensor class; the revised review doc
  carries the correction in its header, §4, the file-change table and the ledger.
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

## [2026-10-19] T3.5c | Read-only box re-verify before the capture session

- Evidence: this entry (read-only probe; nothing written on the box).
- Verified (route): the jump route works — `ssh -J nvidia@100.118.250.28 rcp2026@192.168.1.100`
  reached `iot22-Computer`, up 5 days, 1-min load 0.21; the campus direct route `10.91.242.76` timed
  out from this Mac (the box itself still holds `wlo1 10.91.242.76`), so this is this Mac's path to
  the campus network, not the box.
- Verified (clean slate): no ROS/sensor processes running; `t35c` (window `replay`, 3 panes) and
  `gh-runner` alive; 43 GiB free — a 74.03 s bag measured 2.0–2.3 GiB, so pilot + final is ~2.7 GiB;
  D455 + D435i on USB with 12 video nodes; no OAK/Movidius device; xrdp virtual display `:10` alive.
- **Found (today's blocker):** the MID-360 at `192.168.1.12` answered neither ICMP nor ARP. It
  recorded fine on 17 October, and a Livox can ignore ICMP but it also failed to answer ARP — power
  and cable need eyes before the session; a capture without `/livox/lidar` is a wasted slot.
- **Found:** `ROS_DOMAIN_ID` is pinned nowhere on the box — not `~/.bashrc`, not `/etc/environment`,
  not `global_env.sh`, not any live tmux pane — so a fresh pane silently runs on domain 0 and sees an
  empty graph. The plan already exports it per pane; both the capture plan and the runbook now make
  it an explicit gate.
- **Found:** `~/rcp-Gappler` is on `dev` at `ca0604b` with someone else's uncommitted `grasp/` edits
  and **no** `docs/sherman_docs/tools/fastlivo/`; the session's tooling is the kit's scratch copy
  under `log/`. Do not check out the branch into that shared worktree.
- **Found (kit staleness):** three kit files predate the branch — `check_replay_configs.py` and
  `test_check_replay_configs.py` (both older than the LiDAR→IMU revision) and the kit `README.md`.
  `MANIFEST.sha256` covers only `recipe/` + `replay/`, so `sha256sum -c` passes while a tool script
  is stale; re-staging is owed before the session's post-capture step.
- Outcome: capture plan §1/§3/§5/§6 and the new T3.5d runbook updated with all four findings; the
  LiDAR power check and the per-pane domain export are now explicit gates.
- Next: re-stage the kit with the revised checker, then run the session.

## [2026-10-19] T3.5c | Bag identity for a later bag: `--emit-identity` / `--identity`

- Evidence: [`T3.5_CONSUMER_CONTRACT.md`](T3.5_CONSUMER_CONTRACT.md) §8;
  `tools/fastlivo/check_replay_configs.py` and `test_check_replay_configs.py`.
- Verified: the checker's four frozen topics, counts and duration were hard-wired to `t35b_proof3`,
  so a new bag had no machine-checked identity — the capture plan's "create a new checked config
  pair" step would have been hand-verified. `--emit-identity FILE` now writes a *candidate* snapshot
  (schema, topic → type + count, duration, message count, bag name) from a bag and exits without
  checking anything; a human reviews and commits that JSON; `--identity FILE` then makes it the
  declared expectation. The frozen record stays the default, so the T3.5a/T3.5c re-runs are
  untouched. Emission refuses to overwrite an existing snapshot; `--lio`/`--camera` are required only
  outside emit mode; exit 2 means the invocation was refused or the snapshot unreadable.
- Verified locally: `test_check_replay_configs.py` 50 → 73 tests, all green (6 staged-pair tests still
  skip without PyYAML); `./bench/run.sh quick` PASS. Ran the CLI end to end against a stubbed bag to
  read the real output: frozen mode, declared mode, a snapshot checked against a bag missing one topic
  (exactly one failure naming it), and emission (candidate JSON, sorted keys, `bag` recorded).
- Found while reading that output: my own first edit had duplicated the identity block, printing the
  `IDENTITY` line twice. Fixed, and a regression test now asserts both branches print it exactly once;
  re-introducing the duplicate makes that test fail (negative control run), so the test has the power
  it claims.
- Outcome: the post-capture pair is checked by the machine, and its identity is a reviewed artifact
  instead of a constant edited inside the checker.
- Owed box round: emit against the new bag, review, then both modes `CONFIG_OK` with `--identity`,
  plus one negative control — a snapshot count nudged by one must fail naming that topic and both
  numbers.

## [2026-10-19] T3.5d | Attended-session runbook (protocol; nothing started)

- Evidence: [`T3.5d_ATTENDED_RUNBOOK.html`](T3.5d_ATTENDED_RUNBOOK.html).
- Verified: written from the settled integration review, the LiDAR→IMU finding and the pinned fork's
  source rather than from memory — the mapper's topic names (`/aft_mapped_to_init`,
  `/cloud_registered`, `/Laser_map`, `/path`, `/rgb_img`) and the camera load path
  (`LIVMapper.cpp:212`) were read from the pinned source, and the mapper teardown crash plus the
  empty-diagnostic-cloud behaviour from [`T3.5_FASTLIVO_REPLAY.md`](T3.5_FASTLIVO_REPLAY.md).
- Covered: preconditions; one-build/one-launch staging with the mapper in its own native colcon
  workspace sourced alongside Gappler; per-stage evidence; stationary-then-hand-driven acceptance
  with the rule that offline or stationary success does not prove moving-map quality; the in-place
  spin test as the empirical discriminator for the LiDAR→IMU sign and what each outcome means; the
  ~10 Hz pose-rate measurement for Nav2; stop-and-investigate conditions; the corrected bridge
  constant with its residual eye-estimated mount rotation; evidence to preserve and what to write up.
- Corrections made on review before acceptance: the fork's code applies the Mid-360 value *verbatim*
  (a first draft said it applies the negation — backwards); an unverified "100 ms" parameter-wait
  detail was replaced by the source-read throw; and the acceptance/stop wording now separates a
  diagnostic run (empty registered clouds are the source-observed heartbeat) from a visual run
  (point-less clouds are invalid), so the runbook cannot trigger a false stop.
- Outcome: T3.5d has a written protocol; the task itself is not started and no measurement is
  claimed.
- Next: T3.5c close-out first; the runbook then runs at the attended session.

## [2026-10-19] T3.5c/T3.5f | Config sweep of the pinned fork: 42 parameters, five findings

- Evidence: [`T3.5_CONFIG_SWEEP_20261019.md`](T3.5_CONFIG_SWEEP_20261019.md);
  [`T3.5_CONSUMER_CONTRACT.md`](T3.5_CONSUMER_CONTRACT.md) §2 item 6, §8.
- Verified: a read-only sweep of all twelve `config/*.yaml` in the pinned fork against the Mid-360
  manual, the parent project, the vendored driver and the fork's own source. Method as for the
  extrinsic defect: no finding is accepted on one evidence line. **None of the findings changes a
  number in our staged pair.**
- **F1** `lio.max_iterations` is read by nothing: the code declares and reads `lio.min_iterations`
  (`voxel_map.cpp:50, 65`) and stores it into the field `max_iterations_`; `grep lio.max_iterations`
  in the source returns zero hits, and upstream reads `lio/max_iterations` into that same field, so the
  ROS 2 port renamed the key in code and left the configs behind. Our pair already writes
  `lio.min_iterations` (with a comment naming the trap). No numeric change today (both defaults are 5),
  but raising `lio.max_iterations` in a live config would silently do nothing.
- **F2** `preprocess.blind` cannot act, and this is the one that changed a document. Verified here:
  `blind_sqr` is declared with no initializer (`preprocess.h:185`), is never assigned anywhere in the
  fork, and is what the very gate our path uses compares against (`preprocess.cpp:194`, reached via
  `avia_handler`); upstream sets it one line after its parameter block
  (`p_pre->blind_sqr = p_pre->blind * p_pre->blind`, `hku-mars/FAST-LIVO2` `LIVMapper.cpp:116`, fetched
  and read for this check). So the port dropped that line, and the threshold is an uninitialised
  member — an arbitrary-value read, not a 0.1 m gate. Consequence: the contract's §2 item 6 claim that
  the bag's 51.84% zero-range returns "are dropped by any positive `blind`" is **withdrawn** (item 6
  rewritten), the frozen pair's comment repeating it is superseded — the frozen files themselves stay
  byte-unchanged — and `check_replay_configs.py` now emits a note on every run of a config carrying
  `preprocess.blind`. The magnitude is deliberately left unmeasured: which way the uninitialised value
  falls is not established from the source.
- **F3** the LiDAR→IMU sign finding, re-confirmed rather than repeated. **F4** the unused
  `camera_pinhole.yaml` holds the rational model's coefficients in `cam_d0..d3` (no launch loads it, so
  no current impact). **F5** `common.livox_msg_type` is dead on `lidar_type: 8` — it is read only on
  the AVIA branch — so the mid360 profile's PointCloud2 expectation contradicts the vendored driver's
  CustomMsg default; our pair uses `lidar_type: 1`, so this is inert for us.
- Also positively verified, so it can be cited rather than re-derived: the pair rule (`img_en` the only
  difference between a pair) holds for both LiDAR families, and `scan_line: 4`, `blind: 0.1`,
  `imu_int_frame: 50`, `anchor_factor: 0.5`, `td_step_cap: 0.0005` and the Mid-360 point layout/timestamp
  unit all check out. Items with no ground truth to check (for example `img_time_offset: 1200.252661`,
  `tr_readout: 0.01101`, the camera `scale` values, `Rcl/Pcl`) are listed as unverifiable rather than
  quietly passed.
- Outcome: the checker carries one more note; the contract's point-path section is corrected; the
  capture plan's new-pair step says not to describe the new bag as near-range-filtered. No source patch
  — fixing F2 is a one-line change with its own experimental image tag, compared against the accepted
  image, and is **not** done here.
- Next: decide whether an F2 patched image is worth building (it would make the gate deliberate and the
  point counts reproducible) or whether to leave the pinned source alone while T3.5c is open. The cheap
  empirical reading is the same bag twice, pinned build vs patched build, comparing retained zero-range
  fraction.

## [2026-10-19] T3.5 | F2 patch prepared (blind_sqr)

- Evidence: [`T3.5_F2_BLIND_SQR_PATCH.md`](T3.5_F2_BLIND_SQR_PATCH.md); recipe section 2026-10-19 in
  [`tools/fastlivo/recipe/README.md`](tools/fastlivo/recipe/README.md); MANIFEST re-verified 35/35.
- Verified: Decision taken — patch, as a separate experimental image with the pinned image kept as the
  control. `patch_blind_sqr.py` restores upstream's `p_pre->blind_sqr = p_pre->blind * p_pre->blind`
  where upstream has it, plus one tagged print of the threshold in force; it accepts only the pinned
  `LIVMapper.cpp` (`815b5f89…`), fails closed on an absent or ambiguous anchor, refuses a second
  application, and strips back to the original byte-for-byte. Build mode `T35_BLIND_SQR=1` starts from
  the exact accepted image ID, network `none`, mapper-only, output `t35-fastlivo-blind-sqr:experimental`
  in container `t35-fastlivo-blind-sqr-build`, and refuses other image names, compiler overrides and
  combination with `T35_VIO_DIAGNOSTIC`. `test_blind_sqr.py` (5 tests, including the real-source
  reversibility check) passes; `test_recipe.py` 10/10 after its shared-host-gate assertion moved to the
  new branch text; `bench/run.sh quick` PASS with a new L0 step.
- Outcome: The patch, its build mode and the measurement are prepared and tested; **no image is built
  and no replay has run**, so the pinned binary remains the consumer of record and F2's magnitude stays
  unmeasured. The measurement needs no new instrumentation: the pinned binary already prints the
  post-gate point count (`[ Preprocess ] Output point number:`), and the T3.5b bag's 51.84 %
  zero-range fraction separates "gate off" from "gate on" by a factor 2.08, so the control is the
  already-built accepted image (one build + one replay). Declined with reasons: initialising the member
  in `preprocess.h` (picks a fate instead of restoring the threshold), reusing `T35_VIO_REPAIR` as a
  third stage (mislabels a LiDAR-path fix — F1's defect class), and instrumented counters (the
  observable already exists).
- Next: Sherman runs `T35_BLIND_SQR=1 bash run_build.sh` from a fresh copied bundle, then one replay
  with `T35_REPLAY_IMAGE=t35-fastlivo-blind-sqr:experimental`; compare the median preprocessed point
  count against a pinned-image run of the same bag and pair.

## [2026-10-19] T3.5 | Checker box round closed (LiDAR→IMU + identity + blind note)

- Evidence: [`tools/fastlivo/EVIDENCE_t35c-config-check-20261019.sha256`](tools/fastlivo/EVIDENCE_t35c-config-check-20261019.sha256)
  (21 files); box dir `~/rcp-Gappler/log/t59-fastlivo/log/t35c-config-check-20261019.3rig5x`.
- Verified: The two long-owed box rounds are closed on bytes the box now has, run read-only over the
  Orin jump route. Checks: 77/77 unit tests OK on the box (the round owed 50 when it was written; the
  identity and blind-note revisions landed in between, so the same file was re-run at 77); both staged
  pairs `CONFIG_OK` with the `LIDAR_IMU` line, `retained_precorrection=True`, one retained-sign `NOTE`
  each, and the F2 blind `NOTE` present; a copy of the diagnostic pair under a **non-exempt filename**
  with the *corrected* `extrin_calib.extrinsic_T=[-0.011,-0.02329,0.04412]` gives `CONFIG_OK` with
  `retained_precorrection=False` — the path a new pair must take, exercised before the new bag exists;
  the negative control (that corrected pair with `extrinsic_T[0]` sign mutated back) gives
  `CONFIG_FAILED failures=1`, exactly one failure naming
  `extrin_calib.extrinsic_T[0]=0.011 != -0.011`. Identity mechanism round on `t35b_proof3`:
  `--emit-identity` exit 0 (`IDENTITY_EMITTED … topics=4 sha256=fbbdad9c…`); re-emitting refused,
  exit 2, naming the file as evidence; `--identity <candidate>` → `IDENTITY source=… list=` + `CONFIG_OK`;
  nudged-count copy → `CONFIG_FAILED failures=1` naming the topic and both numbers
  (`/camera/camera/color/camera_info count 2220 != expected 2221`). The five staged files
  (`check_replay_configs.py` `c5aa1c45…`, `test_check_replay_configs.py` `163e99d4…`, both pairs, the
  camera config) hash-match the repo copies byte-for-byte.
- Outcome: Contract §8's "box round owed" for the 2026-10-18 LiDAR→IMU revision and the identity
  revision's mechanism round are now closed with a manifest. Two honest limits: the box's own checkout
  is `dev` `ca0604b` carrying Dion's uncommitted work — I read it and wrote only inside the new evidence
  dir; and `unit.stdout.log` is empty in the manifest because Python's `unittest` writes to **stderr**,
  so the run is in `unit.stderr.log` and `unit.summary.txt` (the empty file is kept as evidence of the
  invocation, not tidied away).
- Next: The identity round's *new-bag* half stays owed (emit against the new lab recording, review,
  commit the snapshot beside the pair). The candidate snapshot in this box dir is `t35b_proof3`'s — a
  mechanism artifact that must **not** be committed as the new bag's identity.

## [2026-10-19] T3.5 | F2 `blind_sqr`: build succeeded, control measured

- Evidence: [`T3.5_F2_BLIND_SQR_PATCH.md`](T3.5_F2_BLIND_SQR_PATCH.md) §4;
  [`T3.5_F2_BLIND_SQR_BUILD.html`](T3.5_F2_BLIND_SQR_BUILD.html);
  `tools/fastlivo/EVIDENCE_f2-blind-sqr-build-20261019.sha256` (42 rows, 42/42 OK, own sha256
  `50d309a28c1c3bea…`), generated on the box over `log/f2-blind-sqr-build.lPMyTM` plus the control
  replay's `result.json` and `mapper.stdout.log`.
- Verified (build; the operator ran it, I read the box read-only): the staged bundle's 19/19
  `recipe/` manifest rows checked clean before the run; `build.log`'s **first** line is
  `src/LIVMapper.cpp: OK`, so the accepted image really carries the byte-identical pinned source and
  the SHA gate held; `Finished <<< fast_livo [1min 31s]`, `State.ExitCode 0`, `OOMKilled false`;
  `blind-sqr/source.patch` is exactly the four tagged lines; container `NetworkMode: none`, 8 GiB /
  8 GiB swap, 2 CPUs, 512 PIDs, no privileges, mounts or devices; the pre-commit tag recheck found no
  collision, and the wrapper's own base inspection (before the run) resolved
  `t59-fast-livo2:experimental` to `sha256:d0dcfa8a…` — a `docker commit` creates a new image and
  leaves its base alone, but the accepted image's post-run state is inferred from that, not
  re-inspected (`docker` needs a sudo timestamp I do not hold).
  Committed as `sha256:81f1c3c2a6dc030c…` under the tag `t35-fastlivo-blind-sqr:experimental`.
  The patched source inside the container hashes to `e61bbdeda3ea578d…` — byte-identical to the same
  patch applied locally on the Mac at staging time, so two independent applications agree.
  `[T35_BLIND_SQR]` present in the binary's strings (the banner's text is split across literals, so
  one chunk is expected).
- **Control measured with no new replay** (read-only): the recorded accepted-image run
  `t59-replay-20261018T062144Z-511887` (bag `t35b_proof3`, pair `t35b_proof3_lio.yaml`, verdict PASS)
  reports median **19,968** `[ Preprocess ] Output point number:` per scan, range 19,872–20,160. The
  audit total (14,799,936 points = 154,166 packets × 96) over 740 handled messages is 208.3 packets
  per message and 19,968 = 208 × 96 exactly, so the median **is the full packet count**. The same
  19,968 appears on the other two images with a run of this bag (VIO-diagnostic `3cd781a6…`,
  visibility `ba66a419…`) and on the `_visual` pair — four runs, no variation. ⇒ the gate dropped
  nothing: **the pinned fork has mapped all 51.84 % zero-range returns in every replay of this bag so
  far.** F2 is confirmed empirically at the pinned end, before any patched replay.
- Correction, mine and recorded: the F2 record, runbook and sweep first predicted ≈ 22.3 k and
  ≈ 10.8 k per scan. Those magnitudes came from the **public** recording's 663 clouds (9.19 M points),
  not from `t35b_proof3`; this bag carries 740 handled messages at ~20,000 points each. The separation
  factor 2.08 was right, the magnitudes were not. All three documents now carry the measured control
  19,968 and the expected patched ≈ 9,617, and say so.
- Next: **one replay** — same bag, same frozen pair, `T35_REPLAY_IMAGE=t35-fastlivo-blind-sqr:experimental`
  — then compare medians (expect ≈ 0.48 of control, ≈ 9,617) and read the
  `[T35_BLIND_SQR] blind=0.1 blind_sqr=0.01` banner. That result feeds the own-data decision: adopt
  the patched image for the T3.5c replays on the new bag, or keep the pin and record F2 as a known
  limit of every replay to date.

## [2026-10-19] T3.5c | New stationary capture and offline checks completed

- Evidence: [`T3.5_CAPTURE_AUDIT_20261019.md`](T3.5_CAPTURE_AUDIT_20261019.md),
  `tools/fastlivo/EVIDENCE_t35c-capture-20261019.sha256` (79/79 files verified;
  paths relative to the box capture root `t35c-capture-20261019.of23agzq`).
- Sherman operated the sensors and recorder in prepared Bash/tmux panes, domain
  174, localhost-only; no arm/base motion or mapper launch. Actual LiDAR config
  targets `.3` with host `.5`, not the previously probed `.12`. SDK verified D455
  serial 146222253541 on USB 3.2; USB identifier is not the SDK serial.
- Pilot02: `ANALYSIS_OK`, SQLite integrity OK, four offline projections show
  improved shared coverage; operator confirmed stationary scene. Pilot01 and
  stationary01 remain preserved, not selected: unequal image/CameraInfo metadata
  counts; stationary01 additionally has reported background walking.
- Selected retake `stationary02`: 74.648 s, 747 LiDAR / 14,931 IMU /
  2,179 image / 2,179 CameraInfo messages. Recorder flush and stop logged,
  `RECORDER_EXIT=124 TEE_EXIT=0`, no recorder remains. Initial pilot timer skipped
  status capture; a harmless sleep pipeline reproduced it, and `setsid --wait`
  isolated-timer control preserved exit 124. Full recordings use that form.
- Read-only native audit: `ANALYSIS_OK`; finite sensor data, strict per-topic
  header order, stable image/calibration variants and exact image/CameraInfo
  timestamp pairing. Rates 10.00 / 200.00 / 29.19 Hz; largest header gaps
  105.028 / 9.987 / 34.262 ms. 14,940,000 LiDAR points, 35.92% zero-range;
  all scans have unsorted offsets, reported without rewriting originals.
- SQLite integrity `ok`; independent DB counts exactly reconcile with metadata.
  Four full-bag overlays at 0.0/24.9/49.7/74.6 s visually reviewed: 2,459–2,569
  projected points at 1.19–8.57 m over shelf/cabinet, chair and floor regions.
  Provisional extrinsics and glass/reflections remain limitations, not tuned away.
  Database/metadata hashes identical before and after checks; exact used tools,
  camera profile, driver arguments and launch-time params are frozen with logs.
- Separate defect: after recorder finalization, D455 stopped cleanly but LiDAR
  exited -7/SIGBUS after SDK deinit; kernel trap points inside libspdlog. Evidence
  retained, cause unresolved, no hardware reproduction attempted. All sensors,
  recorder and preview are stopped; tmux remains open.
- Outcome: no additional stationary capture needed on checked evidence. Not
  proven: successful mapper estimation/visual updates, calibrated extrinsics,
  physical synchronization, moving-map accuracy or clean LiDAR driver shutdown.
  T3.5c stays PROGRESS. Next: shutdown investigation, reviewed new bag identity
  and corrected config pair, F2 image comparison/decision, then user-run A/B
  offline replays. No commit/push/PR/merge performed. Mount-photo receipt pending.
- Local record verification: `git diff --check` clean; report links, manifest
  hash/79 rows, report/task-tree JavaScript syntax and T3.5c PROGRESS status
  checked. `./bench/run.sh quick` PASS for levels that ran; Mac environment and
  hardware/ROS-dependent skips remain skips, not hardware evidence. Reader
  handoff: `T3.5_CAPTURE_AUDIT_20261019.html`.

## [2026-10-19] T3.5c | stationary02 identity/config preparation verified

- Scope: Sherman redirected focus to T3.5c. Native driver repair is parked;
  bag replay does not run the live driver. No new build, driver start or replay.
- Record: `T3.5c_STATIONARY02_REPLAY_PREP.md`; new identity JSON and LIO/visual/
  camera YAMLs under `tools/fastlivo/replay/config/`. Identity emitted from real
  stationary02 metadata: 74,648,076,097 ns, 20,036 messages, 747 / 14,931 /
  2,179 / 2,179, SHA-256 `5485bca4…`. Candidate is not yet human-approved.
- Box: current checker 77/77 tests OK; A and B CONFIG_OK with corrected T and
  retained_precorrection=False. Old-sign negative fails once on extrinsic_T[0];
  nudged-identity negative fails once on LiDAR 747 != expected 748. Semantic diff
  proves only common.img_en differs between A/B; B versus the frozen old visual
  map changes only corrected LiDAR→IMU T and sequence label. Camera params same
  measured values, new provenance. Three old frozen YAMLs byte-unchanged from HEAD.
- Stage: `t35c-stationary02-prep.2vJboq/` in box scratch log area; 25/25 input
  hashes match local bytes. Evidence manifest
  `EVIDENCE_t35c-stationary02-prep-20261019.sha256`, 38/38 files verified.
- Proposal, not decision: same existing visibility+voxel image for both A/B,
  recorded ID `2fa9f264…`, with F2 range-gate defect explicitly retained. This
  avoids changing binary as well as img_en between A/B and requires no new build;
  original accepted tag remains untouched. No k3 or calibration-accuracy claim.
- Next: operator reviews candidate identity/configs and image choice; explicit
  commit authorization still required before freezing reviewed inputs. Then
  user-entered A, audit, then B with unchanged validity/update gates. T3.5c is
  not DONE. No commit, push, PR or merge performed.

## [2026-10-19] T3.5c | Combined visual repairs + F2 recipe ready for operator build

- Sherman selected option 2 and approved the saved combined-image plan. Scope
  remains T3.5c; native driver repair is parked. No subagents or branch moves.
- Added independent `T35_COMBINED_REPAIR=1` mode, exact parent `2fa9f264…`, fixed
  separate tag `t35-fastlivo-visibility-voxel-blind-sqr:experimental`. Reused F2
  generator/inside script with explicit visibility-voxel mapper baseline; original
  pinned default stays SHA-gated. Only four tagged F2 lines added; inherited
  visual source/header hashes checked before patch and after compile.
- Tests first: 15 F2/combined tests ran with 10 expected red failures. After
  implementation, all 34 recipe/diagnostic/visual/F2/combined tests pass locally
  against preserved real source; quick bench PASS for levels that ran. One old
  host-gate string assertion was updated for the new leading combined branch;
  behavioral mode checks preserve old tags and lock-before-download semantics.
  Wrapper preflight now runs the previously omitted F2 suite and new combined
  suite; bench L0 covers combined guards. Recipe manifest regenerated 36/36.
- Fresh box stage `t35c-combined-build.LKf0QQ`: 34 tests OK with one explicit
  repository-bench skip; real-source/C++ checks run. Canonical source review
  independently predicts mapper SHA `75f987089d2a7d4b133955f4812666f484804174c8bc0df7823957a0b025060f`.
  48 staged inputs and 64 prebuild evidence files hash-verified. Manifest:
  `EVIDENCE_t35c-combined-prebuild-20261019.sha256`.
- A source-review helper initially lacked its recipe import path; corrected the
  helper's process-local path and reran successfully. No recipe behavior or
  system environment change was needed. Box shared dirty checkout untouched.
- Operator pane `t35capture:combined-build` (%9) has
  `T35_PINNED_SOURCE_DIR=../pinned-src T35_COMBINED_REPAIR=1 bash run_build.sh`
  typed, no Enter sent. 38 GiB free, no conflicting driver/build/replay found and
  build lock free at preparation. No Docker build/image creation or replay run.
- Next checkpoint: Sherman runs build; agent verifies exit/state, parent and
  output IDs, source patch/hashes and inherited diagnostic/F2 markers. Then old
  bag F2 comparison, public visual regression and reviewed stationary02 A/B.
  Plan steps 1–2 checked; runtime steps remain unchecked. Input review/commit
  still owed; nothing committed, pushed, opened as PR or merged. T3.5c PROGRESS.

## [2026-10-19] T3.5c | Combined image built and verified; F2 replay prepared

- Sherman ran the staged build. Logs `t35c-combined-build.LKf0QQ/recipe/build-logs.3Loz4f`:
  `fast_livo` finished in 26.2 s, summary 26.4 s, container exit 0, OOMKilled false.
  Parent `2fa9f264…`; new separate image
  `sha256:ac276ad768d6ca1907b7b407789574a38f9aebe66216f466d656eb301d546183`.
- Agent verified read-only: 2 CPUs / 8 GiB memory/swap limit / 512 PIDs,
  network none, unprivileged, no binds/devices/mounts. Exact four-line F2 patch;
  mapper SHA `75f98708…` matches prediction and strips to `ae4d3072…`. Inherited
  VIO/header hashes verified by build before and after. Binary SHA `39645871…`;
  F2 and both inherited diagnostic marker strings present. Runtime banner/gate
  behavior is still unmeasured. All 48 staged inputs and prebuild 64-file freeze
  independently rechecked unchanged.
- Old control provenance rechecked: accepted-image run
  `t59-replay-20261018T062144Z-511887` PASS, 740 preprocess lines, median 19,968,
  min/max 19,872/20,160. Its bag's original DB/metadata hashes match the frozen
  capture manifest. Both configs, replay.py/progress/QoS/container verifier match
  staged bytes. Wrapper diff is exactly removal of the two typed-custody prompt
  lines; no playback/threshold/locking logic changed.
- Build/reference evidence: `EVIDENCE_t35c-combined-build-20261019.sha256`,
  95/95 files verified, relative to the build-stage root; manifest SHA `e8c2f9ad…`.
  Control logs/result/inputs retained as copies; no original evidence modified.
- Prepared only the next replay in `t35capture:f2-control` (%11), by immutable
  new image ID, old t35b_proof3 LIO/camera pair and rate 0.25. No Enter sent;
  user-run replay and its validity/gate/count/shutdown checks are next. This is
  not stationary02 acceptance or a geometry claim for the old wrong-sign config.
  Public regression and new-data A/B remain afterward. No commit/push/PR/merge.

## [2026-10-19] T3.5c | F2 gate measured on the combined image — confirmed

- Sherman ran the prepared F2 replay. Run `t59-replay-20261019T073814Z-11063`;
  image `sha256:ac276ad768d6ca1907b7b407789574a38f9aebe66216f466d656eb301d546183`
  by immutable ID; old bag `t35b_proof3` with `t35b_proof3_lio.yaml` +
  `t35b_proof3_camera.yaml`, rate 0.25, `img_en=0`.
- Result: verdict PASS, host and container exit 0, no OOM, 302.3 s, quiet drain,
  no errors in any stream, mapper ending on `signal_handler(SIGINT/SIGTERM)`;
  740/740 LiDAR and 14,789/14,807 IMU inputs reconciled with zero missing stamps.
- Gate measurement: banner `[T35_BLIND_SQR] blind=0.1 blind_sqr=0.01` present;
  `[ Preprocess ] Output point number:` over **740** scans, median **9,607**
  (9,411–9,875) against the retained control's 19,968. Per-scan ratio median
  **0.4811** with range 0.4733–0.4923 — inside the pre-declared 0.48 ± 0.02 band
  at every scan. Removed fraction 0.5206 matches the bag's audited 51.84 %
  zero-range content, so the drop is the intended 0.1 m gate on zeros, not a
  second filter. Independent monitor cross-check: 7,079,105 / 736 = 9,618 average.
  Predicted ≈ 9,617 vs measured 9,607 = 0.11 % apart. F2 therefore confirmed on
  this bag; the ratio is bag-specific and is **not** carried to `stationary02`.
- Explained, not glossed: the control's monitor saw 637/740 clouds because
  validating ~20,000-point clouds cost 43.5 s of wall time and its BEST_EFFORT
  subscription fell behind; the patched run's ~9,600-point clouds validated in
  2.9 s and kept 736. Monitor-side scheduling, not an estimator difference.
- Evidence: `EVIDENCE_t35c-f2-runtime-20261019.sha256` (31 files: whole run
  directory plus verification JSON and operator pane record, paths relative to
  `~/rcp-Gappler/log/t59-fastlivo/`), manifest SHA `0a0addc8…`. The 95-file
  build freeze was re-verified unchanged after the run; all 48 staged inputs
  still match.
- Prepared only the next replay: the retained public visual regression on the
  combined image, typed in `t35capture:public-visual` (%12) with the image by
  immutable ID and otherwise harness defaults (public bag, `bright_screen_wall.yaml`
  + `camera_pinhole.yaml`, rate 0.25). No Enter sent. Its PASS criteria are the
  control's: 663 positive visual retrievals, 664 coloured-cloud rows with zero
  empty, 665/664/606 outputs zero invalid, inputs reconciled. Point totals will
  fall because the same gate now runs there — expected, not a regression.
- No commit, push, PR or merge. T3.5c PROGRESS; public regression and reviewed
  stationary02 A/B still owed.

## [2026-10-19] T3.5c | Public visual regression on the combined image: FAIL, one lost message

- Run `t59-replay-20261019T080101Z-12426`, combined image `ac276ad7…` by immutable ID,
  public bag with `bright_screen_wall.yaml` + `camera_pinhole.yaml`, rate 0.25.
  Verdict **FAIL**, host and container exit 1, elapsed 388.3 s.
- **Root cause, single:** the final `/left_camera/image` message (stamp
  `1661405918.291177`) reached neither the mapper nor the harness observer —
  667 of 668. `replay_progress.CallbackTracker.tails_seen()` requires each
  topic's last expected stamp, so the drain never qualified for its 5-quiet-second
  exit and burned the full 120 s deadline. The estimator was idle across that
  whole window (callback counts and log sizes flat 270.7 s → 380.9 s). Both
  errors — drain timeout and `coverage /left_camera/image: missing=1` — follow
  from that one gap.
- **No visual regression is visible in the mapper-side evidence** vs the retained
  control `t59-replay-20261018T092811Z-520005` (parent `2fa9f264…`, same bag and
  config/QoS bytes, harness identical but for the two removed custody lines):
  664 visual frames and 664 coloured-cloud rows in both; **663 positive visual
  retrievals** in both; `key_hits` = `shadow_key_hits` 2751 vs 2747 (alignment
  held); `projected` 1941 vs 1944; `visible` 805 vs 803; `accepted` 195 vs 194;
  coloured points median 14,187.5 vs 14,191.5 with zero empty rows in both.
- **Correction recorded:** the F2 0.1 m gate is nearly inert on this bag —
  `source_points` median 24,008.5 → 23,885.5 (0.5 %). The near-zero returns are a
  property of `t35b_proof3` (51.84 % zero-range), not of the gate. The standing
  rule against carrying the old bag's 0.4811 across bags now has a mirror case,
  and the pre-run expectation that point totals would fall here was wrong.
- **Open, unattributed:** monitor-observed `/rgb_img` 401 vs 606 and
  `/cloud_registered` 662 vs 664 — both BEST_EFFORT monitor subscriptions, while
  the mapper's own publication count is identical (664 coloured frames, none
  empty). The simple contention story does not fit (monitor cloud validation
  3.9 s here vs 34.6 s in the control) and no per-message history is retained.
  The written criteria ("606 RGB") are unmet independently of the drain timeout,
  so a repeat must clear both.
- Preserved: run directory (nothing deleted, pruned or retagged), manifest
  `EVIDENCE_t35c-public-regression-fail-20261019.sha256` (28 files, relative to
  `~/rcp-Gappler/log/t59-fastlivo/`, SHA `590563fd…`). Control run, accepted
  image, parent image, the F2-only spare and all frozen configs untouched.
- **Operator ruling + allowance audit.** Ruled an input-reconciliation failure, not a
  pass on good-looking output. Audit of every declared allowance in the frozen
  `replay.py`/`replay_progress.py` bytes the run itself hashed: the 0.25 s
  metadata tolerance is scoped to `clock_complete()` and *passed* (|Δ| = 0.0005 s),
  the IMU prestart allowance is 21 messages and is IMU-only and start-side only
  (`max(missing) < min(matched)`), coverage in `finalize_report()` is exact
  (`missing`/`unexpected` nonzero = hard FAIL), and `drain_state()` is a detector
  that cannot leave `waiting` until `tails_seen()` sees each topic's maximum
  expected stamp. **No pre-declared allowance covers the terminal message.** The
  message is the recording's own last message — stored 1661405918.202350 = the
  metadata end, header 1661405918.1911774, expected = header + the configured
  `time_offset.img_time_offset: 0.1` — so the first record's "+0.089 s past the bag
  end" framing was corrected (correction recorded in §1 and on the page).
- **Base rate:** six prior camera runs all delivered the terminal stamp
  1661405918.291177; this is the first terminal-input loss in the record — not a
  known flake, not yet systematic; both readings held open.
- **Control comparison:** terminal delivery happened during playback; mapper image
  subscription depth is 200,000, RELIABLE (`LIVMapper.cpp:310`) so a subscriber-side
  one-message loss is implausible, and there is no second input observer (drain
  `callback_counts` and coverage rows both come from the mapper's own log). Leading,
  **unproven** mechanism: `rosbag2_player` exiting at EOF with its final sample
  unacknowledged. Shutdown identical in both runs (same two `imu loop back` errors
  0.000505/0.000405, mapper exit 0 ending in `signal_handler`, camera exit 0, player
  exit 0 by itself); only the trigger differs (5 quiet seconds vs the 120 s deadline).
- **RGB 401 vs 606 attributed, not excused:** mapper publishes `/rgb_img`
  unconditionally once per LIO iteration (`publish_img_rgb`, `LIVMapper.cpp:1342`
  called at 508) and `[T35_DIAG_CLOUD]` is 664 in both runs → mapper-side publication
  equal; the deficit is already 18 at the first snapshot and grows monotonically on a
  BEST_EFFORT monitor subscription → monitor-side observation loss. The written count
  criterion is unmet; its validity clause is met (`invalid = 0` on all three streams).
- **Outcome: FAIL stands.** No replay staged, stationary02 A/B unstarted, nothing
  tuned. Two items await the operator: whether to authorise a supervised repeat to
  test reproducibility of the publisher-end loss, and whether to make a terminal
  input message lost at playback EOF a named harness condition (changes
  `replay.py`/`replay_progress.py` bytes → re-frozen harness + authorisation).
  Sections §7–§8 of `T3.5c_PUBLIC_REGRESSION_20261019.md` hold the audit.
- No commit, push, PR or merge. T3.5c PROGRESS.

## [2026-10-19] T3.5c | Operator-authorised repeat: the terminal camera loss reproduces 2/2

- Run `t59-replay-20261019T104105Z-15368`, same public bag, same configs, combined image
  `ac276ad7…` by immutable ID, staged harness bytes re-verified before staging
  (`replay.py` `a5c13baf…`, `replay_progress.py` `b70dea01…`, `playback_qos.yaml`
  `e399564e…`, `bright_screen_wall.yaml` `d6709400…`, `camera_pinhole.yaml`
  `0cd0556c…`, `run_replay.sh` `ded7556f…`). Verdict **FAIL**, exit 1, 388.2 s.
- **Same two errors, same missing stamp** `1661405918.291177`; same last logged camera
  stamp `1661405918.191444`; camera 667/668 again. LiDAR 667/667, IMU 13,511 with 4
  prestart drops (allowance 21, missing 0). Not a one-off — systematic on this
  configuration.
- Estimator side reproducible to the digit across the two combined-image runs: 663
  positive retrievals, `key_hits` = `shadow_key_hits` 2,763, 664 retrieve rows / 664
  coloured rows with zero empty, coloured median 14,191.5, `source_points` median
  23,885.5 (identical to the first combined run). Monitor cloud 664, RGB 386.
- **RGB spread attributed structurally:** the mapper advertises `/rgb_img` with queue size
  1 (`pubImage = it.advertise("/rgb_img", 1)`, `LIVMapper.cpp:325`) to a BEST_EFFORT
  monitor, so 606 / 401 / 386 is a depth-1 scheduling artefact, not an estimator signal;
  mapper-side coloured publications stay 664 in all three runs.
- **Still confounded:** the six clean terminal deliveries were on other images *and* on
  18 Oct, so image-versus-box-state is not separated. Discriminator named and **not**
  authorised: replay parent image `2fa9f264…` on the same bag today.
- Evidence `EVIDENCE_t35c-public-repeat-20261019.sha256` (28 files, relative to
  `~/rcp-Gappler/log/t59-fastlivo/`, SHA `415e26cb…`). First failed run, control run and
  every frozen config untouched. No tuning, no stationary02 A/B, no commit, push, PR or
  merge. T3.5c PROGRESS.

## [2026-10-19] T3.5c | Parent image on today's box PASSES — loss tracks the image, on thin numbers

- Run `t59-replay-20261019T110638Z-16247`, image **`2fa9f264…`** (the exact 18 Oct control
  image), same bag, configs, staged harness bytes and pane, same day as both combined
  failures. Verdict **PASS**, exit 0, 276.2 s, drain `callbacks_quiet`, no errors, camera
  **668/668** with the terminal stamp `1661405918.291177` delivered.
- Day held constant and the image is the only change; box state today is indistinguishable
  across the three runs (monitor validation 3.78 / 3.91 / 3.93 s). So on today's box the
  terminal loss tracks the image: 2/2 combined failures at the identical stamp, 0/1 parent.
- Numbers: 663 retrievals, `key_hits` = `shadow_key_hits` 2,753, coloured median 14,185.0
  with zero empty rows, `source_points` median 24,008.5 — identical to the 18 Oct control,
  which confirms F2's ~123-point (0.51 %) reduction is reproducible and transfers only as a
  count, not as a visual change.
- **Caveat recorded:** 2 failures versus 1 pass is a correlation, not a mechanism. F2 touches
  only LiDAR preprocessing thresholds; there is no direct code path from the patch to a
  camera-message acknowledgement race, and none has been found. The effect would have to be
  indirect (per-frame cost shifting the end-of-bag acknowledgement).
- **Second finding, gate-relevant:** the *same parent image* scored **606 RGB on 18 Oct and
  389 today** (same bag and configs). The written "606 RGB" criterion therefore fails a
  known-good image; it must be restated as validity plus a bound before it gates anything
  again — a gate change needing authorisation.
- Evidence `EVIDENCE_t35c-public-parent-discriminator-20261019.sha256` (28 files, relative to
  `~/rcp-Gappler/log/t59-fastlivo/`, SHA `b2de2335…`). All earlier runs and frozen configs
  untouched.
- Next discriminator **not** authorised: two more parent-image runs today (any parent loss →
  race is image-independent, combined image exonerated, harness fix is the answer; parent
  clean 3/3 → image-linked hardens). No tuning, no stationary02 A/B, no commit, push, PR or
  merge. T3.5c PROGRESS.

## [2026-10-19] T3.5c | Parent image loses the terminal frame too — image exonerated, reading withdrawn

- Run `t59-replay-20261019T113638Z-17153`, parent image `2fa9f264…`, same bag, configs and
  staged harness bytes: **FAIL**, exit 1, 388.3 s, camera **667/668**, missing the identical
  stamp `1661405918.291177`; `validation_wall` 3.88 s.
- Today: combined `ac276ad7` 0/2 terminal deliveries; parent `2fa9f264` 1/2. The earlier
  "weight of evidence favours the image" reading is **withdrawn** — the loss is
  image-independent, it is the `ros2 bag play` end-of-bag delivery race at roughly one run in
  two today, and the combined image plus the F2 patch are not implicated.
- **Inertness argument recorded:** in every run the terminal camera message postdates the final
  LiDAR callback (last LiDAR `1661405918.099318` vs terminal camera `1661405918.291177`,
  0.192 s later), so no VIO frame can consume it — 663 retrievals and 664 coloured rows in
  every run, pass or fail. That is the only defensible basis for a bounded terminal-message
  rule; it must not relax coverage anywhere earlier in the run.
- Gate state: no image can pass this harness reliably (3 of 4 runs today lost the frame), so a
  harness change is required before T3.5c can close — name the condition, permit exactly one
  bounded case, red→green tests, re-frozen harness bytes and new manifest. The RGB criterion
  also needs restating as validity plus a bound (389 / 384 today, 606 two days ago, same
  parent image).
- Evidence `EVIDENCE_t35c-public-parent-repeat2-20261019.sha256` (28 files, SHA `2ad059b2…`).
  No tuning, no gate change applied, no stationary02 A/B, no commit, push, PR or merge.
  T3.5c PROGRESS.

## [2026-10-19] T3.5c | Harness fixed: one bounded, recorded terminal-message allowance

- Sherman authorised the harness change after the parent image lost the terminal camera frame too
  (run `t59-replay-20261019T113638Z-17153`), confirming the loss is image-independent.
- Implemented test-first in `tools/fastlivo/replay`: four new tests red (acceptance case, eight
  rejection cases, reconciled-rows helper, supervisor verdict both ways, closed default without a
  declared LiDAR topic), then green. `replay.py` `b7de050b…`, `replay_progress.py` `e13c0275…`,
  `test_progress.py` `10256fbb…`. 59 replay tests and 34 recipe tests OK locally; the same 59 OK
  on the box; repo `MANIFEST.sha256` 36/36.
- Rule (all required): LiDAR complete; exactly one other topic missing exactly one message; that
  stamp is the topic's own last expected stamp; strictly later than the last observed LiDAR
  callback; every other topic exact after the unchanged IMU prestart allowance; no duplicates.
  Anything else still fails. The row keeps `missing = 1`; `result.json` records
  `terminal_message_lost` (topic, stamp, offset) and `input_lidar_topic`. Drain ends at five quiet
  seconds, so a loss costs ~5 s instead of ~112 s.
- Basis: the accepted stamp postdates the last LiDAR callback by 0.192 s, so no VIO frame can
  consume it — 663 retrievals and 664 coloured rows in every run, pass or fail.
- Staged at `~/rcp-Gappler/log/t59-fastlivo/log/t35c-terminal-allowance.y1iqfO/` (replay + recipe
  copied from the combined-build staging, three harness files replaced, `replay.py` and
  `replay_progress.py` hash-verified). Evidence
  `EVIDENCE_t35c-terminal-allowance-20261019.sha256`, 77 files, SHA `62b4e9f7…`. Previous staging
  and all six earlier evidence manifests untouched. Operator commands recorded in
  `operator-terminal-allowance-command.txt`.
- Next: run the candidate image, then the control, one at a time through the new harness; audit
  read-only and freeze each run. No tuning, no QoS/tolerance/rate/input change, no commit, push, PR
  or merge. T3.5c PROGRESS.

## [2026-10-19] T3.5c | Public regression CLOSED: both images PASS on the fixed harness

- Candidate `ac276ad7…` run `t59-replay-20261019T121245Z-18725`: **PASS**, exit 0, 276.3 s,
  `callbacks_quiet`, camera 667/668, `terminal_message_lost` recorded at
  `1661405918.291177` (0.191859 s after the last LiDAR callback), coverage row still
  `missing = 1`. 664 rows, coloured 14,189.0, `source_points` 23,885.5, 663 retrievals, streams
  665/664/441 all valid.
- Control `2fa9f264…` run `t59-replay-20261019T123317Z-19484`: **PASS**, exit 0, 276.1 s, same
  recorded allowance at the identical stamp, 667/668, 664 rows, coloured 14,189.5,
  `source_points` 24,008.5, 663 retrievals, streams 665/664/430 valid.
- Both runs reported the fixed harness bytes they used (`replay.py b7de050b`,
  `replay_progress.py e13c0275`); configs and QoS unchanged. A loss now costs 276 s, not 388 s.
- Estimator side differs only by F2's reproducible ~123-point `source_points` reduction, which is
  the intended patch effect. **The combined image is accepted for the public visual regression.**
- Rate recorded: 4 of 6 runs today lost the terminal frame (combined 3/3 since the build, parent
  1/3); the delivered path still exists (parent delivered at 11:06). The allowance is a race
  handler, not a substitute for delivered-path evidence.
- Evidence `EVIDENCE_t35c-public-allowance-candidate-20261019.sha256` (28 files, SHA `88861499…`)
  and `EVIDENCE_t35c-public-allowance-control-20261019.sha256` (28 files, SHA `852cd07f…`).
- Owed before the next stage: operator review and an explicit commit of the stationary02
  identity/config files plus this harness change; then stationary02 A audited read-only, before B
  on the combined image. Separately: capture-kit re-stage, mount-photo receipt. No tuning beyond
  the declared allowance, no commit, push, PR or merge. T3.5c public regression CLOSED; T3.5c
  overall PROGRESS.

## Record Template


```markdown
## [YYYY-MM-DD] T<id> | Short title

- Evidence: [`T<id>_TOPIC.md`](T<id>_TOPIC.md)
- Verified:
- Outcome:
- Next:
```
