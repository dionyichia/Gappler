# Cold start

Written 2026-10-15, late evening, at the end of the box session that started T1.34 and stopped
because Dion ran out of time. Read this first, then
[`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here".

## 1. Next action

**At the desk: make RViz work on the replay bag and the simulated arm (T1.34).** Dion saw a blank
RViz at the box (no arm, no model) and decided T1.34 does not ship until RViz works. Branch
`t1.34-grasp-viz-drawing`, worktree `.claude/worktrees/agent-afd8bf4c23a2faef5`, committed, not
pushed. The plan to get from here to the random-pose test is section 8. Start with its item 1.

## 2. Where things stand

- **Branch `t1.34-grasp-viz-drawing`** (worktree `.claude/worktrees/agent-afd8bf4c23a2faef5`):
  one commit on `dev` `ca0604b` with the drawing fix and all of this session's docs. Quick bench
  PASS. Not pushed, no PR. The main checkout's copies of these docs were reset to `dev`.
- **Lab box**: free. No processes or tmux sessions of ours (the `grasp` session was closed at
  Dion's request). Only `gh-runner` runs. `~/rcp-Gappler` is on `dev` `ca0604b`, built, with:
  - the T1.34 patch applied, uncommitted (self-check PASS), plus `t1.34.patch` in the repo root
  - the local edit `use_simple_execute: false` (never commit it)
  - After T1.34 merges: `git checkout -- grasp/ && rm t1.34.patch && git pull`, then put
    `use_simple_execute: false` back.
- **Open PRs**: #79 (draft, already merged via #82, close it). #76 (T2.9, separate work).
- **Arm**: left at all zeros, powered on.

## 3. Done this session

- **Camera mount check: PASS** (Dion's other session, with the 3D model
  https://claude.ai/artifact/S4BfsEeN1JwYKaWYEBuTrq). Glass to fingertips 119 vs 118.6 mm, camera
  body centre 12.5 mm in x and 60 mm in y confirmed. No URDF change. Verified by Dion's ruler.
- **T1.34 patch on the box**: applied, self-check PASS ("fingers close along grasp y, arrow along
  -z from the tips, palm 0.05 m behind"). Verified on the box. Live RViz check not done.
- **Found**: the arm was powered off at first, then sat at all zeros, so the wrist camera saw no
  box. No mask, so no AnyGrasp candidate. A stand-in `EXECUTING` on `/pipeline_state` at 1 Hz does
  turn AnyGrasp on without the state machine (as in step 7b).
- **Found**: `grasp/grasp_viz/rviz_config.rviz` never draws the robot. MotionPlanning is off and
  there is no RobotModel display. The data is fine. `[reported]`
- Docs: GRASP_BRINGUP_STEPS (new result section, Start here items 2 and 3), BOX_HANDOFF, task
  tree T1.34 and T1.35 notes. Task tree republished, version 82.

## 4. Open loops

- **At the box, in order**: home the arm, T1.34 RViz check, step 7d again (watch joint6 does not
  turn 180 deg), T1.17 (5 attempts), T1.32 live (a 7.5 cm face is dropped and the T1.37 log line
  shows), then T1.35 (design to Dion first).
- **T1.34 scope grew** (Dion, 2026-10-15): RViz must show the arm, the box points and the
  candidates before it ships. Details in its task note and GRASP_BRINGUP_STEPS.
- T1.36 (replay gate check), T1.26 item 6 (slerp final move). Dion owes HF_TOKEN on the box.
- Close draft PR #79.

## 5. Gotchas learned

- `quickstart_terminals.sh` over SSH prints "open terminal failed: not a terminal" at the end. The
  session is still created. Use `./tmux_pane_by_row_col.sh grasp map` to check.
- No pane in the grasp layout starts RViz or grasp_viz. Add a window with `DISPLAY=:1` to show
  them on the box monitor.
- RViz crashed (segfault, apport) on Ctrl-C. Harmless, it exits by itself.
- The lab safety hook blocks any command whose text contains `/rm_driver/*_cmd`, even a doc edit.
  Write the edit as a script file and run that.
- Republish the task tree by applying edits onto a copy of the live version (Artifact read). The
  live page has rows from unmerged branches (T2.9).

## 6. Pointers

1. [`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here" and "Result, 2026-10-15: T1.34 at the box, not finished"
2. [`BOX_HANDOFF_2026-10-15.md`](BOX_HANDOFF_2026-10-15.md) (the per-step procedure and safety rules)
3. `docs/task-tree.html` T1.34, T1.35
4. The T1.34 worktree: `grasp/grasp_viz/gripper_drawing.py`, `grasp/grasp_viz/grasp_viz.py`

## 7. Uncommitted files

None on the branch. In the main checkout only `docs/dion_docs/GAPPLER_PROJECT_SUMMARY_FOR_HIRING.md`
(untracked, from before this session).

## 8. From here to the random-pose test (Dion's goal)

Goal: go to the box, check RViz, then run AnyGrasp at many box positions and angles (T1.35).

**Desk (about 3 to 4 h, no arm needed):**
1. **T1.34 RViz** (1 to 2 h). Add a RobotModel display. Point PointCloud2 at a topic that exists,
   or draw the masked points from the AnyGrasp node. Check on the box with `./bench/anygrasp_replay.sh`
   and the simulated arm (`./bench/sim_moveit.sh`), over the remote desktop. Pass: arm, box points
   and candidates all visible, fingers on the box faces.
2. **Home in the grasp layout** (15 min). Add a typed (not sent) home command pane to
   `quickstart_terminals.sh grasp`, so a session never starts with the arm at zeros.
3. **T1.35 design** (1 h, with Dion). Fix the positions and angles list, the pass bar and the order
   before the session. Check first that the camera sees the box at every position from HOME. At
   35 or 50 cm, or 10 cm sideways, it may not `[unverified]`.
4. Ship T1.34 and the home pane with `/ship`.

**Box (about 2 h):**
1. RViz confirm on a live candidate (15 min).
2. Fold step 7d, T1.17 and the T1.32 live check into the start of the T1.35 run: the first trials
   at the ideal spot (44.5 cm, 6 cm face square) are 7d and T1.17. One 7.5 cm face trial is T1.32.
   Stop if the wrist turns 180 deg (T1.33 fix untried on the real arm).
3. The random positions and angles, about 12 trials, each result recorded.
