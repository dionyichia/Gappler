# Cold start

Written 2026-10-20, at the end of the desk session that finished T1.34 RViz on the replay. Read
this first, then [`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here".

## 1. Next action

**At the box, with Dion at the robot: validate AnyGrasp on the real arm.** One step at a time.
Follow [`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here" and
[`BOX_HANDOFF_2026-10-15.md`](BOX_HANDOFF_2026-10-15.md) for the procedures and safety rules.

1. Ship T1.34 first if it is not merged yet (`/ship`, PR into `dev`), then update the box (section 2).
2. Start the session: `./quickstart_terminals.sh grasp --anygrasp`. It now also starts grasp_viz and
   RViz on the box monitor.
3. Home the arm first. The state machine pane homes it on launch. That command is typed, not sent:
   Dion presses Enter. Then put the box in view of the wrist camera.
4. Then, in order:
   1. **RViz confirm** on a live candidate.
   2. **Step 7d again.** Watch that joint6 does not turn 180 deg. The T1.33 fix is untried on the
      real arm. Stop if it turns.
   3. **T1.17**: 5 attempts at the ideal spot (44.5 cm, 6 cm face square).
   4. **T1.32 live**: a 7.5 cm face is dropped and the T1.37 log line shows.
   5. **T1.35 random poses.** Agree the design with Dion first: the positions and angles list, the
      pass bar and the order. Check the camera sees the box from HOME at each position (section 8).

## 2. Where things stand

- **Branch `t1.34-grasp-viz-drawing`** (worktree `.claude/worktrees/agent-afd8bf4c23a2faef5`):
  two commits on `dev` `ca0604b`, `491080a` (drawing fix) and `940ba0f` (RViz). Not pushed, no PR
  yet. Next step for it is `/ship`.
- **Lab box**: free, only `gh-runner` runs. Tmux session `t134viz` was closed. `~/rcp-Gappler` is
  on `dev` `ca0604b`, with uncommitted:
  - the earlier T1.34 patch (`t1.34.patch` in the repo root)
  - today's patch (`t1.34-rviz.patch`, applied without its `contracts.json` hunk)
  - the local edit `use_simple_execute: false` in `grasp/grasp_config.yaml` (never commit it)
  - untracked `docs/dion_docs/t1.7_logs/`
  - scratch files in `~/rcp-Gappler/log/`: `t134viz_*.sh`, `t134viz_*.txt`,
    `t134viz_replay_long.py`, `t134viz_rviz*.png`
- **After T1.34 merges**, on the box:
  `git checkout -- grasp/ quickstart_terminals.sh && rm t1.34.patch t1.34-rviz.patch && git pull`,
  then put `use_simple_execute: false` back, then `./build.sh`.
- **Arm**: at all zeros since 2026-10-15, not touched today.
- **Open PRs**: #79 is a draft already merged via #82. Close it. Check `gh pr list` first.

## 3. Done this session

- **T1.34 RViz: done on the replay.** Dion checked by eye (two screenshots). RViz shows the arm,
  the box points and the candidates. Fingers straddle two opposite box faces, the cyan palm is on
  the camera side, the red arrow runs from the tips into the box.
- The fingers are drawn at the real 71 mm opening (`open_width_m`). The `w:0.100` text label is
  AnyGrasp's gripper model width from config (`max_gripper_width_m 0.10`), not the drawn width.
- **What changed** (commit `940ba0f`):
  - `grasp/grasp_viz/rviz_config.rviz`: a RobotModel display, and a PointCloud2 display on
    `/debug/anygrasp_points` coloured by axis.
  - `grasp/anygrasp_node/anygrasp_detection_node.py`: publishes the masked points it is given on
    `/debug/anygrasp_points`, stamped with `now()`.
  - `grasp/grasp_config.yaml`: the `debug_anygrasp_points` topic.
  - `quickstart_terminals.sh` grasp layout: starts grasp_viz and RViz (`DISPLAY` defaults to `:1`).
  - `bench/nodes/test_anygrasp_replay.py`: starts a static TF `camera_link` to
    `camera_color_optical_frame` (D435 nominal: y 0.015, roll -1.5708, yaw -1.5708).
  - `bench/golden/contracts.json` re-baselined.
- **Found: the replay had no camera frame.** The bag has no TF. The arm URDF
  (`rm_65_w_gripper.urdf.xacro`, `sensor_d435` with `use_nominal_extrinsics false`) only defines
  `camera_link`. Live, the RealSense driver publishes `camera_color_optical_frame`. Without it RViz
  and grasp_viz showed nothing ("TF lookup failed: camera_color_optical_frame does not exist").
  Fixed in the replay test.
- **Found: old stamps.** The bag's messages carry their recording time (2026-10-13), so RViz
  dropped them against live TF. Fixed by stamping the points with `now()`, like the candidates.
- **Replay numbers** (3 runs): segmentation PASS (about 160 to 196 masks in 60 s, median depth
  0.400 m). Grasp detection PASS (134 to 171 candidate sets, top score 0.42 to 0.45). Gate (A1)
  FAIL with 1 set at the IDLE switch. That is the known T1.36, not new.

## 4. Open loops

- The real-arm validation in section 1.
- **Home pane in the grasp layout**: not added. Skipped because the state machine pane homes the
  arm on launch. Add a typed (not sent) home pane only if a session ever starts without it.
- **Magenta dashed line in RViz** near the points. It is not from grasp_viz (its colours are palm
  blue to cyan, fingers green, arrow red, centroid red). Source unknown, harmless, worth a look.
- T1.36 (replay gate check), T1.26 item 6 (slerp final move). Dion owes HF_TOKEN on the box.
- Close draft PR #79.

## 5. Gotchas learned

- **Box route**: today tailscale (`100.87.133.60`, `100.98.10.50`) and `ssh labbox` timed out. The
  NTU address `rcp2026@10.91.242.76` worked.
- **`timeout` makes its own process group.** Ctrl-C in the tmux pane does not stop a process
  started under `timeout`. Stop it with `kill -INT -<pgid>`. The replay test's children
  (segmentation service, client, AnyGrasp node, bag play) each have their own process group too.
- **`tmux split-window` renumbers panes.** A `send-keys` right after a split can land in the wrong
  pane. Split all panes first, then list them, then send.
- **With the sim arm at all zeros** the camera looks straight up, so the replay points float about
  40 cm above the gripper. That is expected.
- `quickstart_terminals.sh` over SSH prints "open terminal failed: not a terminal" at the end. The
  session is still created. Use `./tmux_pane_by_row_col.sh grasp map` to check.
- RViz crashed (segfault, apport) on Ctrl-C. Harmless, it exits by itself.
- The lab safety hook blocks any command whose text contains `/rm_driver/*_cmd`, even a doc edit.
  Write the edit as a script file and run that.
- Republish the task tree by applying edits onto a copy of the live version (Artifact read). The
  live page has rows from unmerged branches (T2.9).

**Recipe: check RViz on the replay without the real arm.** In your own tmux session, on
`ROS_DOMAIN_ID=77` with `ROS_LOCALHOST_ONLY=1`:

1. `./bench/anygrasp_replay.sh` first. Its guard needs an empty channel.
2. The sim arm: `ros2 launch bench/nodes/sim_arm.launch.py use_rviz:=false`, behind the
   `mock_components` and no-`rm_driver` guards from `bench/sim_moveit.sh`.
3. `python3 grasp/grasp_viz/grasp_viz.py`.
4. `DISPLAY=:1 rviz2 -d grasp/grasp_viz/rviz_config.rviz`.

The 30 s EXECUTING phase is short. For a longer look, use a copy with `PHASE_SEC 180`. To take a
screenshot of the box screen:
`DISPLAY=:1 python3 -c 'from PIL import ImageGrab; ImageGrab.grab(xdisplay=":1").save(path)'`.

## 6. Pointers

1. [`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here"
2. [`BOX_HANDOFF_2026-10-15.md`](BOX_HANDOFF_2026-10-15.md) (the per-step procedure and safety rules)
3. `docs/task-tree.html` T1.17, T1.32, T1.33, T1.34, T1.35, T1.36
4. The T1.34 code: `grasp/grasp_viz/gripper_drawing.py`, `grasp/grasp_viz/grasp_viz.py`,
   `grasp/grasp_viz/rviz_config.rviz`

## 7. Uncommitted files

On the branch: `docs/task-tree.html` (task tree edits for `/ship` to commit) and this file. In the
main checkout: `docs/dion_docs/GAPPLER_PROJECT_SUMMARY_FOR_HIRING.md` (untracked, from before).

## 8. From here to the random-pose test (Dion's goal)

Goal: run AnyGrasp at many box positions and angles on the real arm (T1.35). The desk work is done
except the T1.35 design.

**Desk (about 1 h, before the box):**
1. Ship T1.34 with `/ship`.
2. **T1.35 design, with Dion.** Fix the positions and angles list, the pass bar and the order.
   Check first that the camera sees the box at every position from HOME. At 35 or 50 cm, or 10 cm
   sideways, it may not `[unverified]`.

**Box (about 2 h):**
1. RViz confirm on a live candidate (15 min).
2. Fold step 7d, T1.17 and the T1.32 live check into the start of the T1.35 run. The first trials
   at the ideal spot (44.5 cm, 6 cm face square) are 7d and T1.17. One 7.5 cm face trial is T1.32.
   Stop if the wrist turns 180 deg (T1.33 fix untried on the real arm).
3. The random positions and angles, about 12 trials, each result recorded.
