# NEXT STEPS — work register

> **Paths moved 2026-09-21 (reorg).** Many cites below use the old layout (`src/`, `ros2_robot_ws/`,
> `Navigation_Module/`). Look up the new path in §2.15 of this file,
> "Where things moved". Line numbers inside moved files did not change with the move.


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

> ➡️ **This file is the register of everything we *could* do. What we *will* do, in what order and
> who owns it, is now in [`PROJECT_PLAN.md`](PROJECT_PLAN.md)** — 11 milestones and 70 tasks, mapped
> onto the real capstone calendar from 2026-09-14 to 2027-04-18 (recess, exam period and winter break
> excluded, the four official deadlines marked), with the three-way split validated, the scope
> written down, and the cut list decided in advance. Visual version:
> [`next-steps-map.html`](next-steps-map.html)
> (<https://claude.ai/code/artifact/65c7784d-1284-4ebd-a481-43951f8ce676>). Items here map onto task
> IDs there — for example §2.5 is T0.3, §2.9 is T0.4, §2.2 is T2.0 and T2.1, §3.2 is T3.1, and
> §3.3 is **T0.0, done 2026-09-21**.

---

## 1. Decide before writing code

### 1.1 🔴 HiCo-Nav's RGB-D requirement — D455 provided, stream verification still urgent

> ✅ **Answered 2026-09-10 by reading the paper — see [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §6.1.**
> Confirmed, and stronger than assumed: the memory graph's nodes *are* RGB keyframes, so there is
> no camera-free variant. **Recommendation: use a base-mounted RealSense D455** (not another
> D435i — wider FOV, longer depth range, and it is what the paper deployed). An Intel RealSense D455
> is now provided to the project, but its USB 3 connection and live RGB-D stream remain unverified. Option 2 (park the
> arm) is now rated worse than this item originally supposed — the paper's own small-object success
> rate falls to 65 % from vibration blur on a *rigidly* mounted camera. Option 3 (LiDAR only)
> discards the entire reason to adopt the paper. **Verify the provided D455 before mount fabrication.**
> The original reasoning below is kept for the record.

`[open]` HiCo-Nav's Cognitive Memory Graph is understood to need a continuous forward-facing RGB-D
stream. An Intel RealSense D455 is provided but not yet connected or stream-tested. The only known
working camera path remains the D435i on the arm's wrist (`Link6`), and `Navigation_Module` is
LiDAR-only. The immediate task is to test the D455 before fabricating its mount.

**Why it is first:** it is the only item whose wrong answer costs weeks rather than days. Confirm the
provided D455's USB 3 connection and RGB-D stream before mount fabrication. See ORIENTATION §10.

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

> ✅ **Answered for the contract topics, 2026-09-20 (`T0.7`).** The graph answers queries, it does
> not drive. Dion's `T7.1` node reads the graph and writes `/manipulation/goal_pose`, keeping that
> channel's meaning unchanged. The frontier layer, if M9 happens, writes `/goal_pose`. The graph is
> reached through a ROS service. See [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §4 P2 and §6 N-2,
> N-3. What is still open is the research-scope half of this question: full memory graph, or
> navigate-to-named-object. That one decides the YOLO-World line in §2.14.

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

There is no triggering *policy* anywhere, just "on frame".

> **Update 2026-09-20.** The HiCo-Nav paper answers most of this with its four-stage cascade
> ([`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §4.4a), and §2.14 below works out which of
> its three models we actually need. The "graph-driven" and "event-driven" rows below turn out to be
> the same row.

> ✅ **Trigger policy decided 2026-09-20 (Dion, `T0.7`).** Which camera's detection runs in which
> phase:
>
> | Phase | Glasses | Base camera | Wrist camera |
> |---|---|---|---|
> | 1, navigating | yes | yes | no |
> | 2, grasping | yes today, probably no once the graph carries the instance | no | yes |
>
> Dion owns both the segmentation service and its trigger, so `T6.5` shrinks to publishing the
> trigger. The channel is [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §4 P4, and the phase table
> lines up with the model residency plan in §2.14 below.

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
| Publishes | `/camera/sam/mask`, `/object_centroid_2d`, `/object_centroid` (`:34-36`) — **call site commented out at `:389`** | the **same three topics** (`:30-32`) — live |

**Two concrete hazards:**

1. **Topic collision.** Both publish the identical three topics. Uncommenting `:389` while
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

#### `[decided 2026-09-20]` Decision: retire `sam3_ros_node.py` (Option 2)

**Dion decided 2026-09-20: Option 2. Retire `sam3_ros_node.py` and restore the pipeline call site
at `object_recognition_pipeline.py:389`.** The trade-off table below is kept as the record of why.

Two things settled it, beyond the gains already listed in the table:

1. **The unified service is mostly already written.** `object_recognition_pipeline.py` already
   subscribes to *both* cameras: the Aria feed (`:127-135`) and the synchronised RealSense
   RGB+depth pair (`:137-143`), which are the same two topics `sam3_ros_node.py` uses. It also
   already holds the `FeatureMatcher` for cross-view confirmation (`:117`). The "one model, two sources" target in
   this section is not a build from scratch. What blocks it is the commented-out call site and the
   topic-ownership hazard, not missing capability.
2. **VRAM.** Two processes × 3.21 GB of the same weights, each with its own CUDA context, on a
   16 GB card that HiCo-Nav will add ~5 GB of models to. This is the single largest saving
   available anywhere in the system. See §2.14.

Retiring the node also closes **L1** and the segmentation half of **B3** for free: the hardcoded
`TEXT_PROMPT = "box"` disappears with the file, and the surviving path already handles the spoken
prompt and the stop keyword through `_on_prompt` (`:250`).

**Sequencing is unchanged.** The *decision* is settled, the *build* still waits on §1.3 (scope) and
§2.1 (trigger policy), for the reason in the sequencing note above. §2.1 is now largely answered by
the HiCo-Nav cascade. See [`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §4.4a and §2.14
below.

What forces the question: `sam3_ros_node.py` never subscribes to `/aria/audio/prompt`, so on the
path that runs today the arm only ever looks for the hardcoded word "box"
(`sam3_ros_node.py:40`, `:114`). Full evidence in [`CODE_AUDIT.md`](CODE_AUDIT.md) **L1**, with the
safety half of the same missing subscription in **B3**.

| | **Option 1: patch in place** | **Option 2: decide ownership first** |
|---|---|---|
| What it is | Add a `/aria/audio/prompt` subscription to `sam3_ros_node.py` and make `TEXT_PROMPT` a default rather than a constant. | Retire `sam3_ros_node.py` and restore the pipeline call site at `object_recognition_pipeline.py:389`, which already handles the prompt and the stop keyword through `_on_prompt` (`:250`). |
| Gains | Small, local, testable on its own. Restores voice retargeting on the path that actually runs. | Reaches the target design above in one step, and gaze disambiguation plus cross-camera confirmation come with it at no extra cost. |
| Costs | Entrenches the duplicate segmentation node this section exists to retire, and adds a second prompt handler that has to be deleted again later. | Larger, and it depends on §1.3 and §2.1 being settled first, per the sequencing note above. |

Either way, **ownership has to be settled before either change lands.** Hazard 1 above is the
reason: uncommenting `object_recognition_pipeline.py:389` while `sam3_ros_node` is still running
gives two publishers racing on the same three topics, with the state machine acting on whichever
message arrives last. Same warning in [`ORIENTATION.md`](ORIENTATION.md) §6.5.

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

> **Target names are frozen, 2026-09-20.** [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §7 holds the
> today-name to target-name table, including `/object_centroid_2d` (G-6), the `/manipulation` versus
> `/manipulator` prefix (B-6), the bare `/goal_pose` and `/goal_reached` (N-6) and the wrist camera
> becoming `/arm_camera/*` (N-4). The decision was to freeze today's names in the contract and rename
> in one pass later, not now.

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

### 2.5 ✅ Paths and environment assumptions — fixed by T0.3

**Status 2026-09-19: done, merged from branch `t0.3-fresh-clone-paths`.** Full record in
[`zongzhe_docs/T0.3_SESSION.md`](zongzhe_docs/T0.3_SESSION.md). The survey below is kept as history,
and its line numbers are from before the fix.

- `[code]` Group A (inside the repo) is derived from the repo root. `sam3_ros_node.py` imports
  `ModelPaths.SAM3_PATH` instead of keeping its own copy, and the `sam3_model.py` demo block is
  deleted. `install.sh` finds the repo from its own location.
- `[code]` Group B map paths use one environment variable, `GAPPLER_MAP_DIR`, default `~/maps`. This
  settles the `[open]` question below in favour of environment variables. It also fixed a real bug:
  mapping saved to `~/maps/current_map` but localisation read `/home/iot22/maps/completed_map`, so
  the two launch files never shared a map.
- **Still open:** the OpenVINS paths (`src/main.py`, the decision below is unchanged) and the
  `conda run` launch of AnyGrasp. Neither is a T0.3 item.
- `[unverified]` Nothing was launched. T0.5 is the real test. On the lab box, set
  `GAPPLER_MAP_DIR=/home/iot22/maps` or copy the map, since the default now resolves to the running
  user's home.

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
`Navigation_Module/OpenVINS/` (now `aria/vendor/open_vins/`, unused), which **has never been built** (no `install/` anywhere).

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
| 2 | ~~Arm needs host `.10`, LiDAR needs host `.5`, one NIC (§8.13)~~ **Done 2026-09-16.** Switch connected; persistent `Wired connection 1` profile carries `.100`, `.10`, and `.5`; RM65 and MID-360 each replied from the required source address after a connection cycle | | Resolved. Do not use the old base scripts unchanged: they flush the arm's `.10` address. |
| 3 | `main` launches an AnyGrasp node/checkpoint that was never verified (§8.14) | `ls .../perception/log/` — is `checkpoint_detection.tar` even there? | Decide which node is authoritative before closing seam §6.2. |
| 4 | `livox_ros_driver2` has no ROS 2 manifest, so §3.2 cannot compile (§8.15) | `ls nav/vendor/livox_ros_driver2/package*.xml` | Commit `package_ROS2.xml` from upstream. Unblocks §3.2. |

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
| 1 | Settle the open questions, several of which are decisions rather than fixes. Question 5 answered 2026-09-20, five left | §"Open questions" |
| 2 | Safety: the phantom `q` key (`main.py:67`), the e-stop's missing delivery delay, the changed `HOME_JOINTS` | B1, B2, B4 |
| 3 | Fix the double `background.launch.py` launch, two `rm_driver` on one arm. **Ownership decided 2026-09-20: `main.py` owns it, delete `orchestrator.py:69-74`.** See §2.14 for the larger design this sits inside | I1 |
| 4 | The `/pipeline_state` gate inversion, and decide on `USE_SIMPLE_EXECUTE` | A1–A3 |
| 5 | Concurrency in `grasp_state_machine.cpp` — the two-mutex condvar and the unlocked centroid read are undefined behaviour, not style | C1–C7 |
| 6 | The deadlock paths in `goal_reached_publisher` / `object_approach_node` | F1–F3 |
| 7 | Frames: `/aria/fused_pose` is `robot_base_link` and its only consumer assumes `map` | E1, E2 |

⚠️ **Do the safety items before the first hardware run, not after.** Everything else can wait for a
bench session.

---

### 2.7 🟡 `bench/` — the offline regression bench

> ➡️ **Continuing this work? Start at [`TESTBENCH_PLAN.md`](TESTBENCH_PLAN.md) → "▶ Start here"** — status
> table, decisions, held fixes and the work queue. As of 2026-09-11 the bench runs on the lab box
> (over tailscale): tiers 0–2 plus Tier 3 tests for MoveIt and the grasp state machine on a simulated
> arm, the e-stop, and the AnyGrasp env. They have found real bugs (CODE_AUDIT B2a, C7). Next: the
> `Navigation_Module` build (W4b).

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

⚠️ **When the reorg moves code, update `OWNED_PREFIXES` in `bench/_common.py`** (one copy, used by all
three tools) — otherwise moved files get classified as vendor and stop failing the build.

**Tiers built since (on the lab box, 2026-09-11):** `bench/build.sh` (colcon, Tier 2) and Tier 3 scripts
on a private ROS channel with a simulated arm — no container needed, the box has ROS. **Still to build:**
the navigation node tests with a mock `navigate_to_pose` server (W7), and replay against a recorded
rosbag (W6/W8).

---

### 2.8 🟡 One folder for model weights — `assets/models/`

Dion, 2026-09-11. Model files are scattered: `src/models/sam3/sam3.pt`, and the AnyGrasp checkpoints
under `ros2_robot_ws/src/rm_mtc/src/perception/log/` — ignored only because of a catch-all `log`
rule. Move them to `assets/models/{sam3,anygrasp}/`, gitignore that folder explicitly, keep the
checksum list in [`ASSETS.md`](ASSETS.md), and make the code read one configurable path (ties into
§2.5). Do it with the modular reorg, not before: `preflight.py`'s `assets` group must move with it.

### 2.9 🟠 Important state lives outside git — decide what is needed, then bring it in

> ✅ **The four "Yes" rows are settled (T0.4, 2026-09-21).** `robot_navigation` and `xpkg_demo` are in
> `Navigation_Module/src/`, and both build on the box `[observed]`. The Livox template is at
> `livox_ros_driver2/package_ROS2.xml`. The map stays outside git on purpose (T0.3's
> `GAPPLER_MAP_DIR`), with its location in [`ASSETS.md`](ASSETS.md). The rows below marked "Unclear",
> "Unknown" and "Possibly" are still open.

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
| MoveIt / MTC source builds in `install/` | same | — | No — MoveIt comes from apt; MTC is in `grasp/vendor/` (was `deps_ws/`) |
| `build/`, `log/` | same | 700 MB | No |
| AnyGrasp conda env, `~/.local` CUDA torch | `~iot22/` | GBs | No — replaced by the uv env (W1, W5) |
| `~/.aria` certificates | `~iot22/` | small | Covered — `aria auth check` already passes for `rcp2026` |
| `sdk_echo_plus_ws` (Echo Plus SDK, `xpkg_demo`'s origin) | `~iot22/` | — | Possibly — compare with `src/demo/` before importing |
| Isaac Sim (+ 8.7 GB zip) | `~iot22/` | ~9+ GB | No, unless simulation work starts |

**When fixing:** bring the "Yes" rows into this repo (a branch for review — robot code), gitignore the
generated/large ones, record the rest in [`ASSETS.md`](ASSETS.md), and after that nothing the robot
needs should live only in someone's home folder.

### 2.10 🟠 One config tree — state every channel and constant in one place

`[code]` Raised by Dion, 2026-09-13, after finding that the `/rm_driver/*` topics are not in
`shared/config.yaml` (now `shared/global_config.yaml`). The inventory is CODE_AUDIT §K: **38 of the 54 topics our code declares are
written somewhere other than the shared config**, and the constants pattern in `src/config/` is not
used outside `src/`.

**The proposal:** a `GlobalConfig` composed of smaller typed groups — `PerceptionConfig`,
`AriaConfig`, `ArmConfig`, `NavConfig` — so that channels and tuning values can be read in one
place instead of being discovered file by file.

**This is the right instinct, and the shape needs one adjustment.** Splitting it three ways:

1. **Constants — do it, and the work is half done.** `src/config/` already holds exactly this
   pattern. The gap is that `ros2_robot_ws/` and `Navigation_Module/` cannot import it. Fixing that
   is packaging, not design: make `src/config` an installed package both colcon workspaces depend
   on, or vendor a small shared module into each. `DEPTH_SCALE`, `CAMERA_X_OFFSET`, the approach
   thresholds and the AnyGrasp tuning values all belong here.

2. **Topic names — prefer ROS parameters over a shared constant.** Freezing a topic name in an
   imported constant removes the ability to remap it at launch, which is ROS 2's own mechanism for
   exactly this problem and the one thing every ROS developer will expect to work. The version that
   gets both properties: each node *declares* the name as a ROS parameter with a sensible default,
   one YAML per workspace supplies the values, and launch can still override. The name is then
   explicit in the node, explicit in the YAML, and still remappable.

3. **`/rm_driver/*` — name them in one place, but do not treat them as ours.** They are the vendor
   driver's API (CODE_AUDIT §K1). A single `ArmDriverTopics` group naming all four is worth having,
   with a comment saying the vendor owns these strings.

**Two real constraints, both of which affect sequencing:**

- **Three colcon workspaces, two languages, separate Python environments.** No single Python import
  reaches all of it. C++ reads none of `shared/global_config.yaml` today (checked: no `.cpp` or `.hpp` we
  own opens it). ROS parameters are the only mechanism that spans all of it natively.
- **⚠️ Indirection currently blinds the bench.** `src/config/ros2.py:11-14` builds the topics enum
  *dynamically at import time*, and the bench's static extractor cannot resolve `ROS2Topics.X.value`
  (TESTBENCH_PLAN §4 C1). So every topic moved behind the enum today becomes invisible to the one
  tool that catches renames. **Teach the extractor first, then consolidate**, or the refactor
  removes its own safety net.

**Suggested order:** teach the extractor (TESTBENCH_PLAN C1) → re-snapshot → collapse the
duplicated constants (§2.4 step 2, already planned) → then topics as parameters, one subsystem at a
time, re-running `./bench/run.sh` across each step.

> ✅ **Decided 2026-09-20 (Dion):** one config tree **per subsystem**, with a shared constants
> package underneath. It fits the three-workspace structure and the four-folder layout in
> [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §6 G-2. Sequencing below is unchanged: teach the
> bench's extractor first, or the refactor removes its own safety net.

**The original question:** whether the target is one repo-wide config tree, or one per subsystem
with a shared constants package underneath. The second fits the three-workspace structure better and
is less disruptive to the reorg; the first is what makes everything visible from one file. Worth
settling before §2.4's rename pass, since both touch the same strings.

### 2.11 🟡 Box vendor code off from ours, and depend on it instead of sitting next to it

Raised by Dion, 2026-09-13: vendor code should be stated as vendor, nested inside its own folders,
and imported or depended on, rather than placed among the code we write. Right now there is no
separation, so it is hard to tell what is ours without already knowing.

**This makes sense, and the ratio is the argument for it.** `[code]` Of 2,426 files tracked in git,
**226 are ours** (excluding `docs/`) and **2,181 are vendor**. Ours is under 10% of the repo, spread
across three workspaces, with nothing in the folder layout marking which is which.

#### Where the boundary is invisible today `[code]`

| Place | What you see | The problem |
|---|---|---|
| `ros2_robot_ws/src/` | 13 sibling folders, 11 of them RealMan's | Only `rm_mtc/` is ours. Nothing in the names says so, and `rm_mtc` sorts in the middle of the vendor `rm_*` packages |
| `Navigation_Module/src/` | `robot_slam/`, `simple_teleop/`, `echo_plus_driver/` sitting beside `livox_ros_driver2/`, `Livox-SDk2/`, `base/`, `drivers/`, `urdf/` | Ours and the vendor base driver are siblings at the same depth |
| `ros2_robot_ws/src/rm_mtc/src/perception/` | our four Python nodes, plus `gsnet`, `lib_cxx` and `tracker` `.so` files | Three compiled AnyGrasp binaries are **committed inside our own package**, in the same directory as code we edit. This is the literal case you described |
| `ros2_robot_ws/src/rm_ros_interfaces/` | one package, 79 message definitions | **77 are the vendor's, 2 are ours** (`GraspCandidate.msg`, `GraspCandidateArray.msg`). One package, both owners, no marking |

**The only place ownership is written down is `bench/_common.py`** (`OWNED_PREFIXES`, 12 entries) and
that is a bench-side list, not something visible in the tree. It is also already wrong in one place:
it claims all of `ros2_robot_ws/src/rm_ros_interfaces/`, so the bench counts 77 vendor message files
as ours.

#### The proposal

> ✅ **Steps 1, 2 and 4 done 2026-09-21** as `NEXT_STEPS` §2.15 step 3, in the final layout rather
> than one `vendor/` per workspace: vendor code is in `aria/vendor/`, `arm/vendor/`, `grasp/vendor/`
> and `nav/vendor/`. `COLCON_IGNORE` only on `aria/vendor/open_vins` (unused). Step 3, the
> `rm_ros_interfaces` split, is §2.15 step 5.

1. **One `vendor/` folder per workspace.** Move vendor packages down one level, into
   `ros2_robot_ws/src/vendor/`, `Navigation_Module/src/vendor/`. What remains at `src/` is ours and
   is readable at a glance.
2. **Mark the trees we never build.** Drop a `COLCON_IGNORE` file in vendor trees that are reference
   only. There is **no `COLCON_IGNORE` anywhere in the repo today** `[code]`, so nothing currently
   tells a build to skip anything.
3. **Split `rm_ros_interfaces`.** Our two grasp messages move to our own interfaces package. This is
   the one item that is a decision rather than a move, because it changes a package name that
   `rm_mtc` depends on.
4. **State it once, in `ORIENTATION.md` §2**, which already carries the "will you edit it?" column.
   The folder layout and that table should agree.

#### Why moving vendor code is safe `[code]`

- **colcon finds packages by walking the tree for `package.xml`**, not by a fixed depth, so nesting
  a package one level deeper still builds.
- **ROS resolves dependencies by package name, never by path.** Verified in our own code: our launch
  files use `get_package_share_directory("rm_driver")` and friends
  (`rm_mtc/launch/background.launch.py:21,31,41,51`), and our manifests use `<depend>` by name
  (`rm_mtc/package.xml:12-20`, `robot_slam/package.xml:11-15`). None of that changes when a folder
  moves.

#### What would actually break, and it is a short list `[code]`

Three places hardcode a vendor path as a string, so a move invalidates them. **All three handled
2026-09-21 (reorg step 3):** the OpenVINS path is `openvins_ws` in `shared/global_config.yaml`,
`BLOCKING_VENDOR` points at `nav/vendor/`, and the `deps_ws/install` checks stay on purpose, to catch
a stale overlay left in old clones.

| File | What it hardcodes |
|---|---|
| `src/main.py:303-304`, `:331` | an **external** OpenVINS workspace under `~/Ros2Workspaces/` (already broken, §2.5) |
| `bench/static.py:85` | `BLOCKING_VENDOR = ("Navigation_Module/src/livox_ros_driver2/",)` |
| `bench/preflight.py:299` | `deps_ws/install` overlay checks |

#### Sequencing

Do this as **step 1 of the modular reorg**, before code we own is moved, so the two kinds of move
are not tangled in one diff. Update `OWNED_PREFIXES` in `bench/_common.py` in the same commit
(§2.7), then re-snapshot: `python3 bench/contracts.py snapshot`. The bench is keyed by contract, not
by file location, so a pure move should show as informational and fail nothing.

⚠️ **Note a gap this exposes:** the "one folder per node" reorg is referred to in four places
(`CLAUDE.md:5`, §2.7, §2.8, TESTBENCH_PLAN C2/S2) but **is not specified in any of them**. Before the
reorg starts, it needs its own item saying what the target layout actually is. This section covers
only the vendor half of it.

**Specified 2026-09-21 in §2.15**, which also puts the full reorg in scope.

### 2.12 🟡 CI: run the bench automatically on every push, once M0 is done

Dion, 2026-09-16. Raised as a task rather than left as the "deferred, after this plan ends" item
`PROJECT_PLAN.md` §4.3 used to call it — a running CI job now has real value once there is more
than one clone of this repo to break.

**Gated on M0, not on anything about the arm or the base.** CI needs exactly the property M0's
acceptance test proves by hand — `./bench/run.sh` giving the same verdict on a machine that is not
this one — so it makes no sense to automate the check before a human has confirmed it works at
all. Once `T0.5` passes (Zongzhe and Sherman each clone, build and get the same bench result), the
CI job is close to writing itself: it runs the same command they just ran manually, on push.

**What it can and cannot cover.** Tiers 0–1 need only Python stdlib and run anywhere. Tier 2
(`./bench/build.sh`) needs ROS 2 Humble and colcon, which a container image can provide with no
real hardware. Tier 3's simulated-arm and mock-Nav2 scripts (`sim_moveit.sh`,
`state_machine_sim.sh`, `nav_nodes.sh`, `estop_delivery.sh`) also use no real hardware — mock
components and a private ROS channel are the whole point — so they are candidates too, once someone
has confirmed they behave the same in a container as on the lab box. **The real arm, the real base
and the real glasses can never be in CI** — nothing here changes the hardware
safety rules elsewhere in this doc and in `CLAUDE.md`.

**What "breaking changes" means for this check:** a push that fails `bench/run.sh` — a renamed
topic/frame/param that the contract snapshot catches, a static-analysis regression, or (once wired
in) a build or simulated-arm failure. It does not mean "the robot still works" — nothing here can
observe real hardware, so a green CI run is a floor, not a guarantee. Say so in the CI job's own
description so nobody over-reads a passing badge.

**Action, once T0.5 is done:**

1. Pick a CI provider (GitHub Actions is the default choice for a repo already on GitHub; no other
   option has been evaluated).
2. Container image with ROS 2 Humble + the project's Python env, close enough to the lab box to run
   Tiers 0–2 (and Tier 3 against the simulated arm, if that survives running outside the lab box —
   verify this before wiring it in, don't assume).
3. Workflow: run `./bench/run.sh` (and whichever Tier 3 scripts prove containerizable) on every push
   and every PR; fail the check on a non-zero exit.
4. Document the CI badge and what it does and does not prove in `docs/README` or `bench/README.md`,
   so a reader doesn't mistake "CI passing" for "verified on hardware".

**Progress 2026-09-19.** Started before T0.5 on purpose, so the next merge tests it.
`.github/workflows/bench.yml` runs `./bench/run.sh` (Tiers 0-1) on `ubuntu-22.04` for every PR into
`main` and every push to `main`. It fails on any finding, so it stays red until the 7 known static
findings are fixed `[code]`: 6 of them come from `xpkg_demo` and the livox `package_ROS2.xml` being
absent (both are T0.4), and 1 is `mtc_sim_test.launch.py` naming an executable `rm_mtc` does not
build. T0.4 now covers all three. Merges are not blocked yet. Branch protection for `main` goes on
once T0.4 turns the bench green. Tiers 2-3 are not wired in. Planned branch model: a `dev` branch gets fast per-subsystem
tests (`T0.11`), `dev` into `main` runs the full suite, and the full suite also runs on `dev` every
Monday and Wednesday night. Where Tiers 2-3 run (lab box as a self-hosted runner, or a Docker image)
is deferred to T0.11.

**First run, 2026-09-19** (run 35433250227, commit `5fa91ee`): red, as expected, but preflight also
failed, not only static. Preflight gated its network and camera checks on "is Linux" rather than
"is the lab box", so any Linux machine without `enp2s0` or a RealSense got FAIL instead of SKIP
`[code]`. That includes a teammate's laptop in T0.5, not just CI. Fixed in `bench/preflight.py`
`g_net` and `realsense_checks`, which now gate on `on_lab_machine()`. Checked by simulating a
non-lab Linux host: all seven checks skip. The lab box still runs them, since it has
`/opt/ros/humble`. With this fix, T0.4 alone should turn CI green `[inferred]`.

**Levels, 2026-09-19.** The tiers are renamed L0-L5 and `run.sh` now runs them in order, running
each level the machine can and reporting the rest as SKIPPED: L0 static, L1 contracts, L2 preflight
(lab box check), L3 build, L4 simulation, L5 hardware (never automated). It ends with a summary
table, which CI also writes to the run's summary page. Definitions in `bench/README.md`. On GitHub,
L3-L4 skip. Runner on the lab box and the `dev`/`main` rules are T0.11.

**Robot check, 2026-09-21.** A new L5 checks the robot (arm, wrist camera, LiDAR, glasses, live
ROS graph) and gates L6, the real arm test, the way L2 gates L3-L4. These checks left L2, so an
unplugged robot no longer fails the bench. With no arm on the network L5 and L6 are SKIPPED.
Neither is needed to merge into `dev` or `main`.

**Branches, 2026-09-21** `[observed]`. `dev` exists and is the default branch. `bench` runs on
every PR into and push to `main` or `dev`, and both branches are protected: a PR is required and
`bench` must pass. T0.10 is done. What remains is T0.11: the lab box runner, the no-skips `full`
job required on `dev` into `main`, the Monday and Wednesday night run, and the per-subsystem
suites. The fork-PR risk of a self-hosted runner on a public repo is still open. Steps in
`TESTBENCH_PLAN.md` "Start here".

Owner: Dion, since he owns `bench/` itself. Depends on `T0.5` (both other clones build and pass the
bench) — see `PROJECT_PLAN.md` §6.2, task `T0.10`.

### 2.13 🟡 Explore: pick the gazed object by geometry, not by appearance

Raised by Dion, 2026-09-19. A possible direction, not a committed task. Decision `D9` and stretch
goal `S9` in `PROJECT_PLAN`.

**The problem.** Two identical objects on the table, say two apples. The current cross-camera step
cannot reliably tell them apart `[inferred]`. `_find_matching_ros_mask`
(`object_recognition_pipeline.py:532-610`) keeps only the keypoint matches that fall inside the gazed
mask in the glasses image (`:572-573`), then votes for whichever robot-side mask those keypoints land
in (`:587-596`). A keypoint on one apple can match either apple, and the background matches that
would say which one is which are discarded. M8 as planned has the same blind spot: T8.1 and T8.2
select by an image feature of the gazed region, and two identical objects give the same feature.

**Three candidate methods, cheapest first:**

| Method | Idea | Needs | Rough cost |
|---|---|---|---|
| A. Scene transfer | Keep the background matches too. Fit a homography between the two views and map the gaze point straight into the robot image, then take the mask it lands in | Only what exists today | Hours. Assumes a roughly flat tabletop scene |
| B. Pose from the shared scene | Lift robot-side keypoints to 3D with RealSense depth, solve the glasses camera pose with `cv2.solvePnPRansac`, move it into the robot frame by TF, cast the gaze ray and pick the object nearest to it. The room acts as the marker | LightGlue (exists), robot depth and intrinsics (exist), glasses intrinsics from the live calibration (exist). New: the 3D lift, the pose solve, the ray test. About 100 to 200 lines `[inferred]` | Days. No marker, no OpenVINS, no drift, because the pose comes from the same frame as the gaze |
| C. Full pose fusion | ArUco fix plus OpenVINS tracking between fixes, as `src/services/pose_fusion/README.md` describes. Then the same gaze ray test as B | OpenVINS brought up for the first time. Its VIO half is commented out today (`pose_fusion_node.py:135-140`, `src/main.py:112`) and the `kalibr_*.yaml` files were derived by hand from the live calibration | Weeks. Also serves return-to-user |

**What limits B** `[inferred]`, all worth measuring: very different viewpoints between head and
wrist camera, too little shared scene, textureless surfaces, and time skew between the two frames
(the matcher pairs the latest frame of each with no time check, the same class as `CODE_AUDIT` G1).
Gaze error of about 2° is about 5 cm at 1.5 m, so objects about 10 cm apart should separate and
touching objects may not.

**Why this is worth doing, not a niche problem.** Use this answer when someone asks. Two truly
identical objects are fairly rare, so they are best used as the **hardest test case, not the
pitch**. The real capability is working out **where the user is looking in the robot's own 3D
space**. That helps with:

- similar but not identical objects
- partly hidden objects
- cases where the image feature is uncertain
- handing an object back to the user
- confirming the robot and the user are attending to the same thing, which matters because the
  robot may not see what the user sees. The base camera is mounted at about knee height.

Where it matters in practice: assistive use (a user who can look but cannot easily point or speak,
in scenes full of near-duplicates such as mugs, pill bottles and cans), warehouse and retail shelves,
kitchens and workshops. Speech ("the left one", "the red one") separates many pairs, so gaze earns
its place when objects are hard to describe or the user cannot easily speak. A reviewer will ask
how the method copes with identical objects. A geometric method has an answer, an appearance-only
method does not.

**Parked open problem: the robot cannot see what the user sees.** Research and think about this
later. If something blocks the apple from the robot's view entirely while the user can still see
it, how does the robot know to look from another angle or reposition itself?
Starting thoughts `[inferred]`, none checked:
- The LiDAR is there, but it serves navigation and gives no object identity.
- The wrist camera could look around. The arm can move it to a new viewpoint.
- Methods B and C give the gaze ray in the robot's frame even when the robot cannot see the object.
  The ray says *where* to look, so the robot could move the wrist camera, or the base, to view the
  ray's end from the side. This is the "next best view" problem in active perception.

**Suggested order.** Try A inside M2. Include an identical pair in T2.5's two-box test so the
failure, if there is one, is measured rather than assumed. Only if A fails, try B. C only if
return-to-user comes back into scope.

**Related, and the true "continuous calibration" case.** Targetless calibration, where natural scene
features correct a camera's extrinsics over time, fits sensors that are bolted together. Here that is
T5.5, the D455 against the LiDAR, not the glasses. Targetless LiDAR-to-camera tools exist (for
example Koide's `direct_visual_lidar_calibration`, ICRA 2023) and may save building a calibration
target. Worth a look at T5.5.

### 2.14 🟠 GPU budget: phase-gated model residency, and which HiCo-Nav models we actually need

**Decided in principle 2026-09-20 (Dion). Four threads still open, listed at the end.**

The problem in one line: every model in this system shares one 16 GB card, and HiCo-Nav adds three
more.

#### The design: boot every process, do not boot every model

Today `/manipulation/start` does not "turn the arm on". It cold-starts seven processes, including a
second SAM3 and AnyGrasp, from nothing, at the moment the robot has already parked in front of the
object (`orchestrator.py:84` launches `ros2_robot_ws/src/main.py`, which launches the rest at
`:85-149`). Launching *is* the interlock, because `grasp_state_machine.cpp` never subscribes to
`/manipulation/start` at all (**CODE_AUDIT B6**). Process lifetime is doing the job a gate should do.

What that costs:

* Startup latency at the worst moment. RealSense enumeration, a 3.21 GB model load, a conda
  environment, an AnyGrasp checkpoint and `move_group`, all after the robot has parked.
* Late failures. A missing conda env or a bad checkpoint path surfaces post-navigation, and the
  `Popen` that would raise runs inside a ROS callback where rclpy swallows it (**CODE_AUDIT I2**).
* Fixed sleeps instead of readiness checks. The state machine starts at `+5s`
  (`ros2_robot_ws/src/main.py:144-148`). If `move_group` takes six seconds that day, it loses.
* No supervision, and no cleanup. Nothing restarts a dead node, and the orchestrator exits leaving
  its children running (**CODE_AUDIT B5**).

**Target design.** Every node starts at boot, subscribed and idle, holding no GPU memory. A phase
signal decides which models are resident. Each GPU-heavy node loads and unloads on phase change.
The state machine subscribes to `/manipulation/start` as an explicit arm and disarm gate, which
closes B6 at the same time.

The distinction that matters: **processes are cheap, weights are not.** An idle ROS node costs a few
hundred MB of host RAM and nothing on the GPU. Boot all of them. Gate the weights.

#### Budget `[inferred unless marked]`

Card: RTX 4060 Ti, 16 GB total, **15.3 GB free at idle `[observed 2026-09-15]`**
([`COMPUTE_REQUEST_VERIFICATION.md`](COMPUTE_REQUEST_VERIFICATION.md) §1.1).

| Phase | Resident | GB |
|---|---|---|
| Phase 1 today (Aria + nav) | SAM3 human view, Qwen2.5-0.5B, faster-whisper int8, LightGlue + SuperPoint, gaze | ~7-9 |
| Phase 1 + HiCo-Nav | the above, plus YOLO-World ~2, MobileSAM ~1, CLIP ~2 | **~12-14** |
| Phase 2 (grasp) | SAM3 robot view, AnyGrasp + MinkowskiEngine | ~5-7, AnyGrasp runtime `[unverified]` |

Two conclusions, both the opposite of the intuitive answer:

1. **The tight phase is navigation, not grasping.** Once the duplicate SAM3 goes (§2.2), phase 2 is
   the cheap phase. All three HiCo-Nav additions land on phase 1, which was already the heavier one.
2. **A local Qwen3-Omni does not fit.** 20-24 GB against a 16 GB card
   ([`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §6.4 and its line on VRAM contention).
   That section treats cloud-versus-local as an open policy decision. On this hardware it is decided
   by the constraint. Record it as such rather than leaving it to be rediscovered.

#### How to actually avoid the OOM

**The peak is at the transition, not in either steady state.** This is the one that bites. If the
navigation models unload lazily while the grasp models are already loading, both are briefly
resident, and that moment is exactly when the robot is standing in front of a person. Make the
handoff explicit: arrived fires, nav models unload, the node publishes an unloaded acknowledgement,
only then does the grasp side load. Acknowledge, do not overlap.

Three supporting mechanics, cheapest first:

1. `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. One environment variable. This workload
   repeatedly frees and reallocates multi-GB blocks, which is what the default caching allocator
   fragments on.
2. `torch.cuda.set_per_process_memory_fraction()` per node. Turns "something ran out of memory" into
   "node X exceeded its budget". Without it the crash lands in whichever process allocated last,
   which is rarely the one at fault.
3. Measure before trusting the table above. Log
   `nvidia-smi --query-gpu=memory.used --format=csv -l 1` across a full run, and have each node
   print `torch.cuda.max_memory_allocated()` on exit. This is a bench script, not a research task.

**Return-to-user is out of scope** ([`PROJECT_PLAN.md`](PROJECT_PLAN.md) §4), so the phase change is
one-way. Reload latency is a one-time cost, not something to engineer around. If the return leg ever
comes back into scope, this changes: the phases cycle, and the unload/reload cost is paid twice per
task.

#### Do we need all three HiCo-Nav models? `[inferred]`

The paper's cascade uses YOLO-World (detect, every frame, 10 fps), MobileSAM (segment, keyframes
only, one per 1-2 s) and CLIP (per-object descriptor). See
[`hico-nav/PAPER_REPORT.md`](hico-nav/PAPER_REPORT.md) §4.4a. They do three different jobs and only
two of them overlap with SAM3.

| Model | Verdict | Why |
|---|---|---|
| **MobileSAM** | **Drop it.** SAM3 replaces it directly | Its job is stage 4, mask from box, on anchors only at 0.5-1 Hz. That is what SAM3 does, and SAM3 is already loaded. `PAPER_REPORT.md` line 493 already notes our cascade saves proportionally more than theirs because we escalate to the bigger model |
| **YOLO-World** | **Probably keep.** Not a swap, a deletion | It is the always-on 10 fps gate feeding the semantic half of the anchor test. SAM3 cannot run at 10 fps on this card. Its ~2 GB is a *latency* budget item, not the thing that causes an OOM |
| **CLIP** | **Investigate, do not assume** | It produces a stored descriptor queried repeatedly against text: the merge cosine (Eq. 4) and the goal score `s(o_i, T)`. SAM3 answers the opposite question, "where is X in this image now". Drop CLIP naively and every query means re-running SAM3 over stored keyframes |

**The CLIP lead worth chasing.** SAM3 loads `bpe_simple_vocab_16e6.txt.gz`
(`src/services/object_recognition/sam3_model.py:37`), the CLIP BPE vocabulary, so it has a
text-image aligned encoder inside it. If that package exposes a per-instance image embedding, it can
serve as the descriptor `f_j` and one model covers stage 4 plus descriptors. Unverified: `sam3` is a
git dependency (`pyproject.toml:23`) and is not installed outside the box. This is a short check on
the box that decides a 2 GB line item. If it works, note that the merge weights λ₁, λ₂ and the
threshold are tuned for CLIP's embedding space and would need retuning. A cost, not a blocker.

**The YOLO-World argument that is specific to us.** The anchor test fires on semantic novelty *or*
geometric novelty, and the geometric half costs no inference at all, it is pure odometry from
FAST-LIVO2. HiCo-Nav needs the semantic half because they do open-ended exploration. We have a human
wearing glasses who says what they want and looks at it, so gaze and voice already supply the
semantic trigger. The catch: register only what the user looked at and the cognitive memory graph is
much poorer for later queries. **This depends entirely on §1.3**, full memory graph or
navigate-to-named-object, which is still open.

#### What this is worth

| Change | Saved | Confidence |
|---|---|---|
| Retire `sam3_ros_node.py` (§2.2) | ~3.2 GB plus a CUDA context | High, the code is mostly there |
| Drop MobileSAM, escalate to SAM3 | ~1 GB | High |
| Drop YOLO-World, geometric anchors only | ~2 GB | Depends on §1.3 |
| SAM3 embeddings replace CLIP | ~2 GB | Unverified, needs the API check |

Phase 1 goes from ~12-14 GB to ~9-11 with the two safe rows, or ~7-9 if all four land. Against
15.3 GB free that is the difference between tight and comfortable.

Ranking honestly: **the duplicate SAM3 is still the biggest single item**, and it is the only one
that needs no research, no retuning and no HiCo-Nav decisions. The other three optimise a phase that
the first row has already made fit.

#### Open threads

1. **Can AnyGrasp unload cleanly?** It runs in a separate conda environment with MinkowskiEngine.
   Do not assume `empty_cache()` returns the memory. It may be the one component that stays a
   start-and-stop process rather than a load-and-unload node. Dion to test on the box.
2. **CPU budget.** FAST-LIVO2 real-time, plus the anchor test, plus Nav2. Separate from everything
   above, and unanswered. Sensor bandwidth (two RGB-D cameras and a LiDAR on one host) belongs in
   the same column, not in the GPU numbers. They fail differently and are fixed differently.
3. **Does `sam3` expose per-instance embeddings?** Short check on the box. Decides the CLIP row.
4. **§1.3 scope**, full memory graph or navigate-to-named-object. Decides the YOLO-World row.

**Not yet in the plan.** This section is not in [`PROJECT_PLAN.md`](PROJECT_PLAN.md) or the task map.
Nothing here is scheduled work until Dion adds it.

---

### 2.15 🟠 The full reorg: target layout, config levels, and the order of moves

Dion, 2026-09-21. **The full reorg is now in scope** (was out, `PROJECT_PLAN` §4.2). This section is
the spec §2.11 said was missing. It builds on two decisions already made on 2026-09-20: the layout
(`CHANNEL_CONTRACT.md` §6 G-2) and one config tree per subsystem over a shared package (T-4, §2.10).
All steps happen on one branch, `t0.10-t0.11-refactor`, which merges into `dev` by PR.

#### Target layout

Four subsystem folders. Inside each, one folder per ROS package, which in practice is one per node.
The exception is code that builds into one program: the state machine and the MTC planner share a
folder. Each subsystem keeps its third-party code in its own `vendor/`.

```
shared/                     used by more than one subsystem
  global_config.yaml        values two or more subsystems read
  gappler_common/           the path helper and shared constants (T-4)
aria/                       glasses: stream, gaze, voice, glasses pose
  aria_app/                 from src/ (main.py, services/aria_device, ros, visualizer, ...)
  pose_fusion/              from src/services/pose_fusion (parked, §4)
  aria_config.yaml
  vendor/open_vins/         from Navigation_Module/OpenVINS
grasp/                      what to grasp and how
  grasp_state_machine/      rm_mtc C++: state machine + MTC planner
  anygrasp_node/            from rm_mtc/src/perception, with its 3 .so files
  segmentation/             SAM3: src/services/object_recognition + sam3_ros_node.py (G-2, §2.2)
  grasp_interfaces/         GraspCandidate, GraspCandidateArray, split out of rm_ros_interfaces
  grasp_config.yaml
  vendor/                   anygrasp_sdk, MinkowskiEngine, moveit_task_constructor (from deps_ws)
arm/                        the RM65 itself
  estop/                    from ros2_robot_ws/src/estop.py
  arm_config.yaml
  vendor/                   rm_driver, rm_description, rm_moveit2_config, rm_control, rm_bringup,
                            rm_ros_interfaces, eg2_4b_description, the other rm_* packages
nav/
  object_approach/  goto_glasses/  goal_reached/  pose_publisher/   from robot_slam/scripts
  echo_plus_driver/  simple_teleop/
  nav_bringup/              launch files and Nav2/SLAM params from robot_navigation + robot_slam
  nav_config.yaml
  vendor/                   livox_ros_driver2, Livox-SDk2, base, drivers, urdf, demo
bench/  docs/  main.py
```

`arm/` holds almost none of our code (only `estop`). That is accurate, not a problem: the arm
subsystem is mostly RealMan's.

#### Config: three levels, each value written once

| Level | File | Holds |
|---|---|---|
| global | `shared/global_config.yaml` | values two or more subsystems read: shared topic names, frame names, machine paths |
| subsystem | `<subsystem>/<subsystem>_config.yaml` | values two or more nodes in that subsystem read |
| node | `<subsystem>/<node>/config.yaml` | values only that node reads |

- **A value lives at the lowest level that covers all its readers.** When it gains a reader in
  another subsystem, move it up and delete it below.
- **References only point down.** Global has no list of subsystem files, and a subsystem file never
  copies a global value. So editing a subsystem file never touches global.
- **ROS nodes get their values as ROS parameters.** The launch file loads global, then subsystem,
  then node, and later files win. One file can hold several nodes, keyed by node name, with `/**:`
  for values every node in the file shares. Nodes still declare each parameter with a default, so
  launch can remap (§2.10 point 2).
- **The Aria app is not launched by ROS.** It reads the same files through `gappler_common`.
- **Vendor parameter files keep their own format and place** (`nav2_params.yaml`, the SLAM Toolbox
  files). Our levels are for our nodes.
- **A bench check fails when one key is defined in two files**, so duplicates cannot creep back.
  L0 is stdlib only, so it reads keys line by line rather than with a YAML parser. `[open]` whether
  that is enough, decide when writing it.

#### Paths: no file finds the repo by itself

Today files find the repo root by counting parent folders, for example `src/config/ros2.py:7` goes
up 3 and `ros2_robot_ws/src/main.py:28` goes up 2 `[code]`. Every move breaks them. It also cannot
work for ROS nodes, which run from `install/`, not from the repo.

- **`shared/gappler_common.py` is the only file that works out the repo root.** It lives in
  `shared/`, which never moves, so it takes the folder above itself. Every other file imports
  `ROOT`, `config()` or `path(name)` from it. (Decided 2026-09-21 instead of a `GAPPLER_ROOT`
  variable: one less setting, same result.)
- **`env.sh` puts `shared/` on `PYTHONPATH`**, so any program started after `source env.sh` can
  import the helper. Source `env.sh` before starting anything, nav included.
- **Shell scripts ask git**: `git rev-parse --show-toplevel` works from any folder depth and stops
  with an error outside a git clone, instead of guessing. Needed because config cannot say where
  the repo is: you must already know the repo to read config.
- **Machine paths live in `global_config.yaml` with defaults**, each one overridable by an environment
  variable, as `GAPPLER_MAP_DIR` already is. This settles §2.5's open "config file or environment
  variables": both, for different jobs.
- **Config is read from the repo, not from `install/`**, so editing a YAML file needs no rebuild.
- The last hardcoded external path, OpenVINS under `~/Ros2Workspaces/`, is now `openvins_ws` in
  `global_config.yaml` (step 2).

#### Order

Run `./bench/run.sh` before and after every step.

1. ✅ **Done 2026-09-21 (on the branch).** **Teach the bench's extractor to read YAML** (TESTBENCH_PLAN C1). Topic names that move into
   config files are otherwise invisible to the contract check, and the refactor removes its own
   safety net (§2.10). Re-snapshot.
2. ✅ **Done 2026-09-21 (on the branch).** **Paths and config.** `shared/config.yaml` became
   `shared/global_config.yaml` (a ROS parameter file, plus `paths:` for `openvins_ws` and `map_dir`).
   `shared/gappler_common.py` added. The launchers, `src/config/`, `src/main.py`, both SLAM launch
   files and two shell scripts no longer count folders. Hardcoded absolute paths in L1 went from 5
   to 3 (two vendor, one the OpenVINS default in `global_config.yaml`). `[unverified]` at runtime:
   compiled and import-checked, not yet started on the box. **Scope narrowed:** `src/config/*.py`
   (the Aria settings classes) folds into `aria_config.yaml` in step 4, when `aria/` exists, and so
   does sorting the aria-only topics out of `global_config.yaml`.
3. ✅ **Done 2026-09-21 (on the branch).** **Vendor moves**, as pure moves (§2.11 steps 1 and 2).
   Commit `2cd2297` is 2,145 renames and nothing else. The next commit fixed the references:
   `bench/build.sh` base paths (and `--symlink-install`), bench exclusions, the AnyGrasp env
   script, `env.sh`. `deps_ws/` and `grasp_module/` are gone. `rm_ros_interfaces` stays until
   step 5, and the AnyGrasp `.so` files stay in `rm_mtc` until the node moves. `temp.urdf` deleted.
   **OpenVINS (`aria/vendor/open_vins/`) is unused and a candidate for deletion**: nothing builds
   or runs it, and pose fusion, its only user, is parked. It carries a `COLCON_IGNORE` saying so.
4. ✅ **Done 2026-09-21 (on the branch).** **Our code moves.** Package names stay the same, so
   launch files and `ros2 run` keep working. Commit `9d0cc60` is the moves (207 renames) plus the 4
   `.gitignore` rules that name moved files. The next commit fixed the references: launchers,
   `PYTHONPATH`, both builds (`arm grasp` and `nav`), `OWNED_PREFIXES`, the bench, CLAUDE.md's safety
   rule. L1 shows only moves. SAM3 segmentation stays inside the Aria app until §2.2 merges the two
   copies. `ros2_robot_ws/install.sh` deleted and `bench/build.sh` moved to the repo root as
   `build.sh` (Dion: `bench/` holds test-bench tools only), so `ros2_robot_ws/` and
   `Navigation_Module/` are gone. The launchers got
   descriptive names in `launchers/` (not `launch/`, which would shadow ROS's `launch` library).

   **Where things moved (old path → new path).** Use this to read older cites in every doc:

   | Old | New |
   |---|---|
   | `src/` (the Aria app) | `aria/aria_app/` |
   | `src/services/object_recognition/` (SAM3) | `aria/aria_app/services/object_recognition/` |
   | `src/models/` | `aria/aria_app/models/` |
   | `ros2_robot_ws/src/rm_mtc/` | `grasp/rm_mtc/` |
   | `ros2_robot_ws/src/rm_ros_interfaces/` | `arm/rm_ros_interfaces/` |
   | `ros2_robot_ws/src/estop.py` | `arm/estop/estop.py` |
   | `ros2_robot_ws/src/main.py` | `launchers/start_grasp_pipeline.py` |
   | `ros2_robot_ws/src/orchestrator.py` | `launchers/grasp_orchestrator.py` |
   | `Navigation_Module/src/<pkg>/` (`robot_slam`, `robot_navigation`, `simple_teleop`, `echo_plus_driver`) | `nav/<pkg>/` |
   | `ros2_robot_ws/src/rm_*`, `eg2_4b_description` (RealMan) | `arm/vendor/` |
   | `deps_ws/src/moveit_task_constructor/`, `grasp_module/src/anygrasp_sdk/`, `grasp_module/dependencies/MinkowskiEngine/` | `grasp/vendor/` |
   | `Navigation_Module/src/{livox_ros_driver2,Livox-SDk2,base,drivers,urdf,demo}/` | `nav/vendor/` |
   | `Navigation_Module/OpenVINS/` | `aria/vendor/open_vins/` (unused) |
   | `shared/config.yaml` | `shared/global_config.yaml` |
   | `ros2_robot_ws/src/output.log` | `docs/archive/output.log` |
   | `bench/build.sh` | `build.sh` (repo root: it is the real build, not only a bench tool) |
   | `ros2_robot_ws/install.sh` | deleted, replaced by `build.sh` |

   Line numbers inside moved files are unchanged by the move itself.
5. **Splits into per-node packages.** `rm_mtc` into `grasp_state_machine`, `anygrasp_node` and
   `segmentation`, the `robot_slam` scripts into their own packages, and `rm_ros_interfaces` into
   ours and theirs (§2.11 step 3). These change package names, so launch files change too. L1 will
   show those renames as deliberate changes, re-snapshot after each.
6. **Replace `OWNED_PREFIXES`** in `bench/_common.py` with one rule: our code is anything not under
   a `vendor/` folder. Until then, update it in every PR that moves code (§2.7).
7. **Last: one env file per subsystem.** `aria/aria_env.sh`, `nav/nav_env.sh` and so on, each
   setting up only its own subsystem, so someone can start one subsystem against stub data from
   the others. The root `env.sh` then sources all four. Rename files only at this step, since
   CLAUDE.md, the docs and the bench all refer to `env.sh`.

Steps 3 and 4 are pure moves: a commit that only moves files lets git track them as renames, which
keeps merges manageable for everyone else.

#### Open, decide in the PR that needs it

- **Where the three launchers go.** Root `main.py`, `ros2_robot_ws/src/main.py` and
  `orchestrator.py` start processes across subsystems. `CODE_AUDIT` I1 already says
  `ros2_robot_ws/src/main.py` owns `background.launch.py`. Keep one launcher at the root.
- **One build or two.** Today there are two builds (`ros2_robot_ws/src` + `arm/vendor` +
  `grasp/vendor`, and `Navigation_Module/src` + `nav/vendor`) and two overlays (`install/`, `install_nav/`). colcon finds packages at any
  depth, so one build from the repo root works. Nav could stay a separate build because it is slow.
- ~~Tell Zongzhe and Sherman before step 3.~~ Not needed: neither had open work, both are waiting on the refactor (Dion, 2026-09-21).

#### For Sherman (nav), found during step 2, not changed

Left for the nav owner, part of `PROJECT_PLAN` T3.5. Checked 2026-09-21 `[code]`.

- **There are two ways to drive, with two kinds of saved map.**

  | Launch file | Localises with | Map it reads | Written by |
  |---|---|---|---|
  | `robot_slam/launch/slam_localization.launch.py` | SLAM Toolbox, and starts Nav2 itself (line 210) | `<map_dir>/completed_map` (`.posegraph`, `.data`), line 150 | no launch file, saved by hand `[inferred]` |
  | `robot_navigation/launch/navigation.launch.py` | Nav2's own AMCL | `map:=` argument, default `<package>/maps/my_map.yaml` (line 16) | `slam_mapping.launch.py:39` writes `<map_dir>/current_map` (`.pgm`, `.yaml`) every 30 s |

- **`navigation.launch.py` fails without `map:=`**, because `my_map.yaml` does not exist
  (`robot_navigation/maps/README.md`). **Recommendation:** default it to
  `path("map_dir") / "current_map.yaml"` (from `gappler_common`), the image map the mapping launch
  writes, which is the format Nav2's map loader needs. It breaks no launch that works today, and
  `map:=` still overrides it.
- **`[open]` Which of the two launch files the team drives with.** Not decided. Sherman starts after
  the refactor.
- **`slam_toolbox_localization.yaml:17`**, `map_file_name`, is commented out with a note: the launch
  file always overrode it. Delete it when next working on that file.

---

## 3. Bring-up (needs the lab machine)

### 3.1 ✅ Find `xpkg_demo` — **in the repo since 2026-09-21 (T0.4)**, at `nav/vendor/demo/demo_general_chassis/`

`[code]` Both SLAM launch files include `bringup_basic_ctrl.launch.py` from a package `xpkg_demo`
that is **not in this repo** (declared `exec_depend` in `robot_slam/package.xml:12`). `[inferred]`
it is the Echo Plus vehicle/power/comm bring-up. `colcon build` may pass — it is an *exec*
dependency — but launching will fail. **Ask whoever set up the base before booking machine time.**

> **Found 2026-09-11** `[observed]`: in `~iot22/Ros2Workspaces/src/demo/` (never committed, no remote); now also in
> `~/rcp-old-ros-wkspace/src/demo/` on the lab box. Bringing it into this repo is part of §2.9.

### 3.2 ✅ Build `Navigation_Module` — **done 2026-09-14**

> ✅ **Done on the lab box 2026-09-14** `[observed]` — `./bench/build.sh nav`, **10 of 10 packages,
> 2 min 34 s, colcon exit 0**
> ([`bench-runs/2026-09-14-labbox-w4b-nav-build.txt`](bench-runs/2026-09-14-labbox-w4b-nav-build.txt)).
> **Neither blocker below was real.** Livox-SDK2 is already installed at `/usr/local/lib/`, so there
> was no sudo step, and the bench's generated manifest turned out byte-identical to `iot22`'s. Two
> corrections to what is written below: there are **10 packages, not 8**, because `Livox-SDk2/` is
> built by colcon as `livox_sdk2` through plain-CMake support **despite having no `package.xml`**, so
> the `[code]` claim that colcon ignores it is **wrong**. `robot_navigation` and `xpkg_demo` were not
> needed for the build, only for the launch, because they are `exec_depend`s. Undo with
> `rm -rf build_nav install_nav log_nav nav/vendor/livox_ros_driver2/package.xml` (path since 2026-09-21).

No `install/` exists for it anywhere. Pure compile, touches no hardware, safe remotely. Blocked on
3.1 for actually *running* it, but the build itself is independent and worth doing first.

⚠️ `[unverified]` **There is a second blocker, and it stops the build rather than the launch.**
`livox_ros_driver2/build.sh:50` generates `package.xml` from `package_ROS2.xml`; the repo ships only
`package_ROS1.xml` and gitignores the result, so colcon cannot see the package at all. See
ORIENTATION §8.15 and §2.6 item 4. Check `ls nav/vendor/livox_ros_driver2/package*.xml`
on the lab clone before booking time for this.

### 3.3 ✅ Consolidate the `realman_manip` docs onto `main` — **T0.0, done 2026-09-21**

> ➡️ **Promoted 2026-09-14 by Dion to first order of business.** It is `PROJECT_PLAN` **T0.0**, 3
> hours, Dion, no dependencies. Full file-by-file table and the reasoning are there. This section
> keeps the evidence.

**Progress 2026-09-19.** File by file, decided with Dion:

| File | Decision | Why |
|---|---|---|
| `calibration.json` | ✅ **Taken**, as `src/services/aria_device/calibration/aria_factory_calibration.json` | Live mode reads calibration from the glasses (`aria_device_controller.py:240` → `main.py:110`), but the image and eye pipelines take it as a JSON string (`image_streaming_pipeline.py:96,163`). Without glasses this file is the only source, since playback mode is broken (`main.py:116`) and no `.vrs` recording is in the repo. It is for one pair of glasses, `1WM10350101291` |
| `env.sh` | ✅ **Taken 2026-09-21**, at the repo root, with a guard added | Box check passed `[observed]`: 5 `moveit_task_constructor` packages, 12 `rm_` packages, the project `.venv` python. It already derives `REPO_ROOT` from its own location, so no re-pointing was needed. A copy outside the repo used to exit 0 with nothing loaded. It now exits 1 with a message |
| `anygrasp_node.sh` | ✅ **Taken 2026-09-21**, command unchanged, with a header comment | Both checkpoints sit at `perception/log/` in the box clone, the relative path it assumes `[observed]`. It is a record for T1.10, nothing calls it. See the two-node note below |
| `RCP_NEW_USER_STARTUP_GUIDE.md` | ✅ **Taken** into `docs/archive/`, unchanged except a header marking it historical | Paths and IPs are stale, but `bench/` and four docs cite it by section. Citations repointed to the new path |
| `docs/SETUP.md` | ✅ **Skipped** | Reviewed 2026-09-19. Everything in it is already covered by `CODE_AUDIT`, `ORIENTATION`, `TESTBENCH_PLAN` and this file. It stays readable on the branch |

**T0.0 is closed (2026-09-21).** All five files are decided and `realman_manip` is no longer treated as live. One box check is still owed: the calibration file's serial `1WM10350101291` has not been compared with the glasses, because they were not plugged in. Evidence: [`bench-runs/2026-09-21-labbox-t0.0-box-checks.txt`](bench-runs/2026-09-21-labbox-t0.0-box-checks.txt).

**The two AnyGrasp nodes are two methods, not two cameras** `[code]`. Both subscribe to the same
RealSense topics (`/camera/camera/color/image_raw`, `.../aligned_depth_to_color/image_raw`,
`/camera/sam/mask`) and publish the same `GraspCandidateArray`. Nothing on the Aria side runs
AnyGrasp.

| | `anygrasp_node.py` | `anygrasp_detection_node.py` |
|---|---|---|
| Method | Tracker (`AnyGraspTracker`, `tracker.so`). Follows grasps across frames, smoothed by a one-euro filter | Detector (`AnyGrasp`, `gsnet.so`). Fresh prediction every frame, no memory |
| Checkpoint | `checkpoint_tracking.tar` | `checkpoint_detection.tar` |
| Launched by | only `anygrasp_node.sh` on `realman_manip` | `ros2_robot_ws/src/main.py:28-32` |
| Added | 2026-03-27, `52c8ce9` | 2026-04-03, `9b8676f` "Approach till final grasp", same commit that switched `main.py` to it |

So the original authors moved to the detector in April `[code]`, yet the 2026-08-25 guide ran the
tracker `[reported]`. Which one is authoritative is T1.10's question.

`[code]` **Scoped 2026-09-10 by a full branch audit — see ORIENTATION §7.** It is a file copy, not a
merge: the branches have no common ancestor, and `main` is later than `realman_manip` on every
shared arm file. **No code should come across.**

`[code]` **Re-checked 2026-09-14 against `origin/realman_manip`.** Exactly **15 files** exist on
that branch and not on `main`. Ten are the pre-reorg flat layout `main` already reorganised
(`src/config.py`, `src/services/eye_tracking.py`, `sam3.py`, `playback.py`, `ros_subscriber.py`,
`realman_camera_subscriber.py`, `visualizer_archive.py`, `streaming_client_observer.py`,
`model_inference_demo.py`, `temp.txt`) and are not wanted. The four below are. **One file the
2026-09-10 audit did not name is worth adding:**
`ros2_robot_ws/src/rm_mtc/src/perception/anygrasp_node.sh`, a single line reading
`python anygrasp_node.py --checkpoint_path log/checkpoint_tracking.tar --filter oneeuro`. `main`
launches the **other** checkpoint, `checkpoint_detection.tar` (`ros2_robot_ws/src/main.py:28`), so
this is the only written record of which of the two was actually proven to work, and it feeds §2.6
item 3 and `PROJECT_PLAN` T1.10. Nothing calls it, so taking it changes no behaviour.

```bash
git checkout origin/realman_manip -- \
    RCP_NEW_USER_STARTUP_GUIDE.md docs/SETUP.md env.sh calibration.json \
    ros2_robot_ws/src/rm_mtc/src/perception/anygrasp_node.sh
```

⚠️ `docs/SETUP.md` lands in the shared `docs/` root, which `CLAUDE.md` forbids. **Move it into
`docs/` in the same commit.**

~~`env.sh` needs its `REPO_ROOT` re-pointed and its assumption of a repo-root `install/` re-checked
on this clone.~~ Wrong: it derives `REPO_ROOT` itself, and the `install/` layout checked out on the box (2026-09-21). `calibration.json` is the Aria factory calibration dump for device
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

> ✅ **Settled 2026-09-20 in `T0.7`.** The return-to-user leg is **out of scope**, so the "Yes" rows
> for §6.3 and §6.4 below are history, not plan. The four return-leg channels have no owner
> ([`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §3). Pose fusion is **parked rather than dropped**,
> because a later gaze-in-3D method would want the glasses transform. Out-of-scope code is commented
> out with a note saying why, not deleted, so it can come back (N-1).

| Seam | Restore for the HiCo-Nav milestone? | Note |
|---|---|---|
| §6.1 Aria stages disabled | **Partly** — pose/image streaming yes (`/aria/fused_pose` feeds the return leg) | Restoring will surface whatever made someone disable them |
| §6.2 mask never reaches robot | **Not required** for nav integration | Needed for the thesis demo. Do §2.2 first or you get the topic collision above |
| §6.3 orchestrator return leg | **Yes** — it is the nav↔manipulation handshake | Small: uncomment two subscriptions |
| §6.4 pose fusion ≠ its README | **Yes** — blocks "return to user" | Decide: restore VIO fusion, or accept ArUco-only and fix the frame + docs |

---

## 5. Done

- **2026-09-16, T0.2:** installed switch topology and persistent host addresses. RM65 and MID-360
  each replied from their required host address after a NetworkManager connection cycle. Evidence:
  [`sherman_docs/T0.2_SESSION.md`](sherman_docs/T0.2_SESSION.md).

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-14 | Claude (Opus 5) + Dion | §3.3 promoted to 🔴 and re-checked against the branch: exactly 15 files exist on `realman_manip` and not on `main`, ten of them pre-reorg duplicates. Added a fifth file to take, `anygrasp_node.sh`, which records that the verified session ran `checkpoint_tracking.tar` while `main` launches `checkpoint_detection.tar`. It is now `PROJECT_PLAN` T0.0, the first task in the plan. §3.2 marked done: the nav workspace built 10/10 on 2026-09-14, with two corrections — 10 packages not 8, and colcon does build `Livox-SDk2/` without a manifest. |
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
| 2026-09-11 | Claude (Opus 5) + Dion | §2.7 refreshed: the bench's lab-box tiers exist; pointer to TESTBENCH_PLAN's Start here; `OWNED_PREFIXES` lives in `bench/_common.py`. |
| 2026-09-13 | Claude (Opus 5) + Dion | Added §2.10: one config tree. Inventory in CODE_AUDIT §K (38 of 54 owned topics declared outside `shared/config.yaml`). Recommends ROS parameters for topic names rather than imported constants, and flags that the dynamic enum blinds the bench's extractor, so TESTBENCH_PLAN C1 must be fixed before consolidating. |
| 2026-09-13 | Claude (Opus 5) + Dion | Added §2.11: box vendor code off from ours. 226 of 2,426 tracked files are ours; vendor and owned packages are siblings in both colcon workspaces, three AnyGrasp `.so` binaries are committed inside `rm_mtc/`, and `rm_ros_interfaces` holds 77 vendor messages plus 2 of ours. Proposes a `vendor/` folder per workspace, checked that colcon and ROS resolve by package name so a move is safe, and listed the three hardcoded paths that would break. Also flags that the reorg itself is referenced in four places but never specified. |
| 2026-09-13 | Claude (Opus 5) + Dion | §2.2: added the open decision on whether to patch the `/aria/audio/prompt` subscription into `sam3_ros_node.py` now or retire the node first, with the trade-off table. Evidence is the new `CODE_AUDIT.md` L1. Also fixed the stale call-site citation `object_recognition_pipeline.py:384`→`:389` in both places it appears in §2.2 (the comparison table and hazard 1). ORIENTATION §6.5 and READING_GUIDE were re-pointed on 2026-09-13 and §2.2 was missed. Line numbers are against the working tree, which is ahead of the last commit in that file by some added comments. |
| 2026-09-13 | Claude (Opus 5) + Dion | Added the pointer to the new `PROJECT_PLAN.md`, which decides what of this register we actually do, in what order, and who owns it. This file stays the full register. |
| 2026-09-16 | OpenCode (GPT-5.6 Terra) + Sherman | Closed the one-NIC arm/LiDAR finding with observed switch, address-persistence, and source-addressed-ping evidence. Updated the RGB-D wording: an Intel RealSense D455 is provided, but USB 3 connection and live RGB-D stream remain unverified. |
| 2026-09-13 | Claude (Opus 5) + Dion | Republished the task tree map under Dion's own account, so its link is `.../65c7784d-...` and the old `.../72753a73-...` one is dead. The page content did not change. |
| 2026-09-16 | Claude (Sonnet 5) + Dion | This file moved from `docs/dion_docs/NEXT_STEPS.md` to `docs/NEXT_STEPS.md` — all global docs moved out of the per-person folder, see `docs/START_HERE.md` and `CLAUDE.md`. Content unchanged by the move; in-repo links updated. |
| 2026-09-16 | Claude (Sonnet 5) + Dion | Added §2.12: a CI task, wiring `./bench/run.sh` to run on every push, gated on `T0.5` (M0's fresh-clone acceptance test) rather than deferred past the whole plan. Assigned to Dion as `PROJECT_PLAN` `T0.10`. Removed "a continuous integration job" from `PROJECT_PLAN` §4.3 and §10 accordingly. |
| 2026-09-19 | Claude (Opus 5) + Dion | §3.3: T0.0 progress. Added the per-file decision table. `calibration.json` taken, `env.sh` and `anygrasp_node.sh` held for a box check. Added the two AnyGrasp nodes comparison: tracker vs detector on the same RealSense topics, with the commits that added each. |
| 2026-09-19 | Claude (Opus 5) + Dion | §3.3: startup guide archived to `docs/archive/`, `SETUP.md` skipped. T0.0 now waits only on the box checks for `env.sh` and `anygrasp_node.sh`. |
| 2026-09-19 | Claude (Opus 5) + Dion | Added §2.13, an exploration item: picking the gazed object by geometry rather than appearance, so two identical objects can be told apart. Three candidate methods (scene transfer, pose from the shared scene, full pose fusion) with costs and limits. Recorded as `PROJECT_PLAN` D9 and S9. |
| 2026-09-19 | Claude (Opus 5) + Dion | §2.13: added the "why this is worth doing" answer (identical objects are the hardest test case, not the pitch) and a parked open problem: the robot cannot see what the user sees, for example when the object is blocked from the knee-height base camera. |
| 2026-09-19 | Claude (Opus 5) + Dion | §2.12: CI started. `.github/workflows/bench.yml` runs Tiers 0-1 strictly on PRs into `main`, red until the 7 known static findings are fixed. Noted the planned `dev`/`main` split and new task `T0.11`. Task count 69 to 70. |
| 2026-09-19 | Claude (Opus 5) + Dion | §2.12: CI blocks merges only after T0.4 turns the bench green. Added the Monday and Wednesday night full-suite run, and deferred the runner question to T0.11. |
| 2026-09-19 | Claude (Opus 5) + Dion | §2.12: first CI run recorded. Fixed preflight reporting FAIL for lab hardware on any non-lab Linux host. |
| 2026-09-19 | Claude (Opus 5) + Dion | §2.12: bench levels renamed L0-L5, `run.sh` runs every level it can and prints a summary table. |
| 2026-09-19 | Claude (Opus 5) + Dion | §2.5 marked done after T0.3 merged. Status block added above the original survey. The OpenVINS paths and the AnyGrasp `conda run` launch stay open. Dropped two mentions of the retired "no fixes yet" rule. |
| 2026-09-19 | Claude (Opus 5) + Dion | §4: flagged the scope conflict with `PROJECT_PLAN` §4 (return leg and pose fusion out of scope), `PROJECT_PLAN` wins. Fixed the broken link to `sherman_docs/T0.2_SESSION.md` in §5. |
| 2026-09-20 | Claude (Opus 5) + Dion | **§2.2 decided: retire `sam3_ros_node.py` (Option 2).** Two reasons added: `object_recognition_pipeline.py` already subscribes to both cameras and holds the cross-view matcher, so the unified service is mostly written, and the duplicate 3.21 GB model is the largest VRAM saving in the system. Retiring it also closes L1 and the segmentation half of B3. Sequencing behind §1.3 and §2.1 is unchanged. |
| 2026-09-20 | Claude (Opus 5) + Dion | **Added §2.14: GPU budget, phase-gated model residency, and which HiCo-Nav models we need.** Target design is every process booted and idle with the models gated by phase, and the state machine subscribing to `/manipulation/start` as a real gate, which closes CODE_AUDIT B6. Key finding: navigation is the tight phase, not grasping, and a local Qwen3-Omni does not fit on a 16 GB card at all. MobileSAM is replaceable by SAM3, YOLO-World probably is not, CLIP needs an API check. The OOM risk is at the phase transition, not in either steady state. Four open threads recorded. Not yet in `PROJECT_PLAN` or the task map. |
| 2026-09-20 | Claude (Opus 5) + Dion | §2.6b: CODE_AUDIT open question 5 answered, so the I1 row now names the owner (`ros2_robot_ws/src/main.py`) and the deletion (`orchestrator.py:69-74`). Five open questions left. §2.1: pointer to the HiCo-Nav cascade and §2.14. |
| 2026-09-20 | Claude (Opus 5) + Dion | `T0.7` landed as [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md). §1.3 answered for the contract topics, §2.1 gains the decided phase-based trigger policy, §2.4 points at the frozen rename targets, §2.10's config question answered (one tree per subsystem plus a shared constants package), §4's scope conflict settled: return leg out, pose fusion parked. |
| 2026-09-21 | Claude (Opus 5) + Dion | **§3.3 closed, T0.0 done.** Box checks run: the Aria calibration file parses, `env.sh` works unchanged in `~/rcp-Gappler`, glasses serial skipped (not plugged in). Took `env.sh` (plus a guard against sourcing a copy outside the repo) and `anygrasp_node.sh` (plus a header comment). Struck the claim that `env.sh` needs `REPO_ROOT` re-pointed. Evidence in `bench-runs/2026-09-21-labbox-t0.0-box-checks.txt`. |
| 2026-09-21 | Claude (Opus 5) + Dion | §2.9 and §3.1: T0.4 done. `robot_navigation` and `xpkg_demo` in the repo, Livox template in its package, map recorded in `ASSETS.md` rather than committed. §2.9 drops from 🔴 to 🟠, the unclear rows stay open. |
| 2026-09-21 | Claude (Opus 5) + Dion | §2.12: L5 robot check added, it gates L6 hardware (was L5). Robot checks left L2. Not needed to merge. |
| 2026-09-21 | Claude (Opus 5) + Dion | §2.12: T0.10 done. `dev` created as the default branch, `bench` on `main` and `dev`, both protected. The runner and the no-skips job stay in T0.11. |
| 2026-09-21 | Claude (Opus 5) + Dion | Added §2.15: the full reorg is in scope. Target layout (four subsystems, one folder per package, `vendor/` per subsystem), three config levels with each value written once, `GAPPLER_ROOT` plus one path helper so no file finds the repo by itself, and a six-step order that teaches the bench to read YAML first. §2.11's gap note points to it. |
| 2026-09-21 | Claude (Opus 5) + Dion | §2.15: steps 1 and 2 done on the branch, now one branch `t0.10-t0.11-refactor`. Flat config names (`shared/global_config.yaml`, `<subsystem>/<subsystem>_config.yaml`). `gappler_common` finds the root from its own place, replacing the `GAPPLER_ROOT` plan. New step 7, per-subsystem env files, last. New block for Sherman: the two nav launch files, the missing Nav2 map default, the dead `map_file_name` line. Docs renamed to `shared/global_config.yaml` where they describe today. **Republish owed** for `wiring-map.html` (cites and the C1 fix) and `next-steps-map.html` (T3.5), held until the refactor ends. |
| 2026-09-21 | Claude (Opus 5) + Dion | §2.15 step 3 done on the branch: vendor code in `<subsystem>/vendor/`, `deps_ws/` and `grasp_module/` gone, OpenVINS marked unused and a deletion candidate. §2.11 steps 1, 2 and 4 marked done, its hardcoded-path table resolved. Current paths updated in §2.5, §2.6, §2.9, §3.1 and §3.2. Step 2 passed the full bench on the box (L0-L4). |
| 2026-09-21 | Claude (Opus 5) + Dion | §2.15 step 4 done on the branch: our code in `aria/`, `arm/`, `grasp/`, `nav/`, launchers renamed into `launchers/`. Added the old-to-new path table that older cites across the docs rely on. |
| 2026-09-21 | Claude (Opus 5) + Dion | Pointer at the top to the old-to-new path table in `NEXT_STEPS` §2.15, after the reorg moved our code. |
