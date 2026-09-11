# CODE AUDIT — 2026-09-10

**What this is:** a line-by-line read of every file this project owns (~10,600 lines), tracing each
connection from publisher to subscriber. Companion to [`ORIENTATION.md`](ORIENTATION.md) (what the
system is) and [`NEXT_STEPS.md`](NEXT_STEPS.md) (what we intend to do).

**Status of every finding here: `[unverified]`.** This was static reading only — no hardware, no
ROS, nothing executed. Line numbers are against `main` @ `2d36a89`. Several findings contradict
existing documentation; where they do, I say so, and **the doc may be right and me wrong.** Treat
this as a list of things to check, not a list of things to fix.

**Severity:** 🔴 blocks the grasp path, or is safety-relevant · 🟠 will fail at runtime ·
🟡 correctness or robustness debt.

**Read §A first.** It is one interlocking defect in three parts and it explains why the grasp
pipeline cannot work as written.

---

## A. 🔴 The grasp path cannot work — three interlocking defects

### A1. The AnyGrasp gate is inverted

`ros2_robot_ws/src/rm_mtc/src/perception/anygrasp_detection_node.py:182`

*Box 2026-09-11:* the `main` checkout on the machine (`~/rcp-github`, byte-identical to `main` @
`2d36a89`) has the same line. The hardware-verified `~/rcp-desktop` has no
`anygrasp_detection_node.py` at all. Behaviour still `[unverified]` — nothing has been run.

```python
def synced_callback(self, rgb_msg: Image, depth_msg: Image):
    if not self.intrinsics_received:
        return
    if self.pipeline_state != "IDLE":     # <-- runs ONLY when IDLE
        return
```

Its own docstring three lines above the function (`:177`) and the file header (`:6`) both say
*"runs per-frame detection when pipeline state is EXECUTING."* `ORIENTATION.md` §5 records the same
intent. The condition does the opposite: it returns early during SELECTING **and** EXECUTING, and
runs only while the state machine is idle.

### A2. The state machine accepts candidates only in EXECUTING

`ros2_robot_ws/src/rm_mtc/src/grasp_state_machine.cpp:171`

```cpp
void graspCallback(const rm_ros_interfaces::msg::GraspCandidateArray::SharedPtr msg)
{
  if (state_ != State::EXECUTING || msg->grasps.empty())
    return;
```

**The producer's gate and the consumer's gate are mutually exclusive.** AnyGrasp publishes only in
IDLE; the state machine discards everything that is not EXECUTING. No grasp candidate can ever
reach the arm.

### A3. `USE_SIMPLE_EXECUTE = true` hides A1 and A2

`grasp_state_machine.cpp:41`

With this flag set, the entire candidate-consuming path — `executingStep()`, `checkStability()`,
`slerpQuat()`, `approachAngleDeg()`, the candidate queue — is **unreachable**. What actually runs
(`:684-716`) is: snapshot the centroid, compute one Cartesian step, move, call `executingSimple()`
which does nothing but `closeGripper()`.

**So AnyGrasp's output is not used at all today.** The arm closes its gripper at a position derived
purely from the SAM3 centroid. The 3.4 GB model, the licence, the conda environment and the whole
`/grasp_candidates` contract are, at runtime, decorative.

**Why this matters more than any single bug here:** the moment anyone flips `USE_SIMPLE_EXECUTE` to
`false` to "turn the real grasping on", it will fail 100 % of the time with
`EXECUTING: no candidates received — aborting` (`:472`) after a 3-second timeout — and the cause
(A1) is in a different file, a different language, and a different conda environment.

**To check:** run the arm driver and camera, publish a fake `/pipeline_state` of `EXECUTING`, and
watch whether `/grasp_candidates` produces anything. Prediction: silence.

---

## B. 🔴 Safety-relevant

### B1. The root launcher promises an emergency stop that does not exist

`main.py:5` (docstring) — *"Press 'q' or Ctrl+C for emergency stop."*
`main.py:67` (printed at runtime) — *"Running — press 'q' for emergency stop."*

`main.py:70-71`:

```python
while True:
    time.sleep(1000)
```

**There is no keyboard handling anywhere in the file.** No `getch`, no `termios`, no thread reading
stdin. Pressing `q` does nothing. Only Ctrl+C works, via the `SIGINT` handler at `:50`.

This is the top-level entry point for a system that moves a robot arm, and it tells the operator
they have a stop key they do not have.

### B2. The e-stop may not deliver its own message on Ctrl+C

`ros2_robot_ws/src/estop.py:72-76`

```python
except KeyboardInterrupt:
    node.emergency_stop()      # publishes
finally:
    node.destroy_node()        # immediately
    rclpy.shutdown()
```

`publish()` hands the message to DDS asynchronously. Destroying the node and shutting down the
context on the next two lines can tear the participant down before delivery.

The author knew this: `orchestrator.py:121` does `time.sleep(1.5)` with the comment
*"allow topic to deliver before exit"* for exactly the same pattern. The e-stop — the one place it
matters most — does not.

Also note the publisher is created with `depth=1` and default VOLATILE durability (`:25`), so a
stop sent before `rm_driver` has subscribed is dropped silently.

**Checked on the box 2026-09-11** (`bench/estop_delivery.sh`, private ROS channel, no `rm_driver`) `[observed]`:
the loss above **did not reproduce** — after `kill -INT`, the stop arrived in 5 of 5 trials, same host
(where `rm_driver` also runs). But the mechanism is different from what this entry assumed: rclpy's own
SIGINT handler shuts the context down *before* the `except KeyboardInterrupt` block runs. The publish
still got out (logging to `/rosout` already failed: "publisher's context is invalid"), and then
`rclpy.shutdown()` at `:76` raises `RCLError: rcl_shutdown already called` → traceback, exit 1. So delivery
rests on a window nothing guarantees. The `depth=1` / VOLATILE point was not tested.

### B2a. Ctrl+C in the e-stop terminal does nothing `[observed]`

`ros2_robot_ws/src/estop.py:48-55` — `getch()` puts the terminal in raw mode while it waits for a key,
which is nearly all the time. In raw mode Ctrl+C is delivered as the character `0x03`, not as SIGINT,
so it matches none of `e`/`r`/`s`/`q` and is ignored: **no stop is sent and the script keeps running**
(`bench/estop_delivery.sh`, 2026-09-11). The `except KeyboardInterrupt` path B2 worries about is
reached only by a signal from outside (`kill -INT`). An operator whose reflex is Ctrl+C gets nothing.
Closing the terminal sends SIGHUP, which is not handled either, so no stop `[inferred]`.
Fix direction: treat `\x03` (and `\x1b`?) as `e`; handle SIGHUP/SIGTERM; publish, then sleep briefly
before shutdown, and guard the second `rclpy.shutdown()`.

### B3. The voice kill word cannot stop the arm

`prompt_extractor.py`'s system prompt maps "stop", "end", "kill", "terminate", "quit", "cancel" →
`"end"`. `goto_glasses.py:94-96` handles it by cancelling the Nav2 goal.

**Nothing in `rm_mtc` subscribes to `/aria/audio/prompt`.** Verified against the full contract
graph: the only two subscribers are `goto_glasses.py:59` and `object_approach_node.py:80`, both in
`Navigation_Module`.

So "stop the robot" stops the base and leaves the arm running. The only arm stop is `estop.py`, in
its own terminal, with the window focused (see B2).

### B4. The home pose changed and the safety warning still quotes the old one

`ros2_robot_ws/src/rm_mtc/include/rm_mtc/mtc_planner.hpp:40-47` (`realman_manip`; `:46-53` on `main`)

*Box 2026-09-11:* both values are on the machine — `~/rcp-desktop` has the `realman_manip` row and
`~/rcp-github` has `main`'s, as tabled. `[inferred]` The only built overlay known to be complete,
`~/rcp-desktop/install/`, was built from the Desktop source, so the 2026-08-25 stack would home to
the `realman_manip` pose. Any build of `main` homes to the new, unvalidated one.

| | joint1 | joint2 | joint3 | joint4 | joint5 | joint6 |
|---|---|---|---|---|---|---|
| `main` (now) | 0.0 | 0.0 | 0.7854 | **0.0** | 1.5708 | 1.5708 |
| `realman_manip` | -0.0175 | -0.1745 | 0.7854 | **-3.0718** | -1.6930 | -1.6057 |

`RCP_NEW_USER_STARTUP_GUIDE.md` §7 — the document that says *"Clear the arm's path, keep the
physical e-stop in reach"* — quotes the `realman_manip` values. **joint4 differs by 176°.** Only
joint3 is unchanged.

The arm homes unprompted within seconds of launch (`ORIENTATION.md` §8.1), and it has never been
commanded to move at all. So the first motion this arm ever makes will be to a pose nobody has
validated, and anyone who cleared space based on the guide cleared the wrong volume.

*Simulated arm 2026-09-11* `[observed]`: a build of `main` homes to `main`'s row (within 0.0001 rad) —
`bench/state_machine_sim.sh`. Reachable and collision-free in the model; that says nothing about the real cell.

### B5. The orchestrator orphans the arm driver and state machine on exit

`orchestrator.py:85-97` — the handler that terminated the child processes is commented out. Nothing
else does it. `main()`'s `finally` (`:140-142`) calls `destroy_node()` and prints "Terminated"
without touching `processes`.

**When the orchestrator exits, `background.launch.py` and `main.py` keep running.** The state
machine is still live and will still move the arm the next time a centroid arrives.

### B6. There is no in-position interlock inside the state machine

`grasp_state_machine.cpp:604-612` — the IDLE→SELECTING transition waits on `has_centroid_` alone.
The state machine does not subscribe to `/manipulation/start` at all; the orchestrator only gates
*launching* it. Once running, any centroid starts the approach, whether or not navigation says the
base is in position.

---

## C. 🔴 Concurrency defects in `grasp_state_machine.cpp`

### C1. One condition variable, two mutexes — undefined behaviour

`queue_cv_` is waited on with `centroid_mutex_` at `:607` and with `queue_mutex_` at `:464`.

`std::condition_variable` requires that **all** concurrent waiters use the same mutex; using two is
undefined behaviour, not merely a race. Symptoms would be lost wakeups and hangs that come and go
with timing and optimisation level.

### C2. The centroid is read without its lock in the loop that decides to close in

`grasp_state_machine.cpp:633-641`

```cpp
double object_depth;
{
  // auto age = this->now() - latest_centroid_.header.stamp;
  // if (age > rclcpp::Duration::from_seconds(1.0)) { ... }
  object_depth = latest_centroid_.point.z;     // <-- no lock
}
```

The braces are left over from the `std::lock_guard` that was removed along with the commented-out
staleness guard. `latest_centroid_` is a 40-byte struct written by `centroidCallback` under
`centroid_mutex_`. This unlocked read is a data race on the single value that decides
SELECTING → EXECUTING, i.e. whether the arm closes on the object.

`ORIENTATION.md` §8.8 records the missing staleness guard. It does not record that removing it also
removed the lock.

### C3. `has_centroid_ = false` written without the mutex

`:604`, one line before the block that locks `centroid_mutex_` to wait on it.

### C4. `state_` is not atomic

Declared `State state_;` (`:756`). Written by the worker thread in `publishState()` (`:206`), read
by `graspCallback()` (`:171`) on the executor thread. Torn or stale reads are possible.

### C5. `shutdown_` is a plain `bool`

Written in the destructor under `queue_mutex_`, read without any lock in `homeWithRetry()` (`:343`)
and `returnWithRetry()` (`:355`).

### C6. Reference cycle — neither destructor ever runs

`GraspStateMachine` holds `std::shared_ptr<MtcPlanner> mtc_planner_` (`:759`).
`MtcPlanner` holds `rclcpp::Node::SharedPtr node_` (`mtc_planner.hpp:37`) — the same node.

**A shared_ptr cycle.** The refcount never reaches zero, so:

- `~GraspStateMachine` never runs → `shutdown_` never set → `worker_thread_` never joined
- `~MtcPlanner` never runs → `mtc_executor_->cancel()` never called → `mtc_spin_thread_` never joined

`main()` returns from `rclcpp::spin()` with two threads still running. `node_` is only used for
logging; a `rclcpp::Node::WeakPtr` or just the logger would break the cycle.

### C7. Unbounded queue growth after a successful grasp

The success path (`:704-716`) calls `returnWithRetry()`, publishes `/manipulator/return_to_user`,
then `return`s out of `workerLoop` — **without** reaching `publishState(State::IDLE)` at `:721`.

`state_` therefore stays `EXECUTING` forever. `graspCallback` (`:171`) keeps accepting candidates
and pushing them into `candidate_queue_`, which nothing drains any more. The node also handles
exactly **one** object per launch, despite the `while (true)` structure.

**Checked 2026-09-11 on the simulated arm** (`bench/state_machine_sim.sh`) `[observed]`: after a full cycle
(return pose reached, `/manipulator/return_to_user` published) `/pipeline_state` stays `EXECUTING` and the arm
never re-homes. The candidate-queue growth itself was not measured (with `USE_SIMPLE_EXECUTE` on, nothing
publishes candidates in the test).

---

## D. Dead edges in the contract graph

Confirmed against the full publisher/subscriber inventory (`bench/contracts.py report`).

| Topic | Publishers | Subscribers | Consequence |
|---|---|---|---|
| `/manipulator/release` | **0** | 2 (`orchestrator.py:63`, `object_approach_node.py:86`) | Steps 5–6 of the orchestrator's documented flow can never fire. It has no normal termination path. |
| `/manipulation/done` | **0** | 1 (`object_approach_node.py:83`) | `_tracking_robot` never becomes true; the marker never follows the robot. Dead feature. |
| `/return_to_user/goal_reached` | 1 (`goto_glasses.py:68`) | **0** | The orchestrator's subscription is commented out at `:57-59`. The return leg reports completion into the void. |
| `/PLACEHOLDER/sam/mask` | 1 | **0** | Known — `ORIENTATION.md` §0b. |

---

## E. Frame and coordinate errors

### E1. 🔴 `goto_glasses` treats a robot-relative pose as a map coordinate

`goto_glasses.py:170-184` (`_compute_goal`) and `:198-217` (`_compute_return_goal`) read
`glasses_pose.pose.position.x/y` **directly** and stamp the result `frame_id = "map"` (`:174`,
`:204`). There is no TF lookup and `msg.header.frame_id` is never read.

`/aria/fused_pose` is stamped `"robot_base_link"` (`pose_fusion_node.py`, the
`_T_to_pose_stamped(T_map_glasses, "robot_base_link", ...)` call). So a position expressed relative
to the moving base is used as an absolute map coordinate. The robot navigates to the wrong place,
and the error changes every time the base moves.

`ORIENTATION.md` §6.4 flags the frame mismatch. What it does not say is that the consumer never
looks at the frame at all, so nothing would ever catch it.

### E2. 🟠 The naming in `pose_fusion_node` says "map" while the maths is robot-relative

```python
T_map_marker = T_map_marker = self._T_robot_marker()   # <-- double assignment
T_map_glasses = T_map_marker @ np.linalg.inv(T_camera_marker)
...
aruco_fused_msg = _T_to_pose_stamped(T_map_glasses, "robot_base_link", msg.header.stamp)
```

Three things at once: a double-assignment typo; a variable named `T_map_marker` assigned from a
function named `_T_robot_marker()`; and a variable named `T_map_glasses` published in the
`robot_base_link` frame. **This naming is the root cause of E1** — a reader downstream would
reasonably assume a map-frame pose. It is exactly the failure `ORIENTATION.md` §0b warns about.

### E3. 🟠 Timestamps are discarded twice on the perception→arm path

- `anygrasp_detection_node.py:152` — `msg.header.stamp = self.get_clock().now()`, not
  `rgb_msg.header.stamp`. The candidates are stamped with wall-clock time, not the frame they were
  computed from.
- `grasp_state_machine.cpp:241` — `transformToBase()` sets `stamped_in.header.stamp = this->now()`,
  asking TF for the transform *now* rather than when the observation was made.

The camera is on the wrist and the arm moves in 4 cm steps during SELECTING. Both of these
interpret an older observation as if it were taken at the arm's current pose.

### E4. 🟡 A third independent copy of the mount geometry

`object_approach_node.py:143` hardcodes `+ 0.48  # arm height above base`. `ORIENTATION.md` §8.10
tracks three copies of `CAMERA_X_OFFSET = 0.18`; this is a fourth constant from the same physical
measurement, in a fifth place.

---

## F. Error paths that wedge the system permanently

### F1. 🔴 `goal_reached_publisher` has three silent-failure paths

`Navigation_Module/src/robot_slam/scripts/goal_reached_publisher.py`

| Line | Situation | What it publishes |
|---|---|---|
| `:36-38` | Nav2 action server unavailable | nothing |
| `:44-46` | Nav2 rejects the goal | nothing |
| `:43` | `future.result()` raises (unguarded, inside a callback) | nothing |

Only `_on_nav_result` (`:50-56`) ever publishes `/goal_reached`.

Now pair that with `object_approach_node.py:146-150`:

```python
def _on_goal_reached(self, msg: String) -> None:
    if msg.data.strip().lower() != "success":
        return                      # <-- returns WITHOUT resetting the guard
    self._approach_done = False
```

`_approach_done` is set `True` on every approach (`:217`, `:243`) and reset **only** on a literal
`"success"`. So any of the three paths above leaves `_approach_done` stuck at `True`, and
`_on_object_pose` (`:160-161`) discards every future object pose. **One nav hiccup and the system
ignores all further detections until restarted.**

### F2. 🟠 A failed return leg can never be retried

`goto_glasses.py:222-225` — if Nav2 is unavailable, it sets `self._navigating = False` but leaves
`self._returning` as `True`, and publishes nothing to `/return_to_user/goal_reached`.

`_on_manipulation_done:116-118` then rejects every subsequent return attempt with
*"already returning to user"*, forever.

### F3. 🟠 `goto_glasses.py:247` — `future.result()` unguarded, same class as F1.

---

## G. Data integrity

### G1. 🟠 The SAM mask has no timestamp relationship to the frame it masks

`anygrasp_detection_node.py:74-75, 125-126, 195`

```python
# Latest mask cache — decoupled from RGB/depth sync
self.latest_mask = None
...
def mask_callback(self, msg: Image):
    self.latest_mask = msg          # no timestamp check, ever
...
sam_mask = self.image_to_numpy(self.latest_mask).astype(bool)
combined_mask = depth_mask & sam_mask
```

RGB and depth are synchronised to within 50 ms by `ApproximateTimeSynchronizer` (`:88-90`). The
mask is then combined from whatever arrived most recently — arbitrarily stale, from a camera on a
moving wrist. The comment presents this as a design choice; the effect is masking the current frame
with an older frame's segmentation.

There is also no shape check before `&`, so a resolution mismatch throws or broadcasts silently.

### G2. 🟠 `bgr8` is silently reinterpreted as 16-bit

`anygrasp_detection_node.py:132`

```python
dtype = np.uint8 if msg.encoding in ("rgb8", "mono8") else np.uint16
```

Any encoding that is not exactly `rgb8` or `mono8` — `bgr8`, `rgba8`, `bgra8` — falls into the
`uint16` branch. Colour data would be read as half-length garbage.

### G3. 🟡 `sam3_ros_node.py:108-110` parses RGB without checking `encoding` at all, and reshapes
with `-1` so a 4-channel image is accepted silently. Channel order into SAM 3 is unverified.

### G4. 🟡 Masks carry 0/1, not 0/255

`sam3_ros_node.py:135` and `dummy_mask_publisher.py:41` both publish `mono8` images whose "true"
pixels are `1`. Consumers use `.astype(bool)`, so the pipeline works — but **the mask renders as a
uniformly black image in RViz**, indistinguishable from an empty detection. That is a debugging
trap on the exact topic you would open RViz to inspect.

### G5. 🟡 The centroid's depth is not the depth at the centroid

`sam3_ros_node.py:12` (docstring): *"z = depth in metres at centroid pixel."*
`sam3_ros_node.py:150-155` (code): the **median over every valid pixel in the mask**.

`grasp_state_machine.cpp` back-projects the centroid pixel using that `z` as if it were the depth of
that pixel. For a tilted, large, or leaky mask the resulting 3D point is not on the object surface.
Same code, same mismatch, in `object_recognition_pipeline.py:435-441`.

### G6. 🟡 No minimum-point guard before AnyGrasp

`anygrasp_detection_node.py:198` checks only `combined_mask.sum() == 0`. Per
`RCP_NEW_USER_STARTUP_GUIDE.md` §5.1, MinkowskiEngine **segfaults rather than raising** on an
inadequate cloud. A handful of surviving points is not zero but may still be fatal.

### G7. 🟠 Null dereference when joint states are absent

`mtc_planner.cpp:120`

```cpp
rt.setRobotTrajectoryMsg(*move_group_->getCurrentState(), trajectory);
```

`getCurrentState()` returns a null `shared_ptr` when the state monitor has not received
`/joint_states`. Dereferenced with no check.

**This is exactly the symptom of the wrong-host-IP trap** (`ORIENTATION.md` §9: "Wrong host IP →
connects fine, zero feedback"). Instead of a diagnosable hang, you get a segfault in the planner.

---

## H. Ignored return values

| Where | Problem |
|---|---|
| `mtc_planner.cpp:66` | `task.execute(...)` result discarded; `moveToPose` returns `true` unconditionally. Currently unreachable (A3), but it is the "real" grasp path. |
| `mtc_planner.cpp:82, 96` | `move_group_->execute(plan)` result discarded in `moveToHome` / `moveToReturn`. `homeWithRetry` retries on **planning** failure only — an execution failure is reported as success and the state machine proceeds believing the arm is home. |

**Correction to existing docs:** `ORIENTATION.md` §8.2 lists a third self-annotated bug —
*"706 — LOGICAL ERROR: return value of moveCartesianStep ignored"*. **The comment at `:706` is
stale; the code below it does check** (`if (!mtc_planner_->moveCartesianStep(...)) { ...; return; }`).
The comment should be deleted and §8.2 amended. The real problem there is different: the failure
branch `return`s out of `workerLoop` entirely, silently bricking the node with only a `WARN`.

---

## I. Process and lifecycle

### I1. 🔴 `background.launch.py` is launched twice

- `orchestrator.py:68` launches it in `__init__`, unconditionally.
- `orchestrator.py:82` then launches `ros2_robot_ws/src/main.py` on `/manipulation/start`, which at
  `:106` launches `background.launch.py` **again**.

That is two `rm_driver` instances, both opening TCP to `192.168.1.18:8080` and both asking the arm
to send UDP state to `192.168.1.10:8089` — plus two `move_group` and two `robot_state_publisher`
publishing to the same topics and the same TF tree.

### I2. 🟠 The orchestrator fails silently on its one job

`orchestrator.py:82` — `launch(["python3", MAIN_PY_PATH], cwd=MAIN_PY_DIR)` where `MAIN_PY_DIR` is
the hardcoded `/home/iot22/GitHub/Renaissance-Capstone-Project/...` (`:23`). On any other machine
`subprocess.Popen` raises `FileNotFoundError` **inside a ROS subscription callback**, where rclpy
swallows it. The orchestrator logs *"Start received — launching main.py"* and then does nothing.

Note also that it invokes plain `python3`, not the project venv.

### I3. 🟠 The release handler no longer matches its documentation

`orchestrator.py:63-64` subscribes `Bool` to `/manipulator/release`. The module docstring (`:10`)
says *"Wait for /aria/audio/prompt (std_msgs/String) containing 'release'"*. The handler is still
called `_on_audio` (`:113`) and the string check is commented out (`:116-117`). Any `True` on that
topic now opens the gripper and shuts the orchestrator down. Combined with D1 (nothing publishes it),
this path is both wrong and dead.

### I4. 🟡 `main.py:18` — `ARIA_PYTHON` is hardcoded even though `ROOT` is computed correctly three
lines above (`:15`) and used for the other two paths. A one-line fix.

### I5. 🟡 `main.py:70-71` — the root launcher sleeps 1000 s per iteration, so a dead child is
noticed roughly never. `ros2_robot_ws/src/main.py:165` polls every 2 s.

### I6. 🟡 `orchestrator.py:45-46` — `_goal_reached` and `_bringup_done` are set up and never read.

---

## J. Lower priority

- **J1** `audio_streaming_pipeline.py:115-128` — the prompt is republished even when the
  transcription is unchanged (the `if transcription == previous_transcription` branch falls through
  to `publish`). `goto_glasses._on_audio_prompt` calls `_trigger_navigation()` on every message, and
  its `_navigating` guard clears on arrival — so a repeated transcription re-sends the robot to the
  user. There is no edge-triggering anywhere on this topic.
- **J2** `prompt_extractor.py` — the few-shot block ends with `"What time is it?" -> ` (an example
  with an *empty* completion) immediately before the user's turn. The model may continue that
  example rather than answer. Worth an eval before trusting the "end" kill word.
- **J3** `prompt_extractor.py:1-6` — mutates `sys.path` at import time, duplicating what
  `PYTHONPATH` already does at `ros2_robot_ws/src/main.py:120`.
- **J4** `qos_relay.py` — relays full `PointCloud2` messages through Python at LiDAR rate purely to
  change a QoS setting. `pointcloud_to_laserscan` can take a `qos_overrides` parameter; this node may
  be deletable.
- **J5** `goto_glasses.py:91` — stray `print(object_name)`. Not in §8.9's list.
- **J6** `grasp_state_machine.cpp:296-302` — the safety walls confine the arm to x < 0.15 m,
  |y| < 0.30 m, with a table plane at x = −0.425 m. That is a narrow slot for a ~650 mm-reach arm.
  These numbers want physical verification before the first motion.
- **J7** `grasp_state_machine.cpp:92-96` — `approachAngleDeg` computes `asin(|1 − 2(qx² + qy²)|)`,
  i.e. `asin` of a **cosine**. It happens to yield the right quantity (angle from horizontal), but it
  reads like a bug and will be "fixed" into one by someone eventually.
- **J8** Dead code in `grasp_state_machine.cpp`: `best_pose_cam` (`:485`, declared, never assigned),
  `grasped_` (`:783`, never used), and everything listed in A3.
- **J9** `goal_reached_publisher.py:52` and `goto_glasses.py:258` — `status == 4` as a magic number
  instead of `GoalStatus.STATUS_SUCCEEDED`.
- **J10** `pose_publisher.py:22-24` — copies x, y and orientation but not z.
- **J11** `sam3_ros_node.py` has **no `/pipeline_state` gate at all** — full SAM 3 inference on every
  synchronised frame pair, forever, unconditionally. This is `NEXT_STEPS.md` §2.1, restated here
  because it is the most expensive thing in the system and the gate already exists next door.
- **J12** Three nodes consume `/pipeline_state` three different ways:
  `anygrasp_detection_node.py` gates inverted (A1), `anygrasp_node.py:199` has its gate **commented
  out** so it runs unconditionally, `grasp_viz.py:65` tracks it for display only.

---

## What I did not audit

- Vendor trees: `rm_driver`, `rm_control`, `rm_example`, `rm_arm_examples`, `rm_description`,
  `rm_moveit2_config`, `rm_gazebo`, `eg2_4b_description`, `xpkg_*`, `livox_ros_driver2`, OpenVINS,
  MinkowskiEngine, MoveIt Task Constructor.
- `src/archive/`.
- `src/services/visualizer/` (524 + 220 + 207 lines) — read for topic contracts only, not logic.
  It is debug UI and cannot move the robot.
- `src/services/feature_matching.py`, `eye_tracking.py`, `arcuo.py` — skimmed for contracts, not
  audited for numerical correctness. The gaze→mask selection maths deserves its own pass.
- `nav2_params.yaml`, `slam_toolbox*.yaml` — parameter *values* not sanity-checked against the
  physical robot. `ORIENTATION.md` §10 already notes the inert `static_layer` in `local_costmap`.

---

## Open questions for you

1. **A3 — was `USE_SIMPLE_EXECUTE = true` a deliberate bring-up shortcut, or did someone forget to
   flip it back?** It changes what "the grasp pipeline" even means right now.
2. **B4 — who changed `HOME_JOINTS`, and against what?** If nobody knows, the first hardware run
   should use the `realman_manip` values, since those are the ones the safety doc describes.
3. **A1 — is the inverted gate a typo, or was there a reason to run detection during IDLE**
   (e.g. pre-computing candidates before the approach)? If the latter, A2 is the bug instead.
4. **D1 — what was meant to publish `/manipulator/release`?** Voice ("release" → the LLM returns the
   word, not a Bool), a button, or the visualiser? The orchestrator has no other way to finish.
5. **I1 — which launcher owns `background.launch.py`?** Removing it from one of the two is a
   two-line fix, but only if the ownership is decided.
6. **E1/E2 — should `/aria/fused_pose` be in `map` or in `robot_base_link`?** The publisher's
   variable names say `map`, its stamp says `robot_base_link`, and its only consumer assumes `map`.
   Two of those three have to change.

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-10 | Claude (Opus 5) + Dion | Created. Line-by-line read of ~10,600 lines of owned code. 45 findings, all `[unverified]`. Corrects `ORIENTATION.md` §8.2 (the `:706` comment is stale). |
| 2026-09-11 | Claude (Opus 5) + Dion | A1, B4: added what the box's two checkouts contain (read over SSH). Fixed B4's line citation for `main`. |
| 2026-09-11 | Claude (Opus 5) + Dion | B2 checked on the box: stop delivered 5/5 after SIGINT (loss not reproduced), but via a double-shutdown crash. New B2a: Ctrl+C key ignored by `estop.py`. |
| 2026-09-11 | Claude (Opus 5) + Dion | C7 reproduced and B4 observed on the simulated arm (`bench/state_machine_sim.sh`). |
