# NEXT STEPS — work register

Companion to [`ORIENTATION.md`](ORIENTATION.md) (what the system *is*),
[`ARCHITECTURE.md`](ARCHITECTURE.md) (diagrams) and [`READING_GUIDE.md`](READING_GUIDE.md) (a
guided walk through the code). **This file is what we intend to *do*.** Index:
[`START_HERE.md`](START_HERE.md).

It accumulates as we learn. ORIENTATION describes reality and should stay stable; this file is
allowed to churn. When an item is done, move it to §5 Done with a one-line outcome — don't delete
it, the reasoning is worth keeping.

Status tags: `[code]` verified by reading source · `[reported]` from the 2026-08-25 hardware
session · `[inferred]` reasoning, not fact · `[open]` genuinely undecided ·
`[unverified]` found mechanically by `bench/`, **not yet confirmed at the machine** (§2.6).

**Priority key:** 🔴 blocks other work · 🟠 needed for the HiCo-Nav milestone · 🟡 quality/debt

---

## 1. Decide before writing code

### 1.1 🔴 HiCo-Nav's RGB-D requirement — procurement lead time makes this urgent

> ✅ **Answered 2026-09-10 by reading the paper — see [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §6.1.**
> Confirmed, and stronger than assumed: the memory graph's nodes *are* RGB keyframes, so there is
> no camera-free variant. **Recommendation: buy a base-mounted RealSense D455** (not another
> D435i — wider FOV, longer depth range, and it is what the paper deployed). Option 2 (park the
> arm) is now rated worse than this item originally supposed — the paper's own small-object success
> rate falls to 65 % from vibration blur on a *rigidly* mounted camera. Option 3 (LiDAR only)
> discards the entire reason to adopt the paper. **Start the mount design in parallel with the
> purchase.** The original reasoning below is kept for the record.

`[open]` HiCo-Nav's Cognitive Memory Graph is understood to need a continuous forward-facing RGB-D
stream. This robot has **one** camera, a D435i on the arm's wrist (`Link6`), and
`Navigation_Module` is LiDAR-only. Options: buy a base-mounted D455 (~$400 + NTU lead time), park
the arm in a fixed observation pose, or substitute the 2D LiDAR scan and adapt the graph.

**Why it is first:** it is the only item whose wrong answer costs weeks rather than days. Raise
with Dr. Yuan before scoping anything else. See ORIENTATION §10.

### 1.2 🟠 Does HiCo-Nav emit goals or velocities?

> ✅ **Answered 2026-09-10 — [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §5.1.**
> **Velocities**, and more than that: the paper runs its own A\* global planner, trajectory
> optimiser and dynamic-obstacle controller, so it is a whole-stack replacement for Nav2, not a
> plugin swap. **But the binary was the wrong question.** The recommendation is a four-tier
> separation: take the frontier-scoring + WTRP goal-ordering layer (Tier A, emits `/goal_pose`,
> needs no camera, largest ablation contribution) and the memory graph + VLM reasoning (Tier B),
> and decline the motion layer (Tier C). That keeps Nav2 and both plugins exactly as they are.

`[open]` Determines the size of the whole integration:

- **Goals** (`/goal_pose`) → it sits beside `goal_reached_publisher.py`; Nav2 and both plugins stay.
- **Velocities** (`/cmd_vel`) → it replaces `RegulatedPurePursuitController` in the `FollowPath`
  slot and inherits the costmap/TF plumbing.

Answer by reading the paper. Plugin table in ORIENTATION §10.

### 1.3 🟠 Scope: how much does HiCo-Nav subsume?

> 🟡 **Narrowed 2026-09-10 — [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §5.3.**
> The CMG *can* become the source of `/manipulation/goal_pose` — it holds every object seen, with a
> 3D point cloud and a CLIP feature, queryable by language. It *cannot* replace the close-range
> SAM 3 → AnyGrasp path: its object geometry comes from a fast segmentation at navigation distance
> and precision. Expected split: the graph answers "which table", live perception answers "grip it
> here". That is a smaller change than this item feared. Still `[open]`: which of the seven contract
> topics change ownership.

`[open]` **This may shrink the work below substantially.** HiCo-Nav registers observed objects
into a memory graph. If that graph becomes the source of "where is the thing I was asked for",
then several things change at once:

- **Where the image comes from.** Today segmentation consumes live RealSense frames. With a memory
  graph, the object may already be *known* and localised from an earlier observation — no live
  segmentation needed at request time.
- **Where SAM is triggered** (see §2.1) — possibly by graph updates rather than by frames.
- **Whether `/manipulation/goal_pose` is still produced by perception at all**, or read out of the
  graph.

**Action:** read HiCo-Nav against ORIENTATION §5's contract-topic table and decide which of those
seven topics it takes over. Do this *before* investing in §2.1 or §2.2 — you may be rebuilding
something the paper already provides.

---

## 2. Architecture work

### 2.1 🟠 When should SAM3 inference run? (currently: every frame)

`[code]` Today `sam3_ros_node.rgb_depth_callback` runs full SAM3 inference on **every
synchronised RGB+depth pair**, against a hardcoded prompt. SAM3 is the most expensive thing in the
system (3.4 GB checkpoint). The other implementation has a related guard commented out
(`object_recognition_pipeline.py:323-324`), so it re-infers every Aria frame too.

There is no triggering *policy* anywhere — just "on frame".

Candidate approaches, cheapest first:

| Approach | Idea | Cost |
|---|---|---|
| **Prompt-gated** | Only run when a prompt is active, and stop once a stable mask is locked. Nearly free — this is what the commented-out guard at `:323-324` was probably for. | Trivial |
| **Two-stage** `[inferred]` | A lightweight always-on model does scene understanding; escalate to SAM3 only when something interesting appears. | Medium — needs a second model and an "interesting" criterion |
| **Graph-driven** | HiCo-Nav's memory graph decides when a region needs (re)segmenting. | Depends on §1.3 |
| **Event-driven** | Re-run on gaze dwell, or on significant scene change. | Low–medium |

⚠️ **Do not build the two-stage design before resolving §1.3.** If the memory graph already keeps
a registry of seen objects, it is likely the correct trigger source and a bespoke lightweight
stage would be wasted work. Scope first.

Whatever is chosen, add a **staleness bound** — see ORIENTATION §8.8: the consumer-side age guard
in `grasp_state_machine.cpp:637-641` is commented out, so SELECTING will happily servo toward a
centroid that stopped updating.

### 2.2 🟠 Unify segmentation into one inference service

`[code]` **The good news: the code is already shared.** There is exactly one `SAM3Model` class
(`src/services/object_recognition/sam3_model.py`), and `sam3_ros_node.py` **imports it from
`src/`** — which is why `ros2_robot_ws/src/main.py` launches it via
`uv run --project <repo root>` with `PYTHONPATH` pointing at `src/`. This is an
**ownership and lifecycle problem, not code duplication.**

What is actually duplicated:

| | `object_recognition_pipeline.py` | `sam3_ros_node.py` |
|---|---|---|
| Instantiates `SAM3Model` | `:89`, via `ModelPaths.SAM3_PATH` | `:58`, via a hardcoded absolute path (`:37`) |
| Prompt source | `/aria/audio/prompt` (voice) | `TEXT_PROMPT = "box"`, hardcoded (`:40`) |
| Gaze disambiguation | yes, `_find_closest_mask` | none |
| Cross-camera confirmation | yes, LightGlue | none |
| Cameras | Aria **and** RealSense | RealSense only |
| Publishes | `/camera/sam/mask`, `/object_centroid_2d`, `/object_centroid` (`:34-36`) — **call site commented out at `:384`** | the **same three topics** (`:30-32`) — live |

**Two concrete hazards:**

1. **Topic collision.** Both publish the identical three topics. Uncommenting `:384` while
   `sam3_ros_node` is running gives two publishers racing on `/object_centroid_2d`, and the state
   machine consuming whichever arrives last. *(This is the answer to Round 2 check-question 1.)*
2. **Two model loads.** Two processes × 3.4 GB checkpoint, each with its own CUDA context, because
   `spawn` gives every child a fresh interpreter.

`[inferred]` This was never integrated, not deliberately designed — `sam3_ros_node.py` looks like a
standalone stopgap so the arm could be tested without the Aria stack.

**Target:** one segmentation service that owns the model, accepts a prompt + a camera source, and
is the sole publisher of the mask/centroid topics. Both current call sites become clients.

**Sequencing:** settle §1.3 and §2.1 first — the trigger policy and the source of truth for object
identity both change what this service's interface should be. Unifying now and re-doing it after
the HiCo-Nav scope lands would be wasted effort.

### 2.3 🟡 `dummy_mask_publisher.py` no longer works

`[code]` It publishes to `/PLACEHOLDER/sam/mask` (`:14`), but every consumer now subscribes to
`/camera/sam/mask` (`anygrasp_detection_node.py:42`, `anygrasp_node.py:35`). The topic names
drifted and the stand-in was left behind. Since this is the tool for testing the arm **without**
the perception stack, it is worth 30 seconds to fix — retarget it to `/camera/sam/mask`. Note
`docs/SETUP.md` on `realman_manip` still describes it as the working bridge.

### 2.4 🟡 Naming cleanup — do it in one deliberate pass, not opportunistically

`[code]` The audit in ORIENTATION §0b found nine name collisions and two defects already caused by
them. Renaming is cheap individually but **risky piecemeal**: ROS matches topic and frame names as
plain strings at runtime, so a rename that misses one occurrence fails silently on the robot
rather than at build time.

Do it as one pass, with `grep -rn` on each old string, and land it as its own commit so it can be
reverted cleanly. Suggested order — cheapest and safest first:

1. **Fix the two live defects.** `dummy_mask_publisher.py:14` → `/camera/sam/mask` (this is §2.3).
   Correct the wrong frame name in the `goto_glasses.py:35` comment.
2. **Collapse the duplicated constants** (§8.10). Start with `VIDEO_QOS`, the one that has already
   drifted. Then `TOPIC_MASK` into one shared perception-constants module, and have
   `sam3_ros_node.py` import `ModelPaths.SAM3_PATH` instead of its own absolute path — that also
   knocks out one of the seven hardcoded paths in §3.4.
3. **Unify the `/manipulation/` vs `/manipulator/` prefix** (§0b case 3). Five topics, one of them
   already commented out. Do it *before* restoring seam §6.3, so the return leg is wired with the
   final names.
4. **Fix the undefined frame** `camera_rgb` (ORIENTATION §8.11) — `/aria/aruco_pose` is stamped
   with a frame nothing defines or publishes. Decide what it should be (`aria_rgb_camera_frame`)
   and whether a transform for it needs publishing. Currently masked by seam §6.1, so it must be
   settled **before** that seam is restored or the return leg will fail for a second reason.
5. **Rename the frames** — `base_link` → `arm_base_link`, `robot_base_link` → `mobile_base_link`.
   **Leave this until last.** It touches URDFs, launch files, C++ and Python, and while it is the
   most valuable rename it is also the only one that can break the arm's motion planning. Do it
   when someone is physically at the robot, not remotely.

⚠️ Wait on the HiCo-Nav scoping decision (§1.3) before renaming any of the seven contract topics —
if HiCo-Nav takes some of them over, their names are its business, not ours.

### 2.5 🔴 Paths and environment assumptions — nothing runs on a fresh clone

`[code]` **Surveyed 2026-09-10 after a fresh clone. This is worse than "seven wrong paths".**

The hardcoded paths assume the repo lives at
`/home/iot22/GitHub/Renaissance-Capstone-Project/`. The current clone is at
`/Users/Dion/sch_repo/Gappler/` — **a different user, a different parent directory, and a
different repository name.** So even another clone by the original author on the original machine
would not match. Every one of these is broken, not just mis-owned.

#### What breaks, in full

**Group A — points inside the repo. Should be derived, never configured.**

| File:line | Constant | Points at |
|---|---|---|
| `main.py:18` | `ARIA_PYTHON` | the venv's Python interpreter |
| `ros2_robot_ws/src/orchestrator.py:23` | `MAIN_PY_DIR` | `ros2_robot_ws/src` |
| `ros2_robot_ws/src/main.py:29` | `ANYGRASP_DIR` | `rm_mtc/src/perception` |
| `ros2_robot_ws/src/main.py:36` | `SAM3_PROJECT_ROOT` | the repo root |
| `ros2_robot_ws/src/main.py:41` | `SAM3_WORK_DIR` | `src/services/object_recognition` |
| `ros2_robot_ws/src/main.py:120` | `PYTHONPATH` | `src/` |
| `sam3_ros_node.py:38` | `SAM3_CHECKPOINT` | the SAM3 weights |
| `sam3_ros_node.py:4` | *(docstring)* | states the venv root as fact |
| `sam3_model.py:91,96` | demo block | weights + a test image |
| `ros2_robot_ws/install.sh:4-5` | `DEPS_WS`, `ROBOT_WS` | uses `$HOME` but still the old repo name |

Every one of these is a fixed offset from the repo root. `src/config/base.py` **already computes
`Settings.PROJECT_ROOT` correctly** and `config/models.py:11` already uses it — that pattern just
was never applied outside `src/`.

**Group B — points outside the repo. Genuinely needs configuration.**

| File:line | Points at | Note |
|---|---|---|
| `src/main.py:303-304` | `~/Ros2Workspaces/OpenVINS/install/…` | an **entire external ROS workspace** — see below |
| `src/main.py:331` | `~/Ros2Workspaces/OpenVINS/src/…/display_ros2.rviz` | RViz layout from that same external workspace |
| `src/main.py:306` | `…/src/services/aria_device/calibration/estimator_config.yaml` | in-repo (Group A), but passed *to* the external binary |
| `slam_toolbox_localization.yaml:14` | `/home/iot22/maps/completed_map` | the saved map — a build artefact, correctly outside the repo |
| `slam_mapping.launch.py:30` | `~/maps/current_map` | where map autosave writes |
| `ros2_robot_ws/src/main.py:28` | conda env named `anygrasp` | environment name, not a path, same class of assumption |
| `ros2_robot_ws/src/main.py:30` | `log/checkpoint_detection.tar` | relative to `ANYGRASP_DIR`; the weights are gitignored |

**Group C — vendor code, leave alone.** `rm_install/scripts/*.sh` use `/home/$USERNAME/`, which is
already parameterised. `rm_driver.cpp:114` is a commented-out line with a stranger's name in it.

#### ⚠️ The finding that is not about paths

`[code]` `src/main.py:303` launches OpenVINS from `~/Ros2Workspaces/OpenVINS/install/` — an
external workspace **that is not in this repo**. Meanwhile the repo *vendors* OpenVINS source at
`Navigation_Module/OpenVINS/`, which **has never been built** (no `install/` anywhere).

So there are two OpenVINS in play: a vendored copy nobody has compiled, and a compiled copy that
exists only on the lab machine. **Decide which is authoritative before touching these paths** — if
the vendored one is, this becomes a Group A path and a build step. If the external one is, it joins
`xpkg_demo` (§3.1) on the list of things this repo needs but does not contain.

#### Recommended approach

Matches the in-code preference at `ros2_robot_ws/src/main.py:26` ("switch to config declared at
main"), with one refinement — **the two groups want different treatment:**

1. **Group A: derive, do not configure.** One `paths.py` at the repo root that computes
   `REPO_ROOT = Path(__file__).resolve().parent` and exposes the handful of derived paths. Making
   these configurable would just be a way to get them wrong. Extend the existing
   `Settings.PROJECT_ROOT` rather than inventing a second mechanism.
2. **Group B: one config file, committed with sensible defaults, overridable per machine.** These
   genuinely differ between machines. Environment variables with defaults would also work and suit
   ROS conventions better.
3. **Delete rather than fix** where possible — the `sam3_model.py` demo block and the
   `sam3_ros_node.py` docstring claim are dead weight either way.
4. **Fold in the duplicated-constant work from §2.4** while you are here: `SAM3_CHECKPOINT` should
   import `ModelPaths.SAM3_PATH` instead of being a second definition of the same value.

`[open]` **Not yet decided:** whether a config file or environment variables. Config file is easier
to discover and document; env vars compose better with ROS launch files and `conda run`. Worth
deciding when someone can test both against the real launch sequence.

#### Why this is 🔴

It is not a tidiness item any more. **On a fresh clone, `main.py`, `orchestrator.py`,
`ros2_robot_ws/src/main.py` and `sam3_ros_node.py` all fail immediately** — so no amount of reading
gets you to a running system, and none of the bring-up work in §3 can start. It also blocks having
a second machine, which blocks anyone else on the team running anything.

---

**AnyGrasp does not need its own conda env** `[observed]` 2026-09-11 (TESTBENCH_PLAN W5): the project uv env plus
MinkowskiEngine, pointnet2 and graspnetAPI's runtime packages ran the SDK demo with the licence passing, on torch
2.10 / numpy 2. Yet `ros2_robot_ws/src/main.py:26-28` still launches the node with `conda run -n anygrasp` from
`/home/iot22/...`. When this section is fixed, the AnyGrasp launch should use the project env — recipe in
[`bench-runs/2026-09-11-labbox-w5-anygrasp-env.txt`](bench-runs/2026-09-11-labbox-w5-anygrasp-env.txt).

### 2.6 🟠 Verify the four `[unverified]` findings at the machine

`[unverified]` `bench/` found these by static analysis on 2026-09-10. **Nobody has confirmed any of
them against the running system.** Each is cheap to check and each changes a plan if true. Do these
in the first ten minutes of the next lab session, before anything else — they are all read-only.

| # | Finding | Check | If true |
|---|---|---|---|
| 1 | `mtc_sim_test.launch.py` names an executable `rm_mtc` does not build (ORIENTATION §8.12) | `ros2 launch rm_mtc mtc_sim_test.launch.py` | The project has no hardware-free MoveIt test. Wire up `trivial_mtc.cpp`, or delete the launch file. |
| 2 | Arm needs host `.10`, LiDAR needs host `.5`, one NIC (§8.13) | `ip -4 addr show enp2s0`, then ping both devices powered | Needs an IP alias **and a switch**. Blocks ever running nav + manipulation together. Raise with whoever set up the base. |
| 3 | `main` launches an AnyGrasp node/checkpoint that was never verified (§8.14) | `ls .../perception/log/` — is `checkpoint_detection.tar` even there? | Decide which node is authoritative before closing seam §6.2. |
| 4 | `livox_ros_driver2` has no ROS 2 manifest, so §3.2 cannot compile (§8.15) | `ls Navigation_Module/src/livox_ros_driver2/package*.xml` | Commit `package_ROS2.xml` from upstream. Unblocks §3.2. |

`bench/preflight.py` automates 2, 3 and 4; `bench/static.py` automates 1 and 4.
**Retag them in ORIENTATION when you settle them** — a stale `[unverified]` is worse than none.

---

### 2.6b 🔴 Work through `CODE_AUDIT.md`

`[unverified]` A line-by-line read of all ~10,600 lines we own, done 2026-09-10 — see
[`CODE_AUDIT.md`](CODE_AUDIT.md). 45 findings, none confirmed against running hardware.

**The headline: the grasp path cannot work as written**, for three interlocking reasons —
`anygrasp_detection_node.py:182` gates detection to run *only when IDLE* (inverted against its own
docstring), `grasp_state_machine.cpp:171` accepts candidates *only when EXECUTING*, and
`USE_SIMPLE_EXECUTE = true` (`:41`) makes the whole candidate path dead code so neither is visible.
AnyGrasp's output is currently unused at runtime. **Flipping that flag to enable "real" grasping
will fail 100 % of the time** until the gate is fixed.

Sequenced by what blocks what:

| Order | Do | Audit § |
|---|---|---|
| 1 | Settle the six open questions — several are decisions, not fixes | §"Open questions" |
| 2 | Safety: the phantom `q` key (`main.py:67`), the e-stop's missing delivery delay, the changed `HOME_JOINTS` | B1, B2, B4 |
| 3 | Fix the double `background.launch.py` launch — two `rm_driver` on one arm | I1 |
| 4 | The `/pipeline_state` gate inversion, and decide on `USE_SIMPLE_EXECUTE` | A1–A3 |
| 5 | Concurrency in `grasp_state_machine.cpp` — the two-mutex condvar and the unlocked centroid read are undefined behaviour, not style | C1–C7 |
| 6 | The deadlock paths in `goal_reached_publisher` / `object_approach_node` | F1–F3 |
| 7 | Frames: `/aria/fused_pose` is `robot_base_link` and its only consumer assumes `map` | E1, E2 |

⚠️ **Do the safety items before the first hardware run, not after.** Everything else can wait for a
bench session.

---

### 2.7 🟡 `bench/` — the offline regression bench

> ➡️ **Continuing this work? Start at [`TESTBENCH_PLAN.md`](TESTBENCH_PLAN.md)** — the detailed
> handoff (2026-09-11). It records three preflight bugs that only show on Linux (rate and TF checks
> always false-fail; the IP check substring-matches `.10` against `.100`), the contracts extractor's
> blind spot for every Aria-side publisher, and the plan: establish which machine and clone
> `rcp2026@10.91.242.76` actually is → get the bench onto it → preflight → verify the
> `[unverified]` findings → build → node-behaviour tests (domain-isolated, simulated arm) → replay.
> SSH was reported up on 2026-09-11; nothing has been run on the lab machine yet.

`[code]` Added 2026-09-10. Stdlib-only, no ROS, no hardware, ~1 s.

```bash
./bench/run.sh              # preflight -> static checks -> contract diff
./bench/run.sh preflight    # environment + hardware only
./bench/run.sh report       # contract inventory + orphan analysis
python3 bench/contracts.py snapshot   # re-baseline after a deliberate change
```

**Why it exists:** every seam in this system is a string — topic name, frame name, param key,
package name, file path — and ROS binds them at runtime by literal match. A rename applied to four
call sites out of five compiles, launches, and silently does nothing. §2.4 and the §0b audit are
both descriptions of that failure mode having already happened. The bench freezes those strings so
a refactor that moves one fails loudly.

It is **keyed by contract, not by file location**, so the reorg planned below (one folder per node,
services pulled out of nested packages) shows moved files as informational and only fails on a
contract that actually changed.

**It does not test behaviour and cannot.** There is no hardware here, and for much of this system
there is no observed behaviour to regress against — the arm has never been commanded to move. Every
run ends with an explicit list of what could not be checked and why. See `bench/README.md`.

⚠️ **When the reorg moves code, update `OWNED_PREFIXES` in `bench/contracts.py` and
`bench/static.py`** — otherwise moved files get classified as vendor and stop failing the build.

**Next tiers, not yet built:** a `ros:humble` container that runs `colcon build` (needed before
touching the 802-line `grasp_state_machine.cpp`), then node-level tests driving synthetic inputs
against a mock `rm_driver`, then replay against a rosbag recorded on the lab machine.

---

### 2.8 🟡 One folder for model weights — `assets/models/`

Dion, 2026-09-11. Model files are scattered: `src/models/sam3/sam3.pt`, and the AnyGrasp checkpoints
under `ros2_robot_ws/src/rm_mtc/src/perception/log/` — ignored only because of a catch-all `log`
rule. Move them to `assets/models/{sam3,anygrasp}/`, gitignore that folder explicitly, keep the
checksum list in [`ASSETS.md`](ASSETS.md), and make the code read one configurable path (ties into
§2.5). Do it with the modular reorg, not before: `preflight.py`'s `assets` group must move with it.

### 2.9 🔴 Important state lives outside git — decide what is needed, then bring it in

Dion, 2026-09-11. Things the robot needs were kept in folders no repo tracks. When `iot22`'s two
project clones were copied to `rcp2026` and pushed, everything outside them was left behind — and
some of it is what actually ran. **Nothing is fixed yet;** this is the list to work from.

`[observed]` `~iot22/Ros2Workspaces` (the base's navigation workspace) is a git repo with **no
commits and no remote** — everything in it was only ever staged. It is now copied whole to
**`~/rcp-old-ros-wkspace`** on the lab box (4.5 GB, 2026-09-11) so `rcp2026` has it. Its `install/`
is built against `/home/iot22/Ros2Workspaces/install`, so it is reference, not something to run.

| What | Where now | Size | Needed? `[inferred]` unless tagged |
|---|---|---|---|
| `robot_navigation` (Nav2 launch + `nav2_params.yaml`) | `~/rcp-old-ros-wkspace/src/` | 32 KB | **Yes** — the base's navigation launch; not in this repo at all |
| `xpkg_demo` (`demo/demo_general_chassis`, includes `bringup_basic_ctrl.launch.py`) | same, `src/demo/` | 328 KB | **Yes** — both SLAM launches and `robot_navigation` include it (§3.1) |
| livox generated `package.xml` (ROS 2 format) | same, `src/livox_ros_driver2/` | 1 file | **Yes** — without it colcon can't see the package (§3.2) |
| SLAM map `completed_map.*` | `~iot22/maps/` | small | **Yes**, for localisation — or re-map |
| `robot_slam`, `simple_teleop`, `echo_plus_driver`, `base`, `drivers`, `urdf`, `Livox-SDk2` | same | — | Already in the repo; the repo's copies are newer and equivalent (W4a) |
| OpenVINS workspace | same, `OpenVINS/` | 3.2 GB | Unclear — which OpenVINS is authoritative is open (§2.5); keep as reference |
| Orbbec camera driver (`orbbec_camera*` in `install/`) | same | — | Unknown — nobody has mentioned an Orbbec camera; ask |
| MoveIt / MTC source builds in `install/` | same | — | No — MoveIt comes from apt; MTC is in `deps_ws/` |
| `build/`, `log/` | same | 700 MB | No |
| AnyGrasp conda env, `~/.local` CUDA torch | `~iot22/` | GBs | No — replaced by the uv env (W1, W5) |
| `~/.aria` certificates | `~iot22/` | small | Covered — `aria auth check` already passes for `rcp2026` |
| `sdk_echo_plus_ws` (Echo Plus SDK, `xpkg_demo`'s origin) | `~iot22/` | — | Possibly — compare with `src/demo/` before importing |
| Isaac Sim (+ 8.7 GB zip) | `~iot22/` | ~9+ GB | No, unless simulation work starts |

**When fixing:** bring the "Yes" rows into this repo (a branch for review — robot code), gitignore the
generated/large ones, record the rest in [`ASSETS.md`](ASSETS.md), and after that nothing the robot
needs should live only in someone's home folder.

## 3. Bring-up (needs the lab machine)

### 3.1 🔴 Find `xpkg_demo` — `Navigation_Module` cannot launch without it

`[code]` Both SLAM launch files include `bringup_basic_ctrl.launch.py` from a package `xpkg_demo`
that is **not in this repo** (declared `exec_depend` in `robot_slam/package.xml:12`). `[inferred]`
it is the Echo Plus vehicle/power/comm bring-up. `colcon build` may pass — it is an *exec*
dependency — but launching will fail. **Ask whoever set up the base before booking machine time.**

> **Found 2026-09-11** `[observed]`: in `~iot22/Ros2Workspaces/src/demo/` (never committed, no remote); now also in
> `~/rcp-old-ros-wkspace/src/demo/` on the lab box. Bringing it into this repo is part of §2.9.

### 3.2 🟠 Build `Navigation_Module` (8 packages, never built)

No `install/` exists for it anywhere. Pure compile, touches no hardware, safe remotely. Blocked on
3.1 for actually *running* it, but the build itself is independent and worth doing first.

⚠️ `[unverified]` **There is a second blocker, and it stops the build rather than the launch.**
`livox_ros_driver2/build.sh:50` generates `package.xml` from `package_ROS2.xml`; the repo ships only
`package_ROS1.xml` and gitignores the result, so colcon cannot see the package at all. See
ORIENTATION §8.15 and §2.6 item 4. Check `ls Navigation_Module/src/livox_ros_driver2/package*.xml`
on the lab clone before booking time for this.

### 3.3 🟡 Consolidate the `realman_manip` docs onto `main`

`[code]` **Scoped 2026-09-10 by a full branch audit — see ORIENTATION §7.** It is a file copy, not a
merge: the branches have no common ancestor, and `main` is later than `realman_manip` on every
shared arm file. **No code should come across.**

```bash
git checkout origin/realman_manip -- \
    RCP_NEW_USER_STARTUP_GUIDE.md docs/SETUP.md env.sh calibration.json
```

`env.sh` needs its `REPO_ROOT` re-pointed and its assumption of a repo-root `install/` re-checked
on this clone. `calibration.json` is the Aria factory calibration dump for device
`1WM10350101291` — `main` has only the derived kalibr chains, and it doubles as an offline test
fixture for calibration parsing.

⚠️ **Do not take `sensors_3d.yaml`.** It looks like a gain (`+25/-1`) but is Setup Assistant
boilerplate pointing at a PR2 Kinect topic that does not exist here. ORIENTATION §7.

### 3.4 Path portability — **moved to §2.5**

Promoted out of bring-up and re-scoped after a fresh-clone survey: it is a 🔴 blocker, not a
tidiness item, and it does not need the lab machine. See §2.5.

---

## 4. Restoring the severed seams

⚠️ **One at a time, so failures are attributable.** All four are described in ORIENTATION §6.

| Seam | Restore for the HiCo-Nav milestone? | Note |
|---|---|---|
| §6.1 Aria stages disabled | **Partly** — pose/image streaming yes (`/aria/fused_pose` feeds the return leg) | Restoring will surface whatever made someone disable them |
| §6.2 mask never reaches robot | **Not required** for nav integration | Needed for the thesis demo. Do §2.2 first or you get the topic collision above |
| §6.3 orchestrator return leg | **Yes** — it is the nav↔manipulation handshake | Small: uncomment two subscriptions |
| §6.4 pose fusion ≠ its README | **Yes** — blocks "return to user" | Decide: restore VIO fusion, or accept ArUco-only and fix the frame + docs |

---

## 5. Done

*(nothing yet — move items here with their outcome as they complete)*

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-11 | Claude (Opus 5) + Dion | Added the pointer under §2.7 to the new `TESTBENCH_PLAN.md` handoff, and a root `CLAUDE.md` so a fresh session loads context automatically. |
| 2026-09-10 | Claude (Opus 5) + Dion | Added §2.6b pointing at the new `CODE_AUDIT.md` — a line-by-line read of all owned code. Headline finding: the grasp path cannot work, for three interlocking reasons. |
| 2026-09-10 | Claude (Opus 5) + Dion | Added `bench/` (§2.7) and §2.6, the four `[unverified]` findings to confirm at the machine. Scoped §3.3 from a full branch audit — it is a four-file copy, no code, and `sensors_3d.yaml` must not come across. Added the second `Navigation_Module` build blocker to §3.2. |
| 2026-09-10 | Claude (Opus 5) + Dion | Surveyed every hardcoded path on a fresh clone and promoted it to §2.5 as a 🔴 blocker (old §3.4 now a pointer). Found the repo was renamed *and* moved, so no path matches; and that `src/main.py` launches OpenVINS from an external workspace while the repo vendors an unbuilt copy. Added the `camera_rgb` undefined frame to the §2.4 naming pass. |
| 2026-09-10 | Claude (Opus 5) + Dion | HiCo-Nav paper read. §1.1 and §1.2 answered, §1.3 narrowed — see `hico-nav/PAPER_REPORT.md`. Three previously unrecorded dependencies surfaced there (FAST-LIVO2 localisation, LiDAR↔camera extrinsic calibration, VLM endpoint choice); they are not yet folded into this register. |
| 2026-09-10 | Claude (Opus 5) + Dion | Added §2.4, the naming cleanup pass, sequenced so the frame rename (highest value, highest risk) comes last and after the HiCo-Nav scoping decision. |
| 2026-09-10 | Claude (Opus 5) + Dion | Created. Seeded with the HiCo-Nav scoping decisions, the SAM3 triggering-policy question (§2.1), the segmentation-unification item (§2.2), the broken dummy mask publisher (§2.3), and the bring-up blockers. |
| 2026-09-11 | Claude (Opus 5) + Dion | Added §2.8: one `assets/models/` folder for model weights (see ASSETS.md). |
| 2026-09-11 | Claude (Opus 5) + Dion | Added §2.9: important state outside git, with a keep/drop list; `~iot22/Ros2Workspaces` (never committed) copied to `~/rcp-old-ros-wkspace`. §3.1: `xpkg_demo` found. |
| 2026-09-11 | Claude (Opus 5) + Dion | §2.5: AnyGrasp runs in the project uv env (W5); the `conda run` launch in `main.py` is now the only reason for conda. |
