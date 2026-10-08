# Grasp bring-up: cold start

**Purpose:** start the grasp phase in a fresh session without re-deriving anything. Written
2026-09-23, after T1.6 passed.

**Shared task list:** [`../task-tree.html`](../task-tree.html). That page is authoritative for task
status. This file is Dion-owned reasoning and evidence pointers.

**Read first:** [`T1.6_FIRST_POWERED_SESSION.md`](T1.6_FIRST_POWERED_SESSION.md) for the powered
arm procedure. It already holds the validated cold start for the arm side, including the stop, the
boot wait and the shutdown order. This file picks up where that one stops.

---

## Where the grasp path stands

The arm and the workstation talk to each other correctly. Nothing has grasped anything.

| Task | State |
|---|---|
| T1.2 safety fixes | DONE 2026-09-22, Sherman |
| T1.4 physical setup | DONE 2026-09-23 |
| T1.6 first powered session | DONE 2026-09-23, all seven criteria pass |
| T1.3 home pose | open, Sherman. Also decides the return pose |
| T1.7 first commanded motion | next at the robot, blocked on T1.3 |
| T1.8 to T1.13 | open, desk work and lab work mixed |

---

## The one thing that changes the order

`CHANNEL_CONTRACT.md` B-1 keeps `USE_SIMPLE_EXECUTE = true` for bring-up
(`grasp/grasp_state_machine/src/grasp_state_machine.cpp:41`). While that flag is true, the arm
grasps from the SAM3 centroid and **never calls AnyGrasp**. The candidate path is dead code at
runtime (`:671`).

T1.11 and T1.12 currently list T1.8 and T1.10 as blockers. With B-1 standing, they are not: nothing
in the three T1.8 defects sits on the code path a bring-up grasp uses.

**Open decision for Dion.** Either cut T1.8 and T1.10 out of T1.11's blockers and do them after
T1.12 as a "switch AnyGrasp on" block, or keep the order and accept that roughly sixteen hours of
desk work sits in front of the first real grasp. This is parked on T1.8 in the task tree and has
not been settled.

---

## The three T1.8 defects, as they stand today

All three are still present. Line numbers checked 2026-09-23.

| | Where | What is wrong |
|---|---|---|
| A1 | `grasp/anygrasp_node/anygrasp_detection_node.py:182` | `if self.pipeline_state != "IDLE": return`. The docstring above it says the opposite. Detection runs only while the state machine is idle |
| A2 | `grasp/grasp_state_machine/src/grasp_state_machine.cpp:183` | `if (state_ != State::EXECUTING ...) return`. The consumer accepts candidates only while executing |
| A3 | `grasp/grasp_state_machine/src/grasp_state_machine.cpp:41` | `USE_SIMPLE_EXECUTE = true` makes the whole candidate path unreachable, which hides A1 and A2 |

A1 and A2 are mutually exclusive. The producer publishes only in one state, the consumer accepts
only in the other, so no candidate can ever reach the arm.

**A1 is `[observed]`, not inferred.** T0.12's replay ran a recorded wrist-camera bag through SAM 3
and AnyGrasp: 154 candidate sets published while the state was IDLE, zero while EXECUTING.
Evidence: [`../bench-runs/2026-09-22-labbox-t0.12-anygrasp-replay.txt`](../bench-runs/2026-09-22-labbox-t0.12-anygrasp-replay.txt).

**Check the fix with the bench, not by eye:**

```bash
./bench/anygrasp_replay.sh      # lab box only
```

Its `gate (A1)` case is an expected failure today. When A1 is fixed it turns from XFAIL to XPASS.

---

## Settle T1.10 before touching A1

There are **two** AnyGrasp publishers, and they disagree:

- `grasp/anygrasp_node/anygrasp_detection_node.py:182` has the inverted gate.
- `grasp/anygrasp_node/anygrasp_node.py:199` has its gate commented out, so it runs on every frame.

Deciding which one is authoritative is T1.10, and it has to come first or the fix lands in the file
nobody runs.

---

## Blockers nobody has a task for yet

These are not in T1.8. A bring-up grasp fails without them.

1. **Nothing publishes `/manipulator/release`.** Only subscribers exist
   (`launchers/grasp_orchestrator.py:66`, `nav/object_approach/object_approach_node.py:87`). After a
   grasp the gripper stays closed until someone sends the message by hand. `CHANNEL_CONTRACT` A-1
   assigns the publisher to the glasses side. No task builds it. Parked on T1.11.
2. **Nothing publishes `/manipulation/done`.** Only `nav/object_approach/object_approach_node.py:84`
   listens, and it stays latched without it. `CHANNEL_CONTRACT` B-5 assigns this to T1.8 or T1.9.
3. **The stand-in mask publisher is on a placeholder channel.**
   `grasp/tools/dummy_mask_publisher.py:19` reads `TOPIC_MASK = "/PLACEHOLDER/sam/mask"`, so nothing
   receives it. T1.11 needs this retargeted to `/camera/sam/mask` first. T2.1 asks whether to keep
   the file at all.
4. **The wrist camera is opened without a serial (T1.13).** Two RealSense cameras are plugged in, a
   D435i and a D455, and both `launchers/start_grasp_pipeline.py` and `aria/aria_app/main.py` pass
   no serial, so the driver takes whichever it finds first. Config already carries
   `WRIST_CAMERA_SERIAL`, which `grasp/tools/record_wrist_camera.sh` reads. One hour of work.

---

## Suggested order

Desk work first, because none of it needs the robot and all of it removes a lab failure:

1. **T1.13**, camera by serial. One hour.
2. **`/manipulator/release` and `/manipulation/done` publishers.** Both are small and both block a
   complete cycle.
3. **Retarget the stand-in mask publisher.**

Then at the robot, with two people:

4. **T1.3** decides home and return poses, **T1.7** commands the first motion to them.
5. **T1.11** grasps with the stand-in mask, **T1.12** with a live mask.

Then the AnyGrasp block, once a bring-up grasp works:

6. **T1.10** decides the authoritative node, **T1.8** fixes A1 to A3, **T1.9** fixes the state
   machine concurrency defects.

---

## What T1.7 now requires, and why it is the sanctioned exception

From T1.6, both `[observed]` at the robot on 2026-09-23:

- **There is no emergency stop button and no controller box.** The only physical control is a power
  button at the rear of the arm. The stop is cutting power.
- **There is no teach pendant**, so the arm cannot be hand-jogged.

The first commanded motion therefore goes through `/rm_driver/movej_cmd` at a low speed value, with
a hand on the rear power button for the whole move. That path bypasses MoveIt, so it does no
planning and no collision checking, and the pose must be correct before it is sent.

`CLAUDE.md` forbids publishing to `/rm_driver/*_cmd` on the real domain. **T1.7 is the one
sanctioned exception, and it needs two people present.** This makes T1.3's pose screening a
precondition rather than a convenience.

A new L0 check guards the class of defect that caused this: `check_joint_poses_within_limits`
(`bench/static.py:516`) fails any hard-coded joint row outside the URDF limits. It was added after
`RETURN_JOINTS` was found setting joint3 to 2.3562 against a 2.355 limit, which made the pose
unreachable and left `moveToReturn()` retrying forever.

---

## Before any hardware session

The box is shared by three people. Check before using a camera, the GPU, the arm, the glasses or the
LiDAR:

```bash
ps -eo pid,user,etime,args | grep -iE "realsense|rs_launch|ros2 launch|bench/run.sh|Runner.Worker"
nvidia-smi
fuser /dev/video*
```

If anyone else is using it, stop and say who and what. **Never stop a process you did not start.**
Start your own with `setsid` and stop them by their own process group, `kill -INT -<pgid>`.

Isolate every test with a private, empty channel: `ROS_DOMAIN_ID` plus `ROS_LOCALHOST_ONLY=1`. The
bench defaults to domain 77 and the T1.6 session used 91, so the two cannot collide.

---

## Open decisions waiting on Dion

1. **Do T1.11 and T1.12 stop waiting on T1.8 and T1.10?** See "The one thing that changes the
   order" above.
2. **Which AnyGrasp node is authoritative**, `anygrasp_detection_node.py` or `anygrasp_node.py`?
   T1.10.
3. **Who publishes `/manipulator/release`?** The contract says the glasses side. No task builds it.

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-23 | Claude Opus 5 + Dion | Created after T1.6 passed. Records the three T1.8 defects at verified line numbers, the B-1 ordering consequence, the four unticketed blockers, the suggested order, and what T1.6 changed about T1.7. |
