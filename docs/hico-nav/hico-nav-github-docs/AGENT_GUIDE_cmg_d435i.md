# Agent Guide — Building a Cognitive Memory Graph from an Intel RealSense D435i

**Audience:** a coding agent working in a **new repository** that does not
contain HiCo-Nav.
**Goal:** reimplement HiCo-Nav's *Cognitive Memory Graph* (CMG). This is a
3D object-and-keyframe memory built from posed RGB-D images, fed by a
RealSense D435i.

This document is self-contained. Everything needed to build the graph is
written here: interfaces, algorithms, parameters and acceptance tests.
Reading the original code is optional. Links to it are pinned to commit
`ffc1517` of <https://github.com/xukuanHIT/HiCo-Nav> and listed in §12.

---

## 0. How to work from this guide

1. **Read §1–§4 before writing code.** They define the scope, the core
   idea, and the data types that every stage shares.
2. **Build in milestone order (§9).** Each milestone has a deliverable and
   an acceptance test. Don't start a milestone until the previous one
   passes.
3. **Build each stage (§6) as a pure function from one §4 type to another**,
   in its own module, with its own unit tests. Keep the stages independent;
   that is the point of the breakdown.
4. **Assume you cannot reach the camera.** Develop and test against
   recorded data (§5.5) and synthetic fixtures. Code that talks to live
   hardware sits in one thin adapter.
5. **Before §11's open decisions affect your code, ask the human.** For
   anything else this guide doesn't cover, choose the simplest option and
   write the choice down in `DECISIONS.md`.
6. Where this guide says the reference has a bug or quirk, **implement the
   corrected behaviour in §10**, not the original.

---

## 1. Scope

**In scope**
- A capture adapter: D435i RGB-D + an external pose → `Observation`.
- The construction pipeline: `Observation` → object nodes, keyframe nodes
  and edges (stages S1–S13).
- Save and load for the graph (the reference has none).
- A minimal read API (§8).
- Visualisation for debugging (Open3D or Rerun) at each milestone.

**Out of scope unless the human asks**
- Exploration, path planning, frontiers and the TSDF planner.
- The VLM reasoning loop. Leave hooks for it (§8), but don't build it.
- A multi-process architecture. The graph has **one writer**. A
  synchronous loop is fine to start with.
- Building the pose estimator. Use an existing VIO or SLAM system (§5.3).

---

## 2. The core idea: pixels → nodes

A camera produces a grid of pixels. The graph needs discrete nodes and
edges. Pixels **never** become nodes directly.

| Graph element | Built from | Holds |
|---|---|---|
| **Object node** | One object **detection** (box → pixel mask), lifted to 3D with depth + pose, cleaned up, and merged with earlier sightings of the same object | World-frame point cloud with colours, an oriented 3D box, a CLIP appearance vector, a label vote history, and its observers |
| **Keyframe node** | One **accepted photo**, downsized | RGB, depth, intrinsics and pose, enough to **re-project a 2D box back into 3D later** |
| **Edge** | "Keyframe *k* saw object *o*" | Two id sets that must agree: `keyframe.objects` and `object.observers` |

The bridge from pixels to the graph is **detection → segmentation →
back-projection**. Most other stages either remove the noise that bridge
introduces, or decide whether a new 3D blob is an object already in the
graph.

---

## 3. Pipeline overview

```
S0  Capture (D435i + pose)          → Observation
S1  Open-vocabulary detection       → Detections (boxes, labels, conf)
S2  Detection filtering             → Detections
S3  Keyframe gate                   → accept / discard the whole photo
S4  Box → mask segmentation         → masks, eroded by 1 px
S5  Mask cleanup                    → deduplicated masks, nested objects cut out
S6  Appearance embedding            → CLIP vector per detection
S7  Back-projection                 → world-frame point cloud per detection
S8  Point-cloud cleanup + 3D box    → clean cloud + oriented bounding box
S9  Range filter                    → drop far objects
S10 Association scoring             → (candidate → existing node | new)
S11 Insert or merge object nodes    → updated object nodes
S12 Keyframe node + edges           → keyframe node, edges both ways
S13 Periodic refinement             → denoise objects, prune keyframes
```

S0 runs once per view. S1–S13 run in one `update(observation)` call per
view. If S3 rejects a photo, stop there.

---

## 4. Interfaces (define these first)

```python
@dataclass
class Observation:                  # S0 → S1
    rgb: np.ndarray                 # uint8 (H, W, 3), RGB order
    depth: np.ndarray               # float32 (H, W), metres, 0 = invalid, aligned to rgb pixels
    K: np.ndarray                   # (3, 3) colour-camera intrinsics
    T_world_cam: np.ndarray         # (4, 4) camera→world; camera axes x right, y down, z forward; world z up
    frame_id: int                   # globally unique, monotonic, never reset
    timestamp: float                # seconds, the frame's capture time

@dataclass
class Detections:                   # S1 → S2 → S4/S5
    xyxy: np.ndarray                # float (N, 4), pixel coords in rgb
    conf: np.ndarray                # float (N,), SORTED DESCENDING
    class_id: np.ndarray            # int (N,), indexes Vocabulary.classes
    label: list[str]                # len N, == Vocabulary.classes[class_id]
    masks: np.ndarray | None        # bool (N, H, W); None until S4

@dataclass
class Candidate:                    # S7–S9 → S10
    points: np.ndarray              # float32 (M, 3), world frame
    colors: np.ndarray              # float32 (M, 3), [0, 1]
    obb: OrientedBox                # centre (3,), R (3, 3), extent (3,)
    clip: np.ndarray                # (D,), L2-normalised
    label: str
    conf: float

@dataclass
class ObjectNode:
    id: int
    points: np.ndarray; colors: np.ndarray; obb: OrientedBox
    clip: np.ndarray                # sighting-weighted mean, re-normalised
    labels: list[str]               # one per sighting; majority vote = label
    confs: list[float]
    observers: set[int]             # keyframe ids (edges)
    task_score: float = 0.0         # cos(clip, task_clip); see §10
    @property
    def label(self) -> str: ...     # most common entry in labels
    @property
    def position(self): ...         # obb centre
    @property
    def size(self) -> float: ...    # mean obb extent

@dataclass
class KeyframeNode:
    id: int                         # == Observation.frame_id
    rgb: np.ndarray                 # resized; see S12
    depth: np.ndarray               # resized with nearest neighbour
    K: np.ndarray                   # rescaled to match the resize
    T_world_cam: np.ndarray
    detections: Detections          # raw S1 output, before filtering
    objects: set[int]               # object ids (edges)
    task_score: float

class Vocabulary:
    classes: list[str]              # base list (ScanNet-200) + extra classes added at runtime
    background: set[str]            # never become objects

class Graph:
    objects: dict[int, ObjectNode]
    keyframes: dict[int, KeyframeNode]
    next_object_id: int
    last_accepted_pose: np.ndarray | None
    updates_since_refine: int
```

**Invariant (test it after every update):** `o.id in kf.objects` holds if
and only if `kf.id in o.observers`.

---

## 5. The D435i: capture stage S0

### 5.1 What the camera gives you, and what it doesn't

| Gives you | Doesn't give you |
|---|---|
| Colour image (rolling shutter, ~69° × 42° field of view) | **Pose.** It has no tracking |
| Stereo-IR depth (global shutter, ~87° × 58°), in z16 units of `depth_scale`, usually 1 mm | Depth on glass, black or shiny surfaces (these read as 0) |
| IMU (accelerometer + gyro) | Reliable depth beyond ~3–4 m, because stereo error grows with the square of distance |
| Factory intrinsics and depth↔colour extrinsics | Depth closer than a few tenths of a metre (check the datasheet for your resolution) |

### 5.2 Capture adapter (live or recorded)

```python
import numpy as np
import pyrealsense2 as rs

def open_pipeline(bag_path: str | None = None, w=848, h=480, fps=30):
    pipe, cfg = rs.pipeline(), rs.config()
    if bag_path:
        cfg.enable_device_from_file(bag_path, repeat_playback=False)
    cfg.enable_stream(rs.stream.depth, w, h, rs.format.z16, fps)
    cfg.enable_stream(rs.stream.color, w, h, rs.format.rgb8, fps)   # RGB, not BGR
    profile = pipe.start(cfg)
    scale = profile.get_device().first_depth_sensor().get_depth_scale()
    return pipe, scale

align      = rs.align(rs.stream.color)                 # depth → colour pixel grid
threshold  = rs.threshold_filter(0.3, 4.0)             # metres
to_disp    = rs.disparity_transform(True)
spatial    = rs.spatial_filter()                       # edge-preserving smoothing
from_disp  = rs.disparity_transform(False)

def grab(pipe, scale):
    fs = align.process(pipe.wait_for_frames())
    d = fs.get_depth_frame()
    d = from_disp.process(spatial.process(to_disp.process(threshold.process(d))))
    c = fs.get_color_frame()
    i = c.profile.as_video_stream_profile().get_intrinsics()
    rgb   = np.asanyarray(c.get_data()).copy()
    depth = np.asanyarray(d.get_data()).astype(np.float32) * scale
    K = np.array([[i.fx, 0, i.ppx], [0, i.fy, i.ppy], [0, 0, 1]], dtype=np.float64)
    return rgb, depth, K, c.get_timestamp() / 1000.0
```

Rules:
- After alignment, **use the colour intrinsics**.
- **Never use `rs.hole_filling_filter`.** It invents depth across object
  edges. Leave holes as 0; S7 treats 0 as invalid.
- **Don't use `rs.temporal_filter`** unless you restart it at every capture
  position. It smears depth while the camera moves.
- If the colour distortion coefficients (`i.coeffs`) are not all near zero,
  undistort the RGB image and depth before S1, or account for distortion
  in S7.
- Capture **while stationary**. The rolling-shutter colour sensor blurs and
  skews while moving. The reference stops, rotates in place, and captures
  several views at each position: 7 views 40° apart at the start, then 3
  views 60° apart. The D435i's field of view is narrower than the
  simulator's 120°, so expect to need more views or tighter spacing.

### 5.3 Pose: `T_world_cam`

Get the pose from an external system:
- **Visual-inertial odometry or SLAM** using the D435i's own IMU and images,
  for example RTAB-Map, ORB-SLAM3, VINS-Fusion or OpenVINS. Calibrate the
  IMU first with Intel's `rs-imu-calibration` tool; the factory IMU
  calibration is rough.
- **Or the robot's own localisation** (wheel odometry plus lidar SLAM)
  combined with a measured mount transform.

Build the pose with this chain:

```
T_world_cam = T_world_body(t) · T_body_mount · R_body_to_optical

R_body_to_optical =        # body: x forward, y left, z up  →  optical: x right, y down, z forward
[[ 0,  0, 1, 0],
 [-1,  0, 0, 0],
 [ 0, -1, 0, 0],
 [ 0,  0, 0, 1]]
```

`T_body_mount` is the camera's position and tilt on the robot. Get the pose
**at the frame's timestamp**: interpolate between pose samples, using SLERP
for rotation. Don't take the latest pose message. The world frame must have
**z up**, which gravity-aligned VIO gives you. If you use ROS, the camera
frame is `camera_color_optical_frame`, not `camera_link` (which has x
pointing forward).

### 5.4 S0 acceptance test (milestone M1)

Back-project the **whole** depth map (S7's math with an all-true mask) from
two poses about 1 m and 30° apart, both looking at the same wall. In the
world frame:
- the wall points should coincide to within about 3 cm (pose error plus
  depth noise);
- the floor should be perpendicular to world z.

If either fails, the pose chain or the alignment is wrong. **Nothing later
works until this passes.**

### 5.5 Test data without hardware

- Ask the human for RealSense `.bag` recordings (rosbag2 or `rs-record`)
  together with a **pose log** (timestamp, x, y, z, qx, qy, qz, qw) from
  their VIO. Read them with `open_pipeline(bag_path=...)`.
- Write a `RecordedSource` that yields `Observation`s, and later a
  `LiveSource` that yields the same type. Nothing downstream should know
  which one it's using.
- Build synthetic fixtures for unit tests, for example a box-shaped object
  rendered at known poses with a known depth map, so S7–S13 can be tested
  exactly.

---

## 6. Stage specifications

Parameter values marked **[ref]** are the reference's simulator settings.
**[D435i]** is the suggested starting value on real hardware. Make every
constant a config key, including the ones the reference hardcoded.

### S1 · Open-vocabulary detection
- **Model [ref]:** YOLO-World `yolov8x-world.pt` (ultralytics) run with
  `conf=0.1`. Set the vocabulary with `model.set_classes(vocab.classes)`.
  The base vocabulary is the ScanNet-200 class list.
- **Output:** `Detections`, **sorted by confidence, highest first**, with
  `label[i] == vocab.classes[class_id[i]]`.
- Call `set_classes` again whenever `vocab.classes` grows.
- **Test:** shuffle the raw model output and check that the adapter
  re-sorts it. Labels must stay paired with their boxes.

### S2 · Detection filtering
Process the detections in confidence order. Drop any that is:
1. a background class (`background = {wall, floor, ceiling, carpet, rug, bath mat}`) **[ref]**;
2. a box smaller than `min_box_area_ratio · H · W` (`0.0001` **[ref]**);
3. below `conf_threshold` (`0.3` **[ref]**), **unless its label is in the
   current target set**. Target detections are kept at any confidence.

Take the target set as a parameter. **Sort once and index one array.** The
reference indexes a sorted list and the unsorted arrays with the same
indices, which is a bug.
**Test:** the output doesn't depend on input order. A 0.15-confidence
target is kept; a 0.15-confidence non-target is dropped.

### S3 · Keyframe gate
- Reject if no detections are left.
- Otherwise accept if any of these holds:
  - `last_accepted_pose` is `None`;
  - ‖Δt‖ > `gate_dist` (1.0 m **[ref]**);
  - the rotation angle > `gate_angle` (45° **[ref]**);
  - any detected label is in the target or relevant sets.
- Otherwise reject.

`last_accepted_pose` updates **only when a photo is accepted**, at the end
of S12. A rejected photo skips S4–S13 completely.
**Test:** a stationary camera with no targets in view is accepted once. A
1.1 m move or a target sighting is accepted again.

### S4 · Box → mask segmentation
- **[ref]** MobileSAM (`mobile_sam.pt`, ultralytics `SAM`), prompted with
  every box in one batch. Skip this if S1 already produced masks.
- **Erode every mask by one pixel**: keep a pixel only if its whole 3×3
  neighbourhood is set (`conv2d(mask, ones(3, 3), padding=1) == 9`). This
  removes edge pixels that would back-project onto the background behind
  the object. **Required.**
- **Test:** the mask outline sits just inside the object. After S7 the
  cloud has no streaks toward the wall.

### S5 · Mask cleanup
1. In confidence order, drop masks with area below
   `min(mask_area_ratio·H·W, mask_area_px)` (`0.0001`, `25` **[ref]**), and
   masks with IoU above `mask_iou_dup` (`0.9`) against an already-kept mask.
2. **Cut nested objects out of their containers.** For boxes *i* and *j*,
   with `inter = area(box_i ∩ box_j)`: if
   `inter/area_j > 0.8 and inter/area_i < 0.7`, then *j* is inside *i*, so
   set `mask_i &= ~mask_j`.

**Test:** for a cup on a table, the table's mask has a hole where the cup
is, and no pixel is set in two masks.

### S6 · Appearance embedding
- **[ref]** open_clip `ViT-B-32`, pretrained `laion2b_s34b_b79k`, which
  gives D = 512.
- Crop each **box** padded on every side and clamped to the image. The
  reference uses 20 px; use a relative padding (≈3% of the image width)
  instead. Run CLIP preprocessing, encode as a batch, and L2-normalise.
- **Test:** two crops of the same chair from nearby views have cosine
  similarity > ~0.8, and a chair vs. a sink scores clearly lower.

### S7 · Back-projection
For each mask:
1. Keep the pixels where `mask & (depth > 0)`. Skip the mask if fewer than
   `min_points` remain (16 **[ref]**).
2. Back-project each pixel:
   `x = (u − cx)·z/fx`, `y = (v − cy)·z/fy`, `z = depth[v, u]`.
3. Cap the cloud at `max_points` (5000 **[ref]**) by taking every k-th
   point, then transform it: `p_world = T_world_cam @ [x, y, z, 1]`.
4. Attach `rgb/255` as point colours. Fit a box and drop the candidate if
   its volume is below 1e-6 m³.

Compute the per-pixel `xyz` once per frame and reuse it for every mask.
**Test:** with synthetic data, the centroid of a known object is within
1 mm of the ground truth.

### S8 · Point-cloud cleanup and 3D box
1. Voxel-downsample (`voxel = 0.02` m **[ref]**).
2. Run DBSCAN (`eps = 0.1` m, `min_points = 10` **[ref]**) and **keep only
   the largest cluster**. If that cluster has fewer than 5 points, keep the
   input cloud.
3. Fit an oriented box with `get_oriented_bounding_box(robust=True)`,
   falling back to an axis-aligned box if that fails.

Note that keeping the largest cluster can cut away real parts of thin or
disconnected objects, such as chair legs.
**Test:** outliers injected 1 m away are removed, and the box shrinks to
fit.

### S9 · Range filter
Keep a candidate if ‖obb.centre − camera position‖ ≤ `max_range`
(6 m **[ref]**, **3.5 m [D435i]**).
Filter all per-detection arrays together (boxes, masks, vectors, labels,
clouds); the reference once had a bug where they fell out of alignment.

### S10 · Association scoring
Compare every candidate *c* with every existing node *n*:
1. **Spatial:** if the two oriented boxes don't intersect (use a
   separating-axis test), `spatial = 0`. Otherwise `spatial` = the fraction
   of *c*'s points whose nearest neighbour in *n*'s points is within
   `overlap_radius` (2.5 cm **[ref]**, **4–6 cm [D435i]**). Use FAISS or a
   KD-tree for each node.
2. **Visual:** `visual = cos(c.clip, n.clip)`.
3. **Combined:** `agg = (1 + phys_bias)·spatial + (1 − phys_bias)·visual`,
   with `phys_bias = 0.5` **[ref]**.
4. **Match:** for each candidate take the node with the highest score. If
   `agg > sim_threshold` (0.6 **[ref]**), match the candidate to that node;
   otherwise it becomes a new node.

Things to understand:
- With the defaults, `visual` alone scores at most 0.5 < 0.6, so **a match
  always needs some 3D overlap**. Retune `phys_bias` and `sim_threshold`
  together.
- The reference match is **greedy and many-to-one**: two candidates from
  one photo can merge into the same node. See §11.
- Before the graph grows large, add a prefilter that only compares
  candidates with nodes whose box centres are within a few metres.

**Test:** the same object seen from poses 30° apart matches. Two identical
chairs side by side stay separate.

### S11 · Insert or merge object nodes
- **New node:** take `id = next_object_id++`, with `labels = [label]`,
  `confs = [conf]` and `observers = {frame_id}`.
- **Merge into node n** (with m sightings so far):
  - concatenate the point clouds, voxel-downsample, and refit the box. Skip
    DBSCAN here; S13 does it;
  - update `clip = normalise((n.clip·m + c.clip) / (m + 1))`;
  - append the label and confidence (the node's label is the majority
    vote);
  - add `frame_id` to `observers`;
  - recompute `task_score` (§10).
- Return the set of node ids touched by this photo.
- Keep any target or relevant index up to date. **If a node's majority
  label changes, remove it from the old label's index.** The reference
  doesn't, so its index goes stale.

**Test:** 10 views of one object give 1 node with 10 labels and 10
observers, and the point count stays bounded.

### S12 · Keyframe node and edges
- Resize RGB with bilinear interpolation and depth with **nearest
  neighbour** to `keyframe_size`. **Keep the aspect ratio**, e.g. 448 wide.
  Scale K's row 0 by `sx` and row 1 by `sy`.
- Set `task_score = Σ_i cos(crop_clip_i, task_clip)` over this photo's
  crops. This is a sum, so photos with more objects score higher; a mean is
  an acceptable alternative (§11).
- Set `objects` to the ids touched in S11. The edges now exist in both
  directions.
- Store the **raw** S1 detections, set `last_accepted_pose = T_world_cam`,
  and increment `updates_since_refine`.
- **Keep depth and K.** Later, a VLM can mark a 2D box on this stored image,
  and you lift it to 3D with S4 → S7 → S8 using the stored pose. Provide
  this as `lift_box(keyframe_id, xyxy)`.

**Test:** the edge invariant holds. Projecting an object's centroid through
the stored K and pose lands inside its box on the stored image.

### S13 · Periodic refinement (every `refine_every` = 10 accepted photos)
1. **Denoise every object:** voxel-downsample, then keep the largest DBSCAN
   cluster. If fewer than 4 points remain, revert. Refit the box.
2. **Prune keyframes** by solving a set-cover problem: choose the fewest
   keyframes such that each object is still seen by at least
   `min(r, |observers|)` of them, with `r = 1` **[ref]**.
   - Reference method: an integer program with PuLP and the CBC solver.
     **Set a time limit.**
   - Fallback: a greedy approach. Visit keyframes from most objects to
     fewest, and drop any whose objects are all covered already.
3. When you drop a keyframe, remove its id from every object's `observers`.
   **Never delete objects.**

Consider raising `r` to 2 if later queries need several viewpoints of each
object.
**Test:** afterwards every object has ≥ 1 observer, and the keyframe count
doesn't grow when you revisit a room you've already mapped.

---

## 7. Parameter table

| Key | [ref] | [D435i] start | Stage |
|---|---|---|---|
| `stream_w × stream_h` | 640×640 (sim) | 848×480 | S0 |
| `depth_min / depth_max` | — | 0.3 / 4.0 m | S0 |
| `gate_dist / gate_angle` | 1.0 m / 45° | same | S3 |
| `conf_threshold` | 0.3 | 0.3 | S2 |
| `min_box_area_ratio` | 0.0001 | same | S2 |
| `mask_area_ratio / mask_area_px` | 0.0001 / 25 | same | S5 |
| `mask_iou_dup` | 0.9 | same | S5 |
| `contain_inner / contain_outer` | 0.8 / 0.7 | same | S5 |
| `crop_pad` | 20 px | 3% of width | S6 |
| `min_points` | 16 | 16 | S7 |
| `max_points` | 5000 | 5000 | S7 |
| `voxel` | 0.02 m | 0.02 m | S8, S11, S13 |
| `dbscan_eps / dbscan_min` | 0.1 m / 10 | same | S8, S13 |
| `max_range` | 6 m | 3.5 m | S9 |
| `overlap_radius` | 2.5 cm | 4–6 cm | S10 |
| `phys_bias` | 0.5 | tune (try 0.3–0.5) | S10 |
| `sim_threshold` | 0.6 | tune | S10 |
| `keyframe_size` | 448×448 | 448×252 | S12 |
| `refine_every` | 10 | 10 | S13 |
| `cover_r` | 1 | 1–2 | S13 |

Put these in a single config file. **Most of the tuning effort goes into
`overlap_radius`, `phys_bias` and `sim_threshold` (milestone M5).**

---

## 8. Minimal read API

These are what a planner or a VLM would call later. Build them after M6.

| Method | Returns |
|---|---|
| `set_task(text)` | Stores the task's CLIP text vector and recomputes `task_score` for every node |
| `set_targets(target: set[str], relevant: set[str])` | Sets the target and relevant classes. Adds unknown labels to the vocabulary; the caller re-syncs S1 |
| `objects_for_planning()` | `{id: (label, task_score, size, position)}` |
| `find_targets(exclude: set[int])` | Target-class object ids minus a blacklist, plus their keyframes |
| `keyframes_for_search(n, exclude)` | Up to n keyframes, ranked: target class first, then relevant class, then by `task_score` |
| `lift_box(kf_id, xyxy)` | A world-frame point cloud and box for a 2D box drawn on a stored keyframe |
| `blacklist_object(id)` | Excludes an object from `find_targets` permanently. Needed so a rejected candidate isn't proposed again |
| `save(path)` / `load(path)` | Point clouds as `.ply` per object; JSON for everything else (labels, observers, poses, K); images and depth as PNG / `.npy` |

---

## 9. Milestones

| # | Stages | Deliverable | Acceptance |
|---|---|---|---|
| M1 | S0 | `RecordedSource` → `Observation`; full-frame point-cloud viewer | §5.4 two-pose wall test |
| M2 | S1, S2 | Detection overlay on recorded frames | S1 and S2 tests |
| M3 | S4, S5 | Mask overlay | S4 and S5 tests |
| M4 | S6–S9 | Per-detection 3D candidates for **one** frame, in a 3D viewer | S7 synthetic centroid test; no background streaks |
| M5 | S10, S11 | Objects accumulated over a sequence | **Nodes per real object ≈ 1** on a sequence the human labels; report the duplicate rate |
| M6 | S3, S12, save/load | Sparse keyframes with edges; round-trip save/load | Edge invariant; reprojection test; `load(save(g)) == g` |
| M7 | S13 | Long-run stability | Bounded keyframe count on revisits; ≥ 1 observer per object |
| M8 | §8 | Read API | Unit tests for each method |

M1–M4 need no graph state. Do them first and get them solid.

---

## 10. Corrections to the reference (implement these)

| Reference behaviour | Do this instead |
|---|---|
| Detection filter assumes the input is already sorted, and mismatches boxes and labels otherwise | Sort once and index one array |
| Many constants hardcoded (gate, padding, overlap radius 2.5 cm, containment 0.8/0.7, refine interval) | Put them all in config |
| Object `task_score` is never computed (always 0), so the graph has no effect on exploration | `task_score = cos(clip, task_clip)`, computed when a node is created or merged and when the task changes |
| Merged CLIP vector not re-normalised | Re-normalise it |
| Task index not updated when a node's majority label changes | Re-index the node on every merge |
| Keyframe depth resized with bilinear interpolation | Use nearest neighbour |
| Keyframe resized to a square, distorting the aspect ratio | Keep the aspect ratio |
| Field of view computed as `2·atan(W/fx)` | `2·atan(W/(2·fx))` |
| Zero-filled CLIP vectors of the wrong length when CLIP is disabled | Use the model's real dimension, or skip the visual term |
| No save/load | Build it in M6 |
| Integer-program solver with no time limit | Set a time limit, with the greedy method as fallback |

---

## 11. Open decisions: ask the human

1. **Pose source:** which VIO or SLAM system, and in what format and
   message will poses arrive? What is `T_body_mount`?
2. **Loop closure.** The reference stores object points **in world
   coordinates, fixed when added**. If the SLAM system later corrects past
   poses, old objects end up in the wrong place and new sightings no longer
   overlap them, which creates duplicates. Options:
   - (a) use odometry without loop closure and accept the drift;
   - (b) store points relative to the keyframe that observed them, and
     re-transform when that keyframe's pose is updated.

   Option (b) changes the data model, so **decide before M5**.
3. **Association:** keep the reference's greedy many-to-one matching, or
   assign each photo's detections one-to-one (Hungarian algorithm)?
4. **Persistence across tasks:** should the graph be cleared for each task
   (the reference default), or kept as a long-lived memory?
5. **Compute target:** an onboard GPU (e.g. a Jetson) or an offboard one?
   This determines model sizes (YOLO-World variant, SAM vs. MobileSAM) and
   whether S1/S4/S6 need batching or a smaller resolution.
6. **Keyframe `task_score`:** keep the reference's sum, or use a mean?

---

## 12. Reference pointers (optional reading, pinned to `ffc1517`)

Base URL: `https://github.com/xukuanHIT/HiCo-Nav/blob/ffc151724698f5ae33866eea044168b0ad02ced1/`

| Stage | File : line |
|---|---|
| Full per-view update (S2–S13) | `map/map.py:551` (`update_scene_graph`) |
| S1 adapter | `habitat/nav_runner.py:91` (`_extract_detections`) |
| S2 | `map/map_utils.py:183` (`filter_detections`) |
| S3 | `map/map.py:513` (`is_map_undate_needed`) |
| S4 | `map/map.py:630` |
| S5 | `map/map_utils.py:257` (`filter_masks`), `:295` (`mask_subtract_contained`) |
| S6 | `map/map_utils.py:95` (`compute_clip_features_batched`) |
| S7 | `map/pointcloud.py:138` (`detections_to_obj_pcd_and_bbox`) |
| S8 | `map/pointcloud.py:366` (`init_process_pcd`), `:124` (`get_bounding_box`) |
| S9 | `map/map.py:439` (`filter_gobs_with_distance`) |
| S10 | `map/pointcloud.py:615` (`compute_overlap_matrix_general`), `map/map_utils.py:357,377`, `map/map.py:838` |
| S11 | `map/map.py:475` (`merge_obj_matches`), `map/map_elements.py:139` (`Object3D.merge`) |
| S12 | `map/map.py:866` |
| S13 | `map/map.py:965` (`periodic_cleanup_objects`), `:915` (ILP), `map/pointcloud.py:787` |
| Body → optical rotation | `habitat/habitat_data.py:51` (`pose_normal_to_tsdf_real`) |
| Data model | `map/map_elements.py` (`Object3D`, `Keyframe`, `TargetManager`) |
| Config values | `cfg/hm3d.yaml` |

**Dependencies:** `pyrealsense2`, `numpy`, `torch`, `open3d`,
`open_clip_torch`, `ultralytics` (YOLO-World, MobileSAM), `faiss-cpu` (or
use a KD-tree instead), `pulp` (optional, for S13), `scipy`.
