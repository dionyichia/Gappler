# TESTBENCH PLAN — handoff for the next session

**Purpose:** everything a fresh session needs to continue building the test bench, cold, without
re-deriving anything. Written 2026-09-11 at the end of the session that built `bench/` tiers 0–1 and
the preflight tier, and wrote [`CODE_AUDIT.md`](CODE_AUDIT.md).

**Where this sits:** [`START_HERE.md`](START_HERE.md) indexes all docs. [`ORIENTATION.md`](ORIENTATION.md)
is what the system *is*. [`NEXT_STEPS.md`](NEXT_STEPS.md) is the project-wide work register — its §2.6,
§2.6b and §2.7 point here. **This file is the detailed plan for the bench specifically.**

**Status tags** as elsewhere: `[code]` read from source · `[reported]` from the 2026-08-25 hardware
session · `[inferred]` reasoning · `[unverified]` found by static analysis, not confirmed at the machine.

---

## 0. State at handoff (2026-09-11)

| Thing | State |
|---|---|
| `bench/` tiers 0–1 (contracts + static) | **Built, working on macOS**, verified against a simulated refactor |
| `bench/preflight.py` (hardware/env tier) | **Built, run only on macOS.** P1–P5 fixed and unit-tested on the Mac (§4); new `home` group. Every Linux/hardware code path is still **unrun** |
| Tier 2 (build), Tier 3 (node behaviour), Tier 4 (replay + hw smoke) | **Not started.** Designed below. |
| `docs/CODE_AUDIT.md` | 45 findings, all `[unverified]`. Published privately: <https://claude.ai/code/artifact/63cc961e-e49a-4421-9132-fec0f3e35822> |
| SSH to the lab machine | **Works** — Dion installed the Mac's key for `rcp2026` on 2026-09-11. **Phase 0 done, read-only** (§1). Nothing written or launched on the box |
| Git | **Nothing committed.** See §2. |

---

## 1. Where things are

| What | Where | Confidence |
|---|---|---|
| Local clone (where `bench/` and `docs/` were written) | `/Users/Dion/sch_repo/Gappler` on Dion's Mac, branch `main` @ `2d36a89` + uncommitted work | `[code]` |
| GitHub remote | `git@github.com:dionyichia/Gappler.git` | `[code]` |
| Lab machine SSH | `ssh rcp2026@10.91.242.76` — key auth from the Mac works (2026-09-11). NTU LAN address, so NTU network / VPN only | observed |
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

## 2. Decisions Dion needs to make before the session starts

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
| P6 ✅ | `Path.exists()` **raises** `PermissionError` under a locked parent on Python < 3.12 (the box has 3.10.12) instead of returning False | `slam-map` and the new `home` check | as `rcp2026`, preflight would have **crashed** on `/home/iot22/...` (found 2026-09-11 by a `chmod 000` unit test) | `_exists()` treats unreachable as absent; `home` names the locked ancestor, e.g. `[no access: /home/iot22]` |

**Contracts extractor:**

| # | Gap | Evidence | Effect | Fix |
|---|---|---|---|---|
| C1 | **Every Aria-side publisher is invisible.** They are created via the `ROSPublisher` wrapper class (`src/services/ros/ros_publisher.py:14`) with topic names from `ROS2Topics`, an enum built from `shared/config.yaml` **at import time** — the AST resolver can see neither | `/aria/audio/prompt` shows `pub=0` in the golden file, yet `audio_streaming_pipeline.py:49` publishes it. Same for `/aria/rgb_camera/raw`, `/aria/imu`, … | the orphan report wrongly lists Aria topics as "subscribed, nobody publishes"; a rename on the Aria side will not be caught | teach `PyExtractor` two things: treat `ROSPublisher(name, MsgType, topic, ...)` as a publisher with the topic in arg 3; resolve `ROS2Topics.X.value` by loading `shared/config.yaml` (key = `X.lower()`). Then **re-snapshot** |
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

### Phase 1 — Get the bench onto the box

After Dion's decision in §2.1: commit + push from the Mac, then on the box
`git worktree add ~/bench_work/gappler main` (or a fresh clone) — **not** a pull into `rcp-desktop`.
~~Then fix P1–P3~~ — done on the Mac 2026-09-11 (§4); they ride along with the `bench/` commit.

### Phase 2 — Run preflight, read-only

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
| `livox_ros_driver2` has no ROS 2 manifest | `ls Navigation_Module/src/livox_ros_driver2/package*.xml` | ORIENTATION §8.15 |
| `xpkg_demo` missing | `ros2 pkg prefix xpkg_demo`; `find / -name 'xpkg_demo' -maxdepth 6 2>/dev/null` | ORIENTATION §8.6 |
| Which OpenVINS is authoritative | `ls ~/Ros2Workspaces/OpenVINS/install` | NEXT_STEPS §2.5 |
| Home pose on the box's checkout | `grep -A8 HOME_JOINTS <rcp-desktop>/ros2_robot_ws/src/rm_mtc/include/rm_mtc/mtc_planner.hpp` | CODE_AUDIT §B4 |
| Whether the box's code has the inverted gate | `sed -n 176,187p .../anygrasp_detection_node.py` | CODE_AUDIT §A1 |

The last two matter: if `rcp-desktop` is the Desktop/`realman_manip` clone, it may have different
home joints and different gate logic from what the audit read.

### Phase 4 — Tier 2: does it build (no hardware)

The lab box already has ROS 2 Humble, so **build natively there** rather than in Docker — Docker
on the Mac is the fallback for when the box is unavailable.

```bash
cd ~/bench_work/gappler
source /opt/ros/humble/setup.bash                      # only this — a stale overlay poisons the build
colcon build --build-base ~/bench_work/build --install-base ~/bench_work/install \
  --base-paths ros2_robot_ws/src deps_ws/src          2>&1 | tee ~/bench_work/build_arm.log
colcon build --build-base ~/bench_work/build_nav --install-base ~/bench_work/install_nav \
  --base-paths Navigation_Module/src                  2>&1 | tee ~/bench_work/build_nav.log
```

Add `bench/build.sh` wrapping this, with a pass/fail summary per package. Expected results:
arm workspace ~6 min, 24 packages, six benign stderr warnings (startup guide §2). `Navigation_Module`
**has never been built** — expect `livox_ros_driver2` to be invisible (ORIENTATION §8.15) and the
build to be discovery, not regression. Then extend `static.py`'s `launch-executables` check to read
the real `install/lib/<pkg>/` instead of parsing CMakeLists.

### Phase 5 — Tier 3: node behaviour against synthetic inputs

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
