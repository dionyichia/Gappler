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

## Start here, 2026-10-14 (at the robot: step 5, then step 6)

**Where we are.** Steps 1 to 4 pass on the real arm. Step 6's code (T1.14, PR #75) and step 7's
prep (PR #79, draft) pass on the simulated arm
([`../bench-runs/2026-10-14-labbox-t1.14-t1.17-sim-and-replay.txt`](../bench-runs/2026-10-14-labbox-t1.14-t1.17-sim-and-replay.txt)).
`~/rcp-Gappler` is on `dev` at `d762f86`. `dev` has moved on since (PR #73, #74, #77), but only memory
graph tests and docs, no grasp code, so a `git pull` is optional.

### Step 5 (T1.12): five attempts, success rate, on `dev`

Same setup as step 4:
1. Power the arm on, wait about a minute, then `./quickstart_terminals.sh grasp` in `~/rcp-Gappler`.
   Start the state machine only after the driver has connected.
2. Two more panes (Ctrl-b %), each set up with
   `source aria/aria_env.sh && export ROS_DOMAIN_ID=91 ROS_LOCALHOST_ONLY=1`:
   the aria client, left running,
   `python aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py`, and per
   attempt the replay, `python aria/tools/replay_audio_file_to_prompt.py assets/recordings/voice_commands/pick_up_box_command.wav`.
   Stop the replay only with Ctrl-C.
3. Per attempt: restart the state machine (on `dev` it still stops after one grasp), wait for
   `IDLE`, replay. Record grasped or not, and where it went wrong if not.
4. Release by hand with three messages, not `--once`:
   `ros2 topic pub -w 1 -t 3 -r 2 /rm_driver/set_gripper_position_cmd rm_ros_interfaces/msg/Gripperset "{position: 1000, block: false, timeout: 0}"`.

Pass: 5 attempts recorded with the success rate.

### Step 6 (T1.14): release by voice, then a second grasp in the same launch

Needs the PR #75 branch on the box. Do it after step 5, with every arm process stopped.
1. In `~/rcp-Gappler`: `git fetch && git checkout t1.14-multi-grasp-loop && ./build.sh`
   (about 2 min). Afterwards put it back with `git checkout dev && ./build.sh`.
2. Same panes as step 5, plus a pane echoing `/manipulation/done`:
   `ros2 topic echo /manipulation/done std_msgs/msg/Empty`.
3. Start the state machine **once**, wait for `IDLE`, replay `pick_up_box_command.wav`.
4. After the grasp the arm goes to the return pose (HOME) and holds. Check: `/manipulation/done`
   prints once, the log says "Holding the object: waiting for /manipulator/release", the gripper
   stays shut, and a typed grasp request is refused as busy.
5. **Hold a hand under the box**, then replay `release_command.wav`. The gripper opens at HOME, so
   the box drops. Check: "Release received", gripper opens, the arm re-homes, `IDLE`.
6. Without restarting anything, put the box back and replay `pick_up_box_command.wav` again.
   Pass: a second grasp in the same launch.

Typed fallback for release:
`ros2 topic pub -w 1 -t 3 -r 2 /manipulator/release std_msgs/msg/Bool "{data: true}"`. The extra
messages after the first are logged "Release ignored" and do nothing. A release sent before the
gripper has closed is also ignored.

**Things to know from step 4:**
- The grip lands about 3 cm short of the box centre: the camera sees only the front face. Accepted,
  fixed by AnyGrasp in step 7 (T1.17).
- The `/pipeline_state` echo pane exits at start. Restart it as
  `ros2 topic echo /pipeline_state std_msgs/msg/String` (T1.26).
- The grasp client prints "Glasses client found: default prompt dropped" once the aria client is
  up. From then on only voice sets the target.
- The CPU ran at 90 to 93 C, clamped to 800 MHz. The replay takes about a minute to load, not 10 to
  20 s. Check the fan.
- The `grasp` layout plus the extra panes is a 4 by 3 grid. Name panes by position when guiding
  someone, not by tmux id: on 2026-10-13 that mix-up sent two typed requests instead of voice.

**Before touching the box:**
- Reach it with `ssh -o HostKeyAlias=10.91.242.76 rcp2026@100.87.133.60`, active again since
  2026-10-13 evening. The second node, `100.98.10.50`, went offline then with an expired key.
  `tailscale status` shows which one is active.
- `git log -1` in `~/rcp-Gappler`: `dev` at `93e49bc` or later.
- **Never run anything from a scratch clone whose env files can build.** On 2026-10-13 a test in a `/tmp` clone sourced `grasp/grasp_env.sh` in six panes. Each found no AnyGrasp venv and started compiling it, the load hit 54 and the box had to be restarted ([`../bench-runs/2026-10-13-labbox-e2e-voice-attempt-box-restart.txt`](../bench-runs/2026-10-13-labbox-e2e-voice-attempt-box-restart.txt)). Run from `~/rcp-Gappler`.
- After a restart, the CI runner needs starting again (tmux `gh-runner`).
- Check who else is on it: `ps -eo pid,user,etime,args | grep -iE "realsense|rs_launch|ros2 launch|bench/run.sh|Runner.Worker"`,
  `nvidia-smi`, `fuser /dev/video*`, `tmux ls`.
- `./bench/state_machine_sim.sh` refuses while any `rm_driver` runs. Run it before or after the
  robot session.

**Wrist camera:** `./quickstart_terminals.sh grasp` starts it at `640x480x15` with no point cloud
(T2.11). At this resolution depth stops at about 0.182 m.

---

## Why step by step

Nothing has ever moved the gripper, and we have been told grasping does not really work. If a full
cycle fails on the first try, we will not know which part failed. So each step adds one new thing.

| Step | Task | Proves | Code change? | Where |
|---|---|---|---|---|
| 1 | T1.22 | The gripper opens and closes on command | none | at the robot |
| 2 | T1.23 | The simple-execute cycle runs on the simulated arm | none | lab box, arm off |
| 3a | T1.24 | The state machine homes the real arm on start, nothing more | none | at the robot |
| 3b | T1.24 | SAM 3 on the wrist camera finds the box: mask, centroid, real depth | the stale-centroid check | at the robot, arm off |
| 3c | T1.24 | The state machine approaches the box with live SAM 3 centroids, one attempt | none | at the robot |
| 4 | T1.11 | The real arm grasps a box | none | at the robot |
| 5 | T1.12 | It grasps again and again with SAM 3 left running | T1.25 (trigger gate), built 2026-10-13 | at the robot |
| 6 | T1.14, T2.6 | Release, done, back to IDLE, a second grasp | yes | desk, then robot |
| 7 | T1.17 | The AnyGrasp path | yes (T1.8, T1.10) | mixed |

Step 3 was split on 2026-10-07 (see "Why step 3 is split" below). The stand-in is out: its depth
is the median of the whole image, so it does not tell us where the box is. SAM 3 takes the median
over the box's own mask, so its depth is the box's depth (`median_depth` in
`shared_services/segmentation/segmentation_logic.py`)
`[code]`. Steps 3c and 4 need one change to the state machine, the stale-centroid check, written with 3b. Its one-shot `return;` at
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

## The trigger, before and after T1.25

**Since T1.25 (merged 2026-10-13, #65):** a centroid starts nothing on its
own. The state machine waits in IDLE for `/manipulator/grasp_request`, then for a centroid. Send
the request by hand: `ros2 topic pub --once /manipulator/grasp_request std_msgs/msg/Empty`. It is
typed, not sent, in the last pane of `./quickstart_terminals.sh grasp`. "Before T1.25" below is
kept for the reasoning.

### Before T1.25

- **Segmentation never stops publishing.** While it has a prompt, the grasp client
  (`grasp/grasp_segmentation_client/grasp_segmentation_client.py`) sends every newest wrist frame to
  the segmentation service and publishes a centroid whenever the box is found with valid depth. With
  no glasses its prompt is the test-only `default_prompt: "box"` in `grasp/grasp_config.yaml` `[code]`.
- **The stand-in never stops either.** `grasp/tools/dummy_mask_publisher.py` publishes an
  image-centre centroid on every depth frame `[code]`.
- **Any centroid started a cycle.** `centroidCallback` set `has_centroid_` on every message
  and IDLE waited only for that flag `[code]`.

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
| new target | `/manipulator/grasp_request` | `std_msgs/Empty` | new in T1.25, `CHANNEL_CONTRACT` H10a. The aria client sends it with each object word since T2.6 |
| release | `/manipulator/release` | `std_msgs/Bool` | contract A-1. The voice pipeline sends it on "release" or "let go" since T2.6. The state machine reads it from T1.14 |

Both still work by hand with `ros2 topic pub --once`, which is the fallback when voice fails.

### The gate (T1.25, option A), as built

Built 2026-10-13 as planned below, with three additions Dion approved: the request lapses after
`grasp_request_timeout_s` (10 s, `grasp/grasp_config.yaml`) if no centroid comes, a request outside
IDLE is refused with a "busy" log line and not queued, and C1 is closed (see "C1" below). Passes on
the simulated arm: [`../bench-runs/2026-10-13-labbox-t1.25-grasp-request-gate.txt`](../bench-runs/2026-10-13-labbox-t1.25-grasp-request-gate.txt).

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
5. SELECTING gets back the stale-centroid check. **Done 2026-10-12 in T1.24 (PR #57), but with the
   camera timestamp, not the arrival time planned here.** The camera stamp counts segmentation time
   too, which is what makes a centroid stale, and the camera, SAM 3 and the state machine share one
   clock on the box. If the clients ever run on another machine, switch to the arrival time.

Option B (T2.4) is the same idea on the SAM 3 side: start segmenting on `grasp_request`, stop on
`/manipulation/done`. It saves GPU time and keeps old centroids off the wire. A alone protects
the arm. B alone does not, because the arm would then depend on another node behaving.

**Overlap with T1.9, and C1.** One condition variable is waited on with two mutexes (`CODE_AUDIT`
C1). That is allowed while only one thread ever waits on it, and only the worker thread does, so
T1.25 keeps it and says so at the IDLE wait. The real defect was shutdown: the destructor set
`shutdown_` under `queue_mutex_` only, so the IDLE wait (on `centroid_mutex_`) could miss the
wake-up and never return. The destructor now takes both locks. Left for T1.9: `state_` and
`shutdown_` are still plain values (C4, C5, `homeWithRetry` reads `shutdown_` unlocked), and C6
means the destructor never runs anyway.

**Why a request cannot race the worker.** The gate flag, the "waiting in IDLE" flag, the deadline
and the centroid all sit under `centroid_mutex_`. The worker leaves IDLE in the same locked block
that saw the centroid. A request is either taken before that, or refused as busy after it. The
deadline is read only inside that IDLE loop, so it cannot fire during SELECTING or EXECUTING.

**Why 10 s.** With the service up and the object in view, SAM 3 gives a centroid in about 1 s
(0.27 to 0.53 s a frame, 0.5 s warm-up). 10 s covers a slow, overheating box. A request sent while
the service is still loading (9.5 s for SAM 3 alone, about 60 s with the glasses client) lapses,
and nothing moves: send it again. If T2.4 ever loads SAM 3 on the request, raise the limit then.

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

## Prep before the 2026-10-07 session (done, kept for reference)

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

**Do not use the launcher.** `launchers/start_camera_arm_grasp.py` starts the state machine
5 s after everything else, on its own (`:109-121`, `:154-159`) `[code]`. Start each part by hand,
so the state machine starts last and only when you choose. In every pane, the T1.6 environment
(domain 91, localhost only). `./quickstart_terminals.sh` on the box sets that up.

### Why step 3 is split

The first try on 2026-10-07 stopped before anything moved, for two reasons. The stand-in reports
the median depth of the whole image, so the arm would approach the table, not the box. And a full
approach is too many new things at once. So step 3 is now three steps, each adding one thing:

1. **3a:** the state machine homes the real arm on start, then waits. No camera.
2. **3b:** SAM 3 finds the box. No arm.
3. **3c:** both together: the approach.

### With 3b: the stale-centroid check (code, desk)

**Done 2026-10-12, PR #57.** The check is at `grasp_state_machine.cpp:646-662`. What follows is the
plan as written, kept for the reasoning.

**The problem.** During SELECTING the state machine reads the last centroid it received and never
asks how old it is. The age check was there but commented out `[code]`. If SAM 3 loses the box,
it stops publishing, and the arm keeps stepping toward the old point, up to 50 steps of 4 cm.

This is needed for 3c, not 3a (3a never leaves IDLE). It lands with 3b, on the branch after 3a
merges, and is tested on the simulated arm before 3c.

**The fix.** Turn the check back on, with the age limit in `grasp/grasp_config.yaml` instead of
hard-coded. A centroid older than the limit ends SELECTING and the node goes back to IDLE. Test on
the simulated arm (`./bench/state_machine_sim.sh`) before the robot. Its fake detector stamps every
centroid with the current time at 10 Hz (`bench/nodes/test_state_machine_sim.py:85`), so it should
still pass `[inferred]`.

~~The limit starts at 1.0 s, the value in the commented code.~~ **Set to 2.0 s (2026-10-12, Dion),
written on branch `t1.24-t2.8-centroid-age-and-voice-replay`.** The age counts from when the camera
took the frame, so it includes segmentation. Measured in 3b: a centroid every 0.54 s and 0.3 to
0.5 s of SAM 3 time, so the newest centroid is about 1.05 s old just before the next arrives, and
1.6 s after one dropped frame. 1.0 s would end good approaches. The check now also takes the lock
before reading the centroid, and publishes `IDLE` when an approach ends. `./bench/state_machine_sim.sh`
has a new case: the fake detector goes quiet mid-approach, the node must log "object lost" and
publish `IDLE`, then the object comes back and the cycle carries on.

### Step 3a: the state machine homes the real arm

**Proves:** the state machine reaches the real arm through MoveIt and homes it. HOME itself was
already proven by direct command in T1.7.

**How.** The state machine homes on its own 2 s after it starts, then publishes `IDLE` and waits
for a centroid (`:606-609`, `:628-634`) `[code]`. So start it with no camera and no SAM 3: nothing
publishes a centroid, and it stops at HOME. No hand-sent message, no code change needed for 3a.

| Pane | Command | Wait for |
|---|---|---|
| `./quickstart_terminals.sh arm` | stop, driver and MoveIt, `/joint_states` rate, one empty pane | `E-stop ready`, then MoveIt's "You can start planning now!" |
| a new pane, T1.6 environment | `ros2 topic echo /pipeline_state` | |
| empty pane, after `source grasp/grasp_env.sh` | `ros2 launch grasp_state_machine grasp_state_machine.launch.py` | **the arm moves to HOME 2 s after this** |

Start the arm away from HOME (as in T1.7) so the move is visible.

**Pass:** a slow move to HOME, then `IDLE` on `/pipeline_state`, then no further motion for a
minute. Stop the state machine with Ctrl-C: the arm stays put.

**Stop (power button) if:** the arm moves anywhere but HOME, moves fast, or moves again after
`IDLE`.

### Result, 2026-10-07: 3a PASS

Dion at the robot, session from `./quickstart_terminals.sh arm` on the box (`dev` at `3dde592`),
domain 91, localhost only. The state machine homed the arm 2 s after start, published `IDLE`,
and nothing moved after that `[reported]`. From the log: safety walls added, plan 3.2 s, execute
4.0 s, `State → IDLE`. No errors in the state machine. MoveIt's warnings were the usual ones (no
octomap sensor, default acceleration limits). Log:
[`../bench-runs/2026-10-07-labbox-t1.24-3a-home.txt`](../bench-runs/2026-10-07-labbox-t1.24-3a-home.txt).

### Step 3b: SAM 3 finds the box (arm off)

**Proves:** SAM 3 on the wrist camera puts a mask on the box, and its centroid depth matches a tape
measure. Nothing on the arm runs, so nothing can move.

**First:** `nvidia-smi` and `fuser /dev/video*`. SAM 3 needs the GPU, and someone else may be on
it. The service and the grasp client have run on this box on the recorded wrist-camera bag
(T2.1, `bench/anygrasp_replay.sh`: 117 masks in 60 s, box at 0.36 m), never on the live camera.

| Pane | Command | Wait for |
|---|---|---|
| 1, `arm/arm_env.sh` | `ros2 launch realsense2_camera rs_launch.py "serial_no:='_243222074878'" align_depth.enable:=true rgb_camera.color_profile:=640x480x15 depth_module.depth_profile:=640x480x15` | serial `243222074878` in the log, then frames: `ros2 topic hz` on the colour topic |
| 2, `shared_services/shared_services_env.sh` | `python ~/rcp-Gappler/shared_services/segmentation/segmentation_service.py` | `Segmentation service ready on /segmentation/segment` (SAM 3 takes a few seconds to load) |
| 2b, `grasp/grasp_env.sh` | `python ~/rcp-Gappler/grasp/grasp_segmentation_client/grasp_segmentation_client.py` | `looking for: default prompt 'box' (testing only)` |
| 3 | `ros2 topic hz /object_centroid_2d` | the rate |
| 4 | `ros2 topic echo /object_centroid_2d` | x, y near the box in the image, z in metres |
| 5 | `rqt_image_view /camera/sam/mask` | the mask |

The quickstart `grasp` layout starts this camera command itself since T2.11, but it also starts
`arm_bringup`. With the arm off, either is fine. The 2026-10-13 run started these panes by hand.

**Record:**
- the centroid rate (it sets the age limit for 3c)
- z against a tape measure, camera glass to box face, at 0.6, 0.4 and 0.25 m
- slide the box toward the camera and note the distance where z stops coming: `/camera/sam/mask`
  keeps arriving but `/object_centroid_2d` stops, because the client publishes no centroid without
  valid depth under the mask. If that is above 0.18 m, the approach can never reach its stop
  depth: raise `execute_depth_thresh_m` or rethink before 3c.
- with the box out of view: does SAM 3 still find a "box" somewhere?

**Pass:** the mask covers the box, z is within about 2 cm of the tape, the rate is steady.

### Result, 2026-10-12: 3b partial, run over SSH, box and tape checks owed

Run from the Mac over SSH while Dion reviewed code, `t2.1-sam3-service` on the box (code as at
`de87183`), domain 91, localhost only. Camera, service and client started by hand as in the table.
The wrist camera pointed at the ceiling, no box in view.

- **Live camera into SAM 3 works.** Serial `243222074878` found, depth at 10 Hz. The service
  loaded SAM 3 in 10 s and answered every call.
- **No box in view, no box found.** The client ran with the default prompt `box` and SAM 3
  returned nothing, so nothing was published on `/camera/sam/mask` or `/object_centroid_2d`.
  No false box.
- **Speed: one SAM 3 call on one 640x480 frame takes 0.27 to 0.53 s**, so about 2 to 3.7
  frames per second, with nothing else on the GPU. 0.27 s at first, then it slowed as the CPU
  throttled (below). The age limit for 3c is 2.0 s, see the stale-centroid check above.
- **The client's centroid rate: 1.85 per second**, 0.53 to 0.56 s apart, steady, with the aria
  client sending the word `light` (T2.8 typed-word check, PASS). Just under the 2 per second bar,
  with the CPU throttled. The age limit is set to 2.0 s with this in mind (see the stale-centroid
  check above).
- **Depth on a real object.** Prompt `light` found the ceiling light panel (score 0.84), depth
  1.255 m. Dion checked the mask by eye: it fits the panel. Depth not checked against a tape.
  Picture: [`t1.24_3b/2026-10-12-ceiling-light-mask.png`](t1.24_3b/2026-10-12-ceiling-light-mask.png).
- **GPU (RTX 4060 Ti, 16 GB).** The service holds 5.8 GB. During back-to-back calls: 61% busy on
  average, 80 W of 165 W, 55 C, not throttled. So the GPU has room for AnyGrasp alongside.
- **CPU (i5-13400F, 16 threads).** The service uses about 1.2 threads on average, 2.1 at peak.
  The camera driver about 0.13. The whole box is only 12% busy.
- **The CPU is overheating.** 89 C at 12% load. The kernel forces it idle a quarter of the time
  and the cores average 0.8 GHz. That is the likely cause of the slowdown from 0.27 to 0.5 s.
  Likely a fan or cooler problem `[inferred]`, not checked at the box. Worth a look before 3c.

Full record: [`../bench-runs/2026-10-12-labbox-t1.24-3b-live-sam3.txt`](../bench-runs/2026-10-12-labbox-t1.24-3b-live-sam3.txt).

Still owed, needs someone at the robot: box in view, the centroid rate on the box, z against
the tape at 0.6, 0.4 and 0.25 m, and the distance where z stops.

### Result, 2026-10-13: 3b PASS, one finding for 3c

Dion at the robot, arm off, Claude over SSH. Session started by hand (camera, service, client,
monitors), not with the quickstart `grasp` layout, which also starts `arm_bringup`.

| Check | Result |
|---|---|
| z at 0.25 m | 0.244 to 0.267. Pass |
| z at 0.4 m | 0.373 to 0.414. Pass |
| z at 0.6 m | first try unsteady (0.45 to 0.61), second try 0.591 to 0.608. Pass |
| Rate, box in view | 0.27 to 0.52 s apart, about 2 to 3.5 per second |
| Box out of view | no centroids, no false box. Pass |
| Closest valid z | 0.157 m, below the 0.18 m stop. Pass |

**Finding: too close reads far.** Closer than about 0.157 m the client did not go quiet. It sent
z of about 1.26 m for 17 frames. The box is inside the camera's minimum range, so most pixels
under the mask have no reading, and the median of the few left is the background `[inferred]`.
The approach steps 4 cm and stops below 0.18 m, so from 0.19 m one step lands near 0.15 m, reads
1.26 m, and keeps going `[inferred]`.

**Fix (branch `t1.24-min-valid-depth`):** `median_depth` gives no depth unless at least half the
mask has a reading (`min_valid_depth_fraction: 0.5` in `shared_services_config.yaml`). No depth
means the client publishes no centroid, and the stale-centroid check ends the approach after
2.0 s. Not yet checked at the box: 0.5 may also drop valid readings just above 0.18 m. If z stops
before 0.18 m, lower the fraction.

SAM 3 took 53 s to load (10 s on 10-12) and the CPU was at 90 C again.

Record: [`../bench-runs/2026-10-13-labbox-t1.24-3b-box-and-tape.txt`](../bench-runs/2026-10-13-labbox-t1.24-3b-box-and-tape.txt).

### Step 3c: the approach with live SAM 3

**Proves:** the full step 3: home, approach the box, stop at 0.18 m, open, last 10 cm step, close,
return to HOME, `true` on `/manipulator/return_to_user`. One attempt.

3a's arm panes, plus 3b's camera, service and client panes. `ros2 topic echo /pipeline_state`. The state
machine last. The one-shot `return;` stops it after one cycle either way.

Run it from `./quickstart_terminals.sh grasp` in `~/rcp-Gappler` (gate merged 2026-10-13, #65). On
2026-10-13 the gate was still unmerged, so the state machine ran from a separate build,
`~/rcp-Gappler-t1.25`, since deleted.

1. Start the state machine pane only after the driver pane prints "RM_65_driver is running".
2. Wait for the home move and `IDLE` on `/pipeline_state`. The arm stays still. The state machine
   logs `Centroid ignored: no grasp request open` every 5 s while the client publishes.
3. Box in view, the client logging centroids, hand on the power button. Send the request from the
   last pane: `ros2 topic pub --once /manipulator/grasp_request std_msgs/msg/Empty`
4. Expect `Grasp request: accepting centroids for 10.0s`, then `SELECTING` within about a second.
   If no centroid comes in 10 s, it logs `Grasp request lapsed` and stays in IDLE. Send it again.

Box on the table, in view, alone.

**Pass:** home, small steps toward the box, a stop at about 0.18 m, gripper open, one more step,
gripper close, back to HOME, `IDLE` then `SELECTING` then `EXECUTING` on `/pipeline_state`, and
`/manipulator/return_to_user` gets `true`.

**Stop (power button) if:** the arm heads for the table, keeps stepping past the box, or moves
fast. If SAM 3 loses the box, the stale check should end the approach. Do not count on it the first
time.

**After:** the gripper stays closed. Open it with the step 1 command, with `-w 1` so it waits for
the driver: `ros2 topic pub --once -w 1 /rm_driver/set_gripper_position_cmd rm_ros_interfaces/msg/Gripperset "{position: 1000, block: false, timeout: 0}"`.
Without `-w 1` the first try on 2026-10-13 was lost.

### Result, 2026-10-13: PASS on the fourth attempt

Full record: [`../bench-runs/2026-10-13-labbox-t1.24-3c-first-grasp.txt`](../bench-runs/2026-10-13-labbox-t1.24-3c-first-grasp.txt).

| Attempt | What happened | Fix |
|---|---|---|
| 0 | State machine started before the driver connected (about 80 s after power-on). Home aborted, IDLE anyway, arm straight up | Restart once the driver says "RM_65_driver is running". Guard in T1.26 |
| 1 | Second approach step rejected: "start point deviates from current robot state more than 0.01" | `step_settle_s: 0.5` wait before each step. `allowed_start_tolerance` 0.02 set at run time |
| 2 | 11 steps, z 0.389 to 0.187 m, then "Cartesian path only 33%": the virtual table top was 0.195 m, the real one 0.12 m | `table_top_z_m: 0.12` |
| 3 | Full cycle, the jaws closed beside the box: not in line with the gripper | Place the box in line |
| 4 | Full cycle: approached, closed on the box, lifted it, back to HOME | PASS |

The gate held on the real arm: "Centroid ignored" every 5 s, no motion until a request.

---

## Step 4 (T1.11): the first real grasp

Same setup as step 3. Now we judge the grasp: is the box in the gripper after the return? Restart
the state machine between attempts (the one-shot `return;`). Record each attempt: grasped or not,
and where it went wrong if not. Start each attempt by voice.

### Result, 2026-10-13: PASS, a grasp started by voice

Full record: [`../bench-runs/2026-10-13-labbox-t1.11-step4-voice-grasp.txt`](../bench-runs/2026-10-13-labbox-t1.11-step4-voice-grasp.txt).

| Attempt | Started by | What happened | Fix |
|---|---|---|---|
| 1 | voice | Voice to target to request to SELECTING worked. Approach ended short: "centroid 2.78s old, object lost" | below |
| 2 | typed (pane mix-up) | Same. Depth fell to 0.182 m, then the camera gave none. The stop was 0.18 m | Config: steps 0.04 to 0.02 m, stop 0.18 to 0.21 m, final step 0.10 to 0.12 m |
| 3 | typed | "object at 0.198m", grasped, back to HOME | |
| 4 | **voice** | "object at 0.206m", grasped, back to HOME | PASS |

The grip lands about 3 cm short of the box centre, along the approach: the mask and the depth
are the box's front face, so the simple path cannot know how deep the box is. Accepted. Step 7
(AnyGrasp, T1.17) uses the point cloud. The simulated arm passes with the new config (13 PASS,
C7 XFAIL).

---

## Steps 5 to 7

- **Step 5 (T1.12):** SAM 3 left running across attempts. SAM 3 itself is proven in 3b and 3c.
  One request per attempt (T1.25). Without it, SAM 3 would start a new cycle as soon as the
  one-shot `return;` is removed.
- **Step 6 (T1.14, T2.6):** release, done, back to IDLE, a second grasp in the same launch.
  Code on branch `t1.14-multi-grasp-loop` (PR #75). Simulated arm PASS 2026-10-14, 20 of 20 ([`bench-runs/2026-10-14-labbox-t1.14-t1.17-sim-and-replay.txt`](../bench-runs/2026-10-14-labbox-t1.14-t1.17-sim-and-replay.txt)).
- **Step 7 (T1.17):** the AnyGrasp path. Desk prep on branch `t1.8-t1.10-anygrasp-gate-and-pane`
  (stacked on PR #75): the gate fix (T1.8), the detector chosen and started from its venv
  (T1.10), `state_` atomic (C4). Box checks PASS 2026-10-14: `./bench/anygrasp_replay.sh` and
  `./bench/state_machine_sim.sh candidates` ([`bench-runs/2026-10-14-labbox-t1.14-t1.17-sim-and-replay.txt`](../bench-runs/2026-10-14-labbox-t1.14-t1.17-sim-and-replay.txt)). At the robot:
  `./quickstart_terminals.sh grasp --anygrasp`, with `use_simple_execute: false`. The sim used a
  fake candidate, so first check that AnyGrasp's grasp axes line up with `grasp_frame`: hand-check
  the first candidate in RViz before letting the arm move to it. **Seen 2026-10-14 on the replay:**
  AnyGrasp's grasps drawn on the camera image look impossible (at an angle no gripper could hold),
  1 to 3 grasps per frame, scores 0.007 to 0.036. Cause not known yet, the possible ones are in the
  bench-run record. Fix before step 7 runs the arm.

---

## Things to watch

From reading the code. None of these is confirmed on the real arm.

- **No height limit during the approach.** SELECTING steps toward the centroid with no floor
  `[code]` (`selectingStep()`, `:381-434`). Only the final step pins the height to the current one (`:718`). With
  no object in view, the stand-in's centroid is the table, so the arm would step toward the table
  for up to 50 steps (2 m). MoveIt's safety walls (`addSafetyWalls()`, `:608`) are the only guard
  `[inferred]`. Never run step 3 or 4 without the box in view.
- **MoveIt's collision boxes were never checked on this robot.** Every motion is collision-checked
  against four hard-coded boxes from an earlier setup (`grasp_state_machine.cpp:302-354`)
  `[unverified]`. Look at them in RViz before 3c.
- **A lost object is not noticed** until the stale-centroid check is in (see "With 3b"). Even
  then, the check only runs between steps, and each step takes a few seconds at 10% speed.
- **A failed final step goes home and back to IDLE** since T1.14 (PR #75). It used to end the node.
- **A late TF can end a request in SELECTING** (CODE_AUDIT E6, T1.28). Seen once in sim. If the arm
  goes back to IDLE right after SELECTING with "EEF transform failed" in the log, ask again.
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
| 2026-10-07 | Claude Opus 5.5 + Dion | Step 3 split into 3a (the state machine homes on start, no camera), 3b (SAM 3 finds the box, arm off) and 3c (the approach with live SAM 3). The stand-in is dropped. Added the stale-centroid check as a code change, landing with 3b. |
| 2026-10-07 | Claude Opus 5.5 + Dion | 3a PASS: the state machine homed the real arm on start, went IDLE, no further motion. |
| 2026-10-08 | Claude Opus 5.5 + Dion | "Start here" added for the next session (3b). Old "Where we stopped" removed, its findings already folded into 3a to 3c. Collision boxes moved to "Things to watch". SAM 3 has run on the box on a bag (T0.12). |
| 2026-10-08 | Claude Opus 5.5 + Dion | T2.1 landed: 3b and 3c use the segmentation service and the grasp client instead of `sam3_ros_node.py`, the trigger notes and the depth cite follow. Box access note updated (100.98.10.50 worked). |
| 2026-10-12 | Claude Opus 5.5 + Dion | Step 3b partial result, run over SSH: SAM 3 works on the live wrist camera, no false box, 0.27 to 0.53 s per frame, GPU and CPU load, CPU overheating found. Box and tape checks still owed. Record in bench-runs/2026-10-12-labbox-t1.24-3b-live-sam3.txt. |
| 2026-10-12 | Claude Opus 5.5 + Dion | 3b: centroid rate measured through the aria client (1.85 per second). |
| 2026-10-12 | Claude Opus 5.5 + Dion | Stale-centroid check written, limit 2.0 s, with the reasoning from the 3b timing. |
| 2026-10-13 | Claude Opus 5.5 + Dion | "Start here" rewritten for the 3b robot session after PR #57. Stale-centroid check marked done, and the T1.25 note says it uses the camera stamp, not the arrival time. |
| 2026-10-13 | Claude Opus 5.5 + Dion | Known gap: T2.11 result added (default 1280x720 sends frames now, SAM 3 about 40 % slower than 640x480). Grasp layout pinned to 640x480x15. |
| 2026-10-13 | Claude Opus 5.5 + Dion | 3b PASS with the box and tape. Found a box too close reads 1.26 m, fix on `t1.24-min-valid-depth`. "Start here" points at checking the fix, then 3c. |
| 2026-10-13 | Claude Opus 5.5 + Dion | T1.25 built: the trigger section says what changed, the gate design is marked as built with the timeout, the busy refusal, the C1 shutdown fix and why a request cannot race the worker. 3c and step 5 send a request. |
| 2026-10-13 | Claude Opus 5.5 + Dion | Start here: PRs #57 to #60 merged, T1.25 built but unmerged. Step 3c: how to run with the gate from `~/rcp-Gappler-t1.25` (binary checked to contain it), and without it. |
| 2026-10-13 | Claude Opus 5.5 + Dion | 3c PASS, the first grasp on the real arm. Start here rewritten for step 4. 3c result table, release with `-w 1`. |
| 2026-10-13 | Claude Opus 5.5 + Dion | After #65 and #67 merged: Start here and step 3c run from `~/rcp-Gappler` and the quickstart grasp layout. The separate `~/rcp-Gappler-t1.25` build is deleted. Start the state machine after the driver is up. |
| 2026-10-13 | Claude Opus 5.5 + Dion | After T2.6 (#64) and T2.7 (#63): Start here says voice sends the grasp request, step 4 starts each attempt with the `pick_up_box_command.wav` replay, the signals table names the publishers. Box restart incident and the runner restart noted. |
| 2026-10-13 | Claude Opus 5.5 + Dion | Step 4 (T1.11) PASS, attempt 4 started by voice. Result table, the depth blind zone and the config change (uncommitted, branch t1.11-stop-before-depth-blind), the 3 cm front-face bias. Start here rewritten for step 5: release with `-t 3 -r 2`, the `/pipeline_state` type, pane names by position. |
| 2026-10-13 | Claude Opus 5.5 + Dion | Start here: the step 4 config is merged (#71), the box is reached at `100.87.133.60` again. |
| 2026-10-14 | Claude Opus 5.5 + Dion | Steps 6 and 7: box sim and replay checks PASS. Things to watch: failed final step now goes home (T1.14), new E6 late TF in SELECTING. |

| 2026-10-14 | Claude Opus 5.5 + Dion | Start here rewritten for the robot: step 5 on `dev`, step 6 on the PR #75 branch (release by voice, second grasp in one launch). Step 7: AnyGrasp's drawn grasps look impossible. |
