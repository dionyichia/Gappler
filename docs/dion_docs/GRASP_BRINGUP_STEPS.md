# Grasp bring-up, one step at a time

**Purpose:** get the arm from "it moves to HOME" to "it picks up a box", proving one thing per
step. No step depends on anything that has not already been shown to work. Written 2026-10-06 for
the session at the machine on 2026-10-07.

**Tasks:** steps 1 to 7 are tasks in [`../task-tree.html`](../task-tree.html). That page is
authoritative for status. This file holds the reasoning, the commands and the pass criteria.

**Read with:** [`T1.6_FIRST_POWERED_SESSION.md`](T1.6_FIRST_POWERED_SESSION.md) for the cold start
(stop, boot wait, environment, shutdown order) and
[`T1.7_FIRST_COMMANDED_MOTION.md`](T1.7_FIRST_COMMANDED_MOTION.md) for how the first motion was
sent. This file does not repeat them.

---

## Why step by step

Nothing has ever moved the gripper, and we have been told grasping does not really work. If a full
cycle fails on the first try, we will not know which part failed. So each step adds one new thing.

| Step | Task | Proves | Code change? | Where |
|---|---|---|---|---|
| 1 | T1.22 | The gripper opens and closes on command | none | at the robot |
| 2 | T1.23 | The simple-execute cycle runs on the simulated arm | none | lab box, arm off |
| 3 | T1.24 | The state machine moves the real arm safely, one attempt | none | at the robot |
| 4 | T1.11 | The real arm grasps a box | none | at the robot |
| 5 | T1.12 | It grasps with a live SAM 3 mask | needs T1.25 (trigger gate) | at the robot |
| 6 | T1.14, T2.6 | Release, done, back to IDLE, a second grasp | yes | desk, then robot |
| 7 | T1.17 | The AnyGrasp path | yes (T1.8, T1.10) | mixed |

Steps 1 to 4 need no change to the state machine. Its one-shot `return;` at
`grasp/grasp_state_machine/src/grasp_state_machine.cpp:735` actually helps there: after one cycle
the worker loop exits, so the arm cannot start a second cycle by accident `[code]`.

---

## What "one grasp" means in the code

One cycle of `workerLoop()` (`grasp_state_machine.cpp:604`) is the whole fetch `[code]`:

1. **IDLE:** wait for a centroid on `/object_centroid_2d` (`:627-634`).
2. Home the arm (`:637`).
3. **SELECTING:** step the camera 4 cm at a time toward the centroid, up to 50 steps, until the
   object is closer than 0.18 m (`:641-671`, values in `grasp/grasp_config.yaml:57-60`).
4. **EXECUTING:** open the gripper, one last 10 cm step, close the gripper (`:678-728`,
   `executingSimple()` at `:594`).
5. Move to RETURN, which is HOME since T1.7 (`:729`).
6. Publish `true` on `/manipulator/return_to_user` (`:732-734`).
7. `return;` (`:735`). The worker thread ends. The node stays up but does nothing more.

All MoveIt motions run at 10% velocity and acceleration
(`grasp/grasp_state_machine/src/mtc_planner.cpp:27-28`, `:74-75`) `[code]`.

---

## The trigger, today and after T1.25

### Today

- **SAM 3 never stops publishing.** `grasp/segmentation/sam3_ros_node.py` runs on every camera
  frame with the fixed prompt prompt word `text_prompt: "box"` (`grasp/grasp_config.yaml:34`, read at `:43`) and publishes a centroid
  whenever it sees one (`:167`) `[code]`.
- **The stand-in never stops either.** `grasp/tools/dummy_mask_publisher.py` publishes an
  image-centre centroid on every depth frame `[code]`.
- **Any centroid starts a cycle.** `centroidCallback` sets `has_centroid_` on every message
  (`grasp_state_machine.cpp:206-212`) and IDLE waits only for that flag `[code]`.

So with the one-shot `return;` removed, the next camera frame would start a new approach, while the
gripper still holds the first object `[inferred]`.

### How the glasses side tells a target from "release" today

It doesn't. `aria/aria_app/services/prompt_extractor.py:49-64` asks the LLM for one thing: an
object name, or `end` for stop words. The result goes out on `/aria/audio/prompt` as plain text
`[code]`. There is no release intent, so saying "release" produces an object name or nothing
`[inferred]`. Two more details `[code]`:

- The audio worker republishes the previous result on every loop, even when nothing new was said
  (`audio_streaming_pipeline.py:115-128`).
- `object_recognition_pipeline.py:252-262` treats a prompt as new only if the word changed. Asking
  for the same object twice is not a new request.

This is a glasses-side problem, recorded on T2.6 (was T1.15). The state machine should not read words. It
should get two separate signals and trust them:

| Signal | Topic | Type | Meaning |
|---|---|---|---|
| new target | `/manipulator/grasp_request` | `std_msgs/Empty` | new, proposed in T1.25 |
| release | `/manipulator/release` | `std_msgs/Bool` | exists in the contract (A-1), nobody publishes it yet |

Until the glasses side publishes them, we send both by hand with `ros2 topic pub --once`.

### The gate (T1.25, option A), as I would build it

The centroid stream is needed during the approach, because SELECTING re-reads the latest centroid
on every step to steer (`:644-655`). So the gate is not "off". It is "only listen while
approaching":

| Phase | Centroids |
|---|---|
| IDLE, no request yet | ignored |
| Request received, until EXECUTING takes its snapshot | accepted, refreshed every frame |
| EXECUTING, return, holding | ignored. EXECUTING already uses a snapshot (`:681`) |
| After release and done | ignored until the next request |

Changes, all in `grasp_state_machine.cpp`:

1. A flag `accepting_centroids_`, false at start.
2. A subscriber on `/manipulator/grasp_request`. In IDLE it sets the flag true and clears
   `has_centroid_`. In any other state it logs "busy" and does nothing.
3. `centroidCallback` returns early when the flag is false. It also stores the time the message
   arrived.
4. Entering EXECUTING sets the flag false, right where the snapshot is taken. Every path back to
   IDLE (a failed approach, a finished cycle) also sets it false, so each request gives one attempt.
5. SELECTING gets back the stale-centroid check that is commented out at `:648-653`. It uses the
   time the message arrived rather than the camera timestamp, so it does not depend on the two
   clocks agreeing. If SAM 3 loses the box mid-approach, the arm stops and returns instead of
   steering toward the last point it saw.

Option B (T2.4) is the same idea on the SAM 3 side: start segmenting on `grasp_request`, stop on
`/manipulation/done`. It saves GPU time and keeps old centroids off the wire. A alone protects
the arm. B alone does not, because the arm would then depend on another node behaving.

**Overlap with T1.9.** IDLE writes `has_centroid_` without the lock (`:627`), and one condition
variable is shared by two mutexes. T1.25 touches exactly this code, so fix those two things in the
same change rather than building on them.

**Bench impact.** A new channel moves the contract, so run `python3 bench/contracts.py snapshot`
and add a row to `CHANNEL_CONTRACT.md`. `bench/nodes/test_state_machine_sim.py` must send a
`grasp_request` before its centroids, or the sim test will wait forever.

### After T1.25: the loop (T1.14, step 6)

Replace the `return;` at `:735` with:

1. wait for `/manipulator/release`,
2. open the gripper,
3. publish `/manipulation/done`,
4. back to IDLE, gate closed.

---

## Prep tonight (no hardware)

- [ ] `git pull` in `~/sch_repo/Gappler` (behind `dev` by two merges) and in `~/rcp-Gappler` on
      the box. Rebuild there with `./build.sh` if the pull touched C++.
- [ ] Decide who holds the power button tomorrow. Two people for steps 1, 3 and 4.
- [ ] Decide whether the exception for step 3 stands: launching `grasp_state_machine` on the real
      arm is forbidden by `CLAUDE.md` until you allow it, the same way T1.7 was allowed.
- [ ] Pick the steps 3 and 4 object: a light, empty cardboard box, no wider than the gripper's
      70 mm opening (`arm/vendor/rm_ros_interfaces/msg/Gripperset.msg`).
- [ ] Read "Things to watch" below.

---

## Step 1 (T1.22): the gripper on its own

**Proves:** the driver accepts the two gripper commands the state machine sends, and the jaws
move. Nothing else runs.

**Setup:** follow the T1.6 cold start up to "Terminal 3: confirm feedback": stop terminal first,
then the driver alone with `ros2 launch rm_driver rm_65_driver.launch.py`, then confirm
`/joint_states` at about 200 Hz. Domain 91, localhost only, in every terminal.

**Terminal 3, watch the results:**

```bash
ros2 topic echo /rm_driver/set_gripper_position_result &
ros2 topic echo /rm_driver/set_gripper_pick_on_result &
```

**Terminal 4, the commands.** These are the exact values the state machine uses
(`grasp_state_machine.cpp:229-248`):

```bash
# open fully (position 1 to 1000 is 0 to 70 mm)
ros2 topic pub --once /rm_driver/set_gripper_position_cmd rm_ros_interfaces/msg/Gripperset \
  "{position: 1000, block: false, timeout: 0}"

# close with force control (speed 200 of 1000, force 150 of 1000)
ros2 topic pub --once /rm_driver/set_gripper_pick_on_cmd rm_ros_interfaces/msg/Gripperpick \
  "{speed: 200, force: 150, block: false, timeout: 0}"
```

Order: open, close on nothing, open, then close on the cardboard box held by hand, then open.

**Pass:** each command gets `data: true` on its result topic, the jaws move each time, and the
close on the box stops on contact without crushing it.

**If nothing moves:** the driver has a `set_tool_voltage_cmd` topic (`std_msgs/UInt16`,
`arm/vendor/rm_driver/src/rm_driver.cpp:4636`). Some RealMan grippers need tool power switched on
before they answer `[unverified]`. Do not send it blind. Check the gripper's model and manual first,
and record what you find.

**Record:** the result values, what the jaws did, the time from command to motion.

### Result, 2026-10-06: air test PASS, box test owed

Sherman at the robot, driver alone. Evidence:
[`../bench-runs/2026-10-06-labbox-t1.22-gripper-only.txt`](../bench-runs/2026-10-06-labbox-t1.22-gripper-only.txt).

| Command | Result topic | Jaws | Arm |
|---|---|---|---|
| open (already open) | `data: true` | no movement, already open | still |
| close on air | `data: true` | closed fully | still |
| reopen | `data: true` | reopened | still |

`[observed]`. No tool-voltage command was needed. Delays were not measured. The close on the
cardboard box was not done, for fear of crushing it. So this shows the jaws open and close. It does
not show that the close stops safely on an object.

**Where the force limit lives.** Sherman noted the arm may have no force sensors, so the force may
have to be hard-coded. It already is, but on the gripper rather than the arm. The close command,
`set_gripper_pick_on_cmd`, is a force-controlled pick: per the message definition the jaws close at
the set speed and stop when the grip force passes the set threshold. `force` runs 1 to 1000, where
1000 is about 1.5 kg (`arm/vendor/rm_ros_interfaces/msg/Gripperpick.msg`) `[code]`. The state
machine's 150 is then roughly 0.2 kg `[inferred]`, if the scale is linear. Whether the gripper
really senses force this way, for example from motor current, is `[unverified]`. Tomorrow's box
test answers that.

**Tomorrow's box test.** An empty cardboard box held in the jaws, not by hand near them. Close at
`force: 150`, the value the state machine uses. If the box crushes, reopen and retry at 50. If
the jaws stop on contact, also try a slightly firmer box to see the grip hold. Record the force
value that holds the box without denting it. That value replaces 150 in `closeGripper()`
(`grasp_state_machine.cpp:243`). It is still hard-coded there, not in
`grasp/grasp_config.yaml` like the other tuning values since T0.14, so moving it into config
(and the open position, `:232`) is a small follow-up.

### Result, 2026-10-07: box test PASS, T1.22 done

Dion and Sherman at the robot. Closing on an empty cardboard box at `force: 150` stopped on contact
without crushing it, so 150 stays `[observed]`. On opening, the jaws squeezed the box slightly
before opening fully `[observed]`, cause unknown. Evidence appended to the same bench-runs file.

---

## Step 2 (T1.23): the cycle on the simulated arm

**Proves:** simple execute runs end to end on current `dev`, including RETURN = HOME, before it
touches the real arm.

**The real arm must be off.** The script refuses to start while the arm is reachable or any
`rm_driver` runs. That is why the 2026-10-05 attempt did not run.

```bash
pgrep -af rm_driver          # must print nothing
cd ~/rcp-Gappler && ./bench/state_machine_sim.sh
```

Or the full bench on `dev` from the Actions tab ("Run workflow").

**Pass:** the run ends 0, with the approach, the gripper close and the return all observed. Save
the log in `docs/bench-runs/`.

### Result, 2026-10-07: PASS

Full bench on `dev` from the Actions tab, run 37596048445, real arm off. Evidence:
[`../bench-runs/2026-10-07-labbox-t1.23-full-bench-dev.txt`](../bench-runs/2026-10-07-labbox-t1.23-full-bench-dev.txt).

- `IDLE -> SELECTING -> EXECUTING` on `/pipeline_state`, approach steps moved the arm.
- Gripper open at position 1000, then close at speed 200, force 150.
- The arm reached the RETURN pose (HOME) and `/manipulator/return_to_user` was published.
- The node stays in EXECUTING after the cycle. That is the one-shot `return;`, reproduced as an
  expected failure (CODE_AUDIT C7), fixed later by T1.14.

The overall run says FAIL only because one L0 check (D455 model) was skipped, and the CI job
counts a skip as a failure. Every L0 to L4 test that ran passed.

---

## Step 3 (T1.24): the first state machine run on the real arm

**Proves:** the state machine drives the real arm the way it drives the simulated one: home,
approach the box, stop near it, close, return. One attempt. We judge the motion, not the grasp.

**Needs your explicit go-ahead.** `CLAUDE.md` forbids launching `grasp_state_machine` on the real
arm. Two people, a hand on the power button the whole time.

**Do not use the launcher.** `launchers/start_camera_arm_sam3_grasp.py` starts SAM 3 rather than
the stand-in, and starts the state machine 5 s after everything else, on its own
(`:109-121`, `:154-159`) `[code]`. Start each part by hand instead, so the state machine starts
last and only when you choose. In every terminal, the T1.6 environment (domain 91, localhost only).

| Terminal | Command | Wait for |
|---|---|---|
| 1 | `python3 ~/rcp-Gappler/arm/estop/estop.py` | `E-stop ready` |
| 2 | `ros2 launch arm_bringup arm_bringup.launch.py` (driver, robot model, control, MoveIt) | the `UDP_Configuration` line, then MoveIt's "You can start planning now!" |
| 3 | the wrist camera, by serial, the way the launcher does it (`launchers/start_camera_arm_sam3_grasp.py:87-99`) | colour and depth publishing |
| 4 | `python3 grasp/tools/dummy_mask_publisher.py` | centroids on `/object_centroid_2d` |
| 5 | `ros2 topic echo /pipeline_state` | |
| 6 | `ros2 launch grasp_state_machine grasp_state_machine.launch.py` | **the arm moves 2 s after this** |

Box on the table, in view, alone. The stand-in claims every pixel is the object, so the arm reaches
for the middle of whatever the camera sees.

**Before the state machine starts, check two things moved here from T1.13 and T1.16:** the
camera driver in terminal 3 reports serial `243222074878` (the wrist D435i, not the base D455), and
`ros2 topic echo /object_centroid_2d` shows centroids near the image centre with a depth that
matches the box distance.

**Pass:** home, then a series of small steps toward the box, a stop at about 0.18 m from the
camera, gripper open, one last step, gripper close, return to HOME, `IDLE` then `SELECTING` then
`EXECUTING` on `/pipeline_state`, and `/manipulator/return_to_user` gets `true`.

**Stop (power button) if:** the arm heads for the table rather than the box, keeps stepping past
the box, or any motion is fast.

**After:** the gripper stays closed. Open it with the step 1 command.

### Where we stopped, 2026-10-07 (cold start here next time)

Nothing ran on the real arm. Found while setting up:

- **The box checkout was stale.** It was on `t3.3-mapping-tf`, built 2026-09-24. It is now on
  `dev` at `6294fae` and rebuilt. Check `git log -1` again before the next run.
- **The wrist camera sent no frames at the driver defaults** (1280x720 colour, 848x480 depth,
  30 fps). Start it at the settings that worked in T0.12:
  `rgb_camera.color_profile:=640x480x15 depth_module.depth_profile:=640x480x15`, no point cloud.
  Not yet confirmed that frames arrive at these settings. The serial check passed: the driver
  found 243222074878, the wrist D435i.
- **Object size.** The gripper opens to 70 mm. The box on hand, 60 x 45 x 45 mm, fits.
- **The stand-in does not see the box** `[code]`. It reports the image centre, at the median depth
  of the whole image. A small box never fills half the image, so the arm approaches whatever fills
  most of the view, usually the table. Decide before step 3 whether that is acceptable for a
  motion-only test, or change the stand-in to take depth from a central patch.
- **MoveIt plans every motion** `[code]`: HOME and RETURN as joint moves, each approach step as a
  straight line, all at 10% speed, collision-checked against four hard-coded boxes
  (`grasp_state_machine.cpp:302-354`). Those boxes come from an earlier setup and were never
  checked against this robot `[unverified]`.

---

## Step 4 (T1.11): the first real grasp

Same setup as step 3. Now we judge the grasp: is the box in the gripper after the return? Restart
the state machine between attempts (the one-shot `return;`). Record each attempt: grasped or not,
and where it went wrong if not.

---

## Steps 5 to 7

- **Step 5 (T1.12):** SAM 3 instead of the stand-in. Needs T1.25 first, or SAM 3 starts a cycle
  the moment the state machine is ready.
- **Step 6 (T1.14, T2.6):** release, done, back to IDLE, a second grasp in the same launch.
- **Step 7 (T1.17):** the AnyGrasp path.

---

## Things to watch

From reading the code. None of these is confirmed on the real arm.

- **No height limit during the approach.** SELECTING steps toward the centroid with no floor
  `[code]` (`selectingStep()`, `:381-434`). Only the final step pins the height to the current one (`:718`). With
  no object in view, the stand-in's centroid is the table, so the arm would step toward the table
  for up to 50 steps (2 m). MoveIt's safety walls (`addSafetyWalls()`, `:608`) are the only guard
  `[inferred]`. Never run step 3 or 4 without the box in view.
- **A failed final step ends the node.** `:725` returns from the worker loop (the check is at `:722`), just like `:735`.
  The gripper is open at that point, so it is safe, but nothing else will happen until a restart.
- **"Object grasped successfully" means nothing.** It is logged unconditionally (`:728`). Judge
  grasp success by eye.
- **Two unguarded transforms in EXECUTING** (`:694`, `:714`). If the camera's TF is late, the
  node throws and dies mid-approach `[code]`. The arm then stops wherever it is.
- **The camera offset.** The approach aims 55 px to the right of the image centre
  (`centroid_target_offset_x_px`, `grasp/grasp_config.yaml:62`). This is a tuning value, presumably for the camera-to-gripper
  offset, never checked on this mount `[unverified]`. If the gripper closes consistently beside the
  box, this is the knob to adjust.

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-10-06 | Claude Opus 5.5 + Dion | Created. Seven bring-up steps (T1.22 to T1.25 added, T1.11, T1.12, T1.14, T1.15, T1.17, T2.4 updated), the trigger as it stands, how the glasses side handles release today (it doesn't), the T1.25 gate design, commands for steps 1 to 3, things to watch. |
| 2026-10-06 | Claude Opus 5.5 + Dion | T1.13 and T1.16 closed (code merged in PR #36). Their remaining box checks, wrist serial and live stand-in centroids, added to step 3. |
| 2026-10-06 | Claude Opus 5.5 + Dion | Re-cited after T0.14 merged into dev: state machine line numbers shifted, tuning values and the SAM 3 prompt word now live in `grasp/grasp_config.yaml`. Noted the gripper force and open position are still hard-coded. |
| 2026-10-06 | Claude Opus 5.5 + Dion | Step 1 result: gripper air test PASS (Sherman at the robot), box test owed. Added where the force limit lives and tomorrow's box test plan. T1.22 marked PROGRESS. |
| 2026-10-07 | Claude Opus 5.5 + Dion | Step 2 result: PASS on the full bench on dev (Actions run 37596048445). T1.23 marked done. |
| 2026-10-07 | Claude Opus 5.5 + Dion | T1.22 box test PASS, task done. Step 3 not run. Added where we stopped and what was found while setting up. |
