# Dion: progress report, repo clone to 2026-10-23

This is a full information dump of Dion's work on Gappler, from cloning the repo in September 2026
to 2026-10-23. It will be merged with Sherman's (navigation) and Zongzhe's (memory graph) reports,
then cut down. So it errs on the side of too much detail. Cut freely.

Dion's part of the system: the glasses (voice and gaze), finding the gazed object again in the
robot's wrist camera (cross camera), and the arm grasp. Plus the project infrastructure (docs, test
bench, CI, refactor) that the whole team builds on.

**How to read the evidence.** Task IDs (T1.17, T8.7) are rows in `docs/task-tree.html`. Run records
are in `docs/bench-runs/`. Pictures and videos are in `docs/dion_docs/local/report_media/`
(gitignored, on Dion's Mac only). Tags: `[measured]` from a run, `[code]` read from source,
`[inferred]` reasoning not yet tested, `[unverified]` to confirm.

---

## 0. Summary

| Stage | Where it stands on 2026-10-23 | Headline number |
|---|---|---|
| Groundwork | Docs, 7-level test bench, CI on a GPU runner, repo refactor, safety tooling | 204 commits, 61 merged PRs by Dion |
| Arm bring-up | Powered, homed, gripper tested, e-stop through software | Joint feedback 199.5 to 199.9 Hz (T1.6) |
| Voice | Sentence detection, speech to text, LLM picks the object word | 31 messages per phrase down to exactly 1 (T2.10) |
| SAM 3 | One shared segmentation service for all clients | 117 masks a minute vs the old node's 119, one copy on the GPU (T2.1) |
| Gaze pick on the glasses | SAM 3 masks the glasses image, gaze votes for one mask | Right box in 60 of 61 frames at 1.4 to 2.4 m (T2.9, T2.20) |
| Cross camera | CLIP embedding per mask, cosine match | Point matching 0 of 15. CLIP 25 of 25 offline, 27 of 27 on replay (T8.4, T8.7) |
| Cross camera, look-alikes | Same matcher, two similar boxes | 148 of 180 frames (T8.5). 6 of 12 on a harder replay (T8.8 row) |
| Glasses to robot calibration | Plan settled, Phase 0 | Not built (T8.8) |
| Grasp, simple path | Step in, close | First real grasp 2026-10-13. 5 of 8 over a session (T1.24, T1.12) |
| Grasp, AnyGrasp path | AnyGrasp picks the pose | 2 of 3 at the ideal spot (T1.17). Fails off the ideal spot (T1.35, T1.44) |
| Grasp, next | New AnyGrasp SDK, multi-view fusion | SDK waiting on a licence. Fusion built, retest owed (T1.45, T1.47) |

---

## 1. Context and framing

### 1.1 The two papers

Gappler joins two research systems into one pipeline.

| | FAM-HRI | HiCo-Nav |
|---|---|---|
| What it is | Human-robot interaction with Meta Aria glasses: the user's gaze and speech tell a robot arm which object to pick. Full title to confirm: "FAM-HRI: Foundation-Model Assisted Multi-Modal Human-Robot Interaction Combining Gaze and Speech" `[unverified]` | Zero-shot language navigation. A robot explores an unseen room and builds a cognitive memory graph of every object it sees (3D points plus a CLIP feature per object). ICRA 2026, extended journal version. Code: github.com/xukuanHIT/HiCo-Nav |
| Where it comes in | The original authors of this repo were recreating FAM-HRI. The glasses pipeline (voice, gaze, SAM 3, the cross-camera matcher) and the grasp state machine are that recreation | Sherman (navigation) and Zongzhe (memory graph) are integrating it |
| Gap we fill | FAM-HRI assumes the object is already in front of the arm | HiCo-Nav's graph is queried with a sentence, so it finds a class ("a box"), not an instance ("that box") |

**How gaze fits.** The robot explores with its base camera and builds the memory graph as it goes,
looking for the user first to speed up the search. The CLIP feature of the glasses crop is compared
with each object it sees. A match above a cutoff is the trigger to stop exploring and drive to that
object, and the wrist camera confirms it (M8, T8.2). Gaze is the base case. A without-gaze version is
a stretch (T8.11). The evaluation is end-to-end trials, success per phase (T8.3).

### 1.2 Open-source parts we build on

We are building something new from existing open-source systems, not tuning one old workflow.

| Open-source part | What it gives us | What we added or changed |
|---|---|---|
| Meta Project Aria client SDK, eye-tracking model | Glasses camera, gaze, audio | Capture timestamps end to end, gaze vote, gaze-to-mask pick, network fix |
| SAM 3 (Meta) | Text-prompted masks ("box") | One shared ROS 2 service on one GPU, two clients |
| faster-whisper, Silero VAD, Qwen2.5-0.5B-Instruct | Speech to text, sentence detection, object word | Sentence-level gating, release intent, replay tools |
| CLIP (open_clip ViT-B-32, the memory graph's encoder) | One image embedding per mask | Cross-camera matcher: cutoff, tie rules, gaze tie-break |
| SuperPoint + LightGlue, LoFTR | Keypoint matching (the inherited matcher) | Measured as the baseline, then replaced |
| AnyGrasp (graspnet, CVPR 2023 / T-RO) | 6-DoF grasp poses from a point cloud | Axis conversion to our gripper, fingertip offset, fit check, approach cone, score floor |
| OK-Robot (2024) | Recipe: AnyGrasp on the whole scene, keep grasps on the target mask | Adopted in T1.44 |
| MoveIt 2, RealMan RM65 ROS 2 driver | Planning and arm control | State machine fixes, e-stop, grasp request gate, multi-grasp loop |
| Intel RealSense D435i (wrist) | RGB-D at grasp range | Started by serial, 640x480 profile, replay bags |

### 1.3 What was there when I cloned the repo (September 2026)

- About a year of code from the earlier team. The root README described a different project.
- No tests, no CI, no docs that matched the code.
- Nothing ran from a fresh clone. Every path pointed at a user account that no longer existed.
- The AnyGrasp path was unreachable: three interlocking defects (an inverted state check, a consumer
  that accepted candidates in one state only, and a flag that switched the whole path off) (T1.8).
- One program homed the real arm within seconds of starting, with no prompt. The stop key the
  launcher promised did not exist, and the stop program ignored Ctrl+C (T1.2, fixed by Sherman).
- The return pose was 0.0012 rad past a joint limit, so the arm retried an impossible move forever
  (T1.3).
- Concurrency defects in the state machine: one condition variable with two locks, unlocked reads,
  a queue that grew without limit (T1.9).

---

## 2. Groundwork: docs, test bench, CI, refactor

Probably one slide at most. It is why every later result has a run record behind it.

### 2.1 Docs that match the code

- `ORIENTATION`, `ARCHITECTURE`, `READING_GUIDE`, `CODE_AUDIT` (every defect in the grasp path, with
  file and line), `NEXT_STEPS` (decision register), `PROJECT_PLAN` (11 milestones, 70+ tasks).
- **Channel contract** (T0.7, `docs/CHANNEL_CONTRACT.md`): 12 live handover channels between
  subsystems, 4 parked, 4 planned, 11 hidden channels, the transform tree edge by edge, 28 recorded
  decisions. The single reference the team builds against.
- Every claim tagged by source, so the team knows what is fact and what needs checking at the robot.
- Task tree (`docs/task-tree.html`): the one task list, published as an interactive page.

### 2.2 The test bench (L0 to L6)

| Level | What it checks | Needs |
|---|---|---|
| L0 static | Python and C++ checks, joint poses within URDF limits, D455 model | Nothing, about 1 s |
| L1 contracts | A scanner pulls every ROS channel from Python, C++ and launch files and compares against a saved baseline. A refactor that drops a publisher or changes a type fails | Nothing |
| L2 preflight | GPU, Python envs, SDK licences, model weights, reachable hardware | The machine |
| L3 build | colcon build of the workspace | ROS 2 Humble |
| L4 simulation | MoveIt on a simulated arm, the grasp state machine end to end, e-stop delivery, the five nav nodes against a mock Nav2, SAM 3 + AnyGrasp replay on a recorded bag, 206 memory graph tests | ROS, GPU |
| L5 robot | Is the robot connected | The robot |
| L6 real robot | Never automated | People at the robot |

Every simulation test refuses to start unless its ROS domain is private and empty, so a test can
never command the real arm.

### 2.3 CI

- GitHub Actions. `bench` (L0 to L2) runs on GitHub's machines on every PR (T0.10).
- `full` (L0 to L4, no level allowed to skip) runs on a self-hosted runner on the lab box, on PRs
  into `main`, Monday and Wednesday nights on `dev`, and on a button (T0.11). One run at a time on
  the shared GPU.
- `main` and `dev` are protected. `dev` is the default branch. Fixes land through PRs into `dev`.
- Found and fixed along the way: CI never sourced ROS so the D455 check skipped (T0.15), the box
  venv lacked open_clip so 206 memory graph tests skipped, and float16 on the GPU shifts a CLIP
  vector by up to 0.0039 when the batch size changes (T0.18).

### 2.4 Refactor

- One folder per subsystem (`aria/`, `arm/`, `grasp/`, `nav/`, `shared/`, `shared_services/`),
  third-party code under `vendor/`. Pure file moves first, so the contract scanner could prove
  nothing changed (NEXT_STEPS 2.15).
- All 53 owned channel names moved into two-level YAML config: `shared/global_config.yaml` plus one
  file per subsystem. The loader refuses a key set twice (T0.14).
- Paths derived from the repo root, so it runs from a fresh clone (Zongzhe and Sherman checked on
  their Macs).
- Both camera serials in config, every camera start passes its serial, so the driver never opens the
  wrong camera (T1.13).

### 2.5 Tools for working on a shared robot safely

- `quickstart_terminals.sh <layout>` (T0.16): one command opens a tmux session, one pane per process,
  on a private ROS domain. Drivers, the stop, cameras and monitors start on their own. Anything that
  moves the arm or base is typed but not sent, so a person presses Enter.
- `tmux_pane_by_row_col.sh`: send a command to a pane by row and column, so the AI agent runs
  commands where the person at the robot can see them.
- A safety hook (`.claude/hooks/lab_safety_guard.py`, T0.19) blocks `pkill`, arm-moving commands and
  publishing to arm topics. Three people share the box.
- `/ship` (review, bench, commit, PR, CI, merge per task) and `/cold-start` (session handoff)
  skills (T0.19, T0.20). Only shipping code and report material go into git. Plans and experiment
  output stay local (T0.21).
- Jetson Orin recorded as a backup machine (T0.17).

---

## 3. Arm bring-up

| Date | Step | Result `[measured]` | Task |
|---|---|---|---|
| 2026-09-16 | Network switch so the arm and LiDAR can be on together | Both reply from their addresses | T0.2 (with Sherman) |
| 2026-09-23 | First powered session | Arm reachable, ping 0.4 ms, driver handshake (RM65-BI), joint feedback 199.5 to 199.9 Hz on a steady 5 ms interval. No motion | T1.6 |
| 2026-09-23 | First commanded motion: HOME, one joint at a time at speed 1 | Every joint within 0.02 deg of the HOME row. HOME validated in sim first, forward kinematics matched TF to the millimetre | T1.7, T1.3 |
| 2026-10-06/07 | Gripper alone | Open, close on air, close on an empty box at force 150: stops on contact, no crush | T1.22 |
| 2026-10-07 | Grasp state machine on the simulated arm | Home, approach, close, return. PASS in CI | T1.23 |
| 2026-10-07 | State machine homes the real arm | 3.2 s plan, 4.0 s execute at 10% speed, then holds still | T1.24 3a |
| 2026-10-20 | E-stop through the state machine | E during the approach and 1.35 s into the final move both stopped the arm. MoveIt cancelled within 1 ms | T1.38 |

Bring-up was one step at a time, each with a written pass rule and a saved log
(`docs/dion_docs/GRASP_BRINGUP_STEPS.md` is the runbook). There is no teach pendant and no hardware
e-stop button. The only physical stop is the arm's power button, so motion tests always have two
people and a hand on it.

---

## 4. Stage 4a: the glasses (voice, SAM 3, gaze)

### 4.1 What happens

1. You wear the Aria glasses, look at the box and say "pick up the box".
2. The glasses stream the RGB camera, the eye cameras and audio to the lab box.
3. **Voice** (T2.10). Silero VAD runs on the newest 15 s every 0.25 s. Once 0.7 s of quiet follows a
   sentence, Whisper transcribes that one sentence and a small LLM (Qwen2.5-0.5B) returns the object
   word. The word is published once. "release" or "let go" publishes a release instead (T2.6).
4. **Gaze.** The eye-tracking model turns the eye images into a gaze point in the RGB image.
5. **Segmentation.** The aria client sends the glasses image captured when you spoke to the SAM 3
   service with the word. SAM 3 returns every "box" mask with a score.
6. **Gaze pick** (T2.9, T2.20). Each gaze sample near that image's capture time votes for the mask
   under it, or the nearest mask within 80 px. The mask with most votes wins if it has at least half.
7. The winning mask and its crop go out on `/grasp/target` as the reference for the robot side, and
   a grasp request is sent.

### 4.2 The SAM 3 service (T2.1)

- Before: two copies of SAM 3 (one per caller) on one 16 GB GPU.
- After: one stateless ROS 2 request/reply service, `/segmentation/segment`, owns the only copy and
  refuses to start a second time. The grasp client and the aria client both call it.
- Checked: 117 masks in 60 s on the recorded box video, old node 119 in 61 s. AnyGrasp output
  unchanged. About 250 ms a call. Built in six steps, each with tests, all on the lab box.
- The service loads SAM 3 itself (it used to import the glasses code to do it, which dragged in the
  glasses SDK).
- Wrist camera pinned to 640x480: 258 to 271 ms a call, against 362 to 412 ms at 1280x720 (T2.11).
- The old SAM 3 node deleted after the service ran on the real robot (T2.7).

### 4.3 Results `[measured]`

| What | Before | After | Task |
|---|---|---|---|
| Voice messages per phrase | 31, with junk words from the sliding window (pick, book, night, and) | Exactly 1. Word out about 1.1 s after you stop | T2.10 |
| Voice replay without the glasses | None | Replay a WAV into the real voice pipeline. Whisper and the LLM load once | T2.8, T2.16 |
| Speech to text latency | Assumed 0.65 s | Measured about 1.5 s | T2.9 review |
| Gaze pick on recording c2cbafe8 | None | 60 of 61 frames at 1.4 to 2.4 m. The miss is SAM 3 finding no box | T2.9 |
| End-to-end replay (VRS onto ROS, words at set times) | None | 4 of 4 words picked a box and sent a reference | T2.9, T2.20 |
| Gaze vote instead of a 1 s mean | Mean of newest gaze | Same masks, 60 of 61. Vote share 0.5 | T2.20 |
| Client unit tests on the box | 0 | 28 | T2.20 |

![Gaze picks the box at four distances](local/report_media/aria_gaze_pick_4_stops_2026-10-13.jpg)
*Recording c2cbafe8. Blue dot is the gaze, circle is the 80 px pick radius, green is the picked
mask. (T2.9)*

![Gaze pick at four distances, a miss at 1.5 m](local/report_media/aria_gaze_pick_vs_distance_2026-10-20.jpg)
*Recording 5e5d6a91. At 1 m and 0.4 m the gaze is on the box and the box is picked. At 1.5 m and
1.6 m the gaze lands a few pixels off the box, on the mat stack, which SAM 3 also calls a "box".
The panel on the right lists every SAM 3 mask and its score. (T8.5)*

### 4.4 Problems found and fixed

| Problem | Effect | Fix | Task |
|---|---|---|---|
| Newest image and newest gaze used, not the ones from when you spoke | Head motion makes old gaze point at the wrong pixels | Glasses capture time carried on every image and gaze sample (gaze became PointStamped, 4 readers updated). Client keeps 20 s of images and gaze, picks the image nearest the spoken word | T2.19, T2.20 |
| The spoken word has no timestamp | A fixed 1.5 s latency is assumed | Word published with the time it was said (Whisper word times). Built, PR #91 open | T2.21 |
| SAM 3 default cutoff 0.5, top 5 | Box hidden in most glasses frames, other objects outscore it | Glasses side uses 0.3 and top 20 | T2.9 |
| Glasses image rotated, then undistorted with the unrotated calibration | Image shifted about 12.5 px (1.2 deg) | Undistort first, then rotate. Code done, not yet on the live stream | T2.13 |
| Eye model would not load on the box's torch 2.10 | No gaze on the box | Bumped the eye-tracking fork | T2.14 |
| Glasses streaming stopped when the receiver had more than two other IPv4 addresses | No live stream on the box | Network-namespace launcher | T2.12 |
| Glasses workers slow on the box (image every 1.8 to 3 s, gaze 4.7 to 6.6 Hz) | Late images | CPU throttled by heat (89 C at 12% load, clamped to 0.8 GHz). Undistortion maps take 20 s to build. Open | T2.15 |
| Same word twice gave a stale reply | Second request ignored | Word counter | T2.9 review |

### 4.5 Gaze error (T2.3, open)

- On c2cbafe8 the gaze sat about 60 px (about 5.6 deg) off the object at 1.4 m `[measured]`. That is
  not the fixed 1.5 m depth assumption (about 2 px between 1.4 and 1.5 m). It is a gaze model or
  calibration bias. Depth matters up close (about 50 px at 0.5 m).
- 5.6 deg is about 15 cm at 1.5 m, wider than the gap between two boxes on a table.
- Options: per-user gaze calibration, use the eye model's uncertainty bounds (dropped today).
- Policy decided: when gaze is missing or no mask is clearly looked at, ask the user, never grasp
  the best score (the best score was the wrong box on c2cbafe8) (T2.18).

---

## 5. Stage 4b: find the same object in the wrist camera (cross camera)

### 5.1 The problem

The glasses see the box from 1 to 3 m away, front on, small (about 90 px). The wrist camera sees it
from 0.2 to 0.5 m, from above, large. The robot must decide which of its own masks is the one you
looked at, then grasp that one. Before this work, the grasp client ignored the glasses reference
and took the highest-scoring mask.

### 5.2 Point matching failed (T8.4)

The inherited matcher (SuperPoint keypoints + LightGlue) chose a wrist mask in **0 of 15** attempts
`[measured]`: 8 to 19 matches per image pair, at most 2 inside the gazed box, none on a wrist box.
Matching only inside each mask's crop chose a mask 11 of 11 times, but every match was wrong (all
glasses points on one spot, partners spread across the wrist box's edges).

![LightGlue matches the ceiling and floor, not the box](local/report_media/lightglue_baseline_wrong_matches_2026-10-19.jpg)
*Glasses view left, wrist view right. Each line is a keypoint match. None connect the blue box.*

![Crop-only matching: 7 matches, all wrong](local/report_media/lightglue_crop_7_matches_2026-10-19.jpg)

Four offline checks found why:

1. LightGlue works: a crop against a half-size copy of itself matches 100% correctly.
2. Its default resize (1024 px) upscales a 90 px glasses crop about 11 times. SuperPoint then fires
   on JPEG block noise, not the box.
3. Without upscaling, the plain box has 16 to 40 keypoints. Equal box size in both crops gives 4 to 5
   matches, about half plausible.
4. LoFTR (a dense matcher) fails the same way.

Conclusion: the input is the limit. A plain box, far and front on against close and from above,
gives point matching nothing to hold. Further diagnostics (a textured cereal box, greying out the
floor) are parked as T8.6. Also found: the matcher's own `__main__` never called `rclpy.init()`.

### 5.3 CLIP embeddings per mask worked (T8.7)

**Idea.** A whole-object embedding should separate different objects (small brown box vs large blue
box) where point matching found too few features. Crop every SAM 3 mask in both cameras, embed each
with CLIP (the encoder the memory graph already uses), pick the wrist mask with the highest cosine
similarity to the gazed glasses mask.

**Rule** (`cross_camera_mask_match_rule.py`): cosine of all pairs, cutoff 0.56, keep masks within
0.01 of the best, the gaze must be within 80 px of the chosen glasses mask, gaze breaks glasses-side
ties, a wrist-side tie returns no match (never guess).

![Glasses crops top, wrist crops bottom](local/report_media/clip_glasses_vs_wrist_crops_2026-10-20.jpg)
*Top: glasses crops (small, far, blurred, some wrong). Bottom: wrist crops of the same box.*

| Matcher, same frames | Box ranked first `[measured]` |
|---|---|
| SuperPoint + LightGlue | 0 of 15 |
| SAM 3 decoder vector | 7 of 25 |
| SAM 3 image features | 15 of 25 |
| **CLIP** | **25 of 25** (2 to 12 decoys per pair) |
| CLIP, live pipeline on replay | 27 of 27, gaze within 30 px |

Also found: SAM 3's 0.5 cutoff hid the box in 7 of 10 glasses frames, so the glasses side uses 0.3.

### 5.4 Matcher takes the glasses pick as its reference (T8.5, PR #100)

The matcher used to run its own SAM 3 on the glasses and use the newest gaze. Now it takes the
reference crop the aria client picked with the gaze from when you spoke (section 4).

| Wrist scene | Result `[measured]` |
|---|---|
| Three different boxes | 245 of 245 matches on the target, 0 ties |
| Two similar cardboard boxes | 148 of 180 on the target. The tall same-colour box wins some frames |
| Two same-colour cardboard boxes, harder replay | 6 of 12 (T8.8 row) |
| Four distances (1, 1.5, 1.6, 0.4 m) | 3 of 4 references were the box. At 1.5 m the reference was the mat stack and the 0.56 cutoff refused it (score 0.51) |

![Reference crop per spoken word](local/report_media/aria_reference_crops_per_word_2026-10-20.png)
*The crop sent for each spoken "box". Word 2 is the mat stack. The matcher's cutoff caught it. The
glasses-side checks (SAM 3 cutoff 0.3, vote share 0.5) did not.*

**What this means.** CLIP separates different objects well. It does not separate look-alikes. That
needs geometry: put the gaze ray into the robot's 3D frame and take the object it hits.

### 5.5 Pick by geometry, and calibrating glasses to robot (T8.8)

Three methods, cheapest first (NEXT_STEPS 2.13):

| Method | Idea | Cost |
|---|---|---|
| A. Scene transfer | Homography between the two views from background matches, map the gaze point into the wrist image | Hours. Assumes a flat tabletop |
| B. Pose from the shared scene | Lift wrist keypoints to 3D with depth, solve the glasses pose with PnP, cast the gaze ray in the robot frame | Days. The room is the marker |
| C. Full pose fusion | ArUco fix plus visual-inertial tracking between fixes | Weeks |

Plan settled with Dion for T8.8:

1. ArUco markers on the table (A4, about 180 mm), seen by both cameras, as ground truth for testing.
2. End goal is targetless (no marker). A marker once at setup is allowed in the final system.
3. 3 or more objects, not in a line (two objects always give two answers 180 deg apart).
4. Object centres from the two cameras differ by 5 to 10 cm (front faces vs top), so use them to
   start ICP, not as the answer.
5. One recording session serves T8.8, gaze error (T2.3) and the distance limit (T2.24).

Status: Phase 0. Aria MPS (cloud SLAM) login works. Tags not printed. The glasses RGB in the
recordings is 1 fps, thin for matching.

**Why this is not a niche problem.** Two truly identical objects are rare, so they are the hardest
test case, not the pitch. The real capability is knowing where the user is looking in the robot's
own 3D space. It helps with similar objects, partly hidden objects, uncertain image features, and
the robot not seeing what the user sees (the base camera is at knee height). Assistive use is the
clearest case: a user who can look but not easily point or speak, in scenes full of mugs, pill
bottles and cans.

---

## 6. Stage 5: the grasp

### 6.1 The pipeline today

1. The arm is at the view pose (HOME), looking down at the table, 44 deg from straight down.
2. A grasp request (from voice) opens the gate (T1.25). SAM 3 masks the target in the wrist camera.
   The mask's centre and median depth give a 3D point (no depth unless half the mask has a reading).
3. **SELECTING / approach.** MoveIt moves the camera 2 cm towards that point, waits 0.5 s to settle,
   looks again. Repeat until the object is 0.21 m away (at most 50 steps). A centroid older than
   3 s ends the request.
4. **EXECUTING.** AnyGrasp runs on the point cloud every frame. Keep grasps that are on the SAM mask,
   inside the approach cone, score at least 0.3, and fit the 71 mm gripper (width under 68 mm,
   fingertips at most 45 mm past the near face). The pose must be stable for 5 frames.
5. MoveIt plans to the grasp. The gripper closes at force 150. The arm lifts, returns to HOME,
   publishes `/manipulation/done` and holds until a spoken "release" (T1.14). Then open, IDLE, ready
   for the next request.

The simple path skips step 4: one blind 12 cm step and close. It grips about 3 cm short of the box
centre, since the mask's depth is the front face.

### 6.2 State machine features added

| Feature | What it does | Task |
|---|---|---|
| Grasp request gate | A cycle starts only on `/manipulator/grasp_request`, not on any centroid. Lapses after 10 s, refused as busy outside IDLE | T1.25 |
| Stale centroid check | Centroid age from the camera stamp, limit 2 s (now 3 s) | T1.24 |
| Multi-grasp loop | Grasp, hold, release by voice, grasp again in one launch. Failed final step goes home instead of stopping the node | T1.14 |
| E-stop | E or S stop the state machine: cancel the move, no gripper command, STOPPED, refuse requests. R back to IDLE with no motion. Planner refuses moves planned before the stop | T1.38 |
| Settle wait and table | 0.5 s settle before each step. Virtual table at the measured 0.12 m | T1.24 |
| No-fit log | When no grasp fits, log why (narrowest width, tip depth). No retry | T1.37 |
| Concurrency fixes | Unlocked reads, atomic state, lost wake-up on shutdown | T1.9 |

### 6.3 Simple path results `[measured]`

| Date | Result | Task |
|---|---|---|
| 2026-10-12/13 | Live SAM 3 on the wrist camera: box found, depth within 2 cm of a tape measure at 0.25, 0.4 and 0.6 m, no false box with none in view, 0.27 to 0.53 s a frame, 5.8 GB of GPU. Closer than 0.157 m the client sent the background (1.26 m), fixed | T1.24 3b |
| 2026-10-13 | **First real grasp**: live SAM 3, approach, close, lift, back to HOME (fourth attempt) | T1.24 3c |
| 2026-10-13 | First grasp started by voice: WAV, Whisper, LLM, SAM 3, gate, approach, grasp | T1.11 |
| 2026-10-14 | 8 voice-started attempts: 5 of 8, 5 of 6 within reach. 44.5 cm: 4 of 4 (three on the box edge). 54.5 cm: 0 of 2 (out of reach). 49.5 cm: 1 of 2 (stale centroid) | T1.12 |
| 2026-10-14 | Grasp, hold, two requests refused as busy, release by voice, second grasp, release | T1.14 |

The wrist camera gives no depth closer than about 0.18 m, so the stop moved from 0.18 m to 0.21 m
with a 12 cm final step (T1.11).

### 6.4 Switching AnyGrasp on: bugs between AnyGrasp and our arm (2026-10-14)

Each would have made the arm miss or push the box. Each was found with the arm still, on numbers,
before any motion, and fixed with a self-check.

| Bug | Effect | Fix | Task |
|---|---|---|---|
| Gripper width given to AnyGrasp as 0.07 m | It found no room round a 6 cm face. Impossible grasps, top score 0.005 | Give 0.10 m (scores 0.34 to 0.5), check the real fit ourselves | T1.17, T1.32 |
| AnyGrasp approaches along x, our grasp frame along -z | Gripper would come in 90 deg off | Fixed -90 deg turn about y on every grasp. Sim check: gripper 0.0 deg off | T1.17 |
| AnyGrasp's point is 2 to 3 cm short of the fingertips | Jaws close on the box edge | Move the point forward by its depth. Tips now 3.8 cm past the face (was 0.7) | T1.17 |
| Gripper is symmetric, AnyGrasp's closing sign is arbitrary | Wrist spun 180 deg before closing, knocked the box off (first AnyGrasp grasp) | Pick the twin with the smaller wrist turn. Now 11 to 29 deg | T1.33 |
| RViz drew grasps wrong (fingers on the wrong axis, wrong sizes, no arm model) | RViz misleading at the robot | Redrawn to the real gripper, all candidates, arm model added | T1.34 |

![AnyGrasp on the replay, before the fixes](local/report_media/t0.12_anygrasp_replay_2026-10-14.gif)
*"Before" picture. Early replay with the 0.07 m width bug: grasps at angles no gripper could hold,
scores 0.007 to 0.036.*

**Result** (T1.17, 2026-10-20): AnyGrasp path **2 of 3** at the ideal spot (44.5 cm, centred, box
square to the arm). Grasp B failed: the planned path twisted the wrist a long way (j4 146, j5 29, j6
274 deg after power-off), on a target 8 cm lower than the others after 5 failed plans (T1.40).

### 6.5 Validation off the ideal spot (T1.35, paused)

Every grasp so far had the box in one spot, so a pass there is a weak claim. Design settled with
Dion: front face 35, 42, 50 cm (50 changed to 46, out of reach) from the base, -10, 0, +10 cm
sideways, box turned 0, 30, 60, 90 deg, 12 trials drawn with a fixed seed, pass bar 9 of 12, no
skipping. Trial 1 (46 cm, 90 deg) pushed the box: the grasp closed across the 75 mm face, wider than
the gripper. That started T1.44. The E key also failed to stop the arm that day, which started T1.38.

### 6.6 The current blocker: AnyGrasp sees one face (T1.44)

Box 75 x 60 x 143 mm. Gripper opens 71 mm, limit 68 mm.

At 0.21 m the wrist camera sees mostly the face pointing at it. AnyGrasp then proposes:

- Confident grasps (score 0.3 or more) across the 75 mm face. Too wide. The fit check rightly drops
  them.
- Low-score guesses on edges and corners. The fit check measures width from the visible points, so a
  slice running off the edge looks narrow and passes wrongly. Replay: 369 of 369 published grasps on
  the 75 mm face passed, median measured width 55 mm `[measured]`.

![Edge grasp on a 75 mm face measured as 56 mm](local/report_media/fit_check_edge_grasp_75mm_face_measured_56mm_passes_wrongly.png)
*Red is the slice the fit check measures. It runs off the visible box, so it reads 56 mm on a 75 mm
face. The grasp passes.*

![Corner grasp measured as 33 mm](local/report_media/fit_check_corner_grasp_75mm_face_measured_33mm_passes_wrongly.png)

![Centre grasp measured 66 mm, score 0.30](local/report_media/fit_check_centre_grasp_measured_66mm_score_0.30_tape_measure.png)
*The fit check measured 66 mm against a tape measure.*

**The root cause, found offline.** We used AnyGrasp against its own README. It expects the whole
scene (table included) so its collision check sees the table, and it expects the real gripper width.
We passed only the masked points and 0.10 m. Also, the camera axis is 44 deg from straight down, so a
30 deg cone round the camera axis dropped every top-down grasp.

**The grasp that should work.** Straight down across the 59 mm top. AnyGrasp proposes it in 49 of 75
frames and it passes the cone and fit check, but scores at most 0.25, under the 0.3 floor
`[measured]`. Likely because the camera sees the top face only, not the sides `[inferred]`.

![AnyGrasp's 8 best grasps on the two-box scene](local/report_media/anygrasp_8_best_grasps_angles_2026-10-20.png)
*cam = degrees from the camera axis, dn = degrees from straight down.*

**What we tried, in order:**

1. **OK-Robot recipe** (T1.44, PR #99, not merged). Whole scene into AnyGrasp, keep grasps centred on
   the SAM mask (grown 5 px), score floor 0.3, cone 40 deg. Offline: 132 vs 97 confident grasps.
   Live, 4 trials at 40 and 44 cm, none passed: one grasped at an angle and pushed the box, two stuck
   in EXECUTING (no stable pose, no timeout), one found no candidates in 3 s.
2. **Desk diagnosis** (T1.44, parked). The 20 deg minimum approach angle in the state machine dropped
   AnyGrasp's steady top grasp, so the stability check never held. Replay reproduces the logged
   rejections exactly. Lowering it only admits more tilted grasps.
3. **Live test with AnyGrasp 2, 2026-10-22.** Fat side to the arm: only front-face grasps, rejected
   at 68 to 69 mm. Box turned 45 deg: best score 0.287. The RViz cloud looked good, so depth holes are
   not the main cause.
4. **Multi-view fusion** (T1.47, experiment, worktree `../Gappler-t1.47`). Fuse frames into the arm's
   base frame during the approach and sweep the camera 5 cm each side at the end. Fusion worked during
   the approach (33,771 scene and 2,965 target points). In EXECUTING every TF lookup failed: AnyGrasp
   blocked the thread the TF listener shared. Fixed (`spin_thread=True`) plus a depth-edge filter for
   flying pixels. Retest owed.
5. **New AnyGrasp SDK** (T1.45, July 2026 release). Native region steering (grasps only on a
   per-point mask) and approach steering (a native cone) replace two of our filters. Blocked: the
   licence is bound to a hardware ID, and a reboot changed a network interface's MAC. New licence
   requested, MAC pinned.

### 6.7 Grasp defects found and still open

| Task | Defect |
|---|---|
| T1.26 | Home and return ignore the execute result. State machine can start before the driver connects. Slerp execute grasps at the wrong angle |
| T1.28 | A TF a few ms late ends a grasp request |
| T1.29 | MoveIt skips its joint-flip check on every approach step (steps too short) |
| T1.30 | Two requests ended with a stale centroid (2.98 s, 2.44 s), cause unknown |
| T1.31 | No HOLDING state published while the box is held |
| T1.36 | Replay gate check fails on a frame straddling the state switch |
| T1.39 | EXECUTING retries forever with no log, up to 90 s of silence |
| T1.40 | Planned path can twist the wrist a long way |
| T1.42 | The arm controller rejects the hardware e-stop (error -4). Stop works only through our software |
| T1.43 | Pause and continue (S pauses, R continues), proposed |
| T1.46 | Labelled grasp replay tests (graspable / not graspable bags), planned |

---

## 7. Is the 2 cm step approach outdated?

Short answer: the stepping is a known, reasonable method. Where we run AnyGrasp is the weak part.

**The stepping.** Move a little, look again, move again is called look-then-move visual servoing.
It is old (1990s) and still used, because it corrects calibration and depth errors as it goes. It is
slow (up to 50 steps of 2 cm with a 0.5 s settle each) and looks stuttery on video.

**The real problem is the distance.** We run AnyGrasp at 0.21 m, where the camera sees one face.
AnyGrasp is meant to see whole objects with their surroundings. OK-Robot runs the grasp model once
from further back, then plans one motion to the grasp `[inferred]`. T1.44 fits this: the confident
top-down grasp scores low because the close view hides the sides.

**Options, cheapest first** `[inferred]`:

| Option | Idea | Cost | Demo value |
|---|---|---|---|
| A. Grasp from the view pose | AnyGrasp once at 0.4 to 0.5 m with the whole box in view, one planned motion. Steps only as a fallback | Small. The pieces exist | One smooth reach. AnyGrasp fires visibly at the start |
| B. Fused views (T1.47) | Several views in one cloud, grasp on that | Built, retest owed | The 3D cloud filling in as the camera moves |
| C. New AnyGrasp SDK (T1.45) | Native mask and angle steering | Waiting on licence | Same flow, cleaner |
| D. Closed-loop tracking | AnyGrasp's tracking mode updates the grasp while the arm moves | Medium. The old tracker node is parked, not deleted | The arm visibly follows the target |
| E. Two-phase (shelved idea, T1.33) | Move to just before the depth blind zone and set the angle there, then a straight move in and close | Small | Clear and explainable |

For the presentation: "coarse approach by visual servoing, then a learned grasp", plus the plan to
move the grasp decision earlier (A or B). Honest and current.

---

## 8. Visuals and media

### 8.1 Media inventory

All in `docs/dion_docs/local/report_media/` unless noted.

| File | Shows | Section |
|---|---|---|
| `aria_gaze_pick_4_stops_2026-10-13.jpg` | Gaze pick at four stops, 1.4 to 2.4 m | 4 |
| `aria_gaze_pick_vs_distance_2026-10-20.jpg` | Gaze pick at 1, 1.5, 1.6, 0.4 m with SAM 3 scores | 4 |
| `aria_reference_crops_per_word_2026-10-20.png` | Reference crop per spoken word, one wrong | 5 |
| `lightglue_baseline_wrong_matches_2026-10-19.jpg` | LightGlue matches, none on the box | 5 |
| `lightglue_crop_7_matches_2026-10-19.jpg` | Crop-only matching, all wrong | 5 |
| `clip_glasses_vs_wrist_crops_2026-10-20.jpg` | Glasses vs wrist crops for CLIP | 5 |
| `t0.12_anygrasp_replay_2026-10-14.gif` | AnyGrasp on replay before the fixes | 6 |
| `fit_check_*.png` (3) | Fit check passing wrong grasps, one tape-measure check | 6 |
| `anygrasp_8_best_grasps_angles_2026-10-20.png` | AnyGrasp's best grasps with angles | 6 |
| `sam3_false_box_ceiling_light_2026-10-12.png` | SAM 3 calls a ceiling light a box | 9 |
| **VIDEO STUB** `grasp_real_arm_<date>.mp4` | Real arm grasp, phone video. **Dion has it, copy it in** | 6 |
| **VIDEO STUB** `rviz_grasp_<date>.mp4` | RViz: arm model, live cloud, AnyGrasp grippers. **Record Monday 2026-10-26 if needed** | 6 |
| More pictures, not copied | `docs/dion_docs/local/experiments/t8.4_*` (LightGlue and LoFTR checks), `t8.7_*` (SAM 3 embedding sheets, replay crops), `t1.44_fit_debug_2026-10-20/` (fit renders) | 5, 6 |
| Data on the box | `~/grasp_replay_bags/` (5.5 GB: colour, depth, mask, AnyGrasp points and candidates), `~/dion_logs/2026-10-20_t1.35/joint_states_bag3` (real arm joint states), `~/dion_t2.9/c2cbafe8...vrs` (glasses) | 8.2 |

### 8.2 Grasp visualisation options (one judge is a visualisation professor)

Ranked by impact for the effort. Pick 1 or 2.

| # | Visual | Data | Effort |
|---|---|---|---|
| 1 | **3D point cloud with AnyGrasp grippers**, rotating in a browser, stepping through frames, the chosen grasp highlighted, rejected ones faded with the reason | The replay bags above. `grasp/tools/wrist_camera_bag_to_point_cloud_page.py` already makes the point cloud page | About half a day to add grippers and frame stepping |
| 2 | **Multi-view fusion animation**: the cloud fills in as the camera sweeps, then the top-down grasp appears | Needs the T1.47 retest recorded | One box session, then option 1's page |
| 3 | **RViz recording side by side with the phone video** of the real grasp | Phone video exists. RViz display works (T1.34) | One box session |
| 4 | **Before and after of the AnyGrasp fixes** on the same frame | The GIF is the "before" | A couple of hours |
| 5 | **Fit check failure figure** | Done | None |

For the glasses section: the gaze-vs-distance sheet and the LightGlue vs CLIP pair. For a live demo,
the cross-camera match on screen (glasses view with gaze and mask left, wrist view with the matched
mask right) needs only the existing pipeline and a display node.

---

## 9. Challenges

1. **One visible face at grasp range.** At 0.21 m AnyGrasp's confident grasps are the wrong ones
   (6.6).
2. **Featureless objects across very different views.** Point matching cannot find a plain box
   between glasses and wrist. Switched to CLIP (5.2, 5.3).
3. **Look-alike objects.** CLIP cannot separate two similar boxes. Needs geometry and calibration
   (5.5).
4. **Gaze bias.** About 5.6 deg, bigger than the gap between nearby objects (4.5).
5. **Timing across devices.** Glasses, wrist camera and voice each have their own delays. Speech to
   text alone is about 1.5 s. Fixed with capture timestamps (4.4).
6. **SAM 3 false positives and cutoffs.** It calls a ceiling light and a mat stack a "box". The right
   cutoff differs between the glasses (0.3) and the wrist (0.5).
7. **Shared, overloaded hardware.** One 16 GB GPU for SAM 3, AnyGrasp, CLIP, Whisper and the memory
   graph. The CPU overheated and throttled. Three people share the box.
8. **Licensing.** AnyGrasp's licence is bound to a hardware ID that changed on a reboot.
9. **Arm safety.** No teach pendant, no hardware e-stop button. The controller rejects the e-stop
   command (T1.42), so the stop is software only, plus the power button.
10. **Inherited code.** Several defects made the grasp path unreachable, and nothing ran from a fresh
    clone (1.3).

![SAM 3 calls a ceiling light a box](local/report_media/sam3_false_box_ceiling_light_2026-10-12.png)
*SAM 3 masks a ceiling light as "box" when no box is in view (T1.24 3b).*

---

## 10. Next steps

| Order | Step | Task |
|---|---|---|
| 1 | Retest multi-view fusion at the arm | T1.47 |
| 2 | New AnyGrasp SDK once the licence arrives, rerun the offline checks | T1.45 |
| 3 | Choose the grasp strategy (section 7), then the 12-trial validation, pass bar 9 of 12 | T1.35 |
| 4 | Merge the stamped spoken word (the cross-camera reference, T8.5, merged in PR #100 on 2026-10-23) | T2.21 (PR #91) |
| 5 | One recording session: ArUco ground truth, gaze error, distance limit | T8.8, T2.3, T2.24 |
| 6 | Glasses-to-robot transform, then pick by gaze ray for look-alikes | T8.8 |
| 7 | Two boxes on a table, pick the one you looked at, on hardware | T2.5 |
| 8 | Graph-driven approach goal, in C++ | T7.1 |
| 9 | Gaze-target trigger: match graph objects against the glasses crop while exploring, then the end-to-end trials. Find the user while exploring | T8.2, T8.3, T7.6 |
| 10 | When the object is not found, follow the gaze ray to look for it | T7.4 |

**Live demo ideas for next semester** (Dion): find the user's beer even when partly hidden, show the
reasoning, show the cross-camera match live on screen, show the arm moving in with AnyGrasp's grasps
drawn in 3D.

---

## 11. Open questions

1. FAM-HRI's full title and authors: confirm the line in 1.1.
2. Copy the phone video of the real grasp into `local/report_media/` and fill in the stub name.
3. RViz recording on Monday: needed only if option 3 in 8.2 is chosen.

## 12. Sources

- Task rows: `docs/task-tree.html` (T0.x, T1.x, T2.x, T8.x owned by Dion)
- Run records in `docs/bench-runs/`: `2026-09-23-labbox-t1.7-home-joint-states.txt`,
  `2026-10-08-labbox-t2.1-*`, `2026-10-12-labbox-t1.24-3b-live-sam3.txt`,
  `2026-10-13-labbox-t1.24-3c-first-grasp.txt`, `2026-10-13-labbox-t1.11-step4-voice-grasp.txt`,
  `2026-10-13-labbox-t2.11-sam3-resolution.txt`, `2026-10-14-labbox-t1.12-t1.14-real-arm.txt`,
  `2026-10-14-labbox-t1.17-anygrasp-live.txt`, `2026-10-17-labbox-t2.19-t2.20-capture-timestamps.txt`,
  `2026-10-19-labbox-t8.4-old-matcher-baseline.txt`, `2026-10-20-labbox-t8.7-mask-embedding-offline.txt`,
  `2026-10-20-labbox-t1.17-t1.35-live.txt`, `2026-10-20-labbox-t1.35-trial1-t1.44-fit.txt`,
  `2026-10-20-labbox-t1.38-robot.txt`, `2026-10-21-labbox-t1.44-live.txt`, and on PR #100's branch
  `2026-10-20-labbox-t8.5-matcher-uses-client-target.txt`
- Design: `docs/NEXT_STEPS.md` 2.2 (SAM 3 service), 2.13 (gaze by geometry), `docs/PROJECT_PLAN.md`,
  `docs/hico-nav/PAPER_REPORT.md`, `docs/CHANNEL_CONTRACT.md`, `docs/dion_docs/GRASP_BRINGUP_STEPS.md`
- Local only: handoffs, plans and experiment folders in `docs/dion_docs/local/`

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-10-23 | Claude (Opus 5.5) + Dion | Created from the task tree, run records, handoffs, worktrees and the lab box, for the progress presentation. |
| 2026-10-23 | Claude (Opus 5.5) + Dion | Expanded into a full info dump for merging with Sherman's and Zongzhe's reports. Added FAM-HRI framing, groundwork, arm bring-up, all grasp bugs and open defects, media inventory with video stubs. Media moved to `local/report_media/`. |
| 2026-10-24 | Claude (Opus 5.5) + Dion | Next step 4: T8.5 (PR #100) is merged, only T2.21 (PR #91) is left. |
| 2026-10-24 | Claude (Opus 5.5) + Dion | Framing fix (T10.5): §1.1 and next step 9 no longer call the gaze feature a research claim. It is the trigger from exploring to approaching, gaze is the base case, without gaze is a stretch. |
