# CLAUDE.md

Gappler: Aria smart glasses (voice + gaze) → SAM 3 segmentation → AnyGrasp → RealMan RM65 arm on a
LiDAR-navigating mobile base, glued by ROS 2 Humble. Being integrated with the HiCo-Nav paper and
refactored toward one-folder-per-node modular code.

## Read first — docs are per person

Several people work in this repo, each with their own Claude sessions. Docs live in per-person
folders under `docs/`: **`docs/<name>_docs/`**.

- **Everyone starts at [`docs/dion_docs/START_HERE.md`](docs/dion_docs/START_HERE.md), then
  [`docs/dion_docs/ORIENTATION.md`](docs/dion_docs/ORIENTATION.md).** START_HERE explains the layout and
  the reading order; `docs/dion_docs/` holds the shared reference (ORIENTATION, ARCHITECTURE,
  READING_GUIDE, CODE_AUDIT, ASSETS).
- **Plans, session notes and handoffs you write go in your user's own `docs/<firstname>_docs/`** (ask
  them if you don't know their name). Never edit another person's folder, and never put files
  directly in `docs/`.
- **Dion's current work:** [`docs/dion_docs/TESTBENCH_PLAN.md`](docs/dion_docs/TESTBENCH_PLAN.md) —
  "▶ Start here" (status, decisions, work queue W1–W8). Only yours if you are working with Dion on the bench.
- The root `README.md` is stale (a different upstream project). Ignore it.

## Safety — this code moves a real robot arm

- Never launch `grasp_state_machine`, `ros2_robot_ws/src/main.py`, `ros2_robot_ws/src/orchestrator.py`
  or root `main.py`. The state machine homes the arm within seconds, unprompted, to a home pose that
  has never been validated. **One exception (Dion, 2026-09-11):** `bench/state_machine_sim.sh` may
  launch the state machine against the *simulated* arm, behind its guards (mock hardware, private
  channel, no `rm_driver`, preflight shows the arm unreachable).
- Never publish to `/rm_driver/*_cmd`, `/goal_pose`, `/cmd_vel`, `/manipulation/*`, or
  `/object_centroid_2d` on the real ROS domain. Isolate tests with `ROS_DOMAIN_ID` + `ROS_LOCALHOST_ONLY=1`.
  Other users (`iot22`, and other people logged in as `rcp2026`) share the box; localhost-only does
  not separate you from their processes — a unique, empty domain id does.
- **No fixes yet** (Dion, 2026-09-11): survey, record findings, build tests. Fixes come later, on
  branches for review.

## The lab machine

- **Connect over tailscale** (works from anywhere): `ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60`.
  Check it's up with `tailscale ping 100.87.133.60`. The campus address `rcp2026@10.91.242.76` works only
  on the NTU network. Key auth from the Mac.
- **All work happens in `~/rcp-Gappler`** — a clone of Gappler `main`; build, test and commit there.
  `~/rcp-desktop` (`realman_manip`), `~/rcp-github` (`combined`) and `~/rcp-old-ros-wkspace` (copy of
  `iot22`'s nav workspace) are old code / reference: never modify them or their `install/` overlays.
  Don't touch `/home/iot22`; never set `PYTHONNOUSERSITE=1`; never `pip install --user`.
- MoveIt with `mock_components` (simulated arm) is allowed; anything with `rm_driver` is not.
- `/home` is nearly full (14 GB free on 2026-09-11) — check `df -h ~` before large builds or downloads.

## The bench

```bash
./bench/run.sh                         # preflight → static → contracts (any machine)
./bench/run.sh report                  # contract inventory + orphan analysis
python3 bench/contracts.py snapshot    # re-baseline after a deliberate contract change
# lab box only (ROS + the built overlay):
./bench/build.sh [nav]                 # Tier 2: colcon build into this checkout
./bench/sim_moveit.sh                  # Tier 3: MoveIt on a simulated arm
./bench/estop_delivery.sh              # Tier 3: does estop.py's stop message leave
./bench/state_machine_sim.sh           # Tier 3: grasp state machine on the simulated arm
./bench/nav_nodes.sh                   # Tier 3: the five nav nodes vs a mock Nav2 (nothing drives)
./bench/anygrasp_env.sh [PYTHON]       # can this env run AnyGrasp (imports + SDK demo)
```

Tiers 0–1 are stdlib-only and need no ROS. Run them before and after any refactor. When the reorg
moves code, update `OWNED_PREFIXES` in `bench/_common.py` (the one copy, shared by all three tools).
Every Tier 3 script refuses to start unless its ROS channel is private and empty. Results go in
`docs/dion_docs/bench-runs/`; status and next work in TESTBENCH_PLAN "▶ Start here".

## Conventions

- Tag claims in docs: `[code]` read from source · `[reported]` from the 2026-08-25 hardware session ·
  `[inferred]` reasoning · `[unverified]` static finding not yet confirmed at the machine. Retag when
  you verify; delete what turns out wrong.
- Append to each doc's changelog on substantive edits. Cite `file.py:123`.
- Name things descriptively by subsystem (`arm_base_link`, not `base_link`) — ORIENTATION §0b.
- Skipped checks are reported as skipped, never as passing.
- Dion's docs and pages: plain language, main point first, jargon only when needed and explained.
  Readers include mechanical engineering students new to code. No em dashes, semicolons or emojis.
- On macOS, `grep` is ugrep; multi-path `grep -r --include` can silently return nothing — use
  `find ... | xargs grep`.
