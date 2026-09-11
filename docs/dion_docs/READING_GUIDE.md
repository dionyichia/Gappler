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
> **Round 2: written but NOT YET READ.** Start at §2 below.
> Two of Round 2's three check questions are still open (§2.8).
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

## 2. Round 2 — the perception path (~1.5 h) ← **START HERE**

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
lock-guarded 7-channel numpy array that wraps around. The pipeline polls it once per second and
pushes a snapshot into a depth-1 queue.

Why different from every other sensor? Because audio is **continuous** — you cannot drop a chunk
mid-word the way you can drop a video frame. The ring buffer keeps the last 10 seconds so Whisper
always receives a coherent window.

Then `audio_worker`: mix 7 channels → mono, resample 48 kHz → 16 kHz, normalise, Whisper, LLM.
Note the dedup at lines 115-124 — if the transcription is unchanged it skips the LLM entirely.

### 2.3 `prompt_extractor.py` — read the system prompt as a spec

This file *is* the voice UX. The prompt says: return only the object, return the **last** one if
several, return `"end"` for stop/kill/cancel.

Then look at the hardcoded fallback below it — a literal `termination_keywords` set checked
independently of the model. **Someone did not trust a 0.5 B model to reliably recognise "stop".**
That is a sound instinct and worth copying: a kill word must never depend on a model's judgement.

### 2.4 `image_streaming_pipeline.py` — RGB, gaze, ArUco

`rgb_worker` publishes raw + undistorted RGB and rate-limits ArUco to every 0.5 s
(`ARUCO_INTERVAL_S`). `et_worker` runs gaze inference and publishes a `Point`.

Connect this to ORIENTATION §8.8 as you read: that `Point` comes from `project_gaze()`, which
projects a **direction** onto a plane at a fixed assumed **1.5 m** (`config/eye_tracking.py`). The
eye tracker gives yaw/pitch, never distance. So the pixel is only correct for objects near 1.5 m —
and that pixel is what decides *which object you meant*.

### 2.5 `object_recognition_pipeline.py` — 718 lines, the heart

Do not read top to bottom. This order:

1. **`_setup_ros_node` (line 112)** — every input and output in one method. Read it twice.
2. **`run` (line 267)** — the main loop. Notice it is driven by *frame-ID comparison*, not callbacks.
3. **`_find_closest_mask` (line 499)** — the gaze→object logic. If gaze falls *inside* a mask take
   it; otherwise nearest by pixel distance.
4. **`_find_matching_ros_mask` (line 527)** — cross-camera confirmation. Feature-match
   Aria↔RealSense, keep only matches landing inside the Aria mask, then pick the RealSense mask
   containing the most of them. The cleverest idea in the codebase.
5. **Line 384** — the commented-out call. **Seam #2, physically.**

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
"just uncomment line 384" instinct from producing a confusing failure.

### 2.8 Round 2 check questions — ⬜ NOT YET ANSWERED

**Q1.** Both `sam3_ros_node.py` and `object_recognition_pipeline.py` produce a mask for the
RealSense camera. If you closed seam #2 by uncommenting line 384 and left both running, what
breaks?

> *Answered in advance during the 2026-09-10 session, because it came up while investigating the
> duplication:* two publishers race on `/object_centroid_2d`, `/camera/sam/mask` and
> `/object_centroid`, and the state machine consumes whichever message lands last. Plus two 3.4 GB
> model loads with separate CUDA contexts. See ORIENTATION §6.5.

**Q2.** `_find_closest_mask` needs a gaze point. Given seam #1, what does it actually receive
today, and what does it do then? ⬜ **open**

*(Hint: follow `_on_gaze` back to its publisher, then check whether that publisher's stage is one
of the four commented out at `src/main.py:107-112`. Then read the first line of
`_find_closest_mask`.)*

**Q3.** Why does the pipeline run SAM3 on the Aria image *and* the RealSense image, instead of
segmenting once and reusing the result? ⬜ **open — the one worth sitting with**

*(The answer explains why `feature_matching.py` has to exist at all.)*

---

## 3. Round 3 — the robot path (~2 h)

Per-file order in ORIENTATION §4. Sequence and rationale:

1. **`estop.py`** — 90 lines, read it *first* in this round. You will need it.
2. **`sam3_ros_node.py`** — short. Compare against `object_recognition_pipeline.py` and notice they
   do overlapping jobs differently. That gap is ORIENTATION §6.2 and §6.5.
3. **`anygrasp_detection_node.py`** — RGB + depth + mask → grasp poses. Note the `/pipeline_state`
   gate: it only runs during EXECUTING.
4. **`mtc_planner.hpp`** — 60 lines = the *entire* arm-motion API, 5 methods. Plus the HOME and
   RETURN joint angles.
5. **`grasp_state_machine.cpp`** — ~760 lines, the hardest file here. Constructor (128-161, all
   I/O) → `workerLoop` (590+) → `selectingStep` → `executingStep`. Skip the math helpers first pass.

Read ORIENTATION §8.1, §8.2 and §8.3 **before** this round, not after. One item to carry in:
`USE_SIMPLE_EXECUTE = true` (`:40`) means the AnyGrasp candidate-evaluation path is compiled but
**not taken** — the arm does a blind 10 cm push and closes. `/grasp_candidates` is subscribed but
unused in this mode.

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
