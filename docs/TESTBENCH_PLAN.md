# TESTBENCH PLAN — handoff for the next session

> **Paths moved 2026-09-21 (reorg).** Many cites below use the old layout (`src/`, `ros2_robot_ws/`,
> `Navigation_Module/`). Look up the new path in [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.15,
> "Where things moved". Line numbers inside moved files did not change with the move.


**Purpose:** everything a fresh session needs to continue building the test bench, cold, without
re-deriving anything. Written 2026-09-11 at the end of the session that built `bench/` tiers 0–1 and
the preflight tier, and wrote [`CODE_AUDIT.md`](CODE_AUDIT.md).

**Where this sits:** [`START_HERE.md`](START_HERE.md) indexes all docs. [`ORIENTATION.md`](ORIENTATION.md)
is what the system *is*. [`NEXT_STEPS.md`](NEXT_STEPS.md) is the project-wide work register — its §2.6,
§2.6b and §2.7 point here. **This file is the detailed plan for the bench specifically.**

**Status tags** as elsewhere: `[code]` read from source · `[reported]` from the 2026-08-25 hardware
session · `[inferred]` reasoning · `[unverified]` found by static analysis, not confirmed at the machine.

---

## ▶ Start here — next session (updated 2026-09-22)

### Next: finish T0.11, the no-skips `full` job (written 2026-09-22 for a cold start)

**Branch:** `t0.11-ci-full-job`, cut from `dev` at `0f87c89` (the refactor, PR #5). Open the PR into `dev`.

**Goal of this branch:** a `full` CI job that runs L0-L4 on the lab box with **no level skipped**,
and is a **required check on PRs from `dev` into `main`**. The rest of T0.11 is decided:

- **Fork-PR guard: waived for now** (Dion, 2026-09-22). The repo is public and stays so until
  GitHub Pro. Revisit when it goes private.
- **Per-subsystem suites: paused until a need arises** (Dion, 2026-09-22). L0-L2 take about 30 s,
  so splitting them by subsystem saves nothing. Every lab box run is the full L0-L4.

**What already exists** `[observed]`:

| Piece | Where | State |
|---|---|---|
| `bench` job | `.github/workflows/bench.yml` | L0-L2 on GitHub's machines, every PR and push to `dev` or `main`. Required on both |
| `full` job (2026-09-22, this branch) | `.github/workflows/bench.yml`, same file | `./bench/run.sh --no-skips` on the lab box. PRs into `main`, Mon and Wed 23:00 on `dev`, and the "Run workflow" button. Replaces `bench-nightly.yml`. Not yet run `[unverified]` |
| ~~`bench-nightly` job~~ | ~~`.github/workflows/bench-nightly.yml`~~, merged into `full` on this branch | Full bench on `dev`, Mon and Wed 23:00 Singapore time, plus the "Run workflow" button. `runs-on: [self-hosted, lab-box]`, `concurrency: lab-box`, `clean: false`. Never runs on a PR |
| The runner | `~/actions-runner` on the box, user `rcp2026`, name `iot22-Computer` | Runs in tmux session `gh-runner` (`tmux attach -t gh-runner`). **A reboot stops it**, restart with `cd ~/actions-runner && ./run.sh` in that tmux session |
| The runner's copy | `~/actions-runner/_work/Gappler/Gappler` | Cleaned 2026-09-22 and on `dev` `0f87c89`. SAM3 weights and AnyGrasp checkpoints are **symlinks** to the files in `~/rcp-Gappler`. L2 there: 17 pass, 0 fail |

**The work, in order:**

1. ✅ **Done 2026-09-22. `--no-skips` in `bench/run.sh`.** Any SKIPPED level from L0 to L4 makes the run fail. L5-L6
   (robot and hardware) stay allowed to skip, they never gate a merge.
2. ✅ **Done 2026-09-22. A `full` job** for `pull_request` into `main`: `runs-on: [self-hosted, lab-box]`,
   `concurrency: lab-box`, `timeout-minutes: 120`, `clean: false`, running `./bench/run.sh --no-skips`.
   Dion chose one file: `full` is a second job in `bench.yml` and also took over the nightly schedule
   and the button, so `bench-nightly.yml` is gone. Each job's `if:` line picks its events.
   Tested on the Mac only: `--no-skips` exits 1 when L3-L4 skip, the plain run still exits 0.
3. **Next: run `full` once.** After this branch merges into `dev`, press "Run workflow" on the
   Actions tab (branch `dev`), or wait for the next night. The button only appears once the workflow
   is on `dev`. Then **make `full` required** in `main`'s branch protection (`gh api` on
   `repos/dionyichia/Gappler/branches/main/protection`). Do this only after the job has passed once,
   or every `dev` into `main` PR is blocked.
4. **Test it** with a real `dev` into `main` PR. Record the run in `bench-runs/`.

**Gotchas for whoever picks this up:**

- **One bench at a time on the box.** Two full runs at once share the GPU, the CPU (throttled) and the
  ROS channel, and the second one's L4 refuses. Before starting anything by hand, check
  `pgrep -af "Runner.Worker|bench/run.sh"`.
- **`clean: false` keeps ignored files between runs.** After any change that moves folders, clear the
  runner copy's `build/`, `install/`, `build_nav/`, `install_nav/` and any leftover generated files
  (the Livox `package.xml`), or the nav build finds two packages with one name. Done once already, for
  the refactor.
- **Timing:** a clean build plus L4 is about 40 minutes, an incremental one about 20.
- **The first nightly since the refactor has not run yet.** Its result is the first proof that the
  runner copy works in the new layout. Check it under the Actions tab.

---

**T0.0 box checks: run 2026-09-21, two of three done.** Evidence:
[`bench-runs/2026-09-21-labbox-t0.0-box-checks.txt`](bench-runs/2026-09-21-labbox-t0.0-box-checks.txt).
Both held files are now on `main`, so T0.0 is closed.

1. ✅ **The Aria calibration file parses** `[observed]`. All five cameras load, the RGB one as
   Fisheye624, 2880x2880.
2. **Still owed: are these the same glasses?** Skipped 2026-09-21, the glasses were not plugged in.
   With them on USB, read the serial from the `aria` CLI and compare it with `1WM10350101291`, the
   serial in the file. If it differs, the file is for another pair and only good as a parsing fixture.
   Note the `aria` CLI is not on `rcp2026`'s PATH. Source `global_env.sh` (was `env.sh`, renamed 2026-09-22) or `aria/aria_env.sh` first so the project `.venv` is active.
3. ✅ **`env.sh` works in `~/rcp-Gappler`** `[observed]`. 5 `moveit_task_constructor` packages,
   12 `rm_` packages, the `.venv` python. It must be sourced from the repo root (`source
   ~/rcp-Gappler/env.sh`). A copy elsewhere now refuses with exit 1.

**Work items live in the task tree, not here** (since 2026-09-21). This page records what the bench
is, what it found and the evidence. Every open item it found is a task in
[`next-steps-map.html`](next-steps-map.html) and [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §6, so it can be
seen, owned and ticked off in one place. Bench and CI tasks: **T0.11** (CI on the lab box, per-subsystem
suites) and **T0.12** (AnyGrasp replay, was W6). Ownership is one rule, `is_owned` in `bench/_common.py` (since 2026-09-22): our code is everything except what sits under a folder named `vendor/`. Put third-party code under its subsystem's `vendor/`, and nothing in the bench needs editing when code moves. The refactor (target layout, config levels, env files) is **done and verified on the box, 2026-09-22**:
[`NEXT_STEPS.md`](NEXT_STEPS.md) §2.15, which also has the old-to-new path table. Build with `./build.sh`, set up a
shell with `source global_env.sh` (or one `<subsystem>/<subsystem>_env.sh`).

CI and branches, set up 2026-09-21 `[observed]`:

- **`dev` is the default branch.** Branch from `dev` and open PRs into `dev`. `main` holds the last
  state promoted from `dev`, by a merge commit, never a squash.
- **`bench` runs on every PR into, and push to, `main` or `dev`.** It runs L0-L2 on GitHub's
  machines. L3-L4 report SKIPPED there.
- **Both branches are protected.** A PR is required and `bench` must pass. No approvals are needed.
  Admins can still push directly (`enforce_admins` is off).
- **The box pulls over SSH with a deploy key** (`~/.ssh/gappler_deploy`, host alias
  `github-gappler` in `~/.ssh/config`), so it keeps working if the repo goes private.
- **The repo stays public for now.** Making it private waits on GitHub Pro (student pack), because a
  free account gets no branch protection on private repos.

**One paragraph (updated 2026-09-14):** the bench runs on the lab box in `~/rcp-Gappler`, and
**tiers 0 through 3 are now complete**. Done there: tiers 0–1, preflight, Tier 2 for **both**
workspaces (arm 22/22, nav 10/10), and every Tier 3 script on a private ROS channel — MoveIt on a
simulated arm, the e-stop, the whole grasp state machine on the simulated arm, the AnyGrasp env
probe, and the five navigation nodes against a mock Nav2. Nothing physical has moved; Aria, arm and
base are unplugged, so their checks fail or skip **as expected**. The 2026-09-14 session ran the two
pieces that were written but never run (W4b, W7) and both passed first time. **What is left is not
more test-writing:** W6 is now task T0.12, W8 is L6 (a person at the robot), and every finding below
is a task in the task tree.
Dion's standing instruction still holds: `~/rcp-Gappler` only, no real-world movement, and
**fixes on branches for review, through a PR into `dev`** (2026-09-19, replacing "no fixes
 without asking").

**Status at a glance:**

| Item | State | Evidence |
|---|---|---|
| W1 project env (uv) | ✅ torch sees the GPU; setuptools pin merged | [`bench-runs/…-w1-venv.txt`](bench-runs/2026-09-11-labbox-w1-venv.txt) |
| W2 state machine, simulated arm | ✅ full cycle; **C7 reproduced**, B4 observed | [`…-w2-state-machine.txt`](bench-runs/2026-09-11-labbox-w2-state-machine.txt) |
| W3 e-stop delivery | ✅ **B2a found** (Ctrl+C ignored). 2026-09-21: B2 loss reproduced, B2c found, all three **fixed** (T1.2), every stop path now a required check | [`…-w3-estop.txt`](bench-runs/2026-09-11-labbox-w3-estop.txt) |
| W4a nav code vs `iot22` | ✅ repo newer; `robot_navigation`, `xpkg_demo` only outside git | [`…-w4a-nav-diff.txt`](bench-runs/2026-09-11-labbox-w4a-nav-diff.txt) |
| W4b nav build | ✅ **PASS** 10/10 packages, 2 min 34 s. No blocker: Livox-SDK2 already installed | [`…-w4b-nav-build.txt`](bench-runs/2026-09-14-labbox-w4b-nav-build.txt) |
| W5 AnyGrasp env | ✅ done 2026-09-21: `grasp/anygrasp_venv/build_anygrasp_venv.sh` (was `envs/anygrasp/build.sh`) rebuilds it from nothing, demo passes | [`…-w5-anygrasp-env.txt`](bench-runs/2026-09-11-labbox-w5-anygrasp-env.txt) |
| W6 AnyGrasp gate + replay | **now task T0.12.** Blocked on a replug. Dion approved starting the camera 2026-09-14; the D435i was already faulty (colour stream dead) and a hardware reset took it off the USB bus. No frames recorded | [`…-w6-camera-attempt.txt`](bench-runs/2026-09-14-labbox-w6-camera-attempt.txt) |
| W7 nav node tests | ✅ **PASS first run**, no fix needed: 6 controls pass, 4 xfail reproduced (F1 ×2, F2, E1), 0 skipped. **E1, F1, F2 now `[observed]`**; new finding F4 | [`…-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt) |
| W8 Tier 4 | now L6 (hardware), gated by the L5 robot check. The runs are tasks T1.6 onward | — |
| Preflight glasses check | ✅ **fix confirmed on the box 2026-09-14**: `aria-sdk` now FAILs "aria CLI works, but no glasses are connected over USB". It used to wrongly PASS | `bench/preflight.py` |
| Preflight camera check | ✅ **rewritten 2026-09-14 (bench bug S4)**: `realsense-usb` used to pass on the USB id alone — and on any "Intel" line, including the Bluetooth adapter. Now strict on `8086:0b3a`, plus a new `realsense-stream` check that actually grabs a frame | `bench/preflight.py` |

**Findings and the task that fixes each** (the tasks hold the work, CODE_AUDIT holds the detail):

| Finding | Task |
|---|---|
| `estop.py`: Ctrl+C ignored, stop lost on SIGINT, keys dropped (B2a, B2, B2c) | T1.2, **fixed 2026-09-21** |
| State machine homes to an unvalidated pose, warning quotes the old one (B4) | T1.3 |
| State machine queue grows without limit after a grasp (C7) | T1.9 |
| Approach node gets no goal after any navigation failure (F1), nav nodes crash on Ctrl+C (F4) | T3.8 |
| `goto_glasses` reads a robot-relative pose as a map coordinate (E1), failed return leg never retried (F2) | stretch S5 (return leg is out of scope) |
| `main.py` launches AnyGrasp through `conda run` | T1.10 |
| ~~Nav packages and Livox manifest not in the repo~~, ~~hardcoded `/home/iot22` paths~~ | done: T0.4, T0.3 |

**The two pages (keep them current):** both are written for readers new to code, including mechanical
engineering students. Republish after each change, to the same link.

| Page | Source | Link |
|---|---|---|
| Test bench: what each check covers, what it found, the simulated arm explained | `testbench-map.html` | <https://claude.ai/code/artifact/cb1f53f5-3154-4271-be1e-4daf46fca7fe> |
| Wiring map, with the tab "One grasp, start to finish" (17 steps: program, method, message, status today) | `docs/wiring-map.html` | <https://claude.ai/code/artifact/837635d4-0107-4248-83cc-ce1d7536d0ea> |

**Box facts a session should know:** `/home` is **96 % full (14 GB free)** — the W5 scratch env
`log/w5/` (~2 GB) and `~/rcp-old-ros-wkspace` (4.5 GB) are today's additions; ask before deleting
either. The CPU is throttled (builds take ~4× longer). **Other people log in as `rcp2026` too** (a
tailscale session from `sams-sidekick` on 2026-09-11) — every Tier 3 script refuses to start unless its
ROS channel is empty, so never skip that guard.

**Decisions already made (don't re-ask):**

| Topic | Decision |
|---|---|
| Where | `~/rcp-Gappler` only. `~/rcp-desktop`, `~/rcp-github` are old code — read-only reference |
| `/home/iot22` | Readable by `rcp2026` (ACL Dion set). Read only; never write |
| `iot22`'s nav workspace | Copied whole to **`~/rcp-old-ros-wkspace`** on 2026-09-11 (4.5 GB, `rsync -a` of `~iot22/Ros2Workspaces`). Reference only — its `install/` points at `/home/iot22` paths. What to keep: NEXT_STEPS §2.9 |
| Fixes | **None yet** (Dion, 2026-09-11): survey, record findings, build tests. Fixes come later, on branches |
| W2 | **Allowed** (Dion, 2026-09-11) — simulated arm only, via `bench/state_machine_sim.sh`; `CLAUDE.md` records the exception |
| `.venv` | **Rebuilt ✅** with `uv sync --locked` (W1). Never copy one; uv is at `~/.local/bin/uv` (not on the non-interactive PATH) |
| Model files | Copied into `~/rcp-Gappler` ✅. Long-term: one `assets/models/` folder (NEXT_STEPS §2.8) — later, with the reorg |
| AnyGrasp env | **One env confirmed** (W5 survey): the project env + MinkowskiEngine etc. runs AnyGrasp. `iot22`'s conda is not used. Scripted 2026-09-21: `grasp/anygrasp_venv/build_anygrasp_venv.sh` (was `envs/anygrasp/build.sh` until 2026-09-22). `grasp_env.sh` builds it the first time it is missing |
| Simulation | MoveIt with `mock_components` is allowed. `rm_driver` never. Private ROS channel always |
| Robot config | Not edited by the bench. `bench/nodes/sim_arm.*` carries the simulated model (ORIENTATION §8.16). The Livox manifest moved out of the bench into `nav/vendor/livox_ros_driver2/package_ROS2.xml` (T0.4, 2026-09-21) |
| Writing | Dion's docs and pages: plain language, main point first, jargon only when needed and explained. Readers include mechanical engineering students. No em dashes, semicolons or emojis in pages |
| Baselines | **Contracts snapshot re-taken 2026-09-21** at `1461e72` (Dion), so the refactor starts from a clean L1 with 0 informational lines. Re-take it only after a deliberate contract change, never to make a refactor pass. Still no static baseline (S1): the static check must stay at 0 findings |

**Every session on the box:** connect over **tailscale**, which works from anywhere:
`ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60` (`HostKeyAlias` reuses the host key already
verified for the campus address — same machine, checked 2026-09-11). Is it up? `tailscale ping
100.87.133.60` (plain `ping` to the campus IP fails off-campus). The campus address
`ssh rcp2026@10.91.242.76` works only on the NTU network. Then `cd ~/rcp-Gappler && git pull` → read §3
(safety). Edit on the Mac, commit, push, pull on the box — the box's tree stays clean. Push work that
changes robot code (`pyproject.toml`, configs, nodes) to a **branch** for Dion's review; `bench/` and
`docs/` go to `main`.

### Work queue, in order

Each item: what to build → how you know it's done. Mark ✅ here as you go.

**W1 ✅ — Rebuild the main Python env (uv).**
`curl -LsSf https://astral.sh/uv/install.sh | sh` (installs `~/.local/bin/uv` for `rcp2026` — that
is fine; **never** `pip install --user` into `~/.local/lib`, which recreates ORIENTATION §8.5's
trap). Then `cd ~/rcp-Gappler && uv sync` (~4 GB of downloads incl. torch 2.10 cu128; 28 GB free).
Fix preflight's `torch-cuda` check to use `.venv/bin/python` when it exists (today it uses
`/usr/bin/python3`). **Done when** preflight `gpu`, `env` and `assets` groups pass except
`aria-sdk` (glasses unplugged) and `conda-anygrasp` (superseded by W5 — change that check).

> ✅ **Done 2026-09-11** ([`bench-runs/2026-09-11-labbox-w1-venv.txt`](bench-runs/2026-09-11-labbox-w1-venv.txt)).
> uv was already at `~/.local/bin/uv` (0.12.12), so nothing new went into `~/.local`. `uv sync --locked
> --python /usr/bin/python3.10` with downloads off: 95 packages, 11 min, `.venv` 8.3 GB (free disk 28 → 20 GB);
> torch 2.10.0+cu128 sees CUDA. Undo = `rm -rf .venv ~/.cache/uv`. Preflight gpu/env/assets: 11 pass, 2 fail —
> `anygrasp-env` (the renamed conda check; expected until W5) and **`aria-sdk`: the lock pulls setuptools 82,
> which removed `pkg_resources`, and the `aria` CLI crashes on import** `[observed]`. Fix on branch
> **`bench/w1-setuptools-pin`** (`setuptools<81`; verified in an ephemeral overlay — the CLI then reports "no
> devices over USB", correct with the glasses unplugged). Dry-run of that lock: swaps setuptools, reinstalls
> `decord`, leaves torch alone. **After Dion merges it:** `git pull && uv sync --locked` on the box, re-run
> preflight `-g env`. `torch-cuda` now uses `.venv/bin/python`; `aria-sdk` reports a crashing CLI as FAIL.

**W2 ✅ — State machine on the simulated arm** (`bench/state_machine_sim.sh` +
`bench/nodes/test_state_machine_sim.py`). Launch `bench/nodes/sim_arm.launch.py` + `rm_mtc
grasp_state_machine` on the private channel, with every guard from `sim_moveit.sh`. The test plays
the other actors: publish `/camera/camera/color/camera_info` (D435i intrinsics), the static TF the
node needs, a `/object_centroid_2d` point, then a `GraspCandidateArray` (topic at
`grasp_state_machine.cpp:142`). Record `/pipeline_state` and the simulated joints, and **subscribe
to** `/rm_driver/set_gripper_*_cmd` to capture what the gripper *would* be told (nothing listens on
the private channel). Assert the intended sequence IDLE → SELECTING → EXECUTING → IDLE with homing
at start and end. Mark audit bugs as expected-fail (CODE_AUDIT C1–C7; B4 home pose; A3
`USE_SIMPLE_EXECUTE`). **Done when** it runs to completion or to a named, audit-linked failure.

> ✅ **Done 2026-09-11** ([`bench-runs/2026-09-11-labbox-w2-state-machine.txt`](bench-runs/2026-09-11-labbox-w2-state-machine.txt)).
> A full cycle on the simulated arm: walls → home → IDLE → SELECTING (one approach step) → EXECUTING → gripper
> open (position 1000) → final step → gripper close (speed 200, force 150) → return pose → `/manipulator/return_to_user`.
> **C7 reproduced** (XFAIL): it never goes back to IDLE. Homes to `main`'s unvalidated pose (B4). The sim model has
> no optical frames, so the test publishes them as the RealSense driver would. A1–A3 untestable while
> `USE_SIMPLE_EXECUTE` is on.

**W3 ✅ — The Python-only Tier 3 tests** (no extra build needed): `estop.py` delivery (B2, subscribe
on the private channel to `/rm_driver/emergency_stop_cmd`, SIGINT the node, expect a message).

> ✅ **Done 2026-09-11** — `./bench/estop_delivery.sh` ([`bench-runs/2026-09-11-labbox-w3-estop.txt`](bench-runs/2026-09-11-labbox-w3-estop.txt)).
> Keys `e`/`r`/`s` deliver. **The Ctrl+C key does nothing** — raw tty mode makes it a plain character, so no
> stop and no exit (new finding, CODE_AUDIT B2a). `kill -INT` delivered **5/5** on localhost, so B2's loss did
> not reproduce — but rclpy's handler has already shut the context down, and `estop.py:76` then crashes (exit 1).
> Both are recorded in CODE_AUDIT B2; a fix is robot code → branch.

**W4 — Navigation_Module: compare (✅ a), then build (b — next).**
(a) Read-only diff of the repo's `Navigation_Module/src/{robot_slam,robot_navigation,simple_teleop,
echo_plus_driver,livox_ros_driver2}` against `~iot22/Ros2Workspaces/src/` — that workspace is what
actually ran on the base (ORIENTATION §8.6). Record which is newer. (b) `./bench/build.sh nav` —
first teach it the Livox prep: copy a ROS 2 `package.xml` into the (untracked) livox folder and pass
`--cmake-args -DROS_EDITION=ROS2 -DHUMBLE_ROS=humble` (from `livox_ros_driver2/build.sh:50-67`).
`xpkg_demo` is only an `exec_depend`, so the build should not need it. **Done when** the nav build
result is in `docs/bench-runs/` and the §8.15 fix (commit `package_ROS2.xml`) is proposed on a branch.

> ✅ **(a) done 2026-09-11** ([`bench-runs/2026-09-11-labbox-w4a-nav-diff.txt`](bench-runs/2026-09-11-labbox-w4a-nav-diff.txt)).
> The repo's copies are the **newer** ones (tidied rewrites, git 2026-04-20; `iot22`'s are Feb–Apr) and do the
> same thing once formatting is ignored — the repo's `qos_relay.py` even fixes a shutdown crash in `iot22`'s.
> `base`, `drivers`, `urdf`, `echo_plus_driver`, `Livox-SDk2` are identical. **But two packages exist only in
> `iot22`'s workspace:** `robot_navigation` (Nav2 launch + `nav2_params.yaml`; not in this repo at all — the
> plan's list above assumed it was) and `demo/` = `xpkg_demo` (ORIENTATION §8.6). `iot22` also has the
> generated ROS 2 livox `package.xml` that (b) needs. Importing the two packages is robot code → branch.

> ✅ **(b) done 2026-09-14** ([`bench-runs/2026-09-14-labbox-w4b-nav-build.txt`](bench-runs/2026-09-14-labbox-w4b-nav-build.txt)).
> `./bench/build.sh nav`: **10 of 10 packages, 2 min 34 s, colcon exit 0.** Slowest were `xpkg_vehicle`
> (2 min 28 s), `livox_sdk2` (2 min 9 s) and `xpkg_power` (1 min 51 s); `livox_ros_driver2` took 53.5 s.
> The only stderr anywhere is the harmless CMake note about `HUMBLE_ROS` / `ROS_EDITION` being unused —
> except in `livox_ros_driver2`, which lists only `HUMBLE_ROS`, so `ROS_EDITION=ROS2` **was** consumed by
> the one package the flag exists for. `robot_slam` installed its 6 scripts.
>
> **Three things the prep expected that turned out otherwise, all in the build's favour** `[observed]`:
> (1) **Livox-SDK2 is already installed** — `/usr/local/lib/liblivox_lidar_sdk_shared.so` exists, so
> `find_library(… REQUIRED)` is satisfied and the build has **no sudo blocker at all**. The plan expected
> it to stop here. (2) **`Livox-SDk2/` is built by colcon**, as `livox_sdk2` — it genuinely has no
> `package.xml` (the tree holds only 9), but its `CMakeLists.txt` declares `project(livox_sdk2)` and
> colcon's plain-CMake support picks it up without a manifest. The plan's `[code]` claim that colcon
> ignores it is **wrong**. Which of the two SDK copies `livox_ros_driver2` linked against was not checked.
> (3) The bench's `livox_package_ROS2.xml` is **byte-identical** to `iot22`'s generated one, comment header
> aside — that clears its `[unverified]` tag.
>
> Still true: `robot_navigation` and `xpkg_demo` exist only in `iot22`'s workspace, so the base cannot be
> brought up from this repo. They are `exec_depend`s, which is why the build did not need them
> (NEXT_STEPS §2.9). Undo: `rm -rf build_nav install_nav log_nav nav/vendor/livox_ros_driver2/package.xml` (path since 2026-09-21).

**W5 — AnyGrasp env, reproducibly.** What `iot22`'s env actually is `[observed]`: conda, Python
3.10, torch 2.7.0 (but at runtime `~iot22/.local`'s torch 2.10 wins), **numpy 1.21.2**,
MinkowskiEngine 0.5.4 (compiled by hand, unrecorded), open3d 0.18.0. The main env pins
**numpy 2.2.6**, torch 2.10.0. The vendor `.so` files do **not** link libtorch, and `libcrypto.so.1.1`
is system-wide — so the only real conflict is MinkowskiEngine (numpy 1.x build, CUDA extension).
Plan: in a scratch copy of the venv, build MinkowskiEngine from `grasp_module/`'s vendored source
against torch 2.10 + `/usr/local/cuda-12.8` (`nvcc` is not on PATH — set `CUDA_HOME`); it may
need patches for CUDA 12. If it builds and imports under numpy 2 → **one env**. If not → a
second, scripted env (`envs/anygrasp/` + lock) matching `iot22`'s versions. **Done when** a script
in the repo builds the env from nothing and AnyGrasp prints `license passed` on a saved frame.

> ✅ **Survey answered 2026-09-11: ONE env works** ([`bench-runs/2026-09-11-labbox-w5-anygrasp-env.txt`](bench-runs/2026-09-11-labbox-w5-anygrasp-env.txt)).
> `.venv` (torch 2.10, numpy 2.2.6) + MinkowskiEngine + pointnet2 + open3d 0.19 + scikit-learn 1.7.2 + graspnetAPI
> (no-deps) and its runtime deps: every import passes, the licence check passes, the SDK demo finds grasps
> (score 0.476). No conda, no second env, no system-header edit. **Left, and held under "no fixes yet":** a repo
> script for the recipe, and whether AnyGrasp's packages join `pyproject.toml` — a branch for review.
>
> *How it was done:* survey only, nothing in `.venv` or `pyproject.toml` changed. The test exists:
> `./bench/anygrasp_env.sh [PYTHON]` imports each dependency separately, then runs the SDK demo on its example frame
> with the perception folder's `.so`, licence and checkpoint (the perception and SDK `.so` files are byte-identical).
> Scratch build: `log/w5/` on the box — a venv that sees `.venv`'s packages through a `.pth` file, plus
> MinkowskiEngine 0.5.4 compiled from a copy of `grasp_module/dependencies/` against torch 2.10 / CUDA 12.8 /
> numpy 2.2.6, system OpenBLAS, GPU arch 8.9 only. The README's `sed` on `/usr/include/c++/11/…` (sudo, system
> file) is **deliberately not applied** — if the build fails there, that is the recorded answer.
> Survey facts `[observed]`: `iot22`'s env = torch 2.7.0 (conda `pytorch-cuda=11.8`), numpy 1.21.2, ME 0.5.4
> (egg), pointnet2, open3d 0.18.0, scikit-learn 1.3.2, scipy 1.10.1, graspnetAPI 1.2.10. The SDK pins numpy 1.21.2,
> scikit-learn 1.3.2, scipy 1.10.1 — all numpy-1 builds, so one env needs newer versions of them. Box toolchain:
> nvcc 12.8, gcc 11.4, libopenblas-dev, python3.10-dev; no system `ninja` (pip-installed into the scratch env).

> ✅ **Done 2026-09-21: the env is rebuilt by a script in the repo.** `./envs/anygrasp/build.sh` makes
> `envs/anygrasp/.venv` from nothing in about 18 minutes on the box: a venv on top of `.venv` (through a `.pth`
> file), MinkowskiEngine and pointnet2 compiled from copies of the repo's sources, then the packages in
> `envs/anygrasp/requirements.txt`, pinned to the set that worked on 2026-09-11. It ends by running the probe:
> every import passes and the SDK demo gives the same grasp score, 0.476 `[observed]`
> ([`bench-runs/2026-09-21-labbox-w5-anygrasp-build.txt`](bench-runs/2026-09-21-labbox-w5-anygrasp-build.txt)).
> Machine paths (`CUDA_HOME`, GPU arch, BLAS folders) are environment variables with the box's values as
> defaults. AnyGrasp's packages did **not** join `pyproject.toml`: MinkowskiEngine needs a CUDA compile, which
> `uv sync` on a laptop or in CI cannot do. L2 `anygrasp-env` and L4 `anygrasp_env.sh` now both test this env.
> The scratch env `log/w5/venv` is no longer used by the bench and can be deleted. Re-running the script
> reuses what is built: MinkowskiEngine and pointnet2 compile only if they do not already import, so a
> rerun takes about 20 s on the box. `--clean` rebuilds everything, needed after changing torch, CUDA or the GPU.

**W6 — AnyGrasp gate test** (A1, expected-fail) and perception replay. Needs W5 + frames.

> **Attempted 2026-09-14 with Dion's go-ahead. Not done: no frames**
> ([`bench-runs/2026-09-14-labbox-w6-camera-attempt.txt`](bench-runs/2026-09-14-labbox-w6-camera-attempt.txt)).
> The camera was **already faulty before anything was launched**: depth opened at 640x480x30, colour
> failed with `xioctl(VIDIOC_S_FMT) errno=5 Input/output error` then a loop of
> `UVCIOC_CTRL_QUERY: Protocol error`. USB was 3.2 at 5000M and nothing else held the device, so this
> was the camera wedged, not a configuration fault. Adding `initial_reset:=true` (librealsense's own
> reset, the documented fix) made it worse: the device could not be created, and it then **dropped off
> the USB bus entirely** — no `8086:0b3a`, no `/dev/video*`, no re-enumeration after 30 s. `[observed]`
>
> **It needs a physical replug** (or a root USB port power cycle; `rcp2026` has no sudo). Dion,
> 2026-09-14: someone can replug it in about two hours. Isolation held throughout — private channel 78,
> localhost only, nothing published to the real domain, no process left running.
>
> **Do not pass `initial_reset:=true` again unless someone is at the machine.** Order to follow after the
> replug: `python3 bench/preflight.py -g net` (both realsense checks should pass) → depth only → add
> colour → record frames.

**W7 — The navigation node tests** (8, from Phase 5's table: approach far/near, nav-failure
recovery F1, goal bridge F1, return retry F2, fused-pose frame E1, QoS relay J4, robot pose). Need
W4's build; a mock `navigate_to_pose` action server replaces Nav2 — nothing drives.

> ✅ **Done 2026-09-14, PASS on the first run, no fix needed** — `./bench/nav_nodes.sh`
> ([`bench-runs/2026-09-14-labbox-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt)).
> **6 controls pass, all 4 expected failures reproduced, 0 skipped.** It starts each node from
> `robot_slam/scripts/`, so it did not need W4b; a mock `navigate_to_pose` server replaced Nav2 and
> nothing drove. The `[inferred]` rclpy details (action-server teardown seen within 2.5 s,
> `--include-hidden-topics` in the guard) all held.
>
> | Case | Kind | Result |
> |---|---|---|
> | approach, far object | control | ✅ goal (1.42, 0.31) in `map`, 0.780 m from the object, facing error **0.0°** |
> | approach, near object | control | ✅ 1 `/manipulation/start`, 0 `/goal_pose` |
> | approach, nav succeeds | control | ✅ approach → bridge → `"success"` → `/manipulation/start` |
> | approach after nav failure | xfail F1 | **reproduced** — goal 1 rejected, bridge silent, second object got **0** `/goal_pose` |
> | goal bridge, nav aborts | control | ✅ `/goal_reached` `"failed"` |
> | goal bridge, server down | xfail F1 | **reproduced** — nothing on `/goal_reached` in 8 s |
> | return retry | xfail F2 | **reproduced** — *"Return ignored — already returning to user"*; return 2 reached Nav2 **0** times |
> | fused pose frame | xfail E1 | **reproduced** — goal (1.00, 0.60) in `map`; the wearer's real map pose puts it at (2.40, 2.00), **2.0 m out** |
> | QoS relay | control (J4) | ✅ `/cloud_relay` BEST_EFFORT; **50/50** frames of 520 kB at 10 Hz, 1.9 ms mean latency |
> | robot pose | control | ✅ 10.0 Hz, `map`, at the TF pose |
>
> **What this changes.** **E1, F1 and F2 move from `[unverified]` to `[observed]`**, each matching the
> mechanism CODE_AUDIT predicted, so the audit's reasoning on this subsystem is now evidence-backed.
> **J4 is not a problem** at MID360 rates — nothing was dropped, so that case is a clean control rather
> than a finding. The happy path works end to end, which localises F1 to failure handling only.
> **New finding F4** (CODE_AUDIT): all five nav nodes exit with a traceback on Ctrl+C, in three shapes,
> the first identical to B2's double-shutdown. `goto_glasses`'s `_cancel_navigation()` is never called on
> shutdown, so Ctrl+C mid-leg would leave the Nav2 goal live and the base driving `[inferred]` — this
> bench cannot test that.
>
> Not covered: the mock replaces only Nav2's accept/abort/reject, so there is no planner, costmap or
> recovery behaviour, and F1's real-world trigger rate is still unknown. `/aria/fused_pose` was
> synthesised; the real `pose_fusion_node` was not started.

**W8 — Tier 4** (record + hardware smoke) — **human at the robot**; not before Dion schedules it.

**Bench chores alongside:** C1 Aria publishers; add every new test to `testbench-map.html` and
republish (artifact `cb1f53f5-3154-4271-be1e-4daf46fca7fe`). (C3's re-snapshot and S1's static baseline are
dropped — Dion, 2026-09-11; see Decisions.)

**Open, not blocking:** the box's CPU is throttled (800 MHz, 90 °C — ask who maintains it);
ORIENTATION §8.16's decision (fix the config's simulated-arm launch, or keep it in `bench/`).

---

## 0. State at handoff (2026-09-11, evening)

| Thing | State |
|---|---|
| Tiers 0–1 (contracts + static) | Working on the Mac and the box. Static: the same 7 pre-existing owned-code findings (no baseline yet — S1); contracts PASS |
| Preflight | Runs on the box. `gpu`/`env`/`assets`: 12 of 13 pass — the fail is `anygrasp-env` on the project env (expected until W5 is made permanent). Arm, LiDAR and Aria checks fail or skip: unplugged. (The Aria check wrongly passed until the 2026-09-11 fix; **confirmed FAILing on the box 2026-09-14**) |
| Tier 2 (build) | **Both workspaces build.** Arm 22/22 (27 min 41 s, CPU throttled); nav 10/10 (2 min 34 s, 2026-09-14) — no Livox blocker, the SDK is already installed on the box |
| Tier 3 (node behaviour) | **All five scripts run.** `sim_moveit.sh` PASS · `estop_delivery.sh` PASS, found B2a · `state_machine_sim.sh` PASS, C7 XFAIL · `anygrasp_env.sh` PASS in the W5 scratch env · `nav_nodes.sh` PASS 2026-09-14, 6 controls + 4 XFAIL, found F4 |
| Tier 4 (replay + hw smoke) | Not started — needs a person at the robot |
| `docs/CODE_AUDIT.md` | **62 findings** (recounted 2026-09-14; the old running total of 51 never included sections D, H and J). 16 blocking/safety, 22 runtime, 21 debt. **7 `[observed]`**: B2a, B4, C7, E1, F1, F2, F4. B2's message loss was tested and not reproduced; the rest `[unverified]`. Page source is now `docs/code-audit-page.html`, published at <https://claude.ai/code/artifact/63cc961e-e49a-4421-9132-fec0f3e35822> |
| Lab box access | tailscale (see Start here). All work in `~/rcp-Gappler`; `rcp-desktop` / `rcp-github` untouched |
| Git | Everything on `main`; the box pulls from it. `bench/w1-setuptools-pin` is merged (the branch can go) |
| Test bench page | <https://claude.ai/code/artifact/cb1f53f5-3154-4271-be1e-4daf46fca7fe> — source `testbench-map.html`; republish after each result |

---

## 1. Where things are

| What | Where | Confidence |
|---|---|---|
| Local clone (where `bench/` and `docs/` were written) | `/Users/Dion/sch_repo/Gappler` on Dion's Mac, branch `main` @ `2d36a89` + uncommitted work | `[code]` |
| GitHub remote | `git@github.com:dionyichia/Gappler.git` | `[code]` |
| Lab machine SSH | **tailscale** (from anywhere): `ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60`. Campus: `ssh rcp2026@10.91.242.76` — NTU network / VPN only. Key auth from the Mac | observed 2026-09-11 |
| The code on the lab machine | `~/rcp-desktop` = `realman_manip`; `~/rcp-github/Renaissance-Capstone-Project` = `combined` = **this Mac's `main`** — see Phase 0 results below | read on the box 2026-09-11 |
| Aria / arm / LiDAR / camera | attached to the lab machine | `[reported]` |

### Phase 0 results — read on the box over SSH, 2026-09-11, read-only

| Fact | Value |
|---|---|
| Machine | `iot22-Computer`, Ubuntu 22.04.5, kernel 6.8, RTX 4060 Ti 16 GB (driver 575.57), ROS 2 Humble in `/opt/ros/humble`. Same box as `10.91.155.97` (identical host key) |
| Accounts | `rcp2026` (in `sudo`), **`iot22` still exists and is in use** — desktop session `:1` logged in since 2026-09-08, SSH sessions 2026-09-09. `/home/iot22` is `drwxr-x---`, so **unreadable to `rcp2026`**. Also `chengyu`, `buildfarm` |
| `~/rcp-desktop` | branch **`realman_manip` @ `55a2815`** (= Gappler `realman_manip`), clean except untracked `build/ install/ log/` + `anygrasp_node.py.bak`. 1,497 tracked files; 44 differ from `main`, 901 of `main`'s (mostly `Navigation_Module`) absent. The **older** line (arm work ends 2026-03-28) — but the clone the 2026-08-25 hardware session ran from |
| `~/rcp-github/Renaissance-Capstone-Project` | branch **`combined` @ `2d36a89`** = Gappler `main` = **this Mac's `main`**: tracked tree byte-identical (2,383 / 2,383). Untracked: 2 `frame_*.png`, 2 `gaze_recording_*.avi`, `src/output/`. `~/rcp-github/src.zip` (3 GB) sits beside it. **So the audit's line numbers apply to this clone, not to `rcp-desktop`** |
| Built overlays | `rcp-desktop`: `install/` (189 MB, built at `/home/iot22/Desktop/...`, the verified one), `deps_ws/install`, `ros2_robot_ws/install` (built at `/home/iot22/GitHub/...`). `rcp-github`: `deps_ws/install`, `ros2_robot_ws/install`, no root `install/`. **None works for `rcp2026`**: after sourcing `install/setup.bash` or `local_setup.bash`, `ros2 pkg executables rm_mtc` → `Package 'rm_mtc' not found`. The overlays chain into `/home/iot22` paths. → **Phase 4 is required before any ROS test** |
| Python | `rcp-desktop/.venv` **works as `rcp2026`**: symlink to `/usr/bin/python3.10`, torch `2.10.0+cu128`, `cuda=True`, `sam3`, `projectaria_tools 1.5.2a1`, client SDK 1.1.0. `rcp-github` has no `.venv`. System `python3` has no torch. No `conda`, no `uv` on `rcp2026`'s PATH |
| Per-user state for `rcp2026` | none: no `~/.local` torch, `~/.aria`, `~/miniconda3` (so **no `anygrasp` env**), `~/maps`, `~/Ros2Workspaces`. `.bashrc` sources no ROS |
| Assets | `sam3.pt` (3.45 GB), `checkpoint_tracking.tar`, licence (`Puneet.*`), `lib_cxx` + `tracker` `.so` in both; `checkpoint_detection.tar` (296 MB) + `gsnet` `.so` only in `rcp-github` |
| Network | `enp2s0` is the only wired port — **`NO-CARRIER`**; its NetworkManager profile is **manual `192.168.1.100/24`** (neither the arm's `.10` nor the LiDAR's `.5`, ORIENTATION §8.13). `wlo1` = `10.91.242.76/16` (NTUSECURE), `tailscale0` = `100.93.102.19`. An `Aria` ethernet profile (DHCP) also exists |
| Live | no ROS / driver / MoveIt / AnyGrasp process from any user at check time |
| Disk | `/home` 325 GB, **33 GB free (90 % used)** — enough for Phase 4, not for many build copies |
| Also in `~rcp2026` | `INTEGRATION_PLAN.md` + `RCP_REPO_DIFF_REPORT.md` (2026-09-09): the record of how the four Gappler branches were pushed from the two clones |

### Lab-box results, 2026-09-11 (Phases 1, 2, 4 and the first of 5)

| What | Result |
|---|---|
| Working repo | `~/rcp-Gappler`, `git clone --branch main git@github.com:dionyichia/Gappler.git` (60 s, 669 MB). Builds go to its own `build/ install/ log/` (gitignored) |
| Bench run (`./bench/run.sh`) | preflight 17 pass / 5 fail / 1 warn / 13 skip; static the same 5 known findings; contracts pass. Report: `docs/bench-runs/2026-09-11-labbox-bench.txt` |
| Tier 2 (`./bench/build.sh`) | **PASS** — 22 packages, 27 min 41 s. stderr (warnings) from `moveit_task_constructor_core`, `rm_driver`. Old overlay had 23: the difference is `pointnet2` (AnyGrasp's CUDA op in `grasp_module/`, built against the conda torch — not part of the arm workspace) |
| Tier 3 (`./bench/sim_moveit.sh`) | **PASS** — both home poses (`main`, `realman_manip`) and zero, SUCCESS, max joint error ≤ 0.0045 rad, on `mock_components`, channel 77, `enp2s0` NO-CARRIER throughout. `move_group` segfaults (−11) **on shutdown**, after all motions `[inferred]` known Humble shutdown behaviour; harmless to the result |
| The config's own simulated-arm launch | **Cannot start** — see ORIENTATION §8.16. The bench carries its own model (`bench/nodes/sim_arm.urdf.xacro`) instead of editing the robot config |
| CPU | **Throttled**: all 16 threads at 800 MHz, max capped at 1.84 of 4.6 GHz, package 90 °C, `intel_powerclamp` injecting idle, RAPL limit 32.5 W. Explains the 28-min build (~6 min reported earlier). Cooling / power profile — a question for whoever looks after the machine |
| Not yet in `~/rcp-Gappler` | `.venv`, `sam3.pt`, both AnyGrasp checkpoints (all gitignored). Copy from `~/rcp-github` / `~/rcp-desktop` (read-only there) — awaiting Dion's OK |
| Found in `~iot22` (read ACL granted by Dion) | `anygrasp` + `grasp` conda envs, `~/.local` CUDA torch 2.10, `~/maps/completed_map.*`, `~/.aria` certs, `xpkg_demo` (§8.6), and `~/Ros2Workspaces` — the base's real nav workspace |

### ⚠️ Three things about the lab machine that do not add up yet — settle these first

**Status after the second 2026-09-11 session** (details in the numbered points below, left as written):

- **Point 2 — settled.** `10.91.242.76` presents the **same ed25519 host key** as `10.91.155.97`
  (both in the Mac's `~/.ssh/known_hosts`), so it is the same box as the old `iot22-Computer` on a new
  lease. `[inferred]` from the key match; `hostname` still to be read once logged in.
- **Point 1 — answered, with a consequence** (update below): Dion: `rcp2026` is a **new account**; `iot22`'s
  folders were copied into it as `rcp-desktop` and `rcp-github` `[reported]`. It follows that:
  - per-user state outside those folders (`~/.local` CUDA torch, `~/.aria`, `~/miniconda3`,
    `~/maps`) exists for `rcp2026` only if someone copied it too `[inferred]`;
  - **10 hardcoded paths in our own code point at `/home/iot22/GitHub/Renaissance-Capstone-Project/...`
    and `/home/iot22/maps/`** `[code]` — preflight's new `home/hardcoded-homes` check lists them. Run
    as `rcp2026`, each one is either missing (if `iot22`'s home is gone) or, worse, **silently reads
    `iot22`'s copy** (if it is still there);
  - note they name the **GitHub** clone, even though the code was pushed from the **Desktop** one;
  - copied colcon `install/` overlays and the uv `.venv` bake absolute paths in at build time, so the
    copies under `rcp2026` very likely still point into `/home/iot22` `[inferred]` — a fresh build
    (Phase 4) is needed anyway.
- **Point 3 — settled by Phase 0, and it corrects the earlier report.** This Mac's `main` came from
  **`rcp-github`** (`combined` → `2d36a89`, byte-identical), **not** `rcp-desktop`. `rcp-desktop`
  is `realman_manip`: older code, but the checkout the 2026-08-25 hardware session actually ran.
  So "which is more up to date" depends on what you mean: newer code (`rcp-github`) versus the
  last known-working build (`rcp-desktop`).
- **Point 1, update:** `iot22`'s home exists but is unreadable to `rcp2026`, so all 10 hardcoded
  `/home/iot22/...` paths **fail** for `rcp2026`; the "silently reads `iot22`'s copy" case cannot
  occur under current permissions.

1. **User mismatch.** Every hardcoded path in the repo is `/home/iot22/...`, and the 2026-08-25
   startup guide was written on machine `iot22-Computer`. The SSH user is **`rcp2026`**. Either it is
   the same machine with a second account, or a different machine. If it is a second account on the
   same box, then **`rcp2026` will not have `iot22`'s `~/.local` CUDA torch, `~/.aria` certs,
   `~/miniconda3` `anygrasp` env, or `~/maps/`** — and the `PYTHONNOUSERSITE` trap
   (ORIENTATION §8.5) behaves differently per user.
2. **IP.** The guide lists the box as `100.93.102.19` (tailscale) and `10.91.155.97` (wlo1, *"NTU
   DHCP — will move"*). `10.91.242.76` is plausibly the same box on a new lease. Unconfirmed.
3. **Which clone is `rcp-desktop`?** The guide records **two** clones on that box:
   `~/Desktop/Renaissance-Capstone-Project` (branch `realman_manip`, the only one ever verified on
   hardware) and `~/GitHub/Renaissance-Capstone-Project` (branch `combined`, never brought up). The
   name `rcp-desktop` suggests the **Desktop** one — which would mean the local `main` was built from
   a *different* clone than the hardware-verified one. Establish this before trusting any comparison.

---

## 2. Decisions Dion needed to make — all answered 2026-09-11 (see "Start here"); kept for the record

1. **Commit and push `bench/` + `docs/`?** They exist only on the Mac, uncommitted. The lab box can
   only get them by `git pull` (after a push) or `scp`. Suggested: two commits — `docs/` + root
   `README.md` + `CLAUDE.md` first, `bench/` second — then push, then `git pull` on the box into a
   **separate** checkout (see §3 rule 5). Also pending in the working tree:
   - `ros2_robot_ws/src/main.py` — Dion's own edit: adds the `# TODO: Change this to fit new repo
     structure...` comment and a trailing space. Harmless; commit or drop.
   - `.README.md.swp` — stale vim swap file. Delete; add `*.swp` to `.gitignore`.
2. **How far may the session go on the lab box?** Recommended default: **read-only until told
   otherwise** — Phase 0–3 below need nothing more. Phase 4 builds into a scratch directory. Phase 5
   runs nodes, but domain-isolated from real hardware. Phase 6 needs a human at the robot.
3. **The six open questions in `CODE_AUDIT.md`** — they don't block the bench, but Q1
   (`USE_SIMPLE_EXECUTE`) and Q3 (the inverted gate) decide what several Tier 3 tests should assert.

---

## 3. Safety rules — non-negotiable for any session on the lab machine

1. **Never launch** `grasp_state_machine` (directly or via `grasp_state_machine.launch.py`),
   `ros2_robot_ws/src/main.py`, `ros2_robot_ws/src/orchestrator.py`, or root `main.py`. The state
   machine homes the arm within seconds, unprompted (ORIENTATION §8.1) — and to a **home pose that has
   changed and never been validated** (CODE_AUDIT §B4). The orchestrator launches the arm stack
   itself and `main.py` launches it a second time (CODE_AUDIT §I1).
2. **Never publish** to any `/rm_driver/*_cmd` topic, `/goal_pose`, `/cmd_vel`,
   `/manipulation/start`, `/manipulation/goal_pose`, or `/object_centroid_2d` on the real ROS domain.
   Each of those moves something, or triggers something that does.
3. **`background.launch.py` connects to the real arm.** Not needed for anything in Phases 0–4.
4. **Before any node runs in Phase 5**, isolate the ROS graph: `export ROS_DOMAIN_ID=77` (any
   unused id) **and** `export ROS_LOCALHOST_ONLY=1`, then confirm `ros2 node list` is empty. A
   synthetic `/object_centroid_2d` on the real domain would reach a running state machine.
4b. **`iot22` is logged in on the same box.** `ROS_LOCALHOST_ONLY=1` keeps traffic off the
   network but does **not** separate `rcp2026` from `iot22`'s processes on the same host. The
   unique `ROS_DOMAIN_ID` is what isolates. Before Phase 5, also check
   `ps -u iot22 -o pid,cmd | grep -E 'ros2|rm_driver|move_group'`, and see what domain it uses.
5. **Work only in `~/rcp-Gappler`** (Dion, 2026-09-11 — supersedes the `~/bench_work` idea below).
   `~/rcp-desktop` and `~/rcp-github` are old code; leave them and their overlays alone.
   Original rule, kept for context: **Do not touch the existing overlays or working tree.** The repo-root `install/` on the
   Desktop clone is the only verified-complete overlay (startup guide §2). Build and test in a
   separate checkout (`git worktree add` or a fresh clone under `~/bench_work/`), with
   `colcon build --build-base ~/bench_work/build --install-base ~/bench_work/install`.
6. **Do not "clean up" `~/.local`, and never set `PYTHONNOUSERSITE=1`** (ORIENTATION §8.5).
7. **Don't fix code on the lab box during bench work.** Findings go into the docs as retagged
   entries; fixes happen in commits on a branch, reviewed by Dion.

---

## 4. What the bench is today

```bash
./bench/run.sh              # 1 preflight → 2 static → 3 contracts; exit 1 if any fail
./bench/run.sh preflight    # environment + hardware only
./bench/run.sh report       # contract inventory + orphan analysis
python3 bench/contracts.py snapshot   # re-baseline after a deliberate change
python3 bench/preflight.py -g net --json   # one group, machine-readable
```

Stdlib-only Python 3.8+. No ROS or pip install needed. Full design rationale in
[`bench/README.md`](../bench/README.md).

| File | Job | Needs a baseline? |
|---|---|---|
| `bench/contracts.py` | Extracts every topic / type / pub-sub endpoint / frame / param / static TF / launch node / hardcoded path; diffs against `bench/golden/contracts.json` **keyed by contract, not file location**, so the planned folder reorg reads as "moved", not "broken" | yes — committed golden |
| `bench/static.py` | 10 internal-consistency checks (syntax, undefined names, intra-repo imports, XML, launch → package / executable / include existence, install targets, generated manifests) | no |
| `bench/preflight.py` | 7 groups: host, gpu, ros, env, assets, net, graph. Read-only. Reports **SKIP with reason, never PASS**, for anything it cannot judge where it runs | no |
| `bench/run.sh` | Runs all three, prints a verdict per stage and the "a green bench does not mean the robot works" reminder | — |

**Verified:** a simulated refactor — renaming `/camera/sam/mask` in 1 of 5 places plus moving
`grasp_viz.py` to a new folder — produced exactly two regressions (`ORPHAN ADDED`, `LOST SUBSCRIBER`,
both naming `anygrasp_detection_node.py:76`) and one `moved` info line. Clean tree passes.

**Current results on the Mac:** preflight 8 pass / 0 fail / 26 skip · static **FAIL** (7 findings in
owned code, all pre-existing — see known issue S1) · contracts PASS.

### Known bugs and gaps — fix these first

**Preflight (none of these can show on macOS, which is why they survived):**

> ✅ **P1–P5 fixed 2026-09-11, tested on the Mac only.** `sh()` now runs each command in its own
> process group; on timeout it sends SIGINT, then SIGKILL, and returns the partial output (rc 124).
> It sets `PYTHONUNBUFFERED=1` so a piped ros2 CLI doesn't lose its buffer. Unit-tested with a
> never-exiting printer behind a `ros2 run`-style wrapper: output kept, no orphan left. `_has_ip`
> matches `inet <addr>/`. `--lab`/`--no-lab` override the guess. The header prints the user, and a
> new **`home`** group reports the running user and every `/home/<other-user>/` path in owned code
> (FAIL if missing on the lab box, WARN if it resolves into another user's home, SKIP off-lab).
> `ros2 topic hz` / `tf2_echo` output format is still unverified against real Humble.

| # | Bug | Where | Effect on the lab box | Fix |
|---|---|---|---|---|
| P1 ✅ | `ros2 topic hz` never exits on its own; `sh()` returns `(124, "timed out")` and **discards the captured output** on `TimeoutExpired` | `preflight.py` `sh()` + `camera-hz-*`, `joint-states` | every rate check reports **false FAIL** ("advertised but no messages") | on `TimeoutExpired`, return `e.stdout`/`e.output` (they hold the partial output), or wrap with coreutils `timeout 8s ...` and parse what printed |
| P2 ✅ | `ros2 run tf2_ros tf2_echo` also never exits | `tf-arm-camera`, `tf-base-bridge` | TF checks always report **"no transform"** | same fix as P1 |
| P3 ✅ | `_has_ip` does `addr in out` — substring match | `preflight.py:394-396` | `192.168.1.10` matches `192.168.1.100`; `192.168.1.5` matches `.50–.59` → false PASS on the arm/LiDAR coexistence check | match `inet 192.168.1.10/` with a regex anchored on `/` |
| P4 ✅ | `on_lab_machine()` is a heuristic (Linux + ROS or NVIDIA) | `preflight.py` | on a Linux laptop with ROS, off-lab asset checks FAIL instead of SKIP | acceptable for now; add a `--lab/--no-lab` override |
| P5 ✅ | Per-user state (`~/.local`, `~/.aria`, conda envs, `~/maps`) is checked for **whoever runs it** | several | as `rcp2026`, may report missing things `iot22` has (§1 point 1) | print the running user in the header; make that visible in results |
| P7 ✅ | `slam-map` looked for `completed_map` or `.yaml`; slam_toolbox stores `.posegraph` + `.data` | preflight | false WARN | `_exists_or_prefix()` |
| P8 ✅ | `hardcoded-homes` reported only unreachable paths, not ones that silently resolve into another user's home | preflight | hid 9 of 10 once the ACL was granted | reports both |
| P9 ✅ | contracts extracted `bench/` itself — the sim test showed as a `/joint_states` orphan; sim guard refused on the word `rm_driver` in a docstring | contracts, sim_moveit | false regression / false refusal | skip `bench/`; match a quoted package name |
| P6 ✅ | `Path.exists()` **raises** `PermissionError` under a locked parent on Python < 3.12 (the box has 3.10.12) instead of returning False | `slam-map` and the new `home` check | as `rcp2026`, preflight would have **crashed** on `/home/iot22/...` (found 2026-09-11 by a `chmod 000` unit test) | `_exists()` treats unreachable as absent; `home` names the locked ancestor, e.g. `[no access: /home/iot22]` |

**Contracts extractor:**

| # | Gap | Evidence | Effect | Fix |
|---|---|---|---|---|
| C1 ✅ | **Every Aria-side publisher is invisible.** **Fixed 2026-09-21 (reorg step 1, `NEXT_STEPS` §2.15):** the extractor now reads our YAML files, resolves `ROS2Topics.X.value`, `get_parameter("x")` and variables set from them, and treats `ROSPublisher` as a publisher. 13 Aria topics gained their publishers. Self-test `bench/test_contracts.py` runs first in L1. They are created via the `ROSPublisher` wrapper class (`src/services/ros/ros_publisher.py:14`) with topic names from `ROS2Topics`, an enum built from `shared/config.yaml` **at import time** — the AST resolver can see neither | `/aria/audio/prompt` shows `pub=0` in the golden file, yet `audio_streaming_pipeline.py:49` publishes it. Same for `/aria/rgb_camera/raw`, `/aria/imu`, … | the orphan report wrongly lists Aria topics as "subscribed, nobody publishes"; a rename on the Aria side will not be caught | teach `PyExtractor` two things: treat `ROSPublisher(name, MsgType, topic, ...)` as a publisher with the topic in arg 3; resolve `ROS2Topics.X.value` by loading `shared/config.yaml` (key = `X.lower()`). Then **re-snapshot** |
| C2 | C++ topics are found only when the string literal is inline in `create_publisher<T>("...")` | regex | a topic held in a `const std::string` is missed | acceptable until the reorg introduces constants; then extend |
| C3 | Golden file was taken on a dirty tree (`2d36a89-dirty`) | `bench/golden/contracts.json` `"git"` field | cosmetic, but makes the baseline's provenance unclear | re-snapshot on the first commit that includes `bench/` |

The audit's dead-edge findings (CODE_AUDIT §D) were **re-confirmed with plain grep on 2026-09-11**,
independently of C1: nothing publishes `/manipulator/release` or `/manipulation/done`, and the only
subscription to `/return_to_user/goal_reached` is commented out (`orchestrator.py:58`).

**Static checks:**

| # | Issue | Fix |
|---|---|---|
| S1 | **No baseline**, so the 7 pre-existing owned-code findings (`xpkg_demo` ×3, `bringup_basic_ctrl.launch.py` ×2, `mtc_sim_test`, livox manifest) make `static` fail **permanently**. A permanent red gets ignored, and a new finding would hide among the old | add `bench/golden/static_known.json` — fail only on findings not in it; `--update-known` to accept |
| S2 ✅ | `OWNED_PREFIXES` is duplicated in `contracts.py` and `static.py` — **fixed: now only in `bench/_common.py`**, used by all three tools | move into one `bench/_common.py`; **update it when the reorg moves code** or moved files get classified as vendor and stop failing |
| S3 | **A filesystem path in a YAML value is extracted as a topic.** `slam_toolbox_localization.yaml:14` sets `map_file_name: /home/iot22/maps/completed_map`; because the value starts with `/` it lands in the topic inventory as an owned topic with 0 publishers and 0 subscribers, inflating the count and the orphan list | in the YAML topic pass, skip values that look like filesystem paths (contain `/home/`, `/opt/`, a file extension, or match the abs-path regex already in `contracts.py:416`) — they are already collected as abs paths |

---

## 5. The plan, phase by phase

Each phase lists what to do, what "done" looks like, and which doc to update. **Do them in order** —
each depends on facts the previous one establishes.

### Phase 0 — Establish ground truth on the lab box (read-only, ~15 min) — ✅ done 2026-09-11, see §1

```bash
ssh rcp2026@10.91.242.76
whoami; hostname; uname -a; lsb_release -a
ls ~ ; ls -d ~/*rcp* ~/Desktop/* ~/GitHub/* 2>/dev/null       # find rcp-desktop
cd <rcp-desktop> && git remote -v && git branch -a && git log --oneline -5 && git status --short
ls -d install ros2_robot_ws/install deps_ws/install 2>/dev/null   # which overlays exist
ls /home                                                        # is iot22 here too?
```

**Done when** these are written into §1 of this file, replacing the `[unverified]` rows: the real
path of `rcp-desktop`, its branch and HEAD, whether it matches the local `main` (`git log` / diff
against `2d36a89`), whether this is `iot22-Computer`, and which user owns the verified overlay.

⚠️ If `rcp-desktop` is **not** the same history as local `main` (remember `main` and `realman_manip`
share **no common ancestor** — ORIENTATION §7), the contract baseline and the audit's line numbers
may not apply to it. Record the divergence before going further.

### Phase 1 — Get the bench onto the box — ✅ done 2026-09-11 in `~/rcp-Gappler`

After Dion's decision in §2.1: commit + push from the Mac, then on the box
`git worktree add ~/bench_work/gappler main` (or a fresh clone) — **not** a pull into `rcp-desktop`.
~~Then fix P1–P3~~ — done on the Mac 2026-09-11 (§4); they ride along with the `bench/` commit.

### Phase 2 — Run preflight, read-only — ✅ first run 2026-09-11 (no live graph yet)

With nothing launched first, then — only if someone at the robot has already started the driver and
camera per the startup guide — again with a live graph:

```bash
cd ~/bench_work/gappler
source /opt/ros/humble/setup.bash && source <verified overlay>/setup.bash
./bench/run.sh preflight | tee docs/preflight-$(date +%F).txt
```

**Done when** the output is committed and every FAIL/WARN is either explained or turned into a
NEXT_STEPS item. Expect to find more preflight bugs — it has never run on Linux.

### Phase 3 — Verify the `[unverified]` findings (read-only)

These can be settled without launching anything. Retag each in ORIENTATION / CODE_AUDIT as you go.

| Finding | Check | Doc |
|---|---|---|
| `mtc_sim_test` not built | `ls <overlay>/lib/rm_mtc/` | ORIENTATION §8.12 |
| Arm + LiDAR share one NIC with different host IPs | `ip -4 addr show enp2s0`; `ip link` for a second NIC | ORIENTATION §8.13 |
| Which AnyGrasp checkpoint exists | `ls ros2_robot_ws/src/rm_mtc/src/perception/log/` | ORIENTATION §8.14 |
| `livox_ros_driver2` has no ROS 2 manifest | `ls nav/vendor/livox_ros_driver2/package*.xml` | ORIENTATION §8.15 |
| `xpkg_demo` missing | `ros2 pkg prefix xpkg_demo`; `find / -name 'xpkg_demo' -maxdepth 6 2>/dev/null` | ORIENTATION §8.6 |
| Which OpenVINS is authoritative | `ls ~/Ros2Workspaces/OpenVINS/install` | NEXT_STEPS §2.5 |
| Home pose on the box's checkout | `grep -A8 HOME_JOINTS <rcp-desktop>/ros2_robot_ws/src/rm_mtc/include/rm_mtc/mtc_planner.hpp` | CODE_AUDIT §B4 |
| Whether the box's code has the inverted gate | `sed -n 176,187p .../anygrasp_detection_node.py` | CODE_AUDIT §A1 |

The last two matter: if `rcp-desktop` is the Desktop/`realman_manip` clone, it may have different
home joints and different gate logic from what the audit read.

### Phase 4 — Tier 2: does it build (no hardware) — ✅ arm workspace 2026-09-11; `Navigation_Module` still to do

The lab box already has ROS 2 Humble, so **build natively there** rather than in Docker — Docker
on the Mac is the fallback for when the box is unavailable.

```bash
cd ~/bench_work/gappler
source /opt/ros/humble/setup.bash                      # only this — a stale overlay poisons the build
colcon build --build-base ~/bench_work/build --install-base ~/bench_work/install \
  --base-paths ros2_robot_ws/src arm/vendor grasp/vendor 2>&1 | tee ~/bench_work/build_arm.log
colcon build --build-base ~/bench_work/build_nav --install-base ~/bench_work/install_nav \
  --base-paths Navigation_Module/src nav/vendor       2>&1 | tee ~/bench_work/build_nav.log
```

Add `bench/build.sh` wrapping this, with a pass/fail summary per package. Expected results:
arm workspace ~6 min, 24 packages, six benign stderr warnings (startup guide §2). `Navigation_Module`
**has never been built** — expect `livox_ros_driver2` to be invisible (ORIENTATION §8.15) and the
build to be discovery, not regression. Then extend `static.py`'s `launch-executables` check to read
the real `install/lib/<pkg>/` instead of parsing CMakeLists.

### Phase 5 — Tier 3: node behaviour against synthetic inputs — started: MoveIt on a simulated arm passes

**Domain-isolated per §3 rule 4. Every test here runs with no hardware and cannot reach it.**

Layout: `bench/nodes/test_*.py`, each launching one node under test plus synthetic publishers,
asserting on its outputs, with a hard timeout. Use `launch_testing` if available, else plain
`subprocess` + `rclpy` in the test. Tests that encode an audit finding are written to assert the
**intended** behaviour and marked **expected-fail**, so they flip green when the bug is fixed and the
bench tells you so.

| Test | Node under test | Stub needed | Asserts | Audit link |
|---|---|---|---|---|
| approach, far object | `object_approach_node` | static TF `map→robot_base_link→base_link` | `/goal_pose` at 0.78 m from object, facing it | — |
| approach, near object | `object_approach_node` | same | `/manipulation/start` fires, no `/goal_pose` | — |
| approach recovers from nav failure | `object_approach_node` + `goal_reached_publisher` | **mock `navigate_to_pose` action server** that rejects | a second `/manipulation/goal_pose` is still acted on — **expected-fail** | F1 |
| goal bridge, server down | `goal_reached_publisher` | none | publishes `"failed"` within 6 s — **expected-fail** | F1 |
| return retry after nav server down | `goto_glasses` | mock action server, then none | a second `/manipulator/return_to_user` is not ignored — **expected-fail** | F2 |
| fused pose frame handling | `goto_glasses` | mock action server | goal is in `map` and differs from the raw `robot_base_link` pose — **expected-fail** | E1 |
| QoS relay | `qos_relay` | RELIABLE cloud publisher | `/cloud_relay` arrives BEST_EFFORT at input rate | J4 |
| robot pose | `pose_publisher` | static TF | `/robot_pose` at ~10 Hz in `map` | — |
| AnyGrasp gate | `anygrasp_detection_node` (conda, licence — lab box only) | recorded RGB/depth/mask frames; `/pipeline_state` sequence | candidates published during `EXECUTING`, none during `IDLE` — **expected-fail** | A1 |
| e-stop delivery | `estop.py` | subscriber on `/rm_driver/emergency_stop_cmd` | a message arrives after SIGINT — **expected-fail** | B2 |
| state machine, simulated arm | `grasp_state_machine` against **MoveIt with `mock_components` fake hardware** (no `rm_driver`) | fake `/camera/camera/color/camera_info`, `/object_centroid_2d`, TF | homes, reaches SELECTING, steps — **simulated arm only** | C1–C7, B4 |

The last row is the highest-value test and the most dangerous to get wrong: it must never be run
with `rm_driver` present. Build a dedicated launch file (`bench/nodes/sim_arm.launch.py`) that
brings up `robot_state_publisher` + `move_group` with fake controllers from `rm_65_w_gripper_config`
and **refuses to start if `/rm_driver` topics exist on the domain**. This is how the state machine
gets exercised "up to the point just before the arm moves" — the arm it moves is simulated.

### Phase 6 — Tier 4: real data, human present

1. **Record once, replay forever.** `bench/record.sh` — 30 s of `/camera/camera/color/image_raw`,
   `/camera/camera/aligned_depth_to_color/image_raw`, `/camera/camera/color/camera_info`,
   `/livox/lidar`, `/tf`, `/tf_static`, `/joint_states`, `/aria/audio/prompt`. Recording is
   read-only, but the drivers must be running, so someone at the robot starts them per the startup
   guide §4 (T1 e-stop first). Store bags outside git (size); record the path in this file.
   Then Tier 3 perception tests replay the bag instead of synthetic frames.
2. **Hardware smoke** — the two startup-guide checks preflight cannot do without launching:
   the driver's `product_version = RM65-BI` handshake line and AnyGrasp's
   `Frame 0: selected 5 seed grasps`. `bench/hw_smoke.sh`, interactive, prompts the operator to
   confirm the e-stop terminal is open before each step. **Stops before any state-machine launch.**

---

## 6. Backlog after the phases

- Pytest wrapper around the three tools, so `pytest bench/` works where pytest exists.
- A pre-commit hook or CI job running `bench/run.sh` minus preflight (GitHub Actions can run tiers
  0–1 with no ROS; Tier 2 in a `ros:humble` container).
- `contracts.py`: also snapshot QoS profiles per endpoint (the `VIDEO_QOS` depth 10→1 drift in
  ORIENTATION §8.10 is a contract change the bench cannot see today).
- A checked-in list of "accepted orphans" (RViz-only markers, manual-test topics like
  `/goto_glasses/trigger`) so the orphan report shows only real breaks.

---

## 7. Facts a new session should not re-derive

All established and written down elsewhere — trust these unless new evidence contradicts them:

- `main` and `origin/realman_manip` have **no common ancestor**; `realman_manip` has no arm code
  `main` lacks; take only its docs, `env.sh`, `calibration.json` (ORIENTATION §7, NEXT_STEPS §3.3).
- The grasp path cannot work as written — inverted gate + EXECUTING-only consumer +
  `USE_SIMPLE_EXECUTE` (CODE_AUDIT §A).
- Arm needs host `192.168.1.10`, LiDAR needs host `192.168.1.5`, same `/24` (ORIENTATION §8.13,
  `[unverified]` whether the box has both).
- The arm has never been commanded to move (startup guide §7).
- Local toolchain: macOS arm64, Python 3.10.9, uv, Docker 28.1.1 (8 CPU / 8 GB), **no ROS, no
  pyyaml, no pytest** — hence stdlib-only. `grep` on the Mac is **ugrep**, which silently returns
  nothing for `grep -rniE ... --include` with multiple path operands; pipe through `find | xargs grep`.

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-11 | Claude (Opus 5) + Dion | Created as the cold-start handoff. Records three preflight bugs found on review (P1–P3: `topic hz` / `tf2_echo` output discarded on timeout; substring IP match), the contracts extractor's blind spot for every Aria-side publisher (C1), and the static tier's missing baseline (S1). Re-confirmed CODE_AUDIT §D with plain grep. Phases 0–6 planned; nothing yet run on the lab machine. |
| 2026-09-11 | Claude (Opus 5) + Dion | Second session. SSH attempted: host reachable, login refused (no key for `rcp2026`). Host key identical to `10.91.155.97`, so §1 point 2 is settled. Recorded Dion's account of the `iot22`→`rcp2026` copy (`rcp-desktop`, `rcp-github`). Fixed P1–P5 and S2 in `bench/`; added preflight `home` group, which found 10 `/home/iot22` paths in owned code. Bench verdicts on the Mac unchanged apart from that. |
| 2026-09-11 | Claude (Opus 5) + Dion | Phase 0 done over SSH, read-only; results table in §1. **Corrected:** the Mac's `main` is `rcp-github`'s `combined`, not `rcp-desktop`. Found: no copied overlay works for `rcp2026`; no conda/AnyGrasp env for `rcp2026`; `rcp-desktop/.venv` has working CUDA torch; `enp2s0`'s saved profile is `192.168.1.100`; `iot22` is still logged in (added §3 rule 4b). Phase 3 findings retagged in ORIENTATION and CODE_AUDIT. |
| 2026-09-11 | Claude (Opus 5) + Dion | Phases 1, 2, 4 (arm) done in `~/rcp-Gappler`; first Tier 3 test (`sim_moveit.sh`) passes. Recorded CPU throttling, the broken config simulated-arm launch (ORIENTATION §8.16), bench bugs P7–P9. Reports in `docs/bench-runs/`. |
| 2026-09-11 | Claude (Opus 5) + Dion | End of day: added **Start here** with Dion's decisions and the ordered work queue W1–W8 for the next session. Model files copied into `~/rcp-Gappler` (docs/ASSETS.md). Recorded the AnyGrasp env facts (numpy 1 vs 2, MinkowskiEngine) behind the one-env-first plan. |
| 2026-09-11 | Claude (Opus 5) + Dion | `docs/` renamed ``, later moved to `docs/` (per-person doc folders as more people join; rules in START_HERE). Paths here and in `bench/` updated; preflight's home scan skips any `*_docs/`. Root `.gitignore` extended for weights, recordings, archives, `*.swp`. |
| 2026-09-11 | Claude (Opus 5) + Dion | **W1 done** on the box (over tailscale): `.venv` rebuilt with uv; preflight `torch-cuda` uses the venv, `conda-anygrasp` → `anygrasp-env`, `aria-sdk` reports CLI crashes. Found setuptools 82 breaks the `aria` CLI; pin on branch `bench/w1-setuptools-pin` for review. Record: `bench-runs/2026-09-11-labbox-w1-venv.txt`. |
| 2026-09-11 | Claude (Opus 5) + Dion | **W4a done** (read-only): repo nav code is newer and equivalent; `robot_navigation` and `xpkg_demo` exist only in `iot22`'s workspace. Record in `bench-runs/`. |
| 2026-09-11 | Claude (Opus 5) + Dion | **W3 done**: `bench/estop_delivery.sh`. Ctrl+C key ignored by `estop.py` (new, B2a); SIGINT stop delivered 5/5 (B2 not reproduced on localhost) but exits via a double-shutdown traceback. |
| 2026-09-11 | Claude (Opus 5) + Dion | **W2 done**: full grasp cycle on the simulated arm, C7 reproduced. W5 test written, scratch MinkowskiEngine build under way (survey only). `~iot22/Ros2Workspaces` copied to `~/rcp-old-ros-wkspace`. Decisions recorded: W2 allowed (sim only), no fixes yet. |
| 2026-09-11 | Claude (Opus 5) + Dion | **W5 survey answered**: one uv env runs AnyGrasp (licence passed, demo grasps found) on torch 2.10 / numpy 2 — recipe in `bench-runs/`. Productising it is held. |
| 2026-09-11 | Claude (Opus 5) + Dion | Cold-start refresh: docs now at `docs/`; Start here rewritten (status table, held fixes, box facts), tailscale as the default route, §0 updated. |
| 2026-09-11 | Claude (Opus 5) + Dion | Box went offline (~19:40). On the Mac: **W4b prep** (`build.sh nav` Livox manifest + flags + SDK warning) and **W7 written** (`nav_nodes.sh`, 10 cases, 4 xfail); neither run. Decision: no contracts re-snapshot, no static baseline. |
| 2026-09-11 | Claude (Opus 5) + Dion | Preflight `aria-sdk` passed with the glasses unplugged (`aria auth check` exits 0 and prints "no devices connected"): now FAIL "no glasses connected". Test bench page rewritten in plain language, with a simulated-arm section. Wiring map: new tab "One grasp, start to finish". Confirmed CODE_AUDIT D1 (nothing publishes `/manipulator/release`) and corrected ORIENTATION §5, which said "voice → orchestrator". |
| 2026-09-12 | Claude (Opus 5) + Dion | Cold-start refresh: box still offline, so Start here now opens with "check it's up" and the run order (preflight, W4b, W7). Added the two pages and the writing decision. |
| 2026-09-13 | Claude (Opus 5) + Dion | New bench bug S3: YAML values that are filesystem paths are extracted as topics (`/home/iot22/maps/completed_map`). Found while inventorying the contract surface for CODE_AUDIT §K. |
| 2026-09-14 | Claude (Opus 5) + Dion | **The box came back up and the two written-but-unrun pieces both passed first time. Tiers 0–3 are now complete.** W4b nav build: 10/10 packages, 2 min 34 s, and **three prep expectations were wrong, all in the build's favour** — Livox-SDK2 is already installed on the box (no sudo blocker), `Livox-SDk2/` *is* built by colcon as plain CMake (correcting a `[code]` claim), and the bench's livox manifest is byte-identical to `iot22`'s. W7 nav nodes: 6 controls pass, 4 expected failures reproduced, 0 skipped, no fix needed — **E1, F1 and F2 move to `[observed]`**, J4 turns out to be a clean control (50/50 frames, 1.9 ms), and new finding **F4** (all five nav nodes traceback on Ctrl+C). Preflight's 2026-09-11 glasses fix confirmed FAILing on the box. What is left is a decision (W6), a person at the robot (W8), and the held findings. |
| 2026-09-14 | Claude (Opus 5) + Dion | **Camera: attempted, not done** ([`bench-runs/2026-09-14-labbox-w6-camera-attempt.txt`](bench-runs/2026-09-14-labbox-w6-camera-attempt.txt)). With Dion's go-ahead the RealSense driver was started on private channel 78. The D435i was **already faulty**: depth opened, colour died with `VIDIOC_S_FMT errno=5`. `initial_reset:=true` then took it off the USB bus entirely, so it needs a physical replug (approved for ~2 h later). No frames recorded, nothing moved, no process left running. **New bench bug S4, fixed the same session:** preflight's `realsense-usb` PASSED that morning on this very camera, because it only grepped `lsusb` — and it matched any "Intel" line, so the box's AX201 Bluetooth adapter alone would have passed it `[code]`. Now two checks: `realsense-usb` (strict on `8086:0b3a` or a "RealSense" description) and a new `realsense-stream` that grabs one frame through `v4l2-ctl`, scoped by sysfs to the RealSense's own nodes so a stray webcam cannot satisfy it, and reporting a busy device as SKIP rather than PASS or FAIL. Verified: both SKIP on the Mac, and on the box `realsense-usb` FAILs with a replug hint while `realsense-stream` SKIPs. **The pass path and the colour-dead path are untested** until the camera is back. |
| 2026-09-19 | Claude (Opus 5) + Dion | Added three read-only box checks to the top of "Start here", from T0.0: does the Aria calibration file parse, are these the same glasses, and does `env.sh` work in `~/rcp-Gappler`. |
| 2026-09-19 | Claude (Opus 5) + Dion | Replaced "no fixes without asking" with fixes on branches through a PR into `main`. |
| 2026-09-21 | Claude (Opus 5) + Dion | Ran the T0.0 box checks. Calibration parses and `env.sh` works, both `[observed]`. The glasses serial check is skipped and still owed. The three-check block in "Start here" now shows the results. Evidence in `bench-runs/2026-09-21-labbox-t0.0-box-checks.txt`. |
| 2026-09-21 | Claude (Opus 5) + Dion | T0.4: struck the "not in the repo" held finding. The Livox manifest moved from `bench/nodes/` into its package, and `bench/build.sh` copies it from there. |
| 2026-09-21 | Claude (Opus 5) + Dion | Contracts snapshot re-taken at `1461e72`: the 12 `robot_navigation` names and the new launch nodes added, the deleted `mtc_sim_test` launch removed. Decisions row updated. Added a "Next" block to "Start here" for T0.10 and T0.11: merge the PR, branch protection, the fork-PR risk of a self-hosted runner on a public repo, and `OWNED_PREFIXES` during the refactor. |
| 2026-09-21 | Claude (Opus 5) + Dion | Full bench L0-L4 on `main` @ `9bbb26a` on the box: L3 and every L4 script PASS. L1 failed on a bench bug: `contracts.py` and `static.py` read `build_nav/` and `install_nav/`, fixed. Robot checks moved out of L2 into a new L5 (`preflight.py --hardware`) that gates L6, the real arm test (was L5). An unplugged arm makes L5 and L6 SKIPPED, not FAIL. Neither is needed to merge. Evidence in `bench-runs/2026-09-21-labbox-full-bench-main.txt`. `next-steps-map.html` T0.11 text edited and republished. |
| 2026-09-21 | Claude (Opus 5) + Dion | **W5 done**: `envs/anygrasp/build.sh` rebuilds the AnyGrasp env from nothing, the SDK demo passes, L2 `anygrasp-env` is green. `estop_delivery.sh` control case made stable (0.5 s between keys) after it exposed a new finding, CODE_AUDIT B2c. B2's loss now observed. The `estop.py` fix is queued in "Start here". `build.sh` reuses built parts, `--clean` rebuilds. |
| 2026-09-21 | Claude (Opus 5) + Dion | CI and branches set up: `dev` is the default branch, `bench` runs on PRs and pushes to `main` and `dev`, both protected. Box pulls over SSH with a deploy key. "Next" block rewritten as the refactor plus the rest of T0.11. Fixes now go through a PR into `dev`. |
| 2026-09-21 | Claude (Opus 5) + Dion | "Start here" points to `NEXT_STEPS` §2.15, the reorg spec. |
| 2026-09-21 | Claude (Opus 5) + Dion | C1 fixed: the contract extractor reads config, so topics moved into YAML during the reorg stay visible. Contracts re-snapshotted, 13 Aria topics now show publishers. New L1 self-test `bench/test_contracts.py`. |
| 2026-09-21 | Claude (Opus 5) + Dion | Reorg step 3: current paths and build recipes point at `<subsystem>/vendor/`. Past run records (W5, the box survey) left as they were. |
| 2026-09-21 | Claude (Opus 5) + Dion | Pointer at the top to the old-to-new path table in `NEXT_STEPS` §2.15, after the reorg moved our code. |
| 2026-09-22 | Claude (Opus 5) + Dion | `OWNED_PREFIXES` replaced by the `is_owned` rule (not under `vendor/`), reorg step 6. |
| 2026-09-22 | Claude (Opus 5) + Dion | `env.sh` renamed `global_env.sh` (reorg step 7) in the current setup instruction. The 2026-09-21 check results keep the old name. |
| 2026-09-22 | Claude (Opus 5) + Dion | "Start here": the refactor is done and verified. Points at `./build.sh`, `global_env.sh` and the path table. |
| 2026-09-22 | Claude (Opus 5) + Dion | "Start here" opens with a cold-start block for finishing T0.11: branch `t0.11-ci-full-job`, the no-skips `full` job, what exists (both workflows, the runner in tmux, the cleaned runner copy with linked weights), the decided scope (fork-PR guard waived, suites deferred) and the gotchas. |
| 2026-09-22 | Claude (Opus 5) + Dion | T0.11 steps 1-2 done: `bench/run.sh --no-skips`, and the `full` job as a second job in `bench.yml`, which also took over the nightly schedule (`bench-nightly.yml` removed). Not yet run on the box. |
| 2026-09-22 | Claude (Opus 5) + Dion | T0.11: per-subsystem suites paused until a need arises (L0-L2 take about 30 s). T0.11 closes once `full` is required on `main` and has passed on a real `dev` into `main` PR. |
| 2026-09-22 | Claude (Opus 5) + Dion | AnyGrasp venv recipe moved from `envs/anygrasp/` into the grasp subsystem: `grasp/anygrasp_venv/build_anygrasp_venv.sh` and `anygrasp_requirements.txt`, venv at `grasp/anygrasp_venv/.venv`. `grasp_env.sh` now builds it on first use (Dion's choice, about 20 min). Also: L2 `hardcoded-homes` now skips `install_nav/`, `build_nav/`, `log_nav/`. It failed the first `full` run on vendor Livox files there. The W5 write-up below keeps the old path as history. |
