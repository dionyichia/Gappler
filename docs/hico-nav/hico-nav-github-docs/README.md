# HiCo-Nav — Repository Overview

A folder-by-folder guide, followed by what you need to know to rebuild the
**Cognitive Memory Graph (CMG)**. For the details, read these two docs:

- [`map_class_diagram.md`](map_class_diagram.md): what the graph *is*. It
  covers the input contracts, classes, and node admission and merge rules.
- [`cmg_usage_flow.md`](cmg_usage_flow.md): how the graph is *driven and
  read* at runtime. It covers processes, the per-step loop, and the public API.
- **[`cmg_construction_pipeline.md`](cmg_construction_pipeline.md): how raw
  pixels become nodes and edges.** It breaks construction into 14 stages
  (S0–S13), each with its own input/output contract, parameters, pitfalls
  and acceptance test, plus a build order. **Start here if you are
  reimplementing the graph.**
- [`AGENT_GUIDE_cmg_d435i.md`](AGENT_GUIDE_cmg_d435i.md): a self-contained
  handoff spec for a coding agent rebuilding the graph in a separate
  repository, using an Intel RealSense D435i. It doesn't require this repo.

Line references are against commit `ffc1517`.

---

## 1. Folder breakdown

### How the pieces fit

Each entrypoint script starts three processes
(`multiprocessing`, `spawn`):

```
data_thread       (habitat/nav_runner.py)       sim/sensors → detector → TSDF/frontiers → policy → move
   │  Pipe: RGB-D + pose + detections
   ▼
mapping_thread    (map/multi_level_perception.py)  owns the CMG (map/map.py)
   │  Pipe: keyframe images            ▲ Manager dict: VLM results
   ▼                                   │
reasoning_thread  (map/multi_level_perception.py)  VLM (vlm/)
```

### Top-level scripts

| File | Purpose |
|---|---|
| `object_nav_hm3d.py` | ObjectNav entrypoint for HM3D, MP3D and OVON. Picks the dataset through `-cf cfg/<x>.yaml` |
| `object_nav_mp3d.py` | Older, standalone MP3D runner with its own inlined `data_thread`. The README uses `object_nav_hm3d.py -cf cfg/mp3d.yaml` instead |
| `instance_nav_hm3d.py` | Instance-ImageNav. Its README section is commented out, but `text_nav_hm3d.py` imports helpers from it |
| `text_nav_hm3d.py` | TextNav (a goal given as a free-text description) |

All of them follow the same pattern. They build a list of `NavigationTask`s,
then spawn `data_thread`, `mapping_thread` and `reasoning_thread`, which are
linked by `Pipe`s and one `Manager` dict. They also accept
`--start_ratio`/`--end_ratio` to run a slice of the episodes.

### `cfg/` — experiment configs (OmegaConf YAML)

There is one file per benchmark: `hm3d`, `mp3d`, `hm3d_ovon`, `hm3d_ins` and
`hm3d_text`. Each one holds dataset paths (these are hardcoded to the
authors' machines, so you must edit them), the VLM mode and model, the
detector, sensor and step settings, and every CMG hyperparameter
(`sim_threshold`, `phys_bias`, DBSCAN, voxel size, keyframe pruning and so
on). **This is the single source of truth for CMG tuning.**

### `map/` — the Cognitive Memory Graph and its drivers

The core of the repo. In the code, the CMG is called the "scene graph".

| File | Role |
|---|---|
| `map_elements.py` | Data model: `Object3D` (object nodes), `Keyframe` (visual-anchor nodes), `TargetManager` (task index and blacklists), `ObjectClasses` (vocabulary) |
| `map.py` | `Map`, the graph itself. Construct, associate, merge, prune (ILP), and query |
| `pointcloud.py` | Lifts 2D masks to 3D point clouds, fits bboxes, computes overlap matrices, removes noise with DBSCAN |
| `map_utils.py` | Filters detections and masks, runs CLIP encoding, matches detections to objects |
| `multi_level_perception.py` | `mapping_thread` and `reasoning_thread`, the process loops that drive `Map` and the VLM |
| `communication.py` | Dataclasses sent between the processes (`TaskDataState`, `ReasoningMsg`, `SceneGraphState`, …) |
| `hierarchy_clustering.py` | **Unused.** Instantiated once and never called |
| `grid_map.py` | **Unused.** Never instantiated |

### `habitat/` — simulator binding, driver loop, policy, metrics

| File | Role |
|---|---|
| `habitat_data.py` | Wraps `habitat_sim`: sensors, agent and navmesh. Also holds the **frame conversions** (Habitat y-up → z-up → TSDF) |
| `nav_runner.py` | `run_navigation_tasks`, the data process. Captures several views per step, runs YOLO-World detection, integrates the TSDF, selects goals and moves the agent. **The best reference for the order of CMG calls** |
| `policy.py` | Goal selection. Scores frontiers (CLIP context + object semantics), orders them with a weighted TRP route, and finds observation points near target objects |
| `hm3d_v1.py`, `mp3d.py` | Episode loaders that use only the standard library |
| `evaluation.py` | Success, SPL and geodesic-distance metrics |

### `planner/` — geometric exploration

| File | Role |
|---|---|
| `tsdf_base.py`, `tsdf_planner.py` | TSDF volume fusion with numba, occupancy maps, and frontier extraction. Each `Frontier` holds a `Frame` snapshot. Adapted from Andy Zeng's tsdf-fusion and Allen Ren's (Princeton) version |
| `geom.py` | Grid and geometry helpers: camera intrinsics, observation-point search, collision checks |
| `wtrp.py` | Weighted Traveling Repairman solvers (DP, heuristic, and OR-Tools). `policy.py` uses them to order frontiers |

### `vlm/` — high-level reasoning

| File | Role |
|---|---|
| `vlm.py` | `VLM` facade. Builds prompts for task parsing, map searching and arrival checking, and **parses the 3-line reply format** |
| `vlm_online.py` | Qwen through DashScope's OpenAI-compatible API (needs `DASHSCOPE_API_KEY`) |
| `vlm_offline.py` | Local Qwen2.5-VL or Qwen3-VL through `transformers` |
| `tts_module.py` | Piper text-to-speech for spoken status. **Turned on by default** (`use_audio: True`) |

### `utils/`

| File | Role |
|---|---|
| `visualization.py` | Rerun-based 3D visualization of the graph |
| `build_map_rgbd.py` | Builds a CMG offline from a ScanNet RGB-D sequence. **Broken as it ships** (see §2.5), but a good template for a simple driver loop |
| `manual_hm3d_viewer.py` | Viewer for walking an HM3D scene by keyboard |
| `cuda_debug.py` | Logs GPU memory usage |

### `data/`, `figures/`, `supplementary/`, `docs/`

- `data/scannet200_classes.txt`: the base detector vocabulary. **Its path is
  hardcoded** in `map_elements.py:382`, so run from the repo root.
  `hm3d_annotated_basis.scene_dataset_config.json` is the Habitat scene
  config. The `aeqa_questions-*.json` files are A-EQA question sets.
- `figures/framework.svg`: the system diagram. It is the only place the term
  "cognitive memory graph" appears.
- `supplementary/HiCo_Nav_supplement.pdf`: the paper supplement.
- `docs/`: these notes.

---

## 2. Replicating the Cognitive Memory Graph — what to watch for

### 2.1 What the graph actually is

- **Two node types and no edge class.** `Object3D` nodes hold a point cloud,
  a bbox, a CLIP feature, a label history and `observers`. `Keyframe` nodes
  (visual anchors) hold RGB, depth, intrinsics, pose and `objects_3d`. The
  edges are the two id sets `Keyframe.objects_3d` and `Object3D.observers`,
  and you have to keep both in sync by hand.
- **Keyframes keep depth and intrinsics** so that a 2D bbox from the VLM on
  an old anchor image can be lifted into 3D later (`keyframe_2d_to_3d`).
  Don't drop them to save memory.
- **Only a flattened view leaves the mapping process:**
  `{obj_id: (label, task_score, size, position)}`.

### 2.2 Input contracts (breaking one fails silently)

| Input | Requirement |
|---|---|
| RGB | `uint8`, **RGB order** (not BGR) |
| Depth | `float32` **metres**, same H×W as the RGB, `0` = invalid |
| Pose | `T_world_camera` (camera→world), OpenCV camera axes, **z-up world** |
| `detection_class_ids` | Must index `Map.obj_classes.get_classes_arr()`. Resync the detector every time the VLM adds a class |
| Detections | **Must be sorted by descending confidence.** `filter_detections` has a latent index-mismatch bug otherwise (`map_utils.py:183`) |
| `frame_idx` | Globally unique and monotonic, **never reset across episodes** |

### 2.3 Construction pipeline to reproduce

A summary follows. The stage-by-stage breakdown is in
[`cmg_construction_pipeline.md`](cmg_construction_pipeline.md).

1. **Keyframe gate** (`is_map_undate_needed`). Admit a view only if it moved
   more than 1 m, turned more than 45°, is the first frame, or contains a
   target or relevant class. This gate is what keeps anchors sparse.
2. SAM masks from the detector boxes, then mask filtering, CLIP crop
   features, 2D→3D lifting, and voxel downsampling plus DBSCAN.
3. **Association:** `agg_sim = (1+phys_bias)·spatial + (1−phys_bias)·visual`,
   with a match accepted when it exceeds `sim_threshold` (0.5 and 0.6 in the
   configs).
4. **Merge:** fuse the point clouds and voxel-downsample them. DBSCAN is
   deferred to step 5. Take a detection-count-weighted mean of the CLIP
   features. The label is a
   **running majority vote** over the appended label history. Union the
   observers.
5. **Refinement every 10 updates:** denoise each object, then prune anchors
   with a **PuLP set-cover ILP** that keeps the fewest keyframes still
   observing every object. A greedy fallback runs when the ILP is disabled.

### 2.4 Task conditioning

- Call `update_task(text)` and then `add_target_class(...)`, or the
  `set_target_object_with_clip()` fallback, **before the first
  observation**. Without them, `find_target` returns nothing and the
  keyframe gate loses its "target seen" trigger.
- `reset_scene_graph_every_task: True` wipes the graph on every task. Set it
  to `False` to get the persistent, cross-task memory the paper implies.
- **Consumers write back to the graph.** When the VLM rejects an object on
  arrival, that object is added to `TargetManager.object_blacklist`. Leave
  this out and the robot keeps navigating back to the same wrong object.
  Also track `processed_kf_ids` so anchors aren't re-sent to the VLM.
- Targets found by the VLM are **navigation goals, not graph nodes**. They
  take ids from the same counter, so object ids are not dense.

### 2.5 Known gaps in the shipped code

- **`Object3D.task_score` is never set** and is always `0.0`. As a result
  the semantic frontier score is zero, and **the graph has no effect on
  exploration in the current code.** To get the "score map" behaviour from
  the paper, set it to cos(`clip_ft`, `task_clip_ft`) when an object is
  created and again when it merges.
- **There is no serialization.** `save_to_disk` doesn't exist, so you have
  to write your own dump of objects and keyframes.
- `utils/build_map_rgbd.py` imports a missing `map.depth_completion` and
  calls a nonexistent `Map.grid_map`.
- With `use_clip_mapping: False`, the visual similarity is all zeros and
  association falls back to geometry alone.
- `Map.__init__` always loads SAM (`mobile_sam.pt`) and open_clip
  ViT-B-32, even if you pass your own masks.

### 2.6 What to port and what to leave behind

- **Port:** `map/map.py`, `map_elements.py`, `pointcloud.py` and
  `map_utils.py`. They never import `habitat/` or `planner/`.
- **Rewrite:** the three-process orchestration. The graph has a single
  writer, so a synchronous loop or threads work as long as nothing else
  changes `Map`. Keep the non-blocking update and the "at most one VLM
  request in flight" gate.
- **Don't port:** `habitat_data.py` (it is the simulator), and the parts of
  `policy.py` and `evaluation.py` that query the oracle navmesh
  (`pathfinder`). Of these, `policy.set_next_navigation_point` uses
  ground-truth navmesh *inside the control loop*, so a real robot needs a
  different design there.
- Remove the Habitat frame conversions deliberately, or poses will be
  transformed twice.
- Turn off `use_audio` unless you have a Piper voice model installed.

### 2.7 Minimal replication order

1. A posed RGB-D source and an open-vocabulary detector (YOLO-World in the
   repo) that fills the `detections` dict.
2. A synchronous loop: `update_task` → `add_target_class` →
   `update_scene_graph` for each view (capture 7 views at step 0 and 3 per
   step after that, rotating in place).
3. Your own save and load.
4. Optional: the VLM for task parsing, map search and arrival checks, using
   the 3-line reply contract in `vlm/vlm.py`.
5. Optional: planner integration through
   `prepare_scene_graph_for_planning`. Fix `task_score` first.
