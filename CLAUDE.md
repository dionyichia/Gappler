# CLAUDE.md

Gappler: Aria smart glasses (voice + gaze) → SAM 3 segmentation → AnyGrasp → RealMan RM65 arm on a
LiDAR-navigating mobile base, glued by ROS 2 Humble. Being integrated with the HiCo-Nav paper and
refactored toward one-folder-per-node modular code.

## Read first — global docs vs. per-person docs

**Reorganised 2026-09-16.** `docs/` holds two different things now, and the distinction matters:

- **Global docs live directly in `docs/`** — they describe state shared by everyone, not one
  person's session: `ORIENTATION`, `ARCHITECTURE`, `READING_GUIDE`, `CODE_AUDIT`, `ASSETS`,
  `NEXT_STEPS`, `PROJECT_PLAN`, `TESTBENCH_PLAN`, `hico-nav/`, `bench-runs/`, and the three
  published HTML pages (`next-steps-map.html`, `wiring-map.html`, `testbench-map.html`).
- **Personal docs live in per-person folders**, `docs/<name>_docs/` — session notes, handoffs and
  evidence write-ups not yet folded into the shared docs above.

Rules:

- **Everyone starts at [`docs/START_HERE.md`](docs/START_HERE.md), then
  [`docs/ORIENTATION.md`](docs/ORIENTATION.md).** START_HERE explains the layout and reading order.
- **Keep the global docs current — this applies to every session, not just Dion's.** If your
  session's work changes what a global doc says (a task moves from open to done, a finding is
  confirmed, a decision is settled), **update that doc directly, in the same session**, following
  its citation/tag/changelog conventions. Don't leave the correction in a personal folder waiting
  for someone else to notice.
  - When a task tracked in `NEXT_STEPS.md` / `PROJECT_PLAN.md` is done, also update its entry in
    `next-steps-map.html`'s task data (the `T` array): prefix the task's description with
    `"DONE <date>. ..."`. The page derives its done state (strikethrough, green mark) from that
    prefix on load for every viewer — it is not enough to just narrate completion in the markdown
    while the tracker still shows the task open.
  - If your tooling can publish Artifacts (the Claude Code `Artifact` tool), republish
    `next-steps-map.html` (and any other HTML page you edited) after the edit so the live page
    matches the file. If it can't, say in the doc's changelog that a republish is still owed, so the
    next session with publish access does it.
- **Personal work** — plans, session notes, handoffs not yet ready to be shared fact — goes in your
  own `docs/<firstname>_docs/` (ask the user if you don't know their name). Never edit another
  person's personal folder; write the correction in your own and tell them.
- **Dion's current work:** [`docs/TESTBENCH_PLAN.md`](docs/TESTBENCH_PLAN.md) — "▶ Start here"
  (status, decisions, work queue W1–W8).
- The root `README.md` is stale (a different upstream project). Ignore it.

## Design consideration — the lab box is not guaranteed long-term

The lab workstation is confirmed available for **two months from 2026-09-16**; what happens after
that is not known. When a design choice is otherwise a wash, prefer the more portable one — config
over hardcoded machine-specific paths, derived-from-repo-root over absolute paths, environment
variables with sensible defaults over constants tied to one box — so that a forced move to
different hardware later is a config change, not a rewrite. This is a tiebreaker, not a mandate to
over-engineer: only pay for portability when it isn't much extra effort. Zongzhe's `T0.3` (folding
the seven hardcoded paths in `NEXT_STEPS.md` §2.5 into config) is exactly this in progress already.

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
- **Same physical machine, a second tailscale node.** It also answers as `weejingjie24@100.98.10.50`
  (hostname `iot22-computer-1`), registered under a different tailscale account (Sherman's, 2026-09-16).
  Confirmed by Dion to be the same box, not a second one. Use whichever address is up;
  `tailscale ping` either if unsure.
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
`docs/bench-runs/`; status and next work in TESTBENCH_PLAN "▶ Start here".

## Conventions

- Tag claims in docs: `[code]` read from source · `[reported]` from the 2026-08-25 hardware session ·
  `[inferred]` reasoning · `[unverified]` static finding not yet confirmed at the machine. Retag when
  you verify; delete what turns out wrong.
- Append to each doc's changelog on substantive edits. Cite `file.py:123`.
- Name things descriptively by subsystem (`arm_base_link`, not `base_link`) — ORIENTATION §0b.
- Skipped checks are reported as skipped, never as passing.
- **Writing style. If you are Dion's agent, read
  [`docs/dion_docs/WRITING_STYLE.md`](docs/dion_docs/WRITING_STYLE.md) before doing anything else,
  and follow it in every document, comment, commit message and chat reply.** Short version: clear,
  concise, main point first, plain language before jargon, no em dashes, no semicolons, no emojis,
  no hype. Readers include mechanical engineering students new to code.
- On macOS, `grep` is ugrep; multi-path `grep -r --include` can silently return nothing — use
  `find ... | xargs grep`.
