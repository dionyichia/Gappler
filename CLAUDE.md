# CLAUDE.md

Gappler: Aria smart glasses (voice + gaze) → SAM 3 segmentation → AnyGrasp → RealMan RM65 arm on a
LiDAR-navigating mobile base, glued by ROS 2 Humble. Being integrated with the HiCo-Nav paper and
refactored toward one-folder-per-node modular code.

## Read first: global docs vs. per-person docs

- **Global docs live directly in `docs/`** and describe state shared by everyone: `ORIENTATION`,
  `ARCHITECTURE`, `READING_GUIDE`, `CODE_AUDIT`, `ASSETS`, `CHANNEL_CONTRACT`, `MEMORY_GRAPH_DESIGN`,
  `NEXT_STEPS`, `PROJECT_PLAN`, `TESTBENCH_PLAN`, `hico-nav/`, `bench-runs/`, and the three published
  HTML pages (`task-tree.html`, `wiring-map.html`, `testbench-map.html`).
- **Personal docs live in `docs/<firstname>_docs/`**: session notes, handoffs and evidence not yet
  folded into the global docs. Write only in your own folder (ask the user's name if unknown). Never
  edit another person's folder: write the correction in yours and tell them.
- **Everyone starts at [`docs/START_HERE.md`](docs/START_HERE.md), then
  [`docs/ORIENTATION.md`](docs/ORIENTATION.md).**
- **Keep the global docs current, in the same session.** If your work changes what a global doc says
  (a task is done, a finding is confirmed, a decision is settled), update that doc directly,
  following its citation, tag and changelog conventions.
- **Tasks live in one place: the `T` array in `docs/task-tree.html`.** Add new tasks there. Other
  docs hold status and evidence and point at task IDs, never their own to-do lists. A task's optional
  9th field holds long notes. When a task is done, start its description with `"DONE <date>. ..."`:
  the page derives the done mark from that prefix.
- **Republish every HTML page you edit** with the Claude Code `Artifact` tool so the live page matches
  the file. If you can't publish, say "republish owed" in that doc's changelog.
- The root `README.md` is stale (a different upstream project). Ignore it.

## Portability tiebreaker

The lab box is confirmed until 2026-11-16 only. When a design choice is otherwise a wash, prefer the
portable one: config over hardcoded machine paths, paths derived from the repo root, environment
variables with defaults. Only when it costs little extra.

## Safety: this code moves a real robot arm

Rule history and the incidents behind these rules: TESTBENCH_PLAN §3.

- **Never launch** `grasp_state_machine`, `launchers/start_camera_arm_grasp.py`,
  `launchers/grasp_orchestrator.py` or root `main.py`. The state machine homes the arm within seconds,
  unprompted, and has never run on the real arm. Exception: `bench/state_machine_sim.sh` runs it on
  the *simulated* arm, behind its guards.
- **Never publish** to `/rm_driver/*_cmd`, `/goal_pose`, `/cmd_vel`, `/manipulation/*` or
  `/object_centroid_2d` on the real ROS domain. Isolate tests with a unique, empty `ROS_DOMAIN_ID`
  plus `ROS_LOCALHOST_ONLY=1`. Localhost-only does not separate you from other users on the box. The
  domain id does.
- **The box's hardware is shared: check before you use it.** `rcp2026` is used by three people, plus
  `iot22`. Before using a camera, the GPU, the arm, the glasses or the LiDAR, run
  `ps -eo pid,user,etime,args | grep -iE "realsense|rs_launch|ros2 launch|bench/run.sh|Runner.Worker"`,
  `nvidia-smi` and `fuser /dev/video*`. If anyone is using it, tell the user who and what, then wait.
- **Never stop a process you did not start.** No `pkill` or `killall`. Start yours with `setsid` and
  stop them only by process group: `kill -INT -<pgid>`.
- **Never close a tmux session without asking first**, even one you think you made. Always target the
  exact name, `-t "=name"`: a plain `-t name` matches by prefix.
- `.claude/hooks/lab_safety_guard.py` blocks or asks before the commands above. It is a backstop, not
  a reason to skip the checks.

## Git workflow

- **Fixes land through a PR into `dev`** (the default branch), where CI runs the bench. `dev` is
  promoted to `main` by PR.
- **Branch names start with the task ID**, lower case: `t1.8-anygrasp-gate`. The PR title starts
  with the same ID: `T1.8: ...`. If no task covers the work, add one to the task tree first.
- Bring a branch up to date by merging `origin/dev` into it. Never rebase and force-push a shared
  branch.
- `/ship` (`.claude/skills/ship/`) runs the commit, PR, CI and merge steps for one task.

## The lab machine

- **Connect over tailscale:** `ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60`. The box has a
  second tailscale node, `rcp2026@100.98.10.50`. Use whichever `tailscale status` shows active. On the
  NTU network, `rcp2026@10.91.242.76` also works.
- **All work happens in `~/rcp-Gappler`.** `~/rcp-desktop`, `~/rcp-github` and `~/rcp-old-ros-wkspace`
  are old reference code: never modify them or their `install/` overlays. Don't touch `/home/iot22`,
  never set `PYTHONNOUSERSITE=1`, never `pip install --user`.
- MoveIt with `mock_components` (simulated arm) is allowed. Anything with `rm_driver` needs a person
  at the robot.
- **Start robot sessions with `./quickstart_terminals.sh <layout>`** (`gripper`, `arm`, `grasp`,
  `nav`, `aria`, `full`). It opens a tmux session named after the layout, one pane per process, on
  domain 91, localhost only. Drivers, the stop, cameras and monitors start on their own. Commands that
  move the arm or base are typed but not sent. `--print` lists the panes, `--dry` starts nothing.
  When giving someone commands for a robot session, point at the script and only spell out what it
  does not cover.
- **During a robot session, run commands in its tmux panes over ssh**, so the user sees them, using
  `./tmux_pane_by_row_col.sh`. Quick read-only checks (`ps`, `nvidia-smi`, reading a log) can run over
  plain ssh.
  - Commands that don't move anything: `run`.
  - Commands that move the arm, gripper or base: `type` only (no Enter), then tell the user which
    pane to press Enter in.
  - Name panes by row and column ("row 1, col 2: the driver"), never by pane number. `map` prints
    the grid.
- **The GitHub Actions runner** lives in `~/actions-runner` (tmux session `gh-runner`). Its checkout
  `~/actions-runner/_work/Gappler/Gappler` belongs to CI: don't work in it. Only one bench run at a
  time on the box: check `pgrep -af "Runner.Worker|bench/run.sh"` first.
- Sourcing a subsystem env file can build its venv. Never run panes from a scratch clone without
  linking its venvs first (TESTBENCH_PLAN §3).
- `/home` is nearly full. Check `df -h ~` before large builds or downloads.

## The bench

```bash
./bench/run.sh                         # L0 static → L1 contracts → L2 preflight → L3 build → L4 sim
                                       # (L3-L4 only where ROS 2 Humble exists, else SKIPPED)
./bench/run.sh quick                   # L0-L2 only
./bench/run.sh robot                   # L5 only: is the robot connected (gates L6)
./bench/run.sh report                  # contract inventory + orphan analysis
python3 bench/contracts.py snapshot    # re-baseline after a deliberate contract change
# lab box only (ROS + the built overlay):
./build.sh [nav]                       # L3: colcon build into this checkout
./bench/sim_moveit.sh                  # L4: MoveIt on a simulated arm
./bench/estop_delivery.sh              # L4: does estop.py's stop message leave
./bench/state_machine_sim.sh           # L4: grasp state machine on the simulated arm
./bench/state_machine_sim.sh candidates # L4: same, the AnyGrasp path (use_simple_execute false)
./bench/nav_nodes.sh                   # L4: the five nav nodes vs a mock Nav2 (nothing drives)
./bench/anygrasp_env.sh [PYTHON]       # can this env run AnyGrasp (imports + SDK demo)
./bench/memory_graph_tests.sh [PYTHON] # all memory graph tests, with the real open_clip model (needs .venv, no ROS)
```

Levels L0-L6 are defined in `bench/README.md`. L0-L2 are stdlib-only and need no ROS: run them before
and after any refactor. L6 is the real robot and is never automated. Our code is everything except
what sits under a `vendor/` folder (`is_owned` in `bench/_common.py`). Put third-party code under its
subsystem's `vendor/`. Results go in `docs/bench-runs/`.

## Conventions

- Tag claims in docs: `[code]` read from source · `[reported]` from the 2026-08-25 hardware session ·
  `[inferred]` reasoning · `[unverified]` static finding not yet confirmed at the machine. Retag when
  you verify. Delete what turns out wrong.
- Append to each doc's changelog on substantive edits. Cite `file.py:123`.
- Name things descriptively by subsystem (`arm_base_link`, not `base_link`): ORIENTATION §0b.
- Skipped checks are reported as skipped, never as passing.
- **Writing style. If you are Dion's agent, read
  [`docs/dion_docs/WRITING_STYLE.md`](docs/dion_docs/WRITING_STYLE.md) before doing anything else,
  and follow it everywhere.** Short version: main point first, plain language before jargon, no em
  dashes, no semicolons, no emojis, no hype. Readers include mechanical engineering students new to
  code.
- On macOS, `grep` is ugrep: multi-path `grep -r --include` can silently return nothing. Use
  `find ... | xargs grep`.
