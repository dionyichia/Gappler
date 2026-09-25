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

## Record Template

```markdown
## [YYYY-MM-DD] T<id> | Short title

- Evidence: [`T<id>_TOPIC.md`](T<id>_TOPIC.md)
- Verified:
- Outcome:
- Next:
```
