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

## [2026-09-23] T1.5 | Driver-only bring-up draft

- Draft: [`../ARM_BRINGUP.md`](../ARM_BRINGUP.md) (shared procedure; not yet validated)
- Verified: source and earlier records only. No controller power-on, driver launch, or joint-feedback
  observation was performed for this draft.
- Outcome: no-motion handshake procedure prepared for Dion and Sherman's T1.6 session. T1.5 and
  T1.6 remain open until the physical prerequisites and session results are recorded.
- Next: complete the T1.4 physical visit, review the procedure with Dion, then validate its outputs
  during the attended T1.6 session.
- 2026-09-23: moved the draft to shared docs and required independent UDP packet observation
  alongside ROS joint feedback. No hardware run performed for this update.

## Record Template

```markdown
## [YYYY-MM-DD] T<id> | Short title

- Evidence: [`T<id>_TOPIC.md`](T<id>_TOPIC.md)
- Verified:
- Outcome:
- Next:
```
