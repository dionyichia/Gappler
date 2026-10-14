# Cold start

Written 2026-10-15, end of the session that fixed the wrist flip (T1.33), built the gripper fit
check (T1.32) and planned the random-pose test (T1.35). Read this first, then
[`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here".

## 1. Next action

**Discuss T1.37 with Dion, at the desk, before any code:** what happens when AnyGrasp only
suggests grasps the real gripper cannot take. Dion's question: is a retry needed, and if so, does
it retry the same grasp, or lower AnyGrasp's width cap (0.10 m, then 0.09, then 0.08) and run
again? Dion is not sure 1 cm is the right step. Facts for that talk are in section 4 and in task
T1.37 in `docs/task-tree.html`.

Before that, check the two PRs from this session (section 2) and merge them if green.

## 2. Where things stand

- **PR for T1.32** (`t1.32-grasp-fits-gripper`, worktree `../Gappler-t1.32`): the node drops a
  grasp when the object between the pads is over 0.068 m wide, or the tips go over 0.045 m past its
  near face. Limits in `grasp/grasp_config.yaml` with comments. Also the point cloud page tool.
- **PR for T1.35** (`t1.35-anygrasp-random-poses`, main checkout): docs only. Step 8 plan, T1.34,
  T1.35, T1.36, T1.37, this file. Both PRs edit `docs/task-tree.html`: the second to merge needs a
  small merge of the `T` array rows.
- **Merged this session:** #83 (fingertip depth), #84 (T1.33 wrist twin).
- **Task tree** republished from both branches onto the live page.
- **Lab box:** arm off, no processes or tmux sessions of ours. `~/rcp-Gappler` is on a local branch
  `t1.32-grasp-fits-gripper` = `dev` f165e02 plus the T1.32 diff uncommitted (an older copy, before
  the log-line fix), plus the local edit `use_simple_execute: false` (never commit it). After the
  T1.32 PR merges: `git checkout -- grasp/anygrasp_node && git checkout dev && git pull`, keeping the
  config edit, then `./build.sh`.
- Not ours: `docs/dion_docs/GAPPLER_PROJECT_SUMMARY_FOR_HIRING.md` is untracked in the main checkout
  since before this session. Worktrees `../Gappler-t1.17-depth` (merged, can be removed),
  `../Gappler-t2.2`, `../Gappler-t2.9` (other work).

## 3. Done this session

- PR #83 merged. Sim re-run after the ponytail edits: 23 of 23. Verified.
- **T1.33** (PR #84, merged): `nearer_twin()` in `anygrasp_to_grasp_frame.py` keeps the grasp twin
  whose closing axis points the gripper's way (camera -x, fixed because the camera is on the wrist).
  Verified in sim: joint6 turns 0.0 deg with it, 180.0 deg without (the 7d failure). Not yet on
  the real arm.
- **Gripper measured** (Dion): a tuning fork on the flange, 147.5 mm to the tips (matches the
  URDF), inside the U 50 mm deep, 71 mm wide, rubber pads 16 mm long from each tip. Recorded in
  the step 7 bench-run record and T1.32.
- **T1.32** built test-first: self-check PASS on the box. Replay of the recorded box: 126
  candidate sets with it, 130 without, same top score, so good grasps survive. Not verified: a
  too-big face dropped on the live camera.
- **Point cloud page tool**, `grasp/tools/wrist_camera_bag_to_point_cloud_page.py`, linked from
  `docs/ASSETS.md`. Dion's page: https://claude.ai/artifact/3Vg4rVefwx916ZegksaVZq (private).
- **Found:** the grasp_viz RViz drawing is wrong since #82 and #83 (T1.34). The replay bench's gate
  check fails on `dev`, one set at the IDLE switch, not caused by T1.32 (T1.36).

## 4. Open loops

- **T1.37** (discuss first). Facts for the talk:
  - Today, when no grasp fits, the node publishes nothing and the state machine gives up after
    3 s (`grasp_state_machine.cpp:570-578`), back to IDLE. There is no retry. `[code]`
  - AnyGrasp is stateless per frame. The next frame from the same view likely gives the same
    grasps, so "retry the same" probably repeats the failure. `[inferred]`
  - AnyGrasp reports every grasp at exactly the width cap. It does not report the opening it
    needs. Step 7a: at 0.08 the good 6 cm face kept grasps in only 58% of frames, at 0.07 none.
    So lowering the cap also loses good grasps. `[measured]`
  - Likely cause: AnyGrasp adds a margin to the width it needs, about 1.2x as in GraspNet. A
    6.1 cm face then needs about 7.3 cm. `[inferred]`
  - Options: (a) re-run AnyGrasp on the same frame with a lower cap, (b) move the camera to see
    another side, (c) tell the user. Also: how many tries, about 0.5 s per AnyGrasp run.
- **At the box, in order** (GRASP_BRINGUP_STEPS "Start here"): update the box, T1.34 (fix RViz
  drawing), camera mount ruler check, step 7d again, T1.17 (5 attempts), T1.32 live check of a
  7.5 cm face, then T1.35.
- `[unverified]` in `grasp_config.yaml`: whether 71 mm is between the pads (pads about 2 mm a
  side), and the pad width (finger_height_m 0.02).
- T1.36: the replay gate check. T1.26 item 6: the slerp final move closes at the wrong angle.
- Dion owes HF_TOKEN on the box (older loop).

## 5. Gotchas learned

- AnyGrasp's width setting is a cap on what it will suggest, not the gripper size. Keep it at
  0.10 m and rely on T1.32 for the real fit.
- The live task tree page often has rows from unmerged branches (T2.9). Republish by applying
  your edits onto a copy of the live version (Artifact read), not from your branch's file.
- The Mac has no numpy. Run Python self-checks on the box: `ssh ... 'python3 -' < file.py`.
- `bench/anygrasp_replay.sh` runs the AnyGrasp node from source, so node edits need no rebuild.
- Auto mode lets read-only and bench commands run on the box over SSH, but check the GPU and
  processes first (CLAUDE.md shared hardware rule).

## 6. Pointers

1. [`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here" and step 8
2. `docs/task-tree.html` tasks T1.32 to T1.37
3. `grasp/anygrasp_node/anygrasp_to_grasp_frame.py` (`nearer_twin`, `fits_gripper`)
4. `grasp/grasp_state_machine/src/grasp_state_machine.cpp:560-680` (candidate wait, pick, final move)
5. [`../bench-runs/2026-10-14-labbox-t1.17-anygrasp-live.txt`](../bench-runs/2026-10-14-labbox-t1.17-anygrasp-live.txt)
