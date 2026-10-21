# Box handoff, 2026-10-15 evening

**Status at end of session:** step 1 (T1.34) was started, not finished. The fix is applied on the
box, uncommitted, and its self-check passes. No candidate was drawn because the arm sat at all zeros
and the camera did not see the box. The `grasp` tmux session is closed and the box is free. Next
time: home the arm first (typed, Dion presses Enter), box in view, then the RViz check. Also add a
RobotModel display to `rviz_config.rviz` if Dion agrees. Details: GRASP_BRINGUP_STEPS.md, "Result,
2026-10-15: T1.34 at the box, not finished". Steps 2 to 5 below are unchanged.

For the agent running the rest of today's box steps. Dion is at the robot. Read `CLAUDE.md`, then
`docs/dion_docs/WRITING_STYLE.md`, then this file. Exact procedures for each step are in
[`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) ("Start here" and steps 7 and 8). Run one step
at a time and log only step results and findings that change the plan.

## Where things stand

- **Step 1 done.** The box (`~/rcp-Gappler`) is on `dev` at `ca0604b` (#88) and built (25 packages,
  PASS). The only local edit is `use_simple_execute: false` in `grasp/grasp_config.yaml`. Never
  commit it.
- **Gripper is closed.** Our own T1.17 run closed it on 2026-10-14 at 19:26:48 and nothing opened it
  (`~/.ros/log/grasp_state_machine_140246_1791977029906.log`). Open it before step 7d.
- **Box was free at 19:30:** no camera, ROS or bench process, GPU idle. Someone else ran nav on the
  shared account from 15:21 to 16:17 today. Check again before starting.
- **Step 3 (camera mount check): PASS.** The robot model matches the real mount within 1.5 mm.
  Recorded in GRASP_BRINGUP_STEPS Start here item 3. Nothing to do.

## Steps left, in order

1. **T1.34: check the RViz gripper drawing.** The fix is written, uncommitted, in the worktree
   `/Users/Dion/sch_repo/Gappler/.claude/worktrees/agent-afd8bf4c23a2faef5` (branch
   `t1.34-grasp-viz-drawing`). The fix covers fingers closing along y, the approach arrow along -z,
   the palm 50 mm behind the tips, the 71 mm opening and 50 mm fingers, and all candidates drawn
   with the top one highlighted.
   - Copy it to the box (Dion's yes needed): from the worktree,
     `git add -N grasp/grasp_viz/gripper_drawing.py && git diff -- grasp/ > t1.34.patch`, then on
     the box `git apply` it and run `python3 grasp/grasp_viz/gripper_drawing.py` (self-check). The
     config hunk does not touch the `use_simple_execute` line, so it applies cleanly.
     `grasp_viz` runs from source, so no rebuild.
   - Start the session: `./quickstart_terminals.sh grasp --anygrasp`. Nothing moves: the state
     machine and the grasp request are typed, not sent.
   - No pane starts RViz or grasp_viz. Add a tmux window to the `grasp` session (target
     `-t "=grasp"`) and run `python3 grasp/grasp_viz/grasp_viz.py` and
     `rviz2 -d grasp/grasp_viz/rviz_config.rviz` with `DISPLAY=:1`, so RViz shows on the box
     monitor.
   - Get a live candidate the way step 7b did (GRASP_BRINGUP_STEPS, "Result, 2026-10-14: step 7b").
     Dion checks by eye that the drawn fingers sit on the box faces, the arrow points into the
     object, and the palm is behind the tips. Pass: all three. Then T1.34 can be shipped with `/ship`
     (Dion says when).
2. **Step 7d again** with the T1.33 wrist fix (never tried on the real arm). Watch joint6: it should
   not turn about 180 deg. Commands that move the arm: type only, Dion presses Enter.
3. **T1.17: 5 attempts** on the AnyGrasp path. Record each result in
   `docs/bench-runs/2026-10-15-labbox-t1.17-anygrasp-live.txt`.
4. **T1.32 live check:** a 7.5 cm face must be dropped (too wide for the 71 mm opening). The AnyGrasp
   node's log should also show the T1.37 line saying why no grasp fits.
5. **T1.35 (step 8, random box positions).** Design to Dion first, before any run.

## Rules that bite here

- Never launch `grasp_state_machine` yourself, never publish to `/rm_driver/*_cmd`,
  `/manipulation/*` or `/goal_pose`. Type arm-moving commands into panes, never send them.
- Use `./tmux_pane_by_row_col.sh` and name panes by row and column.
- Box writes need Dion's yes each time. Auto mode blocks them otherwise: ask Dion to approve.
- Never stop a process you did not start. Never kill a tmux session without asking.
- No commit, push or PR without Dion saying so.
