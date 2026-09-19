# READING GUIDE — a guided walk through the codebase

A round-by-round walkthrough for someone who has never seen this repo and has no ROS 2 experience.
[`ORIENTATION.md`](ORIENTATION.md) §4 lists *which* files to read; this file explains *what to
notice in them* and why it matters.

Each round ends with **check-yourself questions**. Answers are recorded here after they are worked
through, including where a plausible answer turned out to be incomplete — those are usually the
most instructive parts, so they are kept rather than tidied away.

> ## 📍 RESUME HERE
>
> **Round 1: complete** (2026-09-09) — questions answered and marked in §1.4.
> **Round 2: complete** (2026-09-13) — all three check questions answered in §2.8.
> **Round 3: written 2026-09-13, walkthrough in §3.1–3.6. All three check questions still open (§3.7).**
> Read ORIENTATION §8.1–§8.3 *before* starting it. Nothing in Round 3 should be run.
>
> Rounds 3 and 4 are outlined in §3 and §4; the per-file reading order is in ORIENTATION §4.

Status tags as elsewhere: `[code]` verified by reading source · `[reported]` from the 2026-08-25
hardware session · `[inferred]` reasoning, not fact.

---

## 0. Before Round 1 — the one thing that confuses everyone

**There are four entry-point files and three of them are called `main.py`.** Sort this out first
and half the confusion disappears:

| File | What it launches | Who runs it |
|---|---|---|
| `main.py` (repo root) | orchestrator + the Aria app | top level |
| `src/main.py` | the **glasses** side (subsystem A) | root, or by hand |
| `ros2_robot_ws/src/main.py` | the **robot** side — RealSense, MoveIt, SAM3, AnyGrasp, state machine | the orchestrator |
| `ros2_robot_ws/src/orchestrator.py` | waits for signals, launches the robot side at the right moment | root |

When someone says "run main.py", always ask which one.

---

## 1. Round 1 — the shape of it (~45 min)

**Goal:** be able to answer *"what starts what, and how do they find each other?"* Needs no
hardware and no ROS install. Keep ARCHITECTURE L0 open beside you.

### 1.1 `shared/config.yaml` — 20 lines, and it *is* the interface

Two naming conventions to absorb: **`/aria/*` came from the glasses**, **`/realman/*` came from
the robot's camera**. Once you know that, any topic name tells you which camera produced it.

Then the QoS block:

```yaml
qos:
  video:
    reliability: "BEST_EFFORT"
```

**BEST_EFFORT means "drop frames rather than wait."** RELIABLE, the opposite, retries until
delivery. For video you want dropping — a stale frame is worse than no frame.

Remember this, because QoS mismatch is one of the most common ROS bugs and it appears again in
this repo: `qos_relay.py` exists *purely* because the Livox driver publishes RELIABLE while
`pointcloud_to_laserscan` demands BEST_EFFORT. A whole node to bridge one setting.

### 1.2 `src/config/ros2.py` — one clever line, one real cost

```python
ROS2Topics = Enum("ROS2Topics", {k.upper(): v for k, v in config["ros2"]["topics"].items()})
```

Builds a Python enum **at import time** from the YAML, so `ROS2Topics.RGB_CAMERA_RAW.value` is
`"/aria/rgb_camera/raw"`. Rename a topic in the YAML and every publisher and subscriber follows.

The cost: it is dynamic, so **your editor cannot autocomplete it and cannot warn you about a
typo** — you get an `AttributeError` at import. That is why the YAML is the thing to read first:
it is the only place the full list exists.

### 1.3 `src/main.py` — the builder, and what is switched off

Skim to `ProcessPipelineBuilder` (line 30) — each `add_*` method starts one piece. Then line 106:

```python
self.add_streaming(device_ip, profile_name)
# self.add_visualization()          ← OFF
# self.add_object_recognition()     ← OFF
self.add_audio_streaming()
sensors_calib_json_str = self.config_queue.get()
# self.add_image_streaming(...)     ← OFF
# self.add_pose_streaming(...)      ← OFF
```

**This is seam #1** (ORIENTATION §6.1). Four of six stages disabled; the glasses emit only the
voice prompt.

Two subtleties worth catching now:

- `add_streaming` creates a **process**; `add_audio_streaming` creates a **thread**. Same-looking
  names, different mechanisms (`process_manager.py:14` vs `:25`). Full map in ARCHITECTURE L2.
- Line 110 fetches `sensors_calib_json_str` from a queue, but the only two stages that consume it
  are commented out. **It is fetched and thrown away** — a small clue these lines were disabled
  hastily rather than designed out.

### 1.4 `ros2_robot_ws/src/main.py` — a launcher with load-bearing sleeps

Deliberately dumb: `subprocess.Popen` in sequence. Notice the `delay` arguments — `anygrasp` 2 s,
`grasp_viz` 2 s, `rviz` 3 s, **`grasp_state_machine` 5 s**.

Those are not cosmetic. The state machine needs `move_group` fully initialised or it fails.
**This is a startup race handled by guessing.** On a slower machine, or a cold model load, the
guess is wrong and you get confusing failures.

Also `[reported]` (ORIENTATION §8.5): when a child dies, this file **prints a warning and keeps
running**. A dead AnyGrasp node presents as "nothing ever happens, no error". Read the terminal.

### 1.5 `orchestrator.py` — the real top-level logic, mostly disabled

146 lines. The docstring states the intent:

```
1. Wait for /manipulation/start   2. Launch main.py
3. Wait for goal_reached          4. Launch rm_bringup
5. Wait for "release"             6. Open gripper
```

Lines 57-62 — steps 3 and 4 are commented out. **Seam #3** (ORIENTATION §6.3).

Worth sitting with: the highest-level behaviour of a robot that navigates, sees and grasps is
about 40 lines of topic callbacks. That is normal in ROS — behaviour emerges from *which nodes are
running*, not from one big controller.

### 1.6 Round 1 check questions — answered 2026-09-09

**Q1. You publish a string to `/aria/audio/prompt` by hand. Which processes react, given today's
code?**

Partially answered: "currently nothing, because the text prompt is hardcoded."

The read of `sam3_ros_node.rgb_depth_callback` was right — it runs inference on every synced frame
against a module-level constant and never subscribes to a prompt topic. But **"nothing" is not
correct.** `[code]` Three nodes subscribe to `/aria/audio/prompt`:

| Subscriber | File | Running today? |
|---|---|---|
| `object_approach_node` | `object_approach_node.py:81` | ✅ yes (Navigation_Module) |
| `goto_glasses` | `goto_glasses.py:59-61` | ✅ yes (Navigation_Module) |
| `object_recognition_pipeline` | `object_recognition_pipeline.py:148` | ❌ no — its process is commented out (seam #1) |

**So the voice command already reaches navigation — it just never reaches segmentation.** The
robot can hear you well enough to drive somewhere, but not well enough to know what to pick up.
Easy to miss because the two subsystems live in directories you would never read side by side.

**Q2. Why is `add_audio_streaming` a thread but `add_object_recognition` a process?**

Answered: "everything that is not from the Aria device itself is a separate process; within the
device it is a thread."

Good rule, and it predicts most of the table — but there is one clean counterexample:
`add_streaming` (`start_aria_stream`) *is* the Aria device connection and it is a **process**. The
rule that actually holds is about **what the stage owns**:

| Stage | Mechanism | Why |
|---|---|---|
| `stream_audio`, `stream_visual_feed`, `stream_pose` | **thread** | Thin SDK-subscriber shims that immediately hand off to their *own* child processes (`audio_worker`, `rgb_worker`, `et_worker`, `slam_worker`). Making them processes too would add a layer for nothing. |
| `start_aria_stream`, `visualize_feed`, `generate_mask` | **process** | Each owns a heavy resource — the SDK session, an OpenCV window, or a 3.4 GB model with its own CUDA context. |

The CUDA part is why it matters: `set_start_method("spawn")` (`main.py:435`) means every child
re-imports and re-initialises CUDA independently. Two model-loading stages in one process would
fight over the same context.

**Q3. The orchestrator launches `rm_mtc background.launch.py` on startup (line 78) — before any
signal. Given ORIENTATION §8.1, what does that mean for running it remotely?**

Answered: "never launch `ros2_robot_ws/src/main.py`, it initialises the state machine and swings
the robot to default position."

Right conclusion, and the real answer is worse. `background.launch.py` starts only the driver,
`move_group`, `rm_control` and `robot_state_publisher` — **no state machine, the arm does not
move.** The danger is *deferred*: the orchestrator then waits on `/manipulation/start`, and when
that `Bool` arrives it launches `ros2_robot_ws/src/main.py`, which starts the state machine, which
homes the arm.

**So the arm can begin moving because a message arrived, not because a human typed a command** — a
stray `ros2 topic pub`, a leftover nav node, a replayed bag. There is no point in the sequence
where a person confirms. Treat a running orchestrator as a loaded arm. Now recorded as the §8.1
addendum in ORIENTATION.

---

## 2. Round 2 — the perception path (~1.5 h)

**Goal:** understand how a spoken sentence becomes a segmented object, and see exactly where
seam #2 sits.

### 2.1 `streaming_pipeline.py` — 63 lines, read it whole

The Aria session in one function. Note the ordering:

```python
aria_controller.start_streaming(...)
self._streaming_started.set()          # ← unblocks every other stage
sensors_calib_json_str = aria_controller.get_sensors_calibration_json_str()
self._config_queue.put(sensors_calib_json_str)
self._quit_event.wait()                # ← then parks forever
```

Two ideas to take away. **`aria_streaming_started` is a one-shot gate** — other stages `.wait()`
on it so nothing touches the device before it is live. And **calibration travels as a JSON string
through a queue**, not as an object, because `spawn` means children cannot inherit Python objects.
Each consumer re-parses it independently.

### 2.2 `audio_streaming_pipeline.py` — the one path that works today

The observer is a **ring buffer, not a queue** (`audio_streaming_client_observer.py:27`): a
lock-guarded 7-channel numpy array that wraps around (`:38-43`). The pipeline polls it once per
second and pushes a snapshot into a depth-1 queue — the loop is paced to
`ITERATION_INTERVAL_SECONDS = 1` at `audio_streaming_pipeline.py:173-187`.

Why different from every other sensor? Because audio is **continuous** — you cannot drop a chunk
mid-word the way you can drop a video frame. The ring buffer keeps the last 10 seconds
(`MAX_BUFFER_SECONDS = 10`, `src/config/audio_streaming_pipeline_config.py:6`) so Whisper always
receives a coherent window.

Then `audio_worker`: mix 7 channels → mono, resample 48 kHz → 16 kHz, normalise, Whisper, LLM.
Note the dedup at `audio_streaming_pipeline.py:115-124` — if the transcription is unchanged it
skips the LLM entirely. It does **not** skip the publish (`:128` runs either way), which combined
with the 10 s window over a 1 s loop means one spoken word is re-published ~10 times. That is
CODE_AUDIT J1, and it matters again in §2.3.

### 2.3 `prompt_extractor.py` — read the system prompt as a spec

This file *is* the voice UX. The prompt says: return only the object, return the **last** one if
several, return `"end"` for stop/kill/cancel.

Then look at the hardcoded fallback below it (`prompt_extractor.py:101-113`) — a literal
`termination_keywords` set checked independently of the model. **Someone did not trust a 0.5 B model
to reliably recognise "stop".** That is a sound instinct and worth copying: a kill word must never
depend on a model's judgement.

The instinct is right and the implementation is not: the membership test at `:110-111` is
`kw in phrase.lower().split()`, which keeps punctuation, so `"Stop."` never matches — and it fires
on any sentence merely *containing* one of the words. New CODE_AUDIT **B7**.

### 2.4 `image_streaming_pipeline.py` — RGB, gaze, ArUco

`rgb_worker` (`:75`) publishes raw + undistorted RGB and rate-limits ArUco to every 0.5 s
(`ARUCO_INTERVAL_S`, `:123`; detect-and-publish block `:121-145`). `et_worker` (`:148`) runs gaze
inference and publishes a `Point` on `/aria/eye_tracking/gaze_estimate` (publisher `:153-157`,
publish `:187-189`). Both are child processes of `stream_visual_feed` (`:199-210`), i.e. of
`add_image_streaming` — which is one of the four stages commented out at `src/main.py:107-112`.

Connect this to ORIENTATION §8.8 as you read: that `Point` comes from `project_gaze()`, which
projects a **direction** onto a plane at a fixed assumed **1.5 m**
(`DEFAULT_DEPTH_M`, `src/config/eye_tracking.py:5`). The
eye tracker gives yaw/pitch, never distance. So the pixel is only correct for objects near 1.5 m —
and that pixel is what decides *which object you meant*.

### 2.5 `object_recognition_pipeline.py` — 718 lines, the heart

Do not read top to bottom. This order:

1. **`_setup_ros_node` (line 115)** — every input and output in one method. Read it twice.
2. **`run` (line 266)** — the main loop. Notice it is driven by *frame-ID comparison*, not callbacks.
3. **`_find_closest_mask` (line 501)** — the gaze→object logic. If gaze falls *inside* a mask take
   it; otherwise nearest by pixel distance.
4. **`_find_matching_ros_mask` (line 532)** — cross-camera confirmation. Feature-match
   Aria↔RealSense, keep only matches landing inside the Aria mask, then pick the RealSense mask
   containing the most of them. The cleverest idea in the codebase.
5. **Line 389** — the commented-out call. **Seam #2, physically.**

The `CameraFeed` / `RealSenseFrame` pattern at the top is worth internalising: a lock-guarded
latest-value holder returning a defensive `.copy()` plus a monotonic ID; callers compare IDs to
detect new data. Same latest-wins philosophy as `_put_latest`, but in-process.

### 2.6 `feature_matching.py`

SuperPoint extracts keypoints, LightGlue matches them. `match_frames` returns `keypoints0`,
`keypoints1`, `matches`.

Trap from ORIENTATION §8.9: the standalone `feature_matching()` entry point is **dead** —
`add_feature_matching()` is never called. The `FeatureMatcher` *class* is very much alive,
instantiated directly inside `ObjectRecognitionPipeline` (`:97`). Do not waste time on the process
wrapper.

### 2.7 Before you read: the collision you will trip over

`[code]` `sam3_ros_node.py` and `object_recognition_pipeline.py` both declare the **same three
topics**. This is ORIENTATION §6.5 and NEXT_STEPS §2.2. Knowing it in advance stops the natural
"just uncomment line 389" instinct from producing a confusing failure.

### 2.8 Round 2 check questions — answered 2026-09-13

**Q1.** Both `sam3_ros_node.py` and `object_recognition_pipeline.py` produce a mask for the
RealSense camera. If you closed seam #2 by uncommenting line 389 and left both running, what
breaks?

> *Answered in advance during the 2026-09-10 session, because it came up while investigating the
> duplication:* two publishers race on `/object_centroid_2d`, `/camera/sam/mask` and
> `/object_centroid`, and the state machine consumes whichever message lands last. Plus two 3.4 GB
> model loads with separate CUDA contexts. See ORIENTATION §6.5.

**Q2.** `_find_closest_mask` needs a gaze point. Given seam #1, what does it actually receive
today, and what does it do then?

Answered: gaze falling inside a mask wins; otherwise the nearest mask by pixel distance; the result
is stored as the Aria inference state and handed to the ROS frame processing for feature matching.

The mechanism is exactly right (`object_recognition_pipeline.py:501-530`, then `:334-344`). Three
things that answer missed — and the third is the question that was actually asked.

**(a) The hand-off is one iteration stale.** `[code]` The run loop snapshots shared state under the
lock at `:274-278`, processes the Aria frame at `:289`, *then* the ROS frame at `:295`. So
`_process_ros_frame` receives the `aria_inference_state` as it was **before** this iteration's Aria
inference. The mask the cross-camera match runs against is always one loop behind.

**(b) Nothing is actually locked.** `[code]` The guard at `:323-324` is commented out, so the Aria
state is overwritten on every Aria frame despite the name `_aria_locked_image`. ORIENTATION §8.9
already records this (`ORIENTATION.md:796`). The "locked" image is whatever arrived last.

**(c) `_find_closest_mask` is never called today.** `[code]` Follow the chain:

| Step | Where | Result |
|---|---|---|
| Only gaze publisher is `et_worker` | `image_streaming_pipeline.py:156` | part of `add_image_streaming` … |
| … which is commented out | `src/main.py:111` | nothing publishes gaze |
| So `gaze_point is None` → return `0` | `:506-507` | would take **the first mask SAM 3 returned** |

Take the middle row seriously before the last one. Index 0 is not "the best mask": our code never
sorts by score — `sam3_model.py:65-82` returns the processor's state untouched — so whether index 0
is the best detection is upstream behaviour we have not checked. `[unverified]`

**But it never even gets that far.** The same commented-out stage is what publishes the Aria image
on `RGB_CAMERA_UNDISTORTED` (`image_streaming_pipeline.py:88`), which is the topic
`_on_aria_image` subscribes to (`:131-133`). So `_on_aria_image` never fires, `CameraFeed.get()`
returns `(None, -1)` (`:52-57`), `last_aria_id` starts at `-1` (`:269`), the check
`aria_id != last_aria_id` (`:287`) is never true, and **`_process_aria_frame` never runs at all.**

Worth stating plainly, because it is the trap this round exists to prevent: **uncomment line 389
alone and you get no Aria mask, no gaze, `aria_inference_state is None` at `:377`, therefore no
feature matching — and `_process_ros_frame` publishing *every* RealSense mask with no selection at
all.** Wrong object, silently, nothing logged. **Seam #1 and seam #2 have to be closed together.**

**Q3.** Why does the pipeline run SAM3 on the Aria image *and* the RealSense image, instead of
segmenting once and reusing the result?

Answered: the robot's view and the user's view differ, so the same object has to be located in both
and the two aligned. Right — and worth sharpening, because the reason is stronger than "the views
differ".

The two pieces of information the system needs live in spaces with **no transform between them**.
Gaze exists only in Aria pixels. Depth and the whole arm TF chain exist only in RealSense pixels.
And both cameras move independently — one head-mounted, one eye-in-hand on `Link6`
(`ORIENTATION.md:1008`) — so there is no fixed extrinsic anyone could precompute. Segmenting once
would leave the mask in a frame the arm cannot act in.

Two alternatives came up: derive a transform from the matched keypoints, or use Aria depth plus the
published 3D centroid. **The code deliberately does neither**, and that is the part worth keeping.
`_find_matching_ros_mask` (`:532-613`) keeps the matches that fall inside the Aria mask
(`:571-576`), then counts how many land inside each RealSense mask and takes the highest
(`:589-597`). **A vote, not a fit.** It needs no calibration, no scale, no Aria-side depth, and it
tolerates bad matches — because it only ever answers *"which of these masks"*, never *"where in
3D"*. The 3D question is answered later, once, on the RealSense side where depth actually exists.

Three footnotes, since both alternatives are more real than they look:

- **Aria depth is reachable in principle** — the stereo SLAM cameras are handled in
  `pose_streaming_pipeline.py` (`:88` names `camera-slam-left`/`-right`; `slam_worker`, `:112-232`,
  publishes both). Nothing computes depth from them today.
- **The geometric route exists in this repo — for navigation only.** `rgb_worker` publishes
  `/aria/aruco_pose` (`image_streaming_pipeline.py:90-94`, `:121-145`), and `pose_fusion_node` uses
  that detection to anchor the glasses' VIO into the map frame (`pose_fusion_node.py:10`, `:25-29`,
  `:143`). So the project does solve a glasses↔robot geometry problem — with a fiducial, at a
  coarser scale, for driving rather than grasping.
- **The 3D centroid such a scheme would need is exactly the call commented out at `:389`.**

---

## 3. Round 3 — the robot path (~2 h) ← **START HERE**

Read ORIENTATION §8.1, §8.2 and §8.3 **before** this round, not after. Nothing in this round should
be run: launching the state machine moves the arm within about two seconds, before it waits for any
input, and `homeWithRetry` retries forever until it succeeds.

**The one thing to carry in.** `USE_SIMPLE_EXECUTE = true` (`grasp_state_machine.cpp:41`) means the
AnyGrasp candidate-evaluation path is compiled but **not taken**. The arm does a blind 10 cm push
and closes. `/grasp_candidates` is subscribed and unused in this mode.

### 3.1 `estop.py` — 80 lines, read it *first*

Three keys. `E` publishes `Stop(state=true)` to `/rm_driver/emergency_stop_cmd`, `R` the same with
`state=false`, `S` an `Empty` to `/rm_driver/move_stop_cmd` (current motion only). Raw-terminal key
reading at `:48-55`, so the stop only works while that window has focus.

Two weaknesses before you ever rely on it, both CODE_AUDIT B2: it publishes and then immediately
destroys the node (`:72-76`), and DDS may not have delivered by then — `orchestrator.py:121` sleeps
1.5 s for exactly this reason and the e-stop does not; and the publisher is `depth=1` VOLATILE
(`:25`), so a stop sent before `rm_driver` subscribes is dropped silently. Compare B1: the root
`main.py` advertises a `q` stop key that does not exist.

### 3.2 `sam3_ros_node.py` — 197 lines

SAM 3 on every synced RealSense RGB+depth pair → best mask + centroid. Three things:

- `TEXT_PROMPT = "box"` (`:40`) is a module constant. This node never subscribes to
  `/aria/audio/prompt`. **Speaking to the glasses cannot change what it looks for.**
- The checkpoint path (`:37-39`) is an absolute path that exists on no current machine (§8.4).
- `/object_centroid_2d` carries **pixels in `x`/`y` and metres in `z`** (`:161-163`) while being
  stamped `camera_color_optical_frame`, which makes it look like a 3D point. It is not (§8.3).

Then compare against `object_recognition_pipeline.py`: same three topics, but no gaze, no Aria, no
prompt subscription. That overlap is §6.5.

### 3.3 `anygrasp_detection_node.py` — 246 lines

RGB + depth + mask → `/grasp_candidates`.

⚠️ **The gate is inverted, and an earlier version of this guide had it backwards.** `:182` reads
`if self.pipeline_state != "IDLE": return`, so detection runs **only while IDLE**, not during
EXECUTING as the docstring two lines above claims. Meanwhile `graspCallback`
(`grasp_state_machine.cpp:183`) discards anything that is not EXECUTING. The producer's gate and the
consumer's gate are mutually exclusive, so no candidate can ever be used. CODE_AUDIT A1.

### 3.4 `mtc_planner.hpp` — 64 lines

The entire arm-motion API in five methods: `moveToPose`, `moveToHome`, `moveToReturn`,
`getCurrentPose`, `moveCartesianStep`. Plus `HOME_JOINTS` (`:46-53`) and `RETURN_JOINTS` (`:56-63`).
Home is joint3 45°, joint5 and joint6 90°, the rest zero — the pose the arm swings to unprompted at
launch, never validated on hardware (§8.1).

### 3.5 `grasp_state_machine.cpp` — 802 lines, the hardest file here

Order: constructor → `workerLoop` → `selectingStep` → the EXECUTING branch. Skip the quaternion
helpers on the first pass.

| Part | Line | What to notice |
|---|---|---|
| Constructor | 130-162 | ROS wiring only, no motion |
| `workerLoop` start | 590-596 | sleep 2 s, `addSafetyWalls()`, `homeWithRetry()`, *then* IDLE. Motion before any input |
| `homeWithRetry` | 342-351 | retries every second, forever |
| IDLE wait | 613-620 | waits on `has_centroid_` alone; the staleness check is commented out at `:634-639` |
| `selectingStep` | 367-421 | pixel error → lateral offset → 4 cm step. **Both TF calls guarded** |
| Transition | 643-648 | when depth < `EXECUTE_DEPTH_THRESH_M` (0.18 m) |
| EXECUTING (simple) | 671-722 | see below |
| `executingSimple` | 580-585 | **is just `closeGripper()`** |
| After success | 713-721 | `return`s out of `workerLoop` *before* `publishState(IDLE)` at `:740` |

The EXECUTING branch is where the self-annotated bugs live: two **unguarded** TF calls at `:680` and
`:700` (identical to the guarded ones in `selectingStep`), and the goal's z overwritten with the
current z at `:702-704`, labelled "HARDCODING BRITTLE FIX", to stop the planner driving into the
table. The failure branch at `:708-712` also `return`s out of the whole loop, silently halting the
node with one `WARN`. The comment at `:706` is stale — the code below it does check the return value.

C7: because the success path returns before publishing IDLE, `state_` stays EXECUTING forever and
the node handles **exactly one object per launch**, despite the `while (true)`. Confirmed on the
simulated arm, 2026-09-11.

### 3.6 What to carry out of Round 3

The grasp path that exists today is **centroid-driven, not grasp-driven**. SAM 3 looks for the fixed
word "box", the pixel centroid and its depth drive a visual servo, and the gripper closes 10 cm
later. Gaze, the Aria camera, feature matching and AnyGrasp are all bypassed in the path that
actually runs.

### 3.7 Round 3 check questions — ⬜ NOT YET ANSWERED

**Q1.** With `USE_SIMPLE_EXECUTE = true`, name every input that has **no** influence on where the
gripper ends up closing. ⬜ **open**

**Q2.** You hit `E` on the e-stop during a SELECTING approach, then hit `R`. Trace what the state
machine does. ⬜ **open**

*(Hint: `homeWithRetry` at `:342-351`, and the two delivery weaknesses in CODE_AUDIT B2.)*

**Q3.** Given C7, what is the smallest change that lets the node handle a second object, and why
might that `return` at `:721` have been put there deliberately? ⬜ **open**

## 4. Round 4 — navigation (~1 h)

1. **`object_approach_node.py`** — its docstring is the best single description of the
   nav↔manipulation contract anywhere in the repo.
2. **`goto_glasses.py`** — the "go to the user / come back" behaviour.
3. **`slam_mapping.launch.py`** — the full nav node graph. Compare against
   `slam_localization.launch.py`; the differences matter (ARCHITECTURE L1b).
4. **`nav2_params.yaml`** — where HiCo-Nav most likely plugs in.
5. **`pose_fusion_node.py`** + its README — read the code first, *then* the README, and note every
   place they disagree. ORIENTATION §6.4 has the full list.

---

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-10 | Claude (Opus 5) + Dion | Created, capturing the Round 1 and Round 2 walkthroughs that previously existed only in a chat session. Round 1 questions answered and marked; Round 2 written but unread; Rounds 3-4 outlined. |
| 2026-09-13 | Claude (Opus 5) + Dion | Re-verified every line number in §2 against source after comments shifted them (`_setup_ros_node` 112→115, `run` 267→266, `_find_closest_mask` 499→501, `_find_matching_ros_mask` 527→532, seam #2 call 384→389; §2.7 and §2.8 Q1 follow). Added the missing cites in §2.2, §2.3 and §2.4. Round 2 Q2 and Q3 answered; Round 2 marked complete and the START HERE marker moved to Round 3. **Baseline:** §2's numbers are against the *working tree*, which in `object_recognition_pipeline.py` is 8 lines ahead of the last commit (the added comments); every other file cited is clean. |
| 2026-09-13 | Claude (Opus 5) + Dion | Round 3 written out in full (§3.1–3.6) from the walkthrough, replacing the five-line outline: per-file notes, the state machine's key lines as a table, and §3.6's "centroid-driven, not grasp-driven". **Corrected an error in the old outline**, which said `anygrasp_detection_node.py` runs during EXECUTING — it gates on `!= "IDLE"` (`:182`), i.e. only while IDLE, which is CODE_AUDIT A1. Line counts and anchors re-verified. §3.7 added with three open check questions. |
