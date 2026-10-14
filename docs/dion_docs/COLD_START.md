# Cold start

Written 2026-10-14 night, end of the T1.17 (step 7, AnyGrasp) session. Read this first, then
[`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here".

## 1. Next action

Finish PR #83, then design T1.33.

1. If the end-of-session edits are not committed yet (see 2), commit them on `t1.17-grasp-depth-offset`
   in worktree `../Gappler-t1.17-depth` and push.
2. Re-run the sim on the box with the arm off, because the ponytail pass edited the sim test after
   the passing run: `cd ~/rcp-Gappler && git pull && ./bench/state_machine_sim.sh candidates`
   (the box is already on that branch). Expect 23 of 23.
3. Merge #83. Then on the box: `git checkout dev && git pull && ./build.sh`, keep the local edit.
4. T1.33 design with Dion, choices listed in `GRASP_BRINGUP_STEPS.md` "Start here", step 2.

## 2. Where things stand

- **PR #83** `T1.17: AnyGrasp fingertips at grasp depth`, branch `t1.17-grasp-depth-offset`, open,
  into `dev`. Commit `f0bb852` holds the fix and the 7c/7d records. Sim PASS 23 of 23 on `f0bb852`.
- **Uncommitted on that branch at the time of writing** (worktree `../Gappler-t1.17-depth`):
  sim result in the bench-run record, cold-start "Start here", CHANNEL_CONTRACT H6, TESTBENCH_PLAN
  "Start here", task tree changelog, this file, and the ponytail edits to
  `bench/nodes/test_state_machine_sim.py` and `grasp/anygrasp_node/anygrasp_to_grasp_frame.py`.
- **PR #82** merged into `dev` (`c854d07`), with all of #79's commits. **PR #79** is still open as a
  draft but fully merged: close it.
- **Lab box:** arm off, no tmux session of ours, no processes left running. `~/rcp-Gappler` is on
  `t1.17-grasp-depth-offset` (`f0bb852`) plus the local edit `use_simple_execute: false` in
  `grasp/grasp_config.yaml` (needed for the AnyGrasp path, never commit it). Pane logs from the
  grasp in `~/dion_logs/2026-10-14_t1.17_anygrasp/`.
- **Task tree** republished as version 73 (T1.17 notes, T1.33).
- **Worktrees left:** `../Gappler-t1.17-depth` (#83), `../Gappler-t2.2` and `../Gappler-t2.9`
  (uncommitted work, not this session's).

## 3. Done this session

- 7a settings committed to #79 (0.10 m gripper model, 30 degree approach limit). Verified: live data.
- 7b: AnyGrasp axes turned into `grasp_frame`'s (`anygrasp_to_grasp_frame.py`). Verified: live TF,
  sim 22 of 22, merged in #82.
- 7c: `grasp_frame` is at the fingertips (Dion measured 147.5 mm). AnyGrasp point moved `depth`
  along the approach. Verified: live, tips a median 3.8 cm past the box face (was 0.7), sim 23 of 23.
  Not yet confirmed by a finished grasp (7d failed on the wrist flip first).
- 7d: first AnyGrasp grasp on the real arm. FAIL: the wrist turned about 180 degrees before closing
  and knocked the box off. Cause `[inferred]`, the wrist joint was not recorded. Became T1.33.
- Docs: bench-run record steps 7a to 7d, GRASP_BRINGUP_STEPS, task tree, CHANNEL_CONTRACT H6,
  TESTBENCH_PLAN. Eight merged worktrees removed.

## 4. Open loops

- **T1.33** (new): pick the 180 degree twin closest to the current wrist. Design to Dion first.
- **T1.17**: after T1.33, step 7d again, then 5 attempts through AnyGrasp compared with T1.12.
- **T1.32**: AnyGrasp no longer checks the object fits the real 71 mm gripper.
- The final move ignores whether execute succeeded (`mtc_planner.cpp:61`, T1.26 item 1).
- Ponytail finding not applied: in the sim test's candidates block (about `:332`), `eef` does its
  own TF lookup that `_at("grasp_frame")` could replace.
- Dion owes HF_TOKEN on the box (older loop).

## 5. Gotchas learned

- Auto mode blocks most `tmux send-keys` to the box. It allowed typing (not sending) when Dion asked
  in that message. When blocked, give Dion the `! ssh ...` command to paste.
- `./bench/state_machine_sim.sh` refuses while any `rm_driver` runs, so the arm session must be
  closed before a sim, even with the arm idle.
- `gh pr edit` fails on this repo (Projects classic GraphQL error). Use
  `gh api -X PATCH repos/dionyichia/Gappler/pulls/<n> -F body=@file`.
- AnyGrasp's node logs nothing per frame. Check `/grasp_candidates` with `ros2 topic hz`.
- A tmux session made by `quickstart_terminals.sh` over SSH is 80 columns wide until someone
  attaches, so pane captures look garbled. `tmux resize-window -t "=grasp" -x 200 -y 50` fixes it.

## 6. Pointers

1. [`GRASP_BRINGUP_STEPS.md`](GRASP_BRINGUP_STEPS.md) "Start here"
2. [`../bench-runs/2026-10-14-labbox-t1.17-anygrasp-live.txt`](../bench-runs/2026-10-14-labbox-t1.17-anygrasp-live.txt)
3. `grasp/anygrasp_node/anygrasp_to_grasp_frame.py`
4. `grasp/grasp_state_machine/src/grasp_state_machine.cpp:588-680` (candidate pick, stability, final move)
5. `docs/task-tree.html`, tasks T1.17 and T1.33
