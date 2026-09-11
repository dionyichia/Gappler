# CLAUDE.md

Gappler: Aria smart glasses (voice + gaze) → SAM 3 segmentation → AnyGrasp → RealMan RM65 arm on a
LiDAR-navigating mobile base, glued by ROS 2 Humble. Being integrated with the HiCo-Nav paper and
refactored toward one-folder-per-node modular code.

## Read first — docs are per person

Several people work in this repo, each with their own Claude sessions. Docs live in per-person
folders at the repo root: **`<name>_docs/`**.

- **Everyone starts at [`docs/dion_docs/START_HERE.md`](docs/dion_docs/START_HERE.md), then
  [`docs/dion_docs/ORIENTATION.md`](docs/dion_docs/ORIENTATION.md).** START_HERE explains the layout and the
  reading order; `docs/dion_docs/` holds the shared reference (ORIENTATION, ARCHITECTURE, READING_GUIDE,
  CODE_AUDIT, ASSETS).
- **Plans, session notes and handoffs you write go in your user's own `<firstname>_docs/`** (ask
  them if you don't know their name). Never edit another person's `*_docs/` folder, and never create
  a bare `docs/`.
- **Dion's current work:** [`docs/dion_docs/TESTBENCH_PLAN.md`](docs/dion_docs/TESTBENCH_PLAN.md) — "▶ Start
  here" (decisions + work queue W1–W8). Only yours if you are working with Dion on the bench.
- The root `README.md` is stale (a different upstream project). Ignore it.

## Safety — this code moves a real robot arm

- Never launch `grasp_state_machine`, `ros2_robot_ws/src/main.py`, `ros2_robot_ws/src/orchestrator.py`
  or root `main.py`. The state machine homes the arm within seconds, unprompted, to a home pose that
  has never been validated. **One exception (Dion, 2026-09-11):** `bench/state_machine_sim.sh` may launch the
  state machine against the *simulated* arm, behind its guards (mock hardware, private channel, no
  `rm_driver`, preflight shows the arm unreachable).
- Never publish to `/rm_driver/*_cmd`, `/goal_pose`, `/cmd_vel`, `/manipulation/*`, or
  `/object_centroid_2d` on the real ROS domain. Isolate tests with `ROS_DOMAIN_ID` + `ROS_LOCALHOST_ONLY=1`.
  `iot22` shares the box, and localhost-only does not separate you from its processes; the unique
  domain id does.
- On the lab machine (`ssh rcp2026@10.91.242.76`, key auth from the Mac; off the NTU network use tailscale:
  `ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60`): **all work happens in
  `~/rcp-Gappler`** — a clone of Gappler `main` created 2026-09-11; build, test and commit there.
  `~/rcp-desktop` (`realman_manip`) and `~/rcp-github` (`combined`) are old code: never modify
  them or their `install/` overlays. Don't touch `~/.local` or `/home/iot22`; never set `PYTHONNOUSERSITE=1`.
  MoveIt with `mock_components` (simulated arm) is allowed; anything with `rm_driver` is not.

## The bench

```bash
./bench/run.sh                         # preflight → static → contracts
./bench/run.sh report                  # contract inventory + orphan analysis
python3 bench/contracts.py snapshot    # re-baseline after a deliberate contract change
```

Stdlib-only; no ROS needed except for preflight's live-graph checks. Run it before and after any
refactor. When the reorg moves code, update `OWNED_PREFIXES` in `bench/_common.py` (the one
copy, shared by all three tools). Known bugs to fix first are in TESTBENCH_PLAN §4.

## Conventions

- Tag claims in docs: `[code]` read from source · `[reported]` from the 2026-08-25 hardware session ·
  `[inferred]` reasoning · `[unverified]` static finding not yet confirmed at the machine. Retag when
  you verify; delete what turns out wrong.
- Append to each doc's changelog on substantive edits. Cite `file.py:123`.
- Name things descriptively by subsystem (`arm_base_link`, not `base_link`) — ORIENTATION §0b.
- Skipped checks are reported as skipped, never as passing.
- On macOS, `grep` is ugrep; multi-path `grep -r --include` can silently return nothing — use
  `find ... | xargs grep`.
