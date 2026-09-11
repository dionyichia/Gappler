# `bench/` — offline regression bench

> **Status 2026-09-11:** tiers 0–1 and preflight built; verified on macOS only. Preflight has
> three known bugs that only show on Linux, and the contracts extractor cannot see Aria-side
> publishers — both listed in [`docs/TESTBENCH_PLAN.md`](../docs/TESTBENCH_PLAN.md) §4, which is also
> the plan for tiers 2–4. Read it before running this on the lab machine.

A safety net for refactoring this repo **without** the robot, the glasses, ROS,
or any Python dependencies. Runs on a laptop in about a second.

```bash
./bench/run.sh              # preflight -> static checks -> contract diff
./bench/run.sh preflight    # environment + hardware only
./bench/run.sh report       # inventory of every contract, plus orphan analysis
python3 bench/contracts.py snapshot   # re-baseline after a deliberate change
```

Python 3.8+, stdlib only. Nothing to install.

---

## What this is for, and what it is not

**It does not test behaviour.** It cannot: there is no hardware here, and for
much of this system there is no observed behaviour to regress against in the
first place — `RCP_NEW_USER_STARTUP_GUIDE.md` §7 records that the arm has never
been commanded to move, and `ORIENTATION.md` §6 lists four seams that are
commented out. You cannot regression-test something that has never once run.

**It tests the couplings**, which is where this refactor will actually break.
Every seam in this system is a *string*:

| Coupling | Bound by | Fails |
|---|---|---|
| node → node | topic name | silently, at runtime |
| node → TF | frame name | silently, at runtime |
| launch → node | package + executable name | at launch |
| node → config | parameter name | silently, defaults used |
| process → file | absolute path | at startup |

None of these fail at build time. A rename applied to four call sites out of
five compiles, launches, logs nothing, and does nothing. That has already
happened twice in this repo (`ORIENTATION.md` §0b): `dummy_mask_publisher.py`
publishes to `/PLACEHOLDER/sam/mask` while every consumer reads
`/camera/sam/mask`, and `VIDEO_QOS` was redeclared with `depth=1` shadowing the
shared `depth=10`.

So the bench freezes those strings and tells you when one moves.

## Keyed by contract, not by location

The planned refactor moves nearly every file (one folder per node, services
pulled out of nested packages). If the baseline were keyed by file path, every
moved file would show red and the real signal would drown.

So `contracts.py` compares **contracts**, and treats file locations as
informational:

- moving `sam3_ros_node.py` to a new package → `info: moved`
- changing the topic it publishes → `REGRESSION`

## What counts as a regression

| Verdict | Condition |
|---|---|
| **REGRESSION** | a topic / frame / param disappeared |
| **REGRESSION** | a topic's message type changed |
| **REGRESSION** | a topic lost a publisher or subscriber |
| **REGRESSION** | a *new* topic appeared with endpoints on only one side — the signature of a partial rename |
| **REGRESSION** | a static TF disappeared |
| **REGRESSION** | the hardcoded-absolute-path count went **up** |
| warning | endpoints were added |
| info | a contract stayed put but its file moved |

If a change was deliberate, re-baseline: `python3 bench/contracts.py snapshot`,
and commit `bench/golden/contracts.json` in the same commit as the change. The
diff on that file is then a readable summary of what your refactor did to the
system's interface — which is worth having in review on its own.

## The safety boundary

`preflight.py` runs everything up to **but not including** commanding the arm. That line is
enforced in the code, not just in a comment: the script never publishes to any `/rm_driver/*_cmd`
topic and never launches `grasp_state_machine` or `ros2_robot_ws/src/main.py`, because both home
the arm within seconds of start, unprompted (`ORIENTATION.md` §8.1).

Everything short of that is checked: GPU and VRAM, RAM, disk, the `PYTHONNOUSERSITE` trap, ROS
overlay completeness and the double-source trap, the venv and the `anygrasp` conda env, Aria auth,
model weights and AnyGrasp licences, NIC addressing, arm ping and port 8080, LiDAR ping, RealSense
USB, and — when a ROS graph is already running — node list, camera frame rates, `/joint_states`,
and the two TF links that gate every grasp.

What it deliberately does not and cannot test is listed at the end of every run:

- **arm motion** — homing is unprompted; nothing here launches it
- **grasp execution** — never run end to end; no known-good result to compare against
- **the gripper** — a physical command, out of scope
- **Nav2 driving** — publishing `/goal_pose` moves the base
- **the full pipeline** — severed at `object_recognition_pipeline.py:384`, so there is no
  end-to-end path to test yet

## Skips are not passes

The bench runs in two very different places and says which one it is in. On a laptop, most of
`preflight` cannot run — there is no GPU, no ROS, and no route to `192.168.1.0/24`. Those checks
report **skip with a reason**, never pass, and every run ends with them grouped by cause:

```
COULD NOT BE RUN HERE (26) -- these are unverified, not passing:

  this host has no address on 192.168.1.0/24, so the arm and LiDAR
  cannot be reached from here by definition
      - net/arm-ping
      - net/arm-port
      - net/lidar-ping
```

That distinction is the point. A missing `sam3.pt` on a laptop clone is not a failure; it is a
question that cannot be asked here. Reporting it as red would train people to ignore red.

## The three tools

### `preflight.py` — can this machine run it, and is the hardware there

Eight groups: `host`, `home`, `gpu`, `ros`, `env`, `assets`, `net`, `graph`. Run one with
`-g net`, or get JSON with `--json`. `--lab` / `--no-lab` override the "is this the lab box?" guess
(Linux + ROS or NVIDIA). `home` names the running user — per-user state is judged for that user
only — and lists every `/home/<other-user>/` path in owned code (the box moved `iot22` → `rcp2026`). Every device address is read out of the repo
(`rm_driver.cpp`, `MID360_config.json`), not copied from the docs, so the checks stay true when the
config changes.

### `contracts.py` — the baseline differ

Extracts, from Python (AST), C++ (regex), launch files (AST), URDF/xacro and
YAML: every topic with its message type and pub/sub endpoints, every TF frame,
every ROS parameter, every static transform, every launch node and remapping,
every hardcoded absolute path, and every constant defined more than once with
differing values.

AST rather than grep for Python because the repo writes
`TOPIC_MASK = "/camera/sam/mask"` and then `create_publisher(Image, TOPIC_MASK, 10)`
— a regex on the call site sees only an identifier.

`report` additionally does **orphan analysis**: topics published with nobody
listening, and subscribed with nobody publishing. That finds live bugs, not just
regressions — it is how `/PLACEHOLDER/sam/mask` surfaces without knowing to look
for it.

### `static.py` — internal consistency, no baseline needed

Ten checks, chosen for the specific ways a folder reorg breaks a ROS workspace:

| Check | Catches |
|---|---|
| `python-syntax` | parse errors |
| `undefined-names` | a name used but never imported — this bug is live on `realman_manip`'s `src/main.py` |
| `internal-imports` | an intra-repo import that no longer resolves |
| `xml-wellformed` | broken `package.xml` / URDF / xacro |
| `launch-packages` | a launch file naming a package that does not exist |
| `package-xml-deps` | a declared dependency that does not exist |
| `launch-executables` | a launch file naming an executable its package does not build |
| `launch-includes` | an included launch file that is not there |
| `install-targets` | `install(PROGRAMS ...)` pointing at a moved script |
| `generated-manifests` | a vendor package whose `package.xml` is generated but whose template is missing |

Findings are split into **code we own** and **vendor code**. Only the former
fails the run; vendor findings are pre-existing conditions of the RealMan /
Echo Plus / Livox drops, reported with `-v`.

## Scope

Vendored trees are excluded wholesale: `OpenVINS/`, `MinkowskiEngine/`,
`moveit_task_constructor/`, `anygrasp_sdk/`, `src/archive/`, and every build
artefact directory. Ownership is defined by `OWNED_PREFIXES` in `bench/_common.py` (one copy, used by all three tools) —
**update it when the reorg moves things**, or newly-moved code will be
misclassified as vendor and stop failing the build.

## What this bench does not cover

Deliberately out of scope for now, in rough order of value:

1. **Does the C++ compile.** Needs `colcon` in a `ros:humble` container. This is
   the obvious next tier and the one to add before touching
   `grasp_state_machine.cpp` (802 lines).
2. **Does a node behave.** Needs a ROS container: publish synthetic inputs,
   assert outputs. `object_approach_node`, `goal_reached_publisher`, `qos_relay`,
   `orchestrator` and the state machine are all testable this way with a mock
   `rm_driver` standing in for the arm.
3. **Replay against real data.** A 30-second rosbag of `/camera/camera/*`,
   `/livox/lidar`, `/aria/audio/prompt` and `/tf` recorded once on the lab
   machine would turn (2) from synthetic into real. Cheap to capture, high value,
   and it makes the bench useful forever afterwards offline.
4. **The rest of hardware smoke.** `preflight.py` already asserts the camera rate
   and the `base_link → camera_color_optical_frame` transform against the values
   in `RCP_NEW_USER_STARTUP_GUIDE.md` §4. Still unchecked, because each needs a
   node launched rather than merely observed: the driver's
   `product_version = RM65-BI` handshake line, and AnyGrasp's
   `Frame 0: selected 5 seed grasps`.
