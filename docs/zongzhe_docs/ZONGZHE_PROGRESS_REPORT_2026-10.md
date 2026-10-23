# Zongzhe: progress report, joining to 2026-10-23

This is a full information dump of Zongzhe's work on Gappler, from the first commit on 2026-09-15 to
2026-10-23. It will be merged with Dion's (glasses, cross camera, grasp) and Sherman's (navigation)
reports, then cut down. So it errs on the side of too much detail. Cut freely.

Zongzhe's part of the system: the **memory graph**. The robot drives through the lab and keeps a
memory of every object it saw: where it is in 3D, what it looks like, and the photo that shows it
best. A sentence such as "find the box" is turned into object classes, the graph is searched, and it
returns the matching objects with their positions, best first. That position is what the base
drives to before the arm grasps. Plus some early groundwork (making the repo run from a fresh clone,
the navigation node fixes).

**How to read the evidence.** Task IDs (T6.3, T6.4) are rows in `docs/task-tree.html`. Run records
are in `docs/bench-runs/`. Design decisions D-MG1 to D-MG12 are in `docs/MEMORY_GRAPH_DESIGN.md` §8.
Pictures are in `docs/zongzhe_docs/local/report_media/` (gitignored, on Zongzhe's Mac only). Tags:
`[measured]` from a run, `[code]` read from source, `[inferred]` reasoning not yet tested,
`[unverified]` to confirm.

---

## 0. Summary

| Stage | Where it stands on 2026-10-23 | Headline number |
|---|---|---|
| Groundwork | Repo runs from a fresh clone, bench passes on a Mac, nav bridge fixes | T0.3 done 2026-09-19, T0.5 PASS on the Mac 2026-09-21 |
| Upstream study | HiCo-Nav code read, licences and solvers settled, design written | 3 suspected upstream defects checked against source (T6.1) |
| Read the recording (S0) | Loader for the lab's FAST-LIVO bag, depth made from LiDAR | 3536 frames read. LiDAR fills 12 to 14 % of the image (T6.3b) |
| When to take a photo (S3) | Pose check before SAM 3 | 29 photos kept of 3536 frames, 99.2 % of SAM 3 time saved (T6.5) |
| Find objects in a photo (S1 to S5) | SAM 3, all phrases in one batched pass | 40 phrases in 1.69 s instead of 9.7 s, 5.7 times faster (T6.3c) |
| Objects in 3D, with a CLIP feature (S6 to S9) | Masks lifted to 3D points, one CLIP vector each | Same chair from two views 0.934, other objects 0.56 (T6.3f) |
| Merge sightings into objects (S10, S11) | Tuned on two recorded drives against a hand-made answer key | Duplicates 8 to 3, 0 false merges, match radius 10 cm (T6.4) |
| Keep photos, clean up (S12, S13) | Anchor store, periodic pruning, kappa 3 | Tests pass. Kappa not yet checked on a drive (T6.4f) |
| Sentence to classes | Local Qwen2.5-1.5B with a CLIP fall-back | Right class for 20 of 22 instructions by hand (T6.7) |
| Query the graph | Ranked hits with position and best photo built | Never run end to end on the drive yet. That is M6's acceptance test (T6.8) |
| Hand-off to navigation | Query service drafted as planned channel P2 | Waiting for Dion (T6.8b) |
| Size of the work | `memory_graph/` package | 35 merged PRs, 89 commits on `dev`, about 5,000 lines of code and 4,600 of tests, 399 tests pass on the lab box |

---

## 1. Context and framing

### 1.1 The two papers and where the memory graph sits

Gappler joins two research systems and adds something neither has.

| | FAM-HRI | HiCo-Nav |
|---|---|---|
| What it is | Gaze and speech from Meta Aria glasses tell a robot arm which object to pick. The original authors of this repo were recreating it | Zero-shot language navigation. A robot explores a room and builds a cognitive memory graph (CMG) of every object it sees: 3D points plus a CLIP feature per object, linked to the photos ("anchors") that saw it. ICRA 2026, extended journal version. Code: github.com/xukuanHIT/HiCo-Nav |
| Who works on it here | Dion (glasses, cross camera, grasp) | **Zongzhe (the memory graph)**, Sherman (navigation, mapping, localisation) |
| Gap | Assumes the object is already in front of the arm | The graph is queried with a sentence, so it finds a class ("a box"), not the instance the user looked at |

**Where the memory graph fits in the pipeline.**

1. The base drives through the lab. A camera and the LiDAR record, and the localisation gives the
   camera's position (Sherman's part, M3 and M5).
2. **The memory graph** turns that stream into objects with 3D positions and image features (M6,
   Zongzhe).
3. The user says "find the box" (and looks at it, Dion's part). **The graph** answers with the
   position of the best matching box.
4. The base drives there (Nav2, Sherman). The arm finds the box in the wrist camera and grasps it
   (Dion).

**The research claim the graph serves** (M8, Dion leads): carry the gaze-cropped image feature from
the glasses into the graph query, so the robot finds the specific box the user looked at, not just
any box (T8.1 to T8.3). The graph already stores one CLIP feature per object, which is exactly what
a gaze crop would be compared against.

### 1.2 Open-source parts I built on, and what I added

We build something new from open-source systems. We do not tune one old workflow. HiCo-Nav has no
licence file, so its code was read but never copied (T6.1). `memory_graph/` is a fresh
implementation of the method, with the changes below.

| Open-source part | What it gives us | What I added or changed |
|---|---|---|
| HiCo-Nav (the method and its reference code at `ffc1517`) | The pipeline: anchor gate, detect, mask, back-project, merge, prune, query | Rewrote it as 14 small stages (S0 to S13) with tests. Fixed or avoided 9 upstream problems (section 2.2). Re-tuned it for our sensors (10 cm match radius, occlusion filter, kappa 3) |
| SAM 3 (Meta) | Text-prompted masks | Replaces upstream's YOLO-World plus MobileSAM (D-MG6). A batched path: every phrase in one pass, 5.7 times faster at 40 phrases (T6.3c) |
| open_clip ViT-B-32, `laion2b_s34b_b79k` | One 512-number image or text vector | Encoder with upstream's float16 precision, relative crop padding, text and image in one space (T6.3f, D-MG7). The same encoder Dion's cross-camera matcher now uses |
| Qwen2.5-0.5B and 1.5B Instruct | Small local language models | Instruction to target and related classes, with a timeout and a CLIP fall-back. Upstream used Qwen3-Omni, which does not fit our 16 GB GPU (T6.6, T6.7b) |
| FAST-LIVO2 output (Sherman's recordings) | Colour images, registered LiDAR, poses | A loader that renders depth from the LiDAR cloud, with an occlusion filter (T6.3b, D-MG11) |
| TUM RGB-D `freiburg1_xyz` (CC BY 4.0) | A public RGB-D recording with motion-capture poses | Used to test the loader before our own recording existed (T6.3b) |
| numpy, scipy | Arrays, k-d tree, clustering | Back-projection, voxel grid, DBSCAN, PCA box without Open3D (T6.3e) |
| Rerun 0.30 | 3D viewer | One `.rrd` file per run: room LiDAR, camera, masks, each object's points and box (T6.3) |

---

## 2. What existed when I started, and what I changed

### 2.1 State on 2026-09-15

- The repo did not run from a fresh clone. Paths pointed at old user accounts (T0.3).
- No memory graph code in Gappler at all. Navigation drove to a point from live perception only.
- The five navigation bridge nodes had silent failures: after any navigation failure a second object
  got no goal (CODE_AUDIT F1), and every node crashed with a traceback on Ctrl+C (F4) (T3.8).
- HiCo-Nav's reference code existed upstream, as research code with no licence file.

### 2.2 What I found in upstream HiCo-Nav

Read in the source at `ffc1517` (T6.1, T6.7c note, `docs/zongzhe_docs/CMG_GRAPH_STRUCTURE.md`,
`HICO_NAV_CLASS_DIAGRAM.md`). Each one is avoided or fixed in `memory_graph/`. `[code]`

| Upstream problem | Effect | What `memory_graph/` does |
|---|---|---|
| The graph is not stored as a graph. Each edge lives twice, in two classes, kept in step by hand at three places | Nowhere to store data on an edge, no way to check consistency | `AnchorObjectGraph`: each edge stored once, merge and eviction in one step, `check_invariants()` |
| Pruning runs with kappa (photos kept per object) set to 1 | Multicover becomes plain set cover. One photo per object, no viewpoint redundancy | kappa is config, default 3 (D-MG1, T6.4f) |
| The task score on objects is never set | The graph has no effect on exploration | Set on insert, merge and task change (T6.7a) |
| Class ids built from a Python `set` | Ids can change between runs and within one | Vocabulary is an append-only ordered list (T6.7c) |
| Detections sorted in a way that depends on input order (`map_utils.py:183`) | Results can depend on order | Sort once by confidence, tested with shuffled input (T6.3c) |
| The language model call has no timeout | One bad reply hangs the task | 10 s limit, then a CLIP fall-back (T6.7b) |
| Match radius hardcoded at 2.5 cm | Too tight for our sparse LiDAR depth | Config key, now 10 cm, measured on two drives (T6.4) |
| Fixed 20 px crop padding | Small and large objects padded alike | Padding relative to the box (T6.3f) |
| OR-Tools imported but missing from its requirements | Upstream will not start as shipped | Noted for the simulator baseline (T9.1) |

Also confirmed: two divergence paths I had suspected do not happen upstream, the merge arithmetic
is as I read it, and pruning uses PuLP (MIT) with CBC (EPL-2.0), so licences do not block a solver.
I kept greedy pruning for now (D-MG3). `[code]`, T6.1.

### 2.3 Groundwork (first two weeks)

| Date | What | Result | Task |
|---|---|---|---|
| 2026-09-15 to 09-19 | Repo runs from a fresh clone. Paths inside it from the repo root, outside it in one config file | Done | T0.3 |
| 2026-09-14 | Compile the navigation workspace | 10 of 10 packages in 2 min 34 s `[measured]` | T3.1 |
| 2026-09-14 | Run the ten navigation node tests | 6 controls pass, 4 expected failures reproduced, 0 skipped. Found a new defect, F4 `[measured]` | T3.2 |
| 2026-09-21 | Fresh clone and full bench on my Mac (M0 acceptance) | PASS: L0 to L2 pass, L3 to L6 skipped (no ROS). Found that the AnyGrasp env check fails on any laptop once a venv exists `[measured]` | T0.5 |
| 2026-10-05 to 10-07 | Nav bridge fixes: every goal answered once with "failed" on any failure, quiet Ctrl+C, a 180 s result timeout, 3 s back-off after a failed approach, guard cleared on release | Merged (PRs #41, #42). Checked only against stand-in ROS modules on the Mac. The lab box run of `bench/nav_nodes.sh` is still owed | T3.8 |
| 2026-09-21 to 09-29 | Read HiCo-Nav, wrote the graph design, split M6 into sub-tasks | `MEMORY_GRAPH_DESIGN.md`, PRs #23, #33 | T6.1 |

Handed over: T0.4 (bringing the base packages into git) was finished by Dion.

### 2.4 The memory graph as a set of stages

Upstream's pipeline split into 14 stages, each a small, tested function. One photo goes through them
in this order. Section 3 follows the same order.

| Stage | What it does | Task |
|---|---|---|
| S0 | Read one frame: colour, depth, camera intrinsics, camera position | T6.3b |
| S3 | Anchor gate: keep the photo only if the camera moved or turned enough | T6.5a, T6.5 |
| S1, S2 | SAM 3 finds objects for every phrase in the vocabulary, then filter | T6.3c |
| S4, S5 | Masks: erode one pixel, drop tiny and duplicate masks, one owner per pixel | T6.3d |
| S6 | CLIP vector per object crop | T6.3f |
| S7 to S9 | Lift each mask to 3D points, clean, fit a box, drop far objects | T6.3e |
| S10 | Match each new sighting to a stored object: 3D overlap plus CLIP similarity | T6.4a, T6.4b |
| S11 | Insert as new, or merge into the match | T6.4c |
| S12 | Store the photo as an anchor, linked to its objects | T6.4d |
| S13 | Every 10 photos: denoise objects, prune redundant photos | T6.4f |
| Query | Sentence to classes, score objects, return ranked hits | T6.7a to T6.7d, T6.8a, T6.8 |

(S3 runs before S1 in practice, so SAM 3 never runs on a photo the gate would drop. D-MG12.)

---

## 3. The stages, in the order they run

### 3.1 Reading the recording (S0, T6.3b)

**What it does.**

1. A reader opens a recording and hands out one `Observation` per frame: RGB image, depth in metres
   (0 means no reading), camera intrinsics, and the camera-to-world pose.
2. `to_observation` is the one place every reader ends. It flips BGR to RGB, converts depth units to
   metres, and composes the pose once: base pose times camera mount.
3. Two readers exist:
   - `TumSequence`: a public RGB-D recording, used while ours did not exist.
   - `FastLivoBag`: the lab's FAST-LIVO hand-driven bag. It has colour, registered LiDAR and poses,
     but **no depth image**. So depth is rendered by projecting the LiDAR cloud into the colour
     camera, keeping the nearest point per pixel. Pose chain:
     `T_world_cam = T_world_imu @ T_imu_lidar @ inv(T_cam_lidar)`.
4. Occlusion filter (D-MG11): a depth pixel is cleared if a pixel more than 10 % nearer lies in its
   7 x 7 block. Sparse LiDAR otherwise lets the wall show through the gaps in a chair.

**The recording.** `handdriven1`, a FAST-LIVO hand-driven bag on the lab box, 4.7 GB, 118 s, 3536
colour frames, 2356 poses. A stand-in for T6.2's planned D455 recording, which has not happened yet.
A second drive, `t35f-live-20261021` (76 s), was used to check the tuning in T6.4.

![LiDAR depth over the colour image, four frames](local/report_media/mg_lidar_depth_over_colour_4_frames_2026-10-21.jpg)
*LiDAR points projected into the colour image, coloured by distance, frames 700, 1400, 1500 and
2200 of handdriven1. Depth edges sit on object edges to about 10 px by eye, but background points
fill the gaps between foreground points. (T6.3b, T6.3)*

**Results.**

| Check | Result | Tag |
|---|---|---|
| Same wall, two TUM frames 0.40 m apart | Median gap 0.8 cm, 95 % of points within 5 cm | `[measured]` |
| Same check with each mistake made on purpose (pose inverted, pose ignored, wrong depth scale) | 20 cm or more, so the test catches them | `[measured]` |
| Whole TUM recording | 796 of 798 frames kept, typical gap over 766 pairs 1.4 cm | `[measured]` |
| handdriven1 through `FastLivoBag` | 3536 frames | `[measured]` |
| LiDAR coverage of the image | 1.6 to 2.4 % at a 0.2 s cloud window, about 7 % at 1 s, 12.8 to 14.4 % at 1 s either side | `[measured]` |
| Occlusion filter on frame 700 | Chair centre moves from z -0.02 (a floor patch) to z 0.58 (seat height). Coverage 13.8 to 12.3 % | `[measured]` |
| Two views of one bookcase, cameras 1.17 m apart | Books and shelf cells 3.8 to 9 cm apart, height within 2.5 cm | `[inferred]`, no tape measure |
| Loader and geometry tests | 46 pass on the lab box | `[measured]` |

**Problems found and fixed.**

| Problem | Fix |
|---|---|
| The lab recording has no depth image | Render depth from the registered LiDAR cloud |
| The LiDAR-to-camera extrinsic is stated camera-from-LiDAR, easy to use backwards | Inverted in the chain, recorded in `NOTE_fastlivo_bag_facts.md` |
| Sparse LiDAR shows the floor through a chair | Occlusion filter (D-MG11) |
| The same-wall check cannot fail on LiDAR depth: depth is made from world points with the same pose that turns it back | The check that can fail there is the two-view bookcase in T6.3 |

**Still open.** The LiDAR-to-camera extrinsic is tape-level, not calibrated (34 cm lever arm).
Lens distortion is not corrected. A D455 recording with real depth is T6.2 (Sherman).

### 3.2 When to take a photo: the anchor gate (S3, T6.5a, T6.5b, T6.5, D-MG12)

**What it does.**

1. For each frame, check the pose first: did the camera move more than 1 m or turn more than 45
   degrees since the last kept photo? (upstream's numbers)
2. Only if yes, run SAM 3. If SAM 3 finds nothing after filtering, drop the photo.
3. The last kept pose updates only when a photo is kept.

Upstream runs a cheap detector (YOLO-World) on every frame as stage 1, so a target coming into view
also triggers a photo. I chose the pose check alone for now (D-MG12, tentative): no new model, no GPU
time on the shared card, and gaze and voice already say what the user wants. Cost: a target coming
into view no longer adds a photo by itself.

**Results on handdriven1** (`docs/bench-runs/2026-10-22-labbox-t6.5-pose-gate-sweep.txt`) `[measured]`

| Gate (metres, degrees) | Photos kept | Per minute | SAM 3 time | Saved vs every frame | Saved vs 1 photo a second |
|---|---|---|---|---|---|
| 0.5, 30 | 52 | 26.5 | 96 s | 98.5 % | 55.6 % |
| 0.5, 45 | 45 | 22.9 | 83 s | 98.7 % | 61.5 % |
| **1.0, 45 (the real gate)** | **29** | **14.8** | **54 s** | **99.2 %** | **75.2 %** |
| 1.0, 90 | 22 | 11.2 | 41 s | 99.4 % | 81.2 % |
| 2.0, 45 | 24 | 12.2 | 44 s | 99.3 % | 79.5 % |
| 2.0, 90 | 14 | 7.1 | 26 s | 99.6 % | 88.0 % |

Every frame through SAM 3 would be 3536 calls, 6542 s. At 1.85 s a call (T6.4's median). Upstream
reports one anchor every 1 to 2 s, 30 to 60 a minute `[paper]`. We keep 14.8 a minute.

Cross-check: at the fine gate (0.25 m, 15 degrees) the pose sweep keeps 103 photos, the same as the
GPU run that also applied SAM 3. So no photo that passed the pose check was dropped for having no
detections on this drive. `[measured]`

**Problems found and fixed.** The M6 quiz found SAM 3 ran before the gate could reject a photo. The
gate is now split into a pose half (before SAM 3) and a label half (after). T6.4's drive runner had
its own copy of the pose rule, now replaced by `anchor_gate.pose_moved`, so there is one rule.

**Still open.** Picking and timing a real cheap detector (T6.5b), and the re-decision of D-MG12 with
these numbers (T6.10). Whether 29 photos are enough is answered partly by T6.4's misses.

### 3.3 Finding objects in a photo (S1, S2, S4, S5, T6.3c, T6.3d, T6.7c)

**What it does.**

1. **S1.** SAM 3 is prompted with every phrase of the vocabulary (30 phrases today) on the photo.
   Each phrase's masks, boxes and scores come back. A class id is the phrase's position in the list.
2. **S2.** Sort by confidence once. Drop background classes (wall, floor, ceiling), tiny boxes and
   scores under 0.3. Keep a target class down to 0.15. SAM 3 itself runs at threshold 0.15 so that
   rule can work.
3. **S4.** Erode each mask by one pixel, so edge pixels do not land on the wall behind.
4. **S5.** Drop tiny and duplicate masks. Cut a contained object out of its container (the cup out
   of the table). Then **one owner per pixel** (D-MG10, new): a pixel still in two masks stays only in
   the more confident one.

**Batched SAM 3** (T6.3c). The wrapper the repo had took one phrase per call and encoded the image
again each time. SAM 3 itself can take many phrases on one image. `memory_graph/sam3_batched.py`
encodes the image once, then runs all phrases, 16 per pass.

| Phrases per photo | One call each | Batched, 8 per pass | Batched, 16 per pass | Batched, 32 per pass |
|---|---|---|---|---|
| 1 | 0.24 s | 0.24 s | 0.24 s | 0.24 s |
| 10 | 2.42 s | 0.69 s | 0.59 s | 0.59 s |
| 40 | 9.70 s | 1.88 s | **1.69 s** | out of memory |
| 163 | 41.9 s | 7.16 s | **6.19 s** | not run |

*Lab box RTX 4060 Ti 16 GB, bfloat16, 640 x 480. Peak memory 7.7 GiB at 8 per pass, 10.3 GiB at 16.
Roughly 0.20 s plus 0.037 s per phrase at 16 per pass.* `[measured]`

Same answer both ways: on 7 photos every batched detection paired with the one-call detection,
median mask overlap 0.999, lowest 0.90, scores within 0.03. `[measured]`

**The vocabulary** (T6.7c). 30 ScanNet200 names: 23 fired at 0.5 or more on lab photos, plus 7 lab or
grasp objects (bottle, computer tower, keyboard, laptop, mouse, table, whiteboard). `box` is in it.
Left out: umbrella words that fire on everything ("furniture" on every lab crop, up to 0.95, and
"seat" with every chair), one of each synonym pair (sofa and couch fire together), and background
classes. The list only grows, so a class id never changes meaning. New classes from a task are
appended and SAM 3 is prompted with them from the next photo on.

**Results on four lab photos** (T6.3, `docs/bench-runs/2026-10-21-labbox-t6.3-end-to-end-photo.txt`)
`[measured]`

| Frame | What is in it | Raw detections | After S2 and S5 | Objects |
|---|---|---|---|---|
| 700 | Chair, bookcase, sofa at about 2 m | 151 | 60 | 44 |
| 1400 | Office chairs, desks | 238 | 62 | 35 |
| 1500 | Desk with a cup | 79 | 26 | 15 |
| 2200 | TV, bookcase, bench, sofa | 171 | 63 | 42 |

Over the whole drive: median 137 raw detections, 47 after S2 and S5, 28 objects per photo, 1.85 s
per photo. `[measured]`

![Frame 700: masks after S5, and the objects in 3D](local/report_media/mg_frame700_masks_and_3d_objects_2026-10-21.png)
*Left: SAM 3 masks after S5 on frame 700 (chair, cushion, every bookcase cell, sofa, lights). Right:
the objects with 150 or more points as 3D boxes in the world frame, room LiDAR in grey. First run,
before the two fixes below. (T6.3)*

**Problems found and fixed.**

| Problem | Effect | Fix | Task |
|---|---|---|---|
| One SAM 3 call per phrase | 9.7 s a photo at 40 phrases | Batched path, 1.69 s | T6.3c |
| The one-call path kept every result, image features included | Out of GPU memory at 163 phrases | Convert each result before the next call | T6.3c |
| SAM 3's default threshold 0.5 drops everything below it | S2's "keep a target at 0.15" could never fire | SAM 3 at 0.15 | T6.3c |
| After upstream's S5, 0 to 5.4 % of masked pixels still in two masks. One thing under two phrases (desk and table, paper and book) or a part inside a whole | One depth pixel feeds two objects | One owner per pixel (D-MG10). The done-when (no pixel in two masks) passes on the fixture photos | T6.3d |

**Still open.** Many objects per photo: every bookcase cell is a `shelf`, ceiling lights and
reflections are `light`. How SAM 3 is prompted for underscored classes ("tv_monitor" or "tv
monitor") is T6.12. A baseline of SAM 3's failures and a config switch for other models are T2.22
and T2.23 (not started).

### 3.4 Objects in 3D, with an image feature (S6 to S9, T6.3e, T6.3f)

**What it does.**

1. **S6.** Crop each detection with padding relative to its box, encode it with CLIP, L2-normalise
   it. 512 numbers per object.
2. **S7.** Lift every mask pixel that has depth into a 3D point in the world frame.
3. **S8.** Voxel-downsample, keep the largest DBSCAN cluster (drops stray background points).
4. **S9.** Fit a 3D box by PCA. Drop objects more than the range limit away.

All with numpy and scipy, no Open3D.

**Results.** `[measured]`

| Check | Result |
|---|---|
| Same chair, two nearby views (CLIP cosine) | 0.934 on the lab box GPU (float16), 0.934 on the Mac CPU (float32) |
| That chair against a sofa, a shelf, a bench | 0.562 to 0.563 on the GPU, 0.53 to 0.59 on the CPU |
| A different chair of the same model | 0.81 to 0.85. Appearance alone cannot tell two chairs of one model apart |
| Synthetic scenes: centroid of a known object, outliers 1 m away, an object at 7 m vs 5 m | Within a few cm, outliers removed, the 7 m one dropped, the 5 m one kept |
| Frame 700 chair after the occlusion filter | Centre z 0.58, 1.79 m away. Frame 2200 sees it 7 cm away, so the two sightings merge |
| CLIP beside SAM 3 in one process, four photos | No memory trouble |

**Still open.** Objects cut by the image edge get a shifted centre (a cabinet 52 cm, the sofa 34 cm
between two views). A near object's points can still carry some background.

### 3.5 Merging sightings into objects (S10, S11, T6.4a, T6.4b, T6.4c, T6.4e, T6.4)

This is the heart of the graph: the same chair seen from ten places must become **one** entry, and
two chairs side by side must stay two.

**What it does.**

1. **S10, prefilter.** A k-d tree on object centres finds stored objects near each new sighting.
   Skip pairs whose 3D boxes do not touch.
2. **S10, overlap.** The fraction of the sighting's points with a stored point within the match
   radius.
3. **S10, score.** `1.5 x overlap + 0.5 x appearance` (upstream's weights, phys_bias 0.5). Match if
   the score is over 0.6. Greedy: each sighting takes its best object (D-MG8).
4. **S11.** No match: new object with a new id. Match: points joined and downsampled, box refitted,
   CLIP features averaged by sighting count and re-normalised (upstream does not re-normalise), label
   by majority vote. Each sighting remembers which photo it came from, so an object can be rebuilt if
   poses are corrected later (D-MG9).

**The answer key** (T6.4e). To count duplicates and false merges, I marked the real objects by hand
on a top-down view of the drive's LiDAR map (2 cm cells, 10 cm height bands), next to the photos,
and checked each mark by drawing its 3D box back on the photos. 55 outlines were proposed from the
map by geometry only and all were reviewed (4 accepted, 44 rejected, 2 split, 9 already marked). No
SAM 3 or merge code was used, so the key does not depend on what it tests. First 12 objects, then 16
after a second pass: 7 chairs, 2 tables, 2 TVs, 2 computer towers, shelf, sofa, door.

![The first 12 marked objects on the LiDAR map](local/report_media/mg_ground_truth_12_objects_on_lidar_map_2026-10-21.png)
*Top-down LiDAR map of handdriven1. Blue: 0.2 to 0.6 m high (seats). Green: 0.6 to 1.2 m (tables).
Red: marked objects. The black line is the drive. First version, 12 objects. Four more were added
later. (T6.4e)*

![Outlines proposed from the map by geometry](local/report_media/mg_ground_truth_geometry_proposals_2026-10-21.png)
*The 55 outlines proposed from the map before review. (T6.4e)*

![Floor height and object heights on the map](local/report_media/mg_lidar_map_floor_height_check_2026-10-21.png)
*Checks behind the map: lowest point per cell, top height of things, and cells per height band.
(T6.4e)*

**The scorer** (`memory_graph/score_drive.py`). Replays the saved photos through S2 to S13 and counts,
per real object: duplicates (extra objects of the same kind on it), parts (the glass bookcase's cells,
flagged `many_parts`), false merges, misses, and extras (objects on no marked thing).

**Baseline, upstream settings, real gate** `[measured]`: 26 photos, 677 sightings, 228 objects (many
are small things the key does not score). 8 duplicates, 10 parts, 0 false merges, 4 misses, 20
extras.

**The sweep** (one setting at a time, handdriven1) `[measured]`

| Setting | Real gate: duplicates / false merges / misses / extras | Fine gate (103 photos): same |
|---|---|---|
| Baseline (radius 2.5 cm, phys_bias 0.5, threshold 0.6, greedy) | 8 / 0 / 4 / 20 | 9 / 0 / 3 / 27 |
| Radius 1 cm | 31 / 1 / 3 / 40 | 29 / 1 / 3 / 56 |
| Radius 5 cm | 4 / 0 / 3 / 16 | 8 / 0 / 3 / 25 |
| Radius 7.5 cm | 4 / 0 / 3 / 16 | 6 / 0 / 3 / 22 |
| **Radius 10 cm** | **3 / 0 / 3 / 14** | **4 / 0 / 3 / 23** |
| Radius 15 cm | 3 / 0 / 3 / 14 | 3 / 0 / 3 / 21 |
| Radius 20 cm | 2 / 0 / 3 / 14 | 2 / 0 / 3 / 20 |
| phys_bias 0 (appearance only) | 0 / 0 / 12 / 5 | 0 / 0 / 11 / 1 |
| phys_bias 0.25 | 1 / 0 / 6 / 7 | 1 / 1 / 5 / 8 |
| phys_bias 1 | 11 / 0 / 3 / 25 | 20 / 0 / 3 / 42 |
| Threshold 0.3 | 0 / 0 / 14 / 6 | 0 / 0 / 10 / 2 |
| one_to_one instead of greedy | 13 / 1 / 3 / 28 | 26 / 1 / 3 / 40 |
| min_points 32 | 5 / 0 / 3 / 14 | 7 / 0 / 3 / 21 |

**Reading it.**

- **The match radius is the lever.** Upstream's 2.5 cm is too tight for sparse LiDAR depth, where
  two views of one object land 4 to 9 cm apart. 10 to 20 cm cuts duplicates from 8 to 2 or 3 with no
  false merges and no new misses.
- **More weight on appearance is not safe.** With phys_bias 0 or threshold 0.3 every duplicate
  disappears, but only because nearly everything merges: 34 to 36 objects left, 10 to 14 of the 16
  real ones missed. Over-merging shows up as misses, not false merges.
- **Greedy beats one_to_one** (8 against 13 duplicates).

**Second drive** (`t35f-live-20261021`, 76 s, 55 photos, 14 at the real gate). Its map was lined up
with the first by ICP (turned 3.58 degrees, shifted 1.24 m, 81 % of cells within 10 cm, median 2.8
cm), so the same answer key applies. `[measured]`

| Radius | Real gate: dup / fm / miss / extra | Fine gate: dup / fm / miss / extra |
|---|---|---|
| 2.5 cm | 2 / 0 / 7 / 20 | 4 / 0 / 6 / 26 |
| 10 cm | 1 / 0 / 8 / 14 | 2 / 0 / 6 / 19 |
| 15 cm | 1 / 0 / 8 / 14 | 2 / 0 / 6 / 19 |

At 15 cm a chair merged into the desk beside it. So **10 cm**, not 15.

![Second drive lined up with the first by ICP](local/report_media/mg_second_drive_icp_alignment_2026-10-22.png)
*Left: the two drives' maps as recorded. Right: after the fitted turn and shift, so the first drive's
answer key can score the second. (T6.4 step 5)*

**Settled (D-MG2, 2026-10-22):** geometry-dominant, upstream's weights, match radius 10 cm. Effect at
the real gate: handdriven1 8 to 3 duplicates, second drive 2 to 1, no false merges. A guard test
(`StoredPhotosTest`) replays three stored photos and checks the result holds.

**Problems found and fixed.** Two automatic rules for "part vs duplicate" were tried and rejected
(by size, and by touching points) before the `many_parts` flag. A point inside two marked boxes (a
chair pushed under a table) no longer counts toward a false merge.

**Still open.** Two drives, 16 objects, a handful of duplicates: differences of one are noise. The
false-merge rule misses two kinds of over-merging (a blob spread over many objects, and neighbours in
adjoining boxes), caught here only by the misses column and by looking. The glass door and both
computer towers are missed in every setting. Dense D455 depth may want a smaller radius. The key has
no tape-measure check of the map's scale.

### 3.6 Keeping photos and cleaning up (S12, S13, T6.4d, T6.4f)

**What it does.**

1. **S12.** Each kept photo becomes an anchor: image, depth, intrinsics, pose, its detections and
   the box of each object it shows, resized to 448 x 448 (depth nearest-neighbour, intrinsics and
   boxes rescaled with it). A photo linked to no object is not stored (upstream stores it).
2. **S13.** Every 10 photos: denoise each object (downsample, largest cluster, refit the box), then
   prune photos with a greedy multicover so each object keeps min(kappa, photos that saw it) photos.
   Ties go to the photo with the better view.

**Results** (made-up room of six objects, 11 photos per pass) `[measured]`

| kappa | Photos kept of 11 | Anchor count over four passes |
|---|---|---|
| 1 (upstream) | 2 | stays 2 |
| 2 | 5 | stays 5 |
| 3 (our default) | 8 | stays 8 |
| no clean-up | 11 | 22 after two passes |

Every object's centre projects inside its box on the stored photo, at 64 x 96, 448 x 448 and full
size. With the unscaled intrinsics the same check fails, so the test would catch that mistake.

**Still open.** kappa 3 is tentative (D-MG1) and was not checked on a drive. Denoise uses S8's
cluster setting (0.1 m), which may cut a chair leg. Saving the graph to disk (D-MG5) is not built.

### 3.7 Asking the graph: from "find the box" to an object (T6.6, T6.7a to T6.7d, T6.7, T6.8a, T6.8)

**What happens to "find the box", step by step** `[code]`

1. **Classes from the sentence** (`ClassExpander.expand`, T6.7b). A local Qwen2.5-1.5B-Instruct gets
   the vocabulary in id order, one example and the instruction, and replies in JSON: up to 3 target
   classes and up to 5 related ones. The parser puts names in the vocabulary's spelling, drops
   background classes and nonsense, and maps synonyms (couch to sofa, bin to trash can). If the
   reply is empty, unusable, an error, or takes over 10 s, a CLIP fall-back picks the class whose
   text vector is closest to the sentence. For "find the box", `box` is already in the vocabulary.
2. **New classes join the vocabulary** (T6.7c). If the model names a target the list lacks ("plant"),
   it is appended and SAM 3 looks for it from the next photo on.
3. **Score every object against the sentence** (`TaskContext`, `ObjectStore.set_task`, T6.7a). The
   sentence is encoded with CLIP's text encoder, and every object's task score is the cosine between
   its averaged image feature and that vector. This is where "the big brown box" can beat "the small
   white box": same class, different score.
4. **Find and rank** (`TargetFinder.find`, T6.8a). Objects of a target class first, then related
   ones, each group by task score, minus any object already rejected for this instruction.
5. **What comes back.** A list of hits, best first. Each hit holds: object id, label, kind (target or
   related), task score, the centre of its 3D box (x, y, z, metres, world frame), the box's size, the
   number of sightings, and the stored photo with the best view plus the object's box on it.
6. **Reject** (`TargetFinder.reject`). If the robot arrives and the object is wrong, it is rejected
   and the next call skips it, so the robot never loops back to it.

**What is measured, and what is not.** Steps 1 and 2 are measured on 22 instructions (below). Steps 3
to 6 are tested with stand-ins and on a few real photos. **The whole query has never been run on the
recorded drive.** That run, with each answer checked against the answer key, is T6.8, M6's acceptance
test. "Find the box" itself has not been run, and the answer key has no box in it (open question 5).

**The model choice** (T6.6). Local, text only: no API key, no budget, no network needed on the
robot, and no images leave the box. Upstream's Qwen3-Omni does not fit the 16 GB card. Started with
the 0.5B model the voice path already loads.

**Reasoning check** (T6.7, 22 instructions frozen before the run, 6 kinds,
`docs/bench-runs/2026-10-23-labbox-t6.7-reasoning-check.txt`) `[measured]`

| | Scored automatically | By hand (Zongzhe) | Reply time |
|---|---|---|---|
| Qwen2.5-0.5B | 12 of 22 | not marked | 0.11 to 0.35 s |
| **Qwen2.5-1.5B** | **19 of 22** | **20 of 22** | 0.28 to 0.32 s |
| CLIP fall-back alone | 15 of 22 | 13 of 22 | |

Failures by kind (automatic score):

| | In the list (5) | Synonym (4) | Attribute (3) | Indirect (4) | Relation (2) | Not in the list (4) |
|---|---|---|---|---|---|---|
| 0.5B | 0 | 4 | 3 | 2 | 0 | 1 |
| 1.5B | 0 | 2 | 0 | 0 | 0 | 1 |
| Fall-back | 0 | 1 | 0 | 2 | 0 | 4 |

Examples `[measured]`: 1.5B turns "find the TV" into tv_monitor, "find the PC" into computer tower,
"grab the red bottle" into bottle, "I want to sit down" into chair. 0.5B keeps "red bottle", "wooden
chair" and "office chair" as new classes, and "get me a cup of water" gives "water". The fall-back
cannot name anything outside the list by design, and "I need to throw this away" gives light.

**Fixes from the hand check** (step 5): a synonym table in config, underscore and space read alike,
the prompt asks for 2 to 5 related classes (1.5B named related classes for only 1 of 22), the
fall-back makes only its best class a target and the rest related, and 1.5B is the default. 399
memory graph tests pass on the lab box.

**Photo scoring** (T6.7d). Upstream's frontier scoring: one CLIP vector per whole photo, scored
against the sentence. Built, though nothing uses it yet. On the four fixture photos each ranks first
for its own task, with small margins (chair 0.265 against bench 0.236). `[measured]`

**Still open.** T6.8: write and freeze the sentence queries (drafted in `local/T6.8_PLAN.md`: plain,
synonym, description such as "the small wooden chair", indirect, and not-in-the-graph), replay the
drive, ask each one, check the first hit lands on an accepted marked object, and report the distance.
The held-out rerun of the reasoning check is folded into it. Lifting a box drawn on a stored photo
back to 3D is not built and no task covers it.

### 3.8 Hand-off to navigation (T6.8b, T3.8)

**The query service** (T6.8b, branch `t6.8b-query-shape`, pushed 2026-10-23). Drafted as planned
channel P2 in `CHANNEL_CONTRACT.md` §4, for Dion's C++ node (T7.1). Choices:

1. A ROS service called once per task, sentence in, a ranked list of hits out, plus the frame id.
2. Target hits only by default, related ones on request. A desk is a place to look for a cup, not the
   cup.
3. A second service, "reject object id", called when close-range perception says no.
4. Positions in the frame the graph's poses came from, which must be the frame Nav2 drives in.

Waiting for Dion to agree. No ROS code yet.

**The goal bridge** (T3.8). After the graph gives a position, the existing nav nodes send it to Nav2.
I fixed: every goal answered once with "failed" on no server, a rejected goal or an exception (F1),
quiet Ctrl+C in all five nodes (F4), a 180 s result timeout and a 3 s back-off after a failed
approach, and the approach guard cleared by `/manipulator/release` (F5, new). Merged, but checked only
against stand-in ROS modules on the Mac. Still open: the lab box run of `bench/nav_nodes.sh`, no
retry limit, and `goto_glasses` does not cancel a live Nav2 goal on Ctrl+C.

### 3.9 How the work was tested

- Every stage has unit tests in `memory_graph/tests/`. 399 pass on the lab box GPU with the real SAM 3,
  CLIP and Qwen models, none skipped (2026-10-23). `bench/memory_graph_tests.sh` runs them all.
- Stored fixtures (three lab photos, 840 KB, with SAM 3's raw output and CLIP vectors) let the
  end-to-end test run without a GPU.
- When the lab box was busy, the Jetson Orin stood in for CPU-only tests (T6.4d, T6.4f, T6.7a,
  T6.8a). The same tests later passed on the lab box.
- Each GPU run started with `nvidia-smi` and a process check. Twice the GPU was in use by a grasp
  session, so I waited or ran on the CPU.
- After each task, a quiz on the new code (`docs/zongzhe_docs/quizzes/`: M6, T6.3, T6.3c, T6.7). The
  M6 quiz found 11 code issues. Three correctness ones were fixed in T6.9 (a repeated photo counted
  twice, frame ids restarting per recording, two best-photo rules that disagreed). The T6.7 quiz
  found six, all fixed.

---

## 4. Challenges

1. **No depth camera in the recording.** The lab drive has LiDAR, not a depth image. Projected LiDAR
   fills only 12 to 14 % of the image and shows through near objects. Needed a depth renderer and an
   occlusion filter (3.1).
2. **Uncalibrated LiDAR-to-camera extrinsic.** Tape-level, with a 34 cm lever arm. Two views of one
   object land 4 to 9 cm apart, which is why the match radius had to grow from 2.5 to 10 cm (3.5).
3. **No ground truth existed.** I built an answer key by hand from the LiDAR map, checked against
   photos. It has known gaps (no tape check of scale, a few unmarked blobs), and the first version
   was incomplete enough that the first baseline mostly measured gaps in the key (3.5).
4. **SAM 3 over-detects.** Umbrella words ("furniture", "seat") and synonyms fire together, every
   bookcase cell is a shelf, reflections become lights, and part-and-whole masks overlap (3.3).
5. **Look-alike objects.** Two chairs of the same model score 0.81 to 0.85 on CLIP, almost as high
   as the same chair twice (0.934). Appearance alone cannot separate them, so the graph leans on
   geometry, and picking the one the user means needs gaze (M8).
6. **One shared 16 GB GPU.** SAM 3, AnyGrasp, CLIP, Whisper and the language model share it, and
   three people share the box. Batched SAM 3 runs out of memory at 32 phrases per pass. Several runs
   waited for a grasp session to finish.
7. **Upstream research code.** No licence (read, not copied), and several defects (2.2), including
   one that switches off the paper's own pruning guarantee (kappa 1).
8. **Small local language models.** 0.5B kept attributes and synonyms as new classes. 1.5B is better
   but rarely names related objects unless asked.
9. **Small evaluation.** Two drives in one lab, 16 marked objects, a handful of duplicates.
   Differences of one are noise.

---

## 5. Next steps, in order

| Order | Step | Task |
|---|---|---|
| 1 | Dion agrees the query service shape, then mark it done | T6.8b |
| 2 | Write and freeze the sentence queries, build `GraphQuery` and the check script, run on the drive, hand check. **M6's acceptance test** | T6.8 |
| 3 | How SAM 3 is prompted for underscored classes (tv_monitor) | T6.12 |
| 4 | Check kappa 3 and the denoise setting on the drive | T6.4 (left over), D-MG1 |
| 5 | Lab box run of the nav bridge tests, then retag F1, F4, F5 | T3.8 |
| 6 | Re-decide the gate's first stage (pose only, or a cheap detector) with T6.5's numbers | T6.10, T6.5b |
| 7 | A D455 recording with real depth, then re-check the match radius | T6.2 (Sherman), D-MG2 |
| 8 | SAM 3 failure baseline, and segmentation model as a config choice | T2.22, T2.23 |
| 9 | Build the graph while the robot drives, not from a recording | T7.2 |
| 10 | Gaze-cropped feature into the graph query, then the with/without gaze ablation (the research claim) | T8.1 to T8.3 (Dion leads) |
| 11 | Stretch: upstream simulator baseline, frontier scoring, visit ordering, a goal-emitting node | T9.1 to T9.4 |

---

## 6. Visualisation options for the memory graph

Ranked by impact for the effort. One judge is a visualisation professor, so the graph itself (objects
linked to the photos that saw them) is the thing worth showing. Pick 1 or 2.

| # | Visual | What it shows | Data that exists | Effort |
|---|---|---|---|---|
| 1 | **The graph in 3D, in the browser.** Room LiDAR in grey, each object as a labelled box, each anchor as a small camera at its pose, lines from each camera to the objects it saw. Step through the drive and watch objects appear and merge | The whole idea of the memory graph in one picture | A Rerun file for four photos already exists (`mg_t6.3_four_photos_rerun_3d_2026-10-21.rrd`, opens in the Rerun web viewer). The whole drive's 103 saved photos are local and on the box | Zero to show the four-photo file. About half a day to write the whole drive with camera-to-object lines |
| 2 | **Query on the map.** Type "find the chair": the top-down map lights up the hits by task score, the first hit is circled, and its best stored photo pops up beside it | What the graph is for | Map, answer key, saved photos, `TargetFinder`. Needs T6.8's run for real answers | About a day after T6.8 |
| 3 | **Merge radius slider.** Top-down map with the 16 marked boxes and the graph's objects. Slide the radius from 1 to 20 cm and watch duplicates collapse, then a chair swallowed by its desk at 15 cm on the second drive | The tuning result and its trade-off | Sweep results are in `local/t6.4/sweep_*.json` and `live1_*.json`. The scorer can rerun any setting in seconds on a laptop | Half a day (one picture per setting plus a slider page) |
| 4 | **One photo through the pipeline.** Photo, SAM 3 masks, LiDAR depth, 3D points, the merged object, in five panels for the frame 700 chair (including the floor-patch bug and its fix) | How the stages work | All of it, from T6.3 runs | 2 to 3 hours |
| 5 | **Sentence to classes table.** 22 instructions, what 0.5B, 1.5B and the fall-back answered, coloured right or wrong | The reasoning layer | `local/t6.7/out/check_reasoning.json` and `HAND_CHECK.md` | 1 to 2 hours |
| 6 | **Gate timeline.** The drive's path with the 29 kept photos marked, and a bar of SAM 3 time: 6542 s every frame, 217 s at one a second, 54 s with the gate | Why the gate matters | `local/t6.5/sweep_handdriven1.json`, poses from the bag | About 2 hours |
| 7 | **Duplicates against radius**, a line chart for both drives | The tuning result, simplest form | The tables in section 3.5 | About 1 hour |

For a live demo next semester: option 2 running against a graph built live (T7.2), the robot driving
to the first hit.

---

## 7. Media inventory

All in `docs/zongzhe_docs/local/report_media/` unless noted. Copied, not moved. Originals stay in
`local/t6.3/`, `local/t6.4/`, `local/t6.4e/`.

| File | Shows | Task | Section |
|---|---|---|---|
| `mg_lidar_depth_over_colour_4_frames_2026-10-21.jpg` | LiDAR depth projected over four colour frames | T6.3b, T6.3 | 3.1 |
| `mg_lidar_depth_over_colour_zoom_2026-10-21.jpg` | Zoom of the same, depth edges against object edges | T6.3b | 3.1 |
| `mg_handdriven1_survey_every_100th_frame_2026-10-21.jpg` | Contact sheet, every 100th frame of the drive | T6.3 | 3.1 |
| `mg_frame700_masks_and_3d_objects_2026-10-21.png` | SAM 3 masks on frame 700 and the objects as 3D boxes | T6.3 | 3.3 |
| `mg_t6.3_four_photos_rerun_3d_2026-10-21.rrd` | Interactive 3D: room, camera, masks, objects for four photos, after both fixes (open with Rerun 0.30) | T6.3 | 6 |
| `mg_ground_truth_12_objects_on_lidar_map_2026-10-21.png` | Answer key, first 12 objects on the LiDAR map | T6.4e | 3.5 |
| `mg_ground_truth_geometry_proposals_2026-10-21.png` | 55 outlines proposed from the map | T6.4e | 3.5 |
| `mg_lidar_map_floor_height_check_2026-10-21.png` | Floor and height checks behind the map | T6.4e | 3.5 |
| `mg_second_drive_icp_alignment_2026-10-22.png` | The two drives' maps before and after ICP | T6.4 | 3.5 |
| **VIDEO STUB** `mg_graph_3d_flythrough_<date>.mp4` | Screen recording of the Rerun viewer flying through the four-photo graph. **Can be recorded any time from the `.rrd`** | T6.3 | 6, option 1 |
| **VIDEO STUB** `mg_handdriven1_drive_<date>.mp4` | The drive's colour stream as a video, to show what the robot saw. **Export from the bag on the lab box** (`~/rcp-Gappler/log/t59-fastlivo/.../handdriven1_0.db3`). Sherman may already have a video of this run | T6.2 stand-in | 3.1 |
| **VIDEO STUB** `mg_query_find_the_chair_<date>.mp4` | A sentence typed, the hits lighting up on the map, the best photo shown. **Needs T6.8** | T6.8 | 6, option 2 |
| **VIDEO STUB** `mg_merge_radius_slider_<date>.mp4` | Duplicates collapsing as the radius grows. **Needs option 3 built** | T6.4 | 6, option 3 |
| Not copied, local | Marking page with all photos (`local/t6.4e/gt_hd1/index.html`), the 103 saved drive photos (`local/t6.4/drive_hd1/`, 40 MB), sweep results (`local/t6.4/*.json`), reasoning check tables (`local/t6.7/out/`), hand check (`local/t6.7/HAND_CHECK.md`) | | |
| Data on the box | `~/zongzhe_t63/` (96 MB): `drive_hd1`, `drive_live1`, `gt_hd1`, `gt_live1`, `run1`, `run2`. The same content as the local folders above. Nothing extra worth copying was found | | |

---

## 8. Open questions for Zongzhe

1. **Credit for the recordings.** `handdriven1` (2026-10-20) and `t35f-live-20261021` sit under
   `t59-fastlivo` and `t35*` run names on the box, which look like Sherman's FAST-LIVO work
   `[inferred]`. Confirm who recorded them, so the merged report credits them right.
2. **Task tree has duplicate rows.** The `T` array in `docs/task-tree.html` holds T6.7b and T6.7c
   twice. In each pair one copy is stale (T6.7b: one copy has no "Built" note, neither starts with
   DONE although T6.7 closed. T6.7c: the second copy lacks the DONE prefix). Likely a merge artifact.
   Fix it now (a global doc edit and a republish), or leave it for a separate change?
3. **T6.7b's status.** Built and tested on the lab box 2026-10-22, PR #116 merged, but its row has no
   DONE prefix and the close PR #120 was closed unmerged. Should it be marked done?
4. **T3.8.** Merged in October but never run on the lab box. Keep it in this report, or leave it out
   as not memory graph work?
5. **"Find the box".** `box` is in the vocabulary, but the answer key has no box and the draft T6.8
   query set has no box query. Use "find the chair" as the report's example instead, or add a box to
   the lab, the key and the query set?
6. **Which visual to build** for the presentation (section 6). Option 1 needs almost nothing.
7. **HiCo-Nav authors and full title** for the merged report's context table (Dion's report has the
   venue and repo, not the authors).
8. **Hours.** The task tree gives estimates, not hours spent. Add a time line if the presentation
   wants one.

## 9. Sources

- Task rows: `docs/task-tree.html`, every row with owner Z, ZS, SZ or ZD (T0.3, T0.4, T0.5, T2.22,
  T2.23, T3.1, T3.2, T3.8, T5.4, T6.1, T6.3a to T6.3f, T6.3, T6.4a to T6.4f, T6.4, T6.5a, T6.5b, T6.5,
  T6.6, T6.7a to T6.7d, T6.7, T6.8a, T6.8b, T6.8, T6.9, T6.10, T6.12, T7.2, T9.1 to T9.4)
- Run records in `docs/bench-runs/`: `2026-09-21-zongzhe-mac-t0.5-fresh-clone.txt`,
  `2026-10-07-labbox-t6.3-memory-graph-stage-tests.txt`, `2026-10-07-labbox-t6.3b-replay-loader-tests.txt`,
  `2026-10-07-labbox-t6.3d-sam3-adapter-tests.txt`, `2026-10-07-labbox-t6.4c-object-store-tests.txt`,
  `2026-10-11-orin-t6.4d-anchor-store-tests.txt`, `2026-10-11-orin-t6.7a-task-conditioning-tests.txt`,
  `2026-10-12-orin-t6.4f-periodic-cleanup-tests.txt`, `2026-10-12-orin-t6.8a-find-targets-tests.txt`,
  `2026-10-20-mac-t6.3c-sam3-batched-plumbing.txt`, `2026-10-20-labbox-t6.3c-sam3-batched-timing.txt`,
  `2026-10-21-labbox-t6.3-end-to-end-photo.txt`, `2026-10-21-labbox-t6.4-drive-run.txt`,
  `2026-10-21-labbox-t6.4f-kappa-3-tests.txt`, `2026-10-21-labbox-t6.4f-dev-cleanup-tests.txt`,
  `2026-10-21-labbox-t6.7c-vocabulary-tests.txt`, `2026-10-21-labbox-t6.7d-photo-score-tests.txt`,
  `2026-10-22-labbox-t6.5-pose-gate-sweep.txt`, `2026-10-22-labbox-t6.7b-class-expansion-tests.txt`,
  `2026-10-23-labbox-t6.7-reasoning-check.txt`, `2026-10-23-labbox-t6.7-step5-tests.txt`,
  `2026-10-23-labbox-t6.7-check-script-tests.txt`
- Design: `docs/MEMORY_GRAPH_DESIGN.md` (D-MG1 to D-MG12), `docs/hico-nav/PAPER_REPORT.md`,
  `docs/CHANNEL_CONTRACT.md` §4 (P2, on branch `t6.8b-query-shape`)
- My folder: `CMG_GRAPH_STRUCTURE.md`, `HICO_NAV_CLASS_DIAGRAM.md`, `NOTE_fastlivo_bag_facts.md`,
  `T6.3_WALKTHROUGH.md`, `T6.4_WALKTHROUGH.md`, `T0.3_SESSION.md`, `quizzes/`
- Local only: `local/T6.3_PLAN.md` to `local/T6.8_PLAN.md`, `local/t6.3/` to `local/t6.7/`
- Git: 35 merged PRs (#23 to #123), 89 non-merge commits on `dev`, first commit 2026-09-15. Code
  size counted with `wc -l` on `dev` at `605be5f`
- Lab box (read only, 2026-10-23): `~/zongzhe_t63/`

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-10-23 | Claude (Opus 5.5) + Zongzhe | Created from the task tree, run records, my docs folder and local plans, git and PRs, and a read-only look at the lab box, for the team progress presentation. Same structure as Dion's report. Media copied to `local/report_media/`. |
