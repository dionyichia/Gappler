# CODE AUDIT — 2026-09-10

> **Paths moved 2026-09-21 (reorg).** Many cites below use the old layout (`src/`, `ros2_robot_ws/`,
> `Navigation_Module/`). Look up the new path in [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.15,
> "Where things moved". Line numbers inside moved files did not change with the move.


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
`anygrasp_detection_node.py` at all.

**`[observed]` 2026-09-22** (T0.12, `bench/anygrasp_replay.sh`, [`bench-runs/2026-09-22-labbox-t0.12-anygrasp-replay.txt`](bench-runs/2026-09-22-labbox-t0.12-anygrasp-replay.txt)): on a
recorded wrist-camera bag, AnyGrasp published 154 candidate sets while `/pipeline_state` was IDLE
and 0 while it was EXECUTING. The code is now at `grasp/anygrasp_node/anygrasp_detection_node.py:182`.
Fixed by T1.8.

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

**Loss reproduced 2026-09-21** `[observed]`. Four runs of the same test on the box, same code: the stop
arrived in **0, 4, 5 and 3 of 5** trials after `kill -INT`
([`bench-runs/2026-09-21-labbox-full-bench-main.txt`](bench-runs/2026-09-21-labbox-full-bench-main.txt)).
So the race is real and does bite on this machine, more under load. An e-stop that works 60 % of the time
on SIGINT is a safety defect, not a tidy-up.

**Fixed 2026-09-21 (T1.2), together with B2a and B2c** `[observed]`. `estop.py` now turns off rclpy's
SIGINT handler (`SignalHandlerOptions.NO`) and handles SIGINT, SIGTERM and SIGHUP itself, sends the stop,
then waits for subscribers to confirm it (`wait_for_all_acked`) before shutting down with
`rclpy.try_shutdown()`. It exits 0 instead of crashing. `bench/estop_delivery.sh`, five runs on the box:
`kill -INT` delivered 25 of 25, and it is now a required check, not an expected failure.

### B2c. A key pressed while the last one is being handled is lost `[observed]`

`ros2_robot_ws/src/estop.py:48-55`. When the bench sent `r` right after the `e` stop landed, the resume
never arrived in 2 of 3 runs. With a 0.5 s gap between keys it arrived 5 of 5 (2026-09-21). Cause
`[inferred]`: `getch()` calls `tty.setraw(fd)`, whose default `when=TCSAFLUSH` discards input still
waiting in the terminal. A key typed after one `getch()` returns and before the next one starts is
thrown away. Nothing is logged, so the operator cannot tell. The danger case is **S then E pressed
quickly: the e-stop can be lost.** Fix direction: put the terminal in raw mode once at start
(`tty.setcbreak` or `setraw` with `TCSANOW`), restore it at exit, and read keys in a plain loop.

**Fixed 2026-09-21 (T1.2)** `[observed]`. The terminal is switched to key-at-a-time mode once, at start,
with `TCSANOW` so nothing already typed is discarded, and restored at exit. The bench now sends the
keys back to back with no pause, and they arrived in five of five runs.

### B2a. Ctrl+C in the e-stop terminal does nothing `[observed]`

`ros2_robot_ws/src/estop.py:48-55` — `getch()` puts the terminal in raw mode while it waits for a key,
which is nearly all the time. In raw mode Ctrl+C is delivered as the character `0x03`, not as SIGINT,
so it matches none of `e`/`r`/`s`/`q` and is ignored: **no stop is sent and the script keeps running**
(`bench/estop_delivery.sh`, 2026-09-11). The `except KeyboardInterrupt` path B2 worries about is
reached only by a signal from outside (`kill -INT`). An operator whose reflex is Ctrl+C gets nothing.
Closing the terminal sends SIGHUP, which is not handled either, so no stop `[inferred]`.
Fix direction: treat `\x03` (and `\x1b`?) as `e`; handle SIGHUP/SIGTERM; publish, then sleep briefly
before shutdown, and guard the second `rclpy.shutdown()`.

**Fixed 2026-09-21 (T1.2)** `[observed]`. The terminal's signal keys are off, so Ctrl+C arrives as
`0x03`, which now sends the stop and quits. A closed terminal (end of input or SIGHUP) also sends it.
Only Q leaves without a stop. The bench's Ctrl+C case passed in five of five runs and is now required.

### B3. The voice kill word cannot stop the arm

`prompt_extractor.py`'s system prompt maps "stop", "end", "kill", "terminate", "quit", "cancel" →
`"end"`. `goto_glasses.py:94-96` handles it by cancelling the Nav2 goal.

**Nothing in `rm_mtc` subscribes to `/aria/audio/prompt`.** Verified against the full contract
graph: the only two subscribers are `goto_glasses.py:59` and `object_approach_node.py:80`, both in
`Navigation_Module`.

So "stop the robot" stops the base and leaves the arm running. The only arm stop is `estop.py`, in
its own terminal, with the window focused (see B2).

The same missing subscription also costs a capability, not just a safety property: the arm's
segmentation target cannot be set by voice at all. That side of it is **L1**.

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

`archive/RCP_NEW_USER_STARTUP_GUIDE.md` §7 — the document that says *"Clear the arm's path, keep the
physical e-stop in reach"* — quotes the `realman_manip` values. **joint4 differs by 176°.** Only
joint3 is unchanged.

The arm homes unprompted within seconds of launch (`ORIENTATION.md` §8.1), and it has never been
commanded to move at all. So the first motion this arm ever makes will be to a pose nobody has
validated, and anyone who cleared space based on the guide cleared the wrong volume.

*Simulated arm 2026-09-11* `[observed]`: a build of `main` homes to `main`'s row (within 0.0001 rad) —
`bench/state_machine_sim.sh`. Reachable and collision-free in the model; that says nothing about the real cell.

*Real arm 2026-09-23* `[observed]`: T1.3 kept `main`'s row. T1.7 sent it straight to the driver, one
joint at a time at speed 1, and every joint landed within 0.02° of it
(`dion_docs/T1.7_FIRST_COMMANDED_MOTION.md`). The tool ends slightly outside the base footprint.
The state machine itself has still never homed the real arm, so the unprompted-homing risk stands.

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

### B7. The kill-word fallback misses punctuated speech, and fires on ordinary sentences `[unverified]`

`src/services/prompt_extractor.py:110-111`

```python
if extracted in termination_keywords or any(
    kw in phrase.lower().split() for kw in termination_keywords
):
    return AudioStreamingPipelineConfig.STOP_KEYWORD
```

`phrase` is the raw Whisper transcript. **`.split()` splits on whitespace only and keeps
punctuation**, so Whisper's typical punctuated output *"Stop."* lowercases to `"stop."`, which is
not the token `"stop"` and does not match. The first clause (`extracted in termination_keywords`)
does not save it either — that one tests the *model's* output, so it only helps when the model
already recognised the stop word.

**The fallback therefore fails in exactly the case it exists to cover: the model missing the stop
word.** That is the whole reason the set is hardcoded (`:101-109`).

The same expression has the opposite failure. It matches any of `stop`, `kill`, `end`, `terminate`,
`quit`, `cancel`, `abort` appearing **anywhere** in the transcript, so *"put it at the end of the
table"* returns `STOP_KEYWORD` (`:113`) and the object name is lost. One line, both failure modes.

*Aggravating factor:* repetition. The audio ring buffer holds 10 s (`MAX_BUFFER_SECONDS = 10`,
`src/config/audio_streaming_pipeline_config.py:6`) while the poll loop runs once a second
(`ITERATION_INTERVAL_SECONDS = 1`, `:4`; `audio_streaming_pipeline.py:173-187`), and an unchanged
transcription is still published (J1, `audio_streaming_pipeline.py:128`). So a single spoken word is
re-transcribed and re-published roughly **ten times** — a false positive is ~10 stop messages, and a
genuine *"Stop."* is ~10 consecutive misses.

**Not a duplicate of the neighbouring entries, and they should be read together:** J2 is the *model*
path (the few-shot block ending in an empty completion), B7 is the *fallback* meant to back it up,
and B3 is the fact that nothing in `rm_mtc` subscribes to the result anyway. All three sit on the
one path from a spoken "stop" to a stopped robot.

**Fix direction:** tokenise on word boundaries (`re.findall(r"[a-z']+", phrase.lower())`) and
require the keyword to be the whole utterance or an edge token, not merely present in it.

**To check:** call `extract_object()` directly on `"Stop."`, `"stop"` and
`"put it at the end of the table"`. No hardware and no ROS needed — it is a pure function of the
string, given a loaded model.

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

### E1. 🔴 `goto_glasses` treats a robot-relative pose as a map coordinate `[observed]`

`goto_glasses.py:170-184` (`_compute_goal`) and `:198-217` (`_compute_return_goal`) read
`glasses_pose.pose.position.x/y` **directly** and stamp the result `frame_id = "map"` (`:174`,
`:204`). There is no TF lookup and `msg.header.frame_id` is never read.

`/aria/fused_pose` is stamped `"robot_base_link"` (`pose_fusion_node.py`, the
`_T_to_pose_stamped(T_map_glasses, "robot_base_link", ...)` call). So a position expressed relative
to the moving base is used as an absolute map coordinate. The robot navigates to the wrong place,
and the error changes every time the base moves.

`ORIENTATION.md` §6.4 flags the frame mismatch. What it does not say is that the consumer never
looks at the frame at all, so nothing would ever catch it.

**Confirmed on the box 2026-09-14** (`bench/nav_nodes.sh`, case "fused pose frame",
[`bench-runs/2026-09-14-labbox-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt)).
A wearer pose stamped `robot_base_link`, with the robot at (3, 1) in map facing +y, produced the
goal (1.00, 0.60) stamped `"map"` — the raw numbers. Where the wearer actually is puts the goal at
(2.40, 2.00): **2.0 m out**, and the error moves with the base. `[observed]`

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

**Recount 2026-09-14 `[code]`.** The full set is larger than "three plus a fourth". Six source
literals plus a test fixture carry the same two measurements: `slam_localization.launch.py:90` and
`:102`, `slam_mapping.launch.py:97`, `object_approach_node.py:53` and `:143`, `goto_glasses.py:35`,
and `bench/nodes/test_nav_nodes.py:52`. `slam_mapping.launch.py` carried only the LiDAR offset until **T3.3 (DONE 2026-09-26)** added its `robot_base_to_arm` transform; the shared 0.18 stays duplicated until T5.4 single-sources it.

### E5. 🔴 Two nodes race for Nav2 on the same spoken word `[code]`

**Verified 2026-09-14 against the working tree.** `goto_glasses.py` is not a return-leg-only node.
Its own docstring (`:7-15`) says it handles "all user-directed navigation", and it has two
independent paths that both send goals to the single `navigate_to_pose` action client created at
`:67`:

| Path | Trigger | Computes via | Frame handling |
|---|---|---|---|
| Outbound | `/aria/audio/prompt` (`:59-61`, handler `:88-100`) or `/goto_glasses/trigger` (`:51-52`) | `_compute_goal()` `:161-184` | **E1 defect**, stamps `"map"` at `:174` with no TF lookup |
| Return | `/manipulator/return_to_user` (`:63-64`, handler `:112-134`) | `_compute_return_goal()` `:186-217` | **E1 defect**, stamps `"map"` at `:204` |

`object_approach_node.py` runs the forward leg and is structurally independent: no topic of one
feeds the other, and the forward loop
(`/manipulation/goal_pose` → `/goal_pose` → `goal_reached_publisher` → Nav2 → `/goal_reached` →
`/manipulation/start`) never references `goto_glasses.py`. **The coupling is the shared action
server, not a topic.** Both nodes react to `/aria/audio/prompt`, so one spoken object name can make
`goto_glasses` fire an E1-corrupted goal at the same moment the forward leg needs Nav2 for its
approach goal.

`slam_localization.launch.py:156-159` starts `goto_glasses.py` unconditionally, and that is the
launch file for normal operation. So this is live whenever the robot is, regardless of whether the
return leg is in scope.

**Consequence for planning.** `PROJECT_PLAN.md` §4.2 puts the return leg out of scope. That decision
does **not** make E1 safe to leave: its outbound half is on the path we do use. F2 is genuinely
return-leg only (`:222-225` resets `_navigating` but never `_returning`, and the outbound leg uses
`_navigating`, which is reset correctly).

**Also confirmed in the same pass:** the E1 bug pattern, stamping `frame_id = "map"` on values that
never went through a TF lookup, exists in exactly two places repo-wide, both in `goto_glasses.py`
(`:174`, `:204`). `object_approach_node.py:232` looks identical but is correct, because its values
come from `do_transform_pose_stamped` (`:176`) after a real `lookup_transform` (`:167-174`).
`pose_publisher.py:21` is correct for the same reason.

---

## F. Error paths that wedge the system permanently

### F1. 🔴 `goal_reached_publisher` has three silent-failure paths `[observed]`

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

**Confirmed on the box 2026-09-14** (`bench/nav_nodes.sh`, two cases,
[`bench-runs/2026-09-14-labbox-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt)).
Both silent paths reproduced against a mock Nav2: on a rejected goal the bridge logged only
*"Goal rejected by Nav2."* and published nothing, and a second object 1.5 m away at a different
bearing then produced **0** `/goal_pose` — the node was wedged. With no server at all, nothing
reached `/goal_reached` in 8 s. The happy path is fine (a control case took approach → bridge →
success → `/manipulation/start`), so the defect is specific to failures. `[observed]`

The same wedge follows a plain `"failed"` outcome, which the bridge *does* publish (a control case
confirms it) — `:148` returns early for anything but `"success"`. That variant was not exercised
separately. `[inferred from the same two lines]`

### F2. 🟠 A failed return leg can never be retried `[observed]`

`goto_glasses.py:222-225` — if Nav2 is unavailable, it sets `self._navigating = False` but leaves
`self._returning` as `True`, and publishes nothing to `/return_to_user/goal_reached`.

`_on_manipulation_done:116-118` then rejects every subsequent return attempt with
*"already returning to user"*, forever.

**Confirmed on the box 2026-09-14** (`bench/nav_nodes.sh`, case "return retry",
[`bench-runs/2026-09-14-labbox-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt)).
The node's own log, in order: *"Manipulation done. Returning to user. Goal: x=1.68 y=1.00"* → 5 s →
*"[ERROR] Nav2 action server not available."* → next attempt *"[WARN] Return ignored — already
returning to user."* With Nav2 back up, the second return reached it **0** times, and
`/return_to_user/goal_reached` stayed silent throughout. `[observed]`

### F3. 🟠 `goto_glasses.py:247` — `future.result()` unguarded, same class as F1.

### F4. 🟠 All five nav nodes exit with a traceback on Ctrl+C `[observed]`

Found while tearing down each case of `bench/nav_nodes.sh` on 2026-09-14 (the bench SIGINTs the
node it started), [`bench-runs/2026-09-14-labbox-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt).
Three shapes, in `Navigation_Module/src/robot_slam/scripts/`:

| Node | `main()` | On SIGINT |
|---|---|---|
| `object_approach_node.py:306-315` | catches `KeyboardInterrupt`, then `finally: rclpy.shutdown()` | `RCLError: rcl_shutdown already called` |
| `qos_relay.py` | `try`/`finally`, no `except` | the bare `KeyboardInterrupt` **and** the `RCLError` |
| `goal_reached_publisher.py`, `goto_glasses.py`, `pose_publisher.py` | bare `rclpy.spin(Node())` — no `try`, no `destroy_node()`, no `shutdown()` | raw `KeyboardInterrupt` traceback |

The first is the same bug as `estop.py:76` ([B2](#b2-the-e-stop-may-not-deliver-its-own-message-on-ctrlc)):
rclpy installs its own SIGINT handler and shuts the context down before user code runs, so a later
`rclpy.shutdown()` always raises.

Noisy but harmless while the robot is parked. The concern is mid-leg: `goto_glasses` has a
`_cancel_navigation()` (`:231-244`) that **nothing calls on shutdown**, so Ctrl+C during a
navigation leg would leave the Nav2 goal live and the base driving with its commander gone.
`[inferred]` — nothing drove in this run, and this bench cannot test it.

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
Same code, same mismatch, in `object_recognition_pipeline.py:440-446`.

### G6. 🟡 No minimum-point guard before AnyGrasp

`anygrasp_detection_node.py:198` checks only `combined_mask.sum() == 0`. Per
`archive/RCP_NEW_USER_STARTUP_GUIDE.md` §5.1, MinkowskiEngine **segfaults rather than raising** on an
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

**Ownership decided 2026-09-20: `main.py` owns it, delete `orchestrator.py:69-74`.** Reasoning in
open question 5 below. Line numbers above are as written on 2026-09-10; against the working tree on
2026-09-20 they are `orchestrator.py:70` and `:84`, and `ros2_robot_ws/src/main.py:101`.

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

## K. The contract surface is not stated in one place

Measured 2026-09-13 with `bench/contracts.py extract`, scope "code we own". Counts carry the
extractor's known blind spot: it cannot resolve `ROS2Topics.X.value` (TESTBENCH_PLAN §4 C1), so
Aria-side publishers are under-counted, not over-counted.

### K1. 38 of 54 owned channel names are declared outside `shared/config.yaml` `[code]`

| | Topics |
|---|---|
| Declared by code we own | 54 |
| Named in `shared/config.yaml` | 16 |
| **Declared somewhere else** | **38** |

Where the other 38 live:

| Where | Count | How they are written |
|---|---|---|
| `Navigation_Module/` Python | 15 | string literal inline in `create_publisher` / `create_subscription` |
| `ros2_robot_ws/` Python | 14 | module-level `TOPIC_*` constants, re-declared per file |
| `ros2_robot_ws/` C++ | 4 | string literal inline in the constructor |
| `src/` Python | 3 | literal, despite the enum existing in the same workspace |
| YAML only (nav params) | 2 | named in `nav2_params.yaml` / `slam_toolbox*.yaml`, no code reference |

One of those last two is not a topic at all: `/home/iot22/maps/completed_map` is a `map_file_name`
value the extractor mistook for a topic because it starts with `/` (recorded as bench bug
TESTBENCH_PLAN §4 S3). **Net of it the real figures are 53 declared and 37 outside the shared
config.** The headline numbers are left as the tool reports them so re-running it reproduces them.

**Why this matters here specifically.** ROS binds publisher to subscriber by literal string at
runtime. A rename that misses one of five copies compiles, launches, and silently does nothing.
That failure mode has already occurred twice in this repo (ORIENTATION §0b), and `TOPIC_MASK` is
live proof: five copies, one of which says `/PLACEHOLDER/sam/mask` (`dummy_mask_publisher.py:14`).

**The `/rm_driver/*` case is different and worth separating.** Those names are the RealMan vendor
driver's API, so we do not get to choose them. We do choose where they are written down, and today
that is four unrelated literals: `estop.py:25`, `:26`, `orchestrator.py:49`, and
`grasp_state_machine.cpp:150`, `:153`. The safety-critical stop topic is named in exactly one
place, with no test that the string is right.

**What should change:** every channel a node opens should be stated where a reader can find it
without opening the node. See NEXT_STEPS §2.10 for the proposed shape and its constraints.

### K2. The constants pattern exists but stops at `src/` `[code]`

`src/config/` already holds typed constant groups (`AriaConfig`, `AudioStreamingPipelineConfig`,
`ModelPaths`, `EyeTrackingConfig`). Nothing outside `src/` imports them, so the same values are
re-declared as module-level constants in each node:

- `DEPTH_SCALE = 0.001` in 4 files (ORIENTATION §8.10)
- `TOPIC_MASK` in 5 files, one already divergent
- `CAMERA_X_OFFSET = 0.18` in 2 scripts plus a third literal in `slam_localization.launch.py:102`
- `NUM_CANDIDATES`, `LIMS`, `CONFIDENCE`, `TEXT_PROMPT` in `anygrasp_detection_node.py` and
  `sam3_ros_node.py`, each a tuning value nobody can find without knowing the file

These are not separate bugs from §8.10, they are its cause: there is no shared place to put a
constant that both workspaces can import, so each file grows its own. `[inferred]`

---

## L. Capability defects: the feature exists but the wiring stops short

### L1. 🟠 Voice cannot change what the arm looks for: the target word is fixed in the source

`[code]` Verified 2026-09-13 against the working tree, not against a commit.

`ros2_robot_ws/src/rm_mtc/src/perception/sam3_ros_node.py` never subscribes to
`/aria/audio/prompt`, so speech cannot change what the robot segments.

- The node has exactly **one** `create_subscription`, and it is for `CameraInfo`
  (`sam3_ros_node.py:52`). RGB and depth do not arrive that way: they come from two
  `message_filters.Subscriber` objects (`:71-72`) feeding an `ApproximateTimeSynchronizer`
  (`:73-75`). There is no other subscription in the file.
- The target word is a module-level constant, `TEXT_PROMPT = "box"` (`sam3_ros_node.py:40`), handed
  straight to `self.model.process_text_prompt(img, TEXT_PROMPT)` (`:114`). The file's own docstring
  says so at `:8`: "Runs SAM3 inference with a fixed text prompt".
- **The topic itself is live and correctly wired everywhere else.** Published by
  `src/services/aria_device/stream/audio_streaming_pipeline.py:49-50` and `:127-128`, named in
  `shared/config.yaml:14` as `audio_transcription_prompt: "/aria/audio/prompt"`, and subscribed by
  `src/services/object_recognition/object_recognition_pipeline.py` (handler `_on_prompt` at `:250`,
  which also acts on the stop keyword), `Navigation_Module/src/robot_slam/scripts/object_approach_node.py:81`
  and `Navigation_Module/src/robot_slam/scripts/goto_glasses.py:60`.

**What this means for an operator** `[inferred]`: on the robot path that actually runs today, the
object being looked for is the literal word "box", fixed when the file was written. The whole voice
chain (the Aria microphone, transcription, and the LLM object extraction in `prompt_extractor.py`)
ends at the navigation nodes and at a segmentation call site that is commented out
(`object_recognition_pipeline.py:389`). Ask for a bottle and the base will still drive, but the one
segmentation node feeding the arm keeps hunting for a box, and nothing anywhere reports that the
request was dropped.

It compounds with **A3**: with `USE_SIMPLE_EXECUTE = true`
(`ros2_robot_ws/src/rm_mtc/src/grasp_state_machine.cpp:41`), even a live prompt would only steer
the visual servo. It would not select a grasp.

**Related:** **B3** is the same missing subscription seen from the safety side (the kill word cannot
reach the arm). The two ways to fix this, and the open decision between them, are in
[`NEXT_STEPS.md`](NEXT_STEPS.md) §2.2. Read [`ORIENTATION.md`](ORIENTATION.md) §6.5 first: simply
uncommenting `object_recognition_pipeline.py:389` while `sam3_ros_node` is running leaves two
publishers racing on the same three topics.

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

1. ✅ **A3 — was `USE_SIMPLE_EXECUTE = true` a deliberate bring-up shortcut? Answered 2026-09-20:
   treat it as deliberate and leave it `true` for now.** Bring-up proceeds step by step, and the
   previous team most likely set it for a reason. It hides A1 and A2, so both are fixed before
   anyone flips it. `CHANNEL_CONTRACT` §6 B-1.
2. ✅ **B4 — who changed `HOME_JOINTS`? Answered 2026-09-20: use the `realman_manip` values**, the
   ones the safety document describes. ⚠️ **Trust neither set.** Dion's instruction is to
   recalibrate and validate the pose on the simulated arm before any powered run.
   `CHANNEL_CONTRACT` §6 B-2, task T1.3. **Superseded 2026-09-23:** T1.3 kept `main`'s row and T1.7
   validated it on the real arm (§B4).
3. ✅ **A1 — typo. Answered 2026-09-20: AnyGrasp runs during `EXECUTING`, so A1 is the bug and A2
   is correct.** `[code]` The sequence is `SELECTING` (step the arm toward the segmentation centroid
   4 cm at a time until the object is under 0.18 m away), then `EXECUTING` (AnyGrasp proposes, wait
   for a pose stable across 5 frames, then plan and execute the final move),
   `grasp_state_machine.cpp:625-716`. Candidates are therefore computed after the object is
   identified and approached and before the final planned move. Pre-computing while idle is not
   useful: candidates are in the camera frame and the wrist camera moves during the approach.
   `CHANNEL_CONTRACT` §6 G-4.
4. ✅ **D1 — what publishes `/manipulator/release`? Answered 2026-09-20: the Aria side**, publishing
   `Bool(true)` when the spoken word is "release". With the return leg out of scope the order is:
   the grasp finishes, the state machine publishes `/manipulation/done` (B-5), then release is
   accepted. ⚠️ The keyword path has its own defect, B7. `CHANNEL_CONTRACT` §3 H10 and §6 A-1.
5. ✅ **I1 — which launcher owns `background.launch.py`? Answered 2026-09-20:
   `ros2_robot_ws/src/main.py` owns it.** Delete the launch in `orchestrator.py:69-74`.

   Three reasons. `main.py` is the only launcher that needs the bringup present, because it starts
   the state machine five seconds later (`ros2_robot_ws/src/main.py:144-148`) and `move_group` has
   to exist by then, so removing it there would stop `main.py` being runnable on its own. The
   orchestrator's only use of `rm_driver` is the open-gripper publish at the end
   (`orchestrator.py:51-53`, `:127-132`), which happens after `main.py` is already up. And the
   orchestrator's copy is vestigial: its docstring puts bringup at step 4, after `goal_reached`
   (`:9`), and that handler is now commented out (`:102-112`), so the `__init__` launch is what is
   left of a step that moved and was never cleaned up.

   Side effect, stated so it is not a surprise: with this gone, no `rm_driver` exists until
   `/manipulation/start` arrives. That is an improvement, not a regression. The arm driver no
   longer comes up merely because someone started the orchestrator.

   **This sits inside a larger decision.** See [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.14. If the
   phase-gated design lands, the orchestrator stops launching processes at all and the duplicate
   disappears by construction. The deletion above is correct either way, so it is not wasted work.
6. ⏸ **E1/E2 — should `/aria/fused_pose` be in `map` or in `robot_base_link`? Parked 2026-09-20.**
   Its only consumer is the return-to-user leg, which `PROJECT_PLAN` §4 puts out of scope, so the
   frame is not fixed now. Pose fusion is parked rather than dropped: a later gaze-in-3D method
   would want the glasses transform. If it comes back, this question comes back with it.
   `CHANNEL_CONTRACT` §3 H13 and §6 A-2. The publisher's variable names say `map`, its stamp says
   `robot_base_link`, and its only consumer assumes `map`. Two of those three have to change.

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-10 | Claude (Opus 5) + Dion | Created. Line-by-line read of ~10,600 lines of owned code. 45 findings, all `[unverified]`. Corrects `ORIENTATION.md` §8.2 (the `:706` comment is stale). |
| 2026-09-11 | Claude (Opus 5) + Dion | A1, B4: added what the box's two checkouts contain (read over SSH). Fixed B4's line citation for `main`. |
| 2026-09-11 | Claude (Opus 5) + Dion | B2 checked on the box: stop delivered 5/5 after SIGINT (loss not reproduced), but via a double-shutdown crash. New B2a: Ctrl+C key ignored by `estop.py`. |
| 2026-09-11 | Claude (Opus 5) + Dion | C7 reproduced and B4 observed on the simulated arm (`bench/state_machine_sim.sh`). |
| 2026-09-13 | Claude (Opus 5) + Dion | New B7: the hardcoded kill-word fallback (`prompt_extractor.py:110-111`) misses punctuated speech and false-positives on any sentence containing a keyword. `[unverified]`, static only. Cross-referenced to J2 (model path) and B3 (no arm subscriber). |
| 2026-09-13 | Claude (Opus 5) + Dion | G5 citation `object_recognition_pipeline.py:435-441`→`:440-446`, shifted by uncommitted comments in that file. |
| 2026-09-13 | Claude (Opus 5) + Dion | New section K: the contract surface is not stated in one place. K1 (38 of 54 owned topics declared outside `shared/config.yaml`, with the breakdown by subsystem and the `/rm_driver/*` distinction), K2 (the `src/config/` constants pattern stops at `src/`). Measured with `bench/contracts.py extract`. |
| 2026-09-13 | Claude (Opus 5) + Dion | New section L and finding L1: `sam3_ros_node.py` never subscribes to `/aria/audio/prompt`, so the segmentation target is the hardcoded `TEXT_PROMPT = "box"` (`:40`). `[code]`, verified against the working tree. Cross-referenced both ways with B3 (same missing subscription, safety side), and to `NEXT_STEPS.md` §2.2 and `ORIENTATION.md` §6.5. The audit now holds **49** findings (the "45" in the 2026-09-10 row is left as the count on the day it was written). |
| 2026-09-14 | Claude (Opus 5) + Dion | New finding E5: `goto_glasses.py` has an outbound path triggered by `/aria/audio/prompt`, the same topic that starts the forward leg, and both send goals to the one `navigate_to_pose` server. It is launched unconditionally by `slam_localization.launch.py:156-159`. This corrects a scoping assumption that E1 was return-leg only and therefore droppable: its outbound half is on the live path. F2 is confirmed return-leg only. Repo-wide check found the E1 frame pattern in exactly two places, both in `goto_glasses.py`. E4 recounted: six source literals plus a test fixture, not three plus one. The audit now holds **50** findings. |
| 2026-09-14 | Claude (Opus 5) + Dion | **Recounted the findings, and the running total in this changelog was wrong.** Counting the actual entries gives **62**, not 51: 43 with their own heading, plus the four rows of D, the two rows of H and its doc correction, and the twelve bullets of J. Those three table-and-bullet sections were never in the total, and the 45 → 49 → 50 → 51 arithmetic carried the omission forward. By severity: 16 blocking or safety, 22 fail at runtime, 21 debt, of which **7 are now `[observed]`** (B2a, B4, C7, E1, F1, F2, F4). B2's message loss was tested and **not** reproduced. The published page is now generated from `code-audit-page.html`, committed alongside this file, and computes its own counts from its own entries so they cannot drift again. It carries 59 of the 62: B7, K1 and K2 are inventory rather than defects and stay here only. |
| 2026-09-14 | Claude (Opus 5) + Dion | **W7 ran on the box** (`bench/nav_nodes.sh`, 10 cases, [`bench-runs/2026-09-14-labbox-w7-nav-nodes.txt`](bench-runs/2026-09-14-labbox-w7-nav-nodes.txt)): 6 controls pass, 4 expected failures reproduced, nothing skipped, no fix needed on the first run. **E1, F1 and F2 move from `[unverified]` to `[observed]`**, each matching the mechanism this audit predicted — E1's goal landed 2.0 m out; F1 wedged the approach node so a second object got no goal; F2's `_returning` latch refused every later return. J4 is *not* a problem at MID360 rates (50/50 frames of 520 kB at 10 Hz, 1.9 ms mean latency), so the QoS relay case is a clean control, not a finding. New finding **F4**: all five nav nodes exit with a traceback on Ctrl+C, in three shapes, the first identical to B2's double-shutdown; `goto_glasses`'s `_cancel_navigation()` is never called on shutdown (`[inferred]`). The audit now holds **51** findings. |
| 2026-09-19 | Claude (Opus 5) + Dion | Repointed citations of `RCP_NEW_USER_STARTUP_GUIDE.md` to its new home, `docs/archive/`, after T0.0 brought it onto `main`. |
| 2026-09-20 | Claude (Opus 5) + Dion | **Open question 5 answered: `ros2_robot_ws/src/main.py` owns `background.launch.py`, delete `orchestrator.py:69-74`.** Reasoning recorded under the question and pointed to from I1. Refreshed I1's line citations against the working tree (`orchestrator.py:70`, `:84`, `ros2_robot_ws/src/main.py:101`). Flagged that the fix sits inside the larger phase-gating decision now in `NEXT_STEPS.md` §2.14, and is correct either way. Five open questions remain. |
| 2026-09-20 | Claude (Opus 5) + Dion | **Five more open questions answered in `T0.7`** (see [`CHANNEL_CONTRACT.md`](CHANNEL_CONTRACT.md) §6): A3 stays `true` for bring-up, B4 uses the `realman_manip` home pose but recalibrate first, A1 is a typo so AnyGrasp runs during `EXECUTING`, `/manipulator/release` comes from the Aria side after `/manipulation/done`, and E1/E2 is parked with the out-of-scope return leg. All six open questions are now answered or parked. |
| 2026-09-21 | Claude (Opus 5) + Dion | **B2 now `[observed]`**: the e-stop's SIGINT stop was lost in 0-5 of 5 trials across four box runs. **New B2c `[observed]`**: `estop.py` drops a key pressed while the previous one is being handled, so S then E fast can lose the e-stop. Both found by `bench/estop_delivery.sh`. `code-audit-page.html` not yet updated with either, still owed. |
| 2026-09-21 | Claude (Opus 5) + Dion | **B2, B2a and B2c fixed** in `estop.py` (task T1.2) and confirmed on the box: five runs of `bench/estop_delivery.sh`, every key and every stop path delivered, `kill -INT` 25 of 25. The Ctrl+C and SIGINT cases are now required checks. `code-audit-page.html` still owes these updates. |
| 2026-09-21 | Claude (Opus 5) + Dion | Pointer at the top to the old-to-new path table in `NEXT_STEPS` §2.15, after the reorg moved our code. |
| 2026-09-22 | Claude (Opus 5) + Dion | T1.1 closed in the task tree. Checked the six answers against the code: A1's gate is still inverted (`anygrasp_detection_node.py:182`), the duplicate arm bring-up launch is still in `launchers/grasp_orchestrator.py:69` (T1.2), and nothing yet publishes `/manipulation/done` or `/manipulator/release`. |
| 2026-09-22 | Claude (Opus 5) + Dion | **A1 now `[observed]`** on real wrist-camera frames by the new L4 replay (T0.12). |
| 2026-09-23 | Claude Opus 5.5 + Dion | B4: real-arm result from T1.7 added. Open question 2 answer superseded by T1.3 and T1.7. |
| 2026-09-26 | OpenCode + Sherman | E4: T3.3 DONE — `slam_mapping.launch.py` now carries `robot_base_to_arm`. Shared 0.18 still duplicated; single-sourcing stays with T5.4. |

