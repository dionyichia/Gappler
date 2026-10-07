# MEMORY_GRAPH_DESIGN — the anchor-object graph for M6

**The data structure M6 builds on, specified before the code exists.** Owner: Zongzhe.
Serves `PROJECT_PLAN.md` T6.3, T6.4 and stretch goal S3. Written 2026-09-21, ahead of M6 opening on
2026-12-28.

M6 is "the memory graph is built offline" (`PROJECT_PLAN.md:386`), accepted when a recorded drive
produces object entries, the same physical object is not registered twice, and a sentence query
returns it. This document specifies the structure that holds those entries and the relationships
between them. It does not specify the perception that fills it.

> **Status: proposed, not built.** Nothing here is implemented in `src/`. A validated reference
> implementation exists as a prototype (section 7). Treat this as a design to argue with before
> T6.3 starts, not as a record of what is there.

## Contents

1. [What this is and is not](#1-what-this-is-and-is-not)
2. [Requirements, traced to M6](#2-requirements-traced-to-m6)
3. [Why not copy HiCo-Nav's arrangement](#3-why-not-copy-hico-navs-arrangement)
4. [The finding that matters most for M6's stated risk](#4-the-finding-that-matters-most-for-m6s-stated-risk)
5. [The design](#5-the-design)
6. [Pruning, and the redundancy parameter](#6-pruning-and-the-redundancy-parameter)
7. [Reference implementation and its evidence](#7-reference-implementation-and-its-evidence)
8. [Open decisions](#8-open-decisions)
9. [How this maps onto the M6 task tree](#9-how-this-maps-onto-the-m6-task-tree)

---

## 1. What this is and is not

**In scope.** The index that relates stored camera views to 3D object entries: how an edge is
stored, how entries merge, how the structure is pruned as it grows, and what it guarantees about its
own consistency.

**Out of scope, and specified elsewhere or not yet.**

| Not here | Where it belongs |
|---|---|
| Detection, masks, CLIP features, 2D-to-3D lifting | T6.3, and the two-stage trigger in T6.5 |
| The similarity function that decides whether two entries are the same object | T6.4. Section 4 below is an input to that decision, not the decision |
| The reasoning layer that expands an instruction | T6.7 |
| Which ROS channels carry any of this | `CHANNEL_CONTRACT.md`, once T6.8 has something to publish |
| Solver choice and licensing | T6.1, and S3 |

**Vocabulary.** The paper calls these *visual anchors* and *object nodes*; HiCo-Nav's code calls the
whole thing a *scene graph* (`zongzhe_docs/HICO_NAV_CLASS_DIAGRAM.md:1-5`). This document uses
**anchor** for a stored camera view and **object** for a 3D entry, and follows the descriptive-naming
rule in `ORIENTATION.md` §0b: an anchor here is a base-camera view, never a wrist-camera one.

## 2. Requirements, traced to M6

Derived from the M6 acceptance text at `PROJECT_PLAN.md:500-506` and the T6 task tree at
`PROJECT_PLAN.md:680-688`. Each is testable without hardware.

| # | Requirement | Comes from |
|---|---|---|
| R1 | Relate anchors to objects in both directions, one hop, cheaply | T6.3, T6.8 |
| R2 | Merge two entries into one without leaving either direction stale | T6.4, and M6's "not registered twice" |
| R3 | Evict an anchor atomically, since pruning does this constantly | S3 |
| R4 | Carry per-sighting information, so "which stored view shows this object best" is answerable | T6.8, and M8's gaze-into-query step |
| R5 | Verify its own consistency, so a defect fails loudly rather than skewing a number | The bench convention: skipped checks are reported as skipped |
| R6 | Bound growth over a long run, with the redundancy parameter a stated decision | S3 |
| R7 | Run with no ROS and no solver, so it is checkable at bench levels L0 to L2 | `bench/README.md` |

R4, R5 and R7 are the three that HiCo-Nav's arrangement cannot satisfy. That is the case for
writing our own rather than porting, and it is a small piece of code either way.

## 3. Why not copy HiCo-Nav's arrangement

`[code]` via `zongzhe_docs/HICO_NAV_CLASS_DIAGRAM.md`, which read upstream source at commit
`ffc1517`. Upstream stores each edge twice, as two independent `Set[int]` fields owned by two
different classes: `Keyframe.objects_3d` (`map.py:871`) and `Object3D.observers` (`map.py:798`,
`map_elements.py:172`). There is no edge object and no graph library.

**The access pattern genuinely does not need a graph, and that is the honest defence of the
upstream design.** Nothing traverses it. Every query is one hop. There is no pathfinding, no
connected components, no matching. A pair of integer sets is the right shape, and pulling in
`networkx` would add a dependency we would use a fraction of. We are not rejecting the shape.

We are rejecting three consequences of storing the edge twice.

**No single source of truth (R2, R5).** Every mutation has to touch both sets, and there is no third
record to check them against. Two divergence paths were suspected here in September. **T6.1 read
the source on 2026-10-05 and neither occurs in upstream as written** `[code]`:

- *Anchor eviction is clean.* `delete_keyframe` (`map.py:420-431`) walks the keyframe's
  `objects_3d` and discards the frame id from each object's `observers` before dropping the
  keyframe. Both sides stay in step.
- *No anchor can point at an absorbed id.* The only merge call (`map.py:493`) folds a sighting from
  the current frame into an existing object (`Object3D.merge`, `map_elements.py:139-176`). The
  sighting's own id was never added to any keyframe: the keyframe is built afterwards, from the ids
  of the existing objects it touched (`map.py:871-881`). Objects are never deleted or merged with
  each other anywhere in the code.
- *Even a stale id could not make pruning infeasible.* The pruning program counts each object's
  degree from the keyframe side (`keyframe_to_objs`, `map.py:1002-1007`), not from `observers`, and
  clamps it with `min(r, len(Ks))` (`map.py:952`). One reader, `find_target`, also intersects
  `observers` with the live keyframes before use (`map.py:302`).

So upstream's two sets are kept consistent by careful code, not by structure. The remaining
argument is the weaker structural one: nothing checks the pair, so a future write site could break
it silently. That is a reason for R5 (self-check), not evidence of a bug. The prototype's
`TwoSetFailureModes` tests still show what the layout permits, and claim nothing about upstream.
`merge_objects(surviving, absorbed)` in the prototype has no upstream counterpart. S11 needs only
`observe`. Section 3's case for our own structure now rests on R4 (edge payload), R5 and R7.

**Nowhere to put edge information (R4).** An edge is a bare membership fact. There is no place for
the bounding box within that anchor, the occluded fraction, the pixel area, the confidence of that
sighting, or its timestamp. Yet "which stored view best shows this object" is a property of the
edge, not of either endpoint, and it is exactly what T6.8 and M8 will ask.

**Redundancy set to 1 (R6).** Covered in section 6.

## 4. The finding that matters most for M6's stated risk

`[code]` Upstream's merge test scores a candidate against an existing entry as

```
agg_sim = (1 + phys_bias) * spatial_sim + (1 - phys_bias) * visual_sim
```

with `phys_bias = 0.5` and acceptance threshold `sim_threshold = 0.6`, both from `cfg/hm3d.yaml`.
That is `1.5 * spatial + 0.5 * visual`. The weights sum to 2, so it is not the convex combination
the paper's formula suggests (`hico-nav/PAPER_REPORT.md` §4.4).

`[code]` Both similarities lie in `[0,1]`: the spatial term is the fraction of the new sighting's
points with a stored point within 2.5 cm, and 0 when the 3D boxes do not overlap
(`pointcloud.py:704-714`), and the visual term is a cosine (`map_utils.py:372`). A match needs a
score strictly above the threshold (`map_utils.py:396`). So the visual term contributes at most 0.5,
which is below the 0.6 threshold. Confirmed by T6.1 on 2026-10-05. **Two sightings with no point-cloud overlap can never be merged, however
certain the appearance match is.** Appearance cannot outvote geometry; it can only refine it.

**Why this lands squarely on M6.** `PROJECT_PLAN.md:502-506` names the risk plainly: the merge test
depends on camera pose accuracy, our pose comes from 2D localisation with no reliable pitch or roll,
and the mitigation is to measure the duplication rate and decide from data whether a better pose
source is needed.

If we inherit these weights, that mitigation has only one lever. Pose error displaces the lifted
point cloud, the clouds stop overlapping, and no amount of appearance similarity can recover the
merge. Duplication rate becomes a pure function of pose quality, and the only fix is the expensive
one.

`[inferred]` Three cheaper options exist, and T6.4 should choose between them on recorded data
rather than inherit a number:

1. **Rebalance.** Make it a real convex combination and set the threshold so a strong appearance
   match plus weak overlap can merge. Cheapest, and it trades duplicates for false merges, which are
   worse. Needs measurement.
2. **A second, stricter appearance-only path.** Merge on very high CLIP similarity and plausible
   proximity, even with no overlap. Keeps the strict geometric path as the common case.
3. **Keep the geometry-dominant rule and accept duplicates**, then deduplicate at query time. Safest
   for M6's acceptance test, which asks that a query return the right object, and it defers the
   problem to T6.8.

**This document does not choose.** It records that the choice exists, that it is not what upstream
does, and that measuring the duplication rate (which M6 already plans) is what settles it.

## 5. The design

One decision does the work: **the edge is stored once, and both directions are derived from it.**

```
_edges       : Dict[(anchor_id, object_id), Sighting]     the source of truth
_by_anchor   : Dict[anchor_id, Set[object_id]]            private cache
_by_object   : Dict[object_id, Set[anchor_id]]            private cache
```

The two direction maps are private and only the mutating methods touch them. A caller cannot update
one direction and forget the other, because a caller cannot reach them. That is the whole difference
from the upstream arrangement, and it is what makes R2, R3 and R5 achievable.

`Sighting` is the per-edge payload that R4 needs: detection count, mask pixels, confidence, occluded
fraction. What exactly it carries is a T6.3 decision once we see recorded data. That there is a
place for it is the design commitment.

### Interface

| Method | Purpose | Requirement |
|---|---|---|
| `observe(anchor, obj, sighting)` | record an edge, fusing the payload on repeat sightings | R1 |
| `remove_anchor(anchor)` | evict an anchor and every edge touching it, atomically | R3 |
| `remove_object(obj)` | the mirror | R2 |
| `merge_objects(surviving, absorbed)` | move every edge, fuse colliding payloads, drop the absorbed id | R2 |
| `anchors_of(obj)` · `objects_of(anchor)` · `degree(obj)` | the one-hop queries, which is all the pipeline asks | R1 |
| `best_anchor_for(obj)` | pick the stored view that shows the object best | R4 |
| `coverage_requirements(kappa)` | `r_j = min(kappa, degree(j))` for every object | R6 |
| `prune(kappa, cost, apply)` | weighted set multicover, returns kept and evicted | R6 |
| `incidence()` | the anchor-to-objects mapping an external solver wants | R6 |
| `check_invariants()` | list of violations, empty when consistent | R5 |

`check_invariants` is the part upstream cannot offer: with two hand-kept sets there is no third
record to compare against. With a stored edge there is. It costs under a millisecond at realistic
scale (section 7), so it can run after every prune in debug builds. That converts the whole failure
class in section 3 from "silently wrong numbers" into "an assertion fires".

### What this deliberately does not do

No traversal, no path queries, no components, no persistence, no thread safety. Each is absent
because nothing in the M6 task tree needs it. Persistence in particular is worth naming: `[code]`
upstream has none at all (`Map.save_to_disk` is called but never defined), and M6 is explicitly an
**offline** milestone built from recorded data, so a rebuild-from-recording path covers it. If M7
needs a graph that survives a restart, that is a new requirement and a new section here.

## 6. Pruning, and the redundancy parameter

`[paper]` Anchor pruning is a weighted set multicover solved by integer linear programming
(`hico-nav/PAPER_REPORT.md` §4.4):

```
minimise   sum_i  c_i * x_i                          over x_i in {0,1}
subject to sum over {i : (a_i,o_j) in E} x_i  >=  r_j     for every object o_j
where      r_j = min(kappa, |{a_i : (a_i,o_j) in E}|)
```

Read `x_i = 1` as "keep anchor i". The last line says: keep `kappa` anchors for every object, unless
it was seen by fewer than `kappa`, in which case keep all it has. `kappa` is one global setting
chosen by us. `r_j` is derived per object and changes on every update.

**The clamp exists for feasibility.** Without it, an object seen once would demand `kappa` anchors
from a pool of one, and in integer programming an impossible constraint makes the whole program
infeasible rather than failing for that object alone. One briefly-seen object would break pruning
for the entire graph.

**Multicover against set cover** differs only in the right-hand side: set cover is `r_j = 1`
everywhere. Both are NP-hard, greedy approximates either within `ln n`, so the choice is about what
we keep, not about tractability.

**Upstream sets `r = 1`** `[code]`, which collapses the multicover to set cover. The `cost` argument
survives, so the weighted axis is kept and the multi axis is dropped.

`[inferred]` What that gives up is specific. The consumer of anchors is a vision-language model, and
it consumes the **images**. Under set cover an object is retained by exactly one image, and if that
view is oblique or half occluded, the entry exists but is useless for any visual question. `kappa > 1`
buys viewpoint redundancy, which is the property the pruning step existed to guarantee.

Measured on the reference implementation at 500 anchors and 300 objects, `kappa = 1` keeps 54
anchors and `kappa = 3` keeps 141. That is 2.6 times the memory while still evicting 72 percent.
**The redundancy is affordable, and the M6 default should be a decision we write down rather than a
number we inherit.** See D-MG1 in section 8.

**Greedy now, a solver later.** The reference implementation uses greedy, repeatedly taking the
anchor with the best unmet-demand-per-unit-cost. No dependency, satisfies R7, and
`hico-nav/PAPER_REPORT.md` §6.5 lists solver dependencies as an open blocker while T6.1 is the task
that settles licensing. `PROJECT_PLAN.md:997` already has S3, "graph pruning with a real solver", as
Zongzhe's stretch goal. **This design makes S3 a drop-in**: an exact solver replaces the body of
`prune` without changing its signature, and the greedy result becomes the baseline it is measured
against.

## 7. Reference implementation and its evidence

[`../memory_graph/anchor_object_graph.py`](../memory_graph/anchor_object_graph.py), about 230
lines, stdlib only. Moved there from `docs/zongzhe_docs/prototypes/` on 2026-10-05 (T6.3a). Its
tests run in the bench at L0. `OWNED_PREFIXES` no longer exists: since 2026-09-22 everything outside
a `vendor/` folder counts as ours (`is_owned` in `bench/_common.py`), so the move needed no bench
edit. The top-level `memory_graph/` folder is a **provisional** answer to D-MG4, chosen so T6.3a
could proceed. The team may still move it, and **`memory_graph` is a temporary name**, to be
changed when the code is integrated into the navigation module (Zongzhe, 2026-10-05).

```bash
python3 -m unittest -v memory_graph.tests.test_anchor_object_graph     # from the repo root
```

16 checks, all passing on 2026-09-21 on Zongzhe's Mac. Three groups:

- `TwoSetFailureModes` writes out the upstream two-set arrangement and demonstrates all three
  consequences from section 3, including an inflated degree demanding three anchors when one exists.
  It demonstrates what the arrangement permits. It is not upstream code and proves nothing about it.
- `GraphStaysConsistent` runs the same sequences against the design, including 3000 randomised mixed
  operations asserting consistency throughout.
- `CoverageAndPruning` checks the clamp, that `kappa = 1` reduces to set cover, that pruning meets
  every requirement at several `kappa`, and that costs steer which anchors survive.

Measured at 500 anchors, 300 objects, 3597 edges, roughly a ten-minute drive at the paper's observed
anchor rate of one every one to two seconds:

| Operation | Time | Result |
|---|---|---|
| build | 5.9 ms | |
| `check_invariants` | 0.8 ms | 0 violations |
| `prune(kappa=1)` | 13.7 ms | keeps 54 of 500 |
| `prune(kappa=3)` | 31.4 ms | keeps 141 of 500 |

The full reasoning behind these findings, including what was and was not verified against upstream
source, is in [`zongzhe_docs/CMG_GRAPH_STRUCTURE.md`](zongzhe_docs/CMG_GRAPH_STRUCTURE.md).

## 8. Open decisions

Recorded here in the style of `PROJECT_PLAN.md` §1.1. None blocks anything before M6 opens.

| # | Question | Why it matters | Settle by |
|---|---|---|---|
| D-MG1 | What is `kappa`, the anchors kept per object? | Section 6. Upstream's effective 1 gives up viewpoint redundancy; 3 costs 2.6x the anchors and still evicts most | T6.4, on recorded data from T6.2 |
| D-MG2 | Does the merge test stay geometry-dominant? | Section 4. With upstream's weights, appearance cannot rescue a pose error, so M6's duplication-rate mitigation has one expensive lever | T6.4, measured |
| D-MG3 | Greedy, or a solver in M6 rather than as S3? | **Decided 2026-10-05 (Zongzhe): greedy in M6, the solver stays stretch goal S3.** T6.4f prunes with the prototype's greedy multicover. Reasons: a solver adds a dependency that breaks R7 and the stdlib-only bench tests, it needs a time limit (upstream sets none) and so a greedy fallback anyway, and its benefit over greedy is unmeasured. Licences do not block it: T6.1 found upstream uses PuLP (MIT) with CBC (EPL-2.0). Reopen if the recorded drive (T6.4) shows greedy keeping noticeably more anchors than needed. S3 then drops in behind `prune()` | Settled |
| D-MG4 | Where does the code live once it is real? | It is not a ROS node, it is a library used by one. Provisionally a top-level `memory_graph/` package since 2026-10-05 (T6.3a). The name is temporary too: it will change when the code is integrated into the navigation module (Zongzhe, 2026-10-05). No bench edit is needed wherever it goes, since `is_owned` counts everything outside `vendor/` | T6.3, team to confirm |
| D-MG5 | Does the graph need to survive a restart? | M6 is offline and rebuilds from recordings, so no. M7 may differ. Note the HiCo-Nav agent guide (§9, its milestone M6) does require save and load with `load(save(g)) == g`, since the reference has none | M7 planning |
| D-MG6 | Which model detects objects and makes their masks (S1, S4)? | **Decided 2026-10-07 (Zongzhe): SAM 3**, not upstream's YOLO-World plus MobileSAM. It is already in the repo and on the lab box (`aria/aria_app/services/object_recognition/sam3_model.py`, `grasp/segmentation/sam3_ros_node.py`), so no new model or licence. **Known consequence** `[code]`: that wrapper takes one text prompt per call (`process_text_prompt(image, prompt)`), while upstream's detector takes a whole class list at once. T6.3c has to decide how the vocabulary maps to prompts and measure the cost per photo. **To change it later:** S2 onward only needs a `Detections` object with boxes, labels, confidences and masks (`memory_graph/stage_types.py`), so another detector is a new adapter, not a rewrite | Settled, revisit if T6.3c's cost per photo is too high |
| D-MG7 | Which model gives the image feature (S6)? | **Decided 2026-10-07 (Zongzhe): follow upstream**, open_clip `ViT-B-32` with the `laion2b_s34b_b79k` weights (`map_utils.py:95` upstream). Adds open_clip and torch as dependencies of the feature step only. **Built 2026-10-07** `[code]`: `memory_graph/clip_encoder.py`, in the same `.venv` as SAM 3 (the lock gained one package, torch and numpy did not move). It encodes images (`encode`) and text (`encode_text`) into the same 512-number space. `memory_graph/tests/test_clip_encoder.py` has one test class for each of upstream's four uses of CLIP: object features, matching, task relevance, frontier scoring. **Precision decided 2026-10-07 (Zongzhe): follow upstream, float16 on a GPU.** Upstream wraps both the image and the text encoder in `torch.amp.autocast("cuda")` (`map/map_utils.py:77` and `:85` at `ffc1517`) `[code]`, which runs most of the model in float16. `OpenClipEncoder._precision` does the same for both `encode` and `encode_text`. On a CPU there is no autocast and the model runs in float32, as upstream. The vectors handed back are stored as float32 either way. **Why this matters next to SAM 3:** SAM 3's wrapper switches bfloat16 on in its thread and never switches it off (`aria/aria_app/services/object_recognition/sam3_model.py:63`) `[code]`, so a model called later in that thread would run in bfloat16. Asking for float16 explicitly overrides that for the CLIP call only, so a vector does not depend on whether SAM 3 loaded first. SAM 3 itself still runs in bfloat16. **History:** float32 was chosen first on 2026-10-07, on the wrong belief that upstream ran CLIP in float32. That was checked against the source the same day and reversed. **Consequence:** a graph built on a GPU (float16) and one built on a CPU (float32) hold slightly different vectors for the same crop. **Not yet checked** `[unverified]`: the GPU path has never run, so far only the CPU path is tested, and the size of the float16 against float32 difference in similarity scores has not been measured. **To change it later:** edit `_precision` in `memory_graph/clip_encoder.py`, then rebuild any stored graph. **To change it later:** `memory_graph/image_feature.py` takes any object with an `encode` method, so another model is a new encoder class. Vectors from different models cannot be mixed in one graph | Settled |
| D-MG8 | May two sightings from one photo merge into the same object (S10)? | **Decided 2026-10-07 (Zongzhe): yes, greedy matching as upstream** (`map_utils.py:377`). Each sighting takes its best-scoring object. **To change it later:** set `association_mode: one_to_one` in the config. Both rules are implemented and tested in `memory_graph/association.py`. T6.4 can compare them on the recorded drive | Settled, T6.4 may revisit with data |
| D-MG9 | Loop closure: are object points stored in world coordinates, or relative to the anchor that saw them? | **Decided 2026-10-07 (Zongzhe): world coordinates, as upstream.** A point is fixed in the map frame when it is added. Decided without waiting for T5.7, for five reasons. (1) Neither pose source in the repo hands back corrected poses for old photos, so anchor-relative storage would have nothing to use. `nav/robot_navigation/launch/navigation.launch.py:77` starts Nav2's AMCL, which keeps no past poses `[code]`. `nav/robot_slam/launch/slam_localization.launch.py:143` starts SLAM Toolbox in localisation mode, which gives us only the current `map` to `odom` correction `[inferred]`. (2) Waiting is circular: T5.7 measures the duplicate rate in the graph, and T6.4c is part of that graph. (3) M6 is offline, so a pose fix means rerunning the recording, not migrating stored data. (4) The built stages already work in one shared frame (`memory_graph/geometry.py`, `memory_graph/association.py`). (5) It unblocks T6.4c and the six tasks behind it. **Known risk:** if a past pose was wrong, the object stays in the wrong place, and a later sighting may not overlap it, which makes a duplicate. **Kept open on purpose:** T6.4c records on each sighting which anchor it came from, and T6.4d stores each anchor's pose, depth and intrinsics. An object can then be rebuilt from its anchors if poses are corrected. **Reopen if** T5.7 picks full SLAM in mapping mode running during the drive, where a loop closure moves every past pose, **or** the T6.4 run shows duplicates of one object, seen at different times, that sit a consistent offset apart. That pattern is drift and no merge threshold fixes it. **To change it later:** store each sighting's points in its anchor's camera frame and transform them to the map frame when read. The change sits behind the graph's `observe` and `merge_objects`. The overlap score and the k-d tree prefilter in `memory_graph/association.py` would then read transformed points, or a world-frame cache that is rebuilt after each correction. Any stored graph has to be rebuilt. **Not yet checked** `[unverified]`: whether loop closure is on in SLAM Toolbox's localisation mode here. `nav/robot_slam/config/slam_toolbox_localization.yaml` does not set `do_loop_closing`, so the built-in default applies. Which of the two pose sources the lab runs is also not known | Settled, T5.7 or T6.4 may reopen with data |

**Claims checked against source (T6.1, 2026-10-05).** Section 3's two divergence paths turned out
not to occur upstream, and section 4's arithmetic is confirmed. Both are now tagged `[code]` with
line citations at `ffc1517`. D-MG3's licence half is settled too: upstream prunes with PuLP (MIT)
driving CBC (EPL-2.0), both acceptable (`map.py:18`, `map.py:956`). It calls the solver with
`r = 1` written at the call site and no time limit (`map.py:1007`, default `time_limit=None` at
`map.py:915`).

**What the prototype does not cover, checked against the reference docs on 2026-10-05.** It stores
edges only. Object and anchor data (points, boxes, labels, images, the next object id) need their
own store (T6.4c, T6.4d). An object that loses every anchor drops out of `objects()`, while the
reference never deletes objects, so T6.4c must not treat `objects()` as the list of all objects.
Pruning cannot cause this, since coverage keeps every object at least one anchor. Built that way on 2026-10-07 `[code]`: `ObjectStore` in `memory_graph/object_store.py` keeps its own entries, and a test removes an entry's last anchor to check the entry stays. The task index
with re-indexing on label change, the blacklist and the task score belong to T6.7a and T6.8a. On
3,000 random graphs per kappa, `prune` met every coverage requirement, and with kappa = 1 never kept
an anchor whose objects are a subset of another kept anchor's, which is the reference's S13 test.

## 9. How this maps onto the M6 task tree

| Task | What this document gives it |
|---|---|
| T6.1 read upstream, settle solvers | Three specific claims to confirm (sections 3, 4), and D-MG3. Done 2026-10-05 |
| T6.3 build object entries | The structure they go into, and D-MG4 |
| T6.4 the merge test | R2, `merge_objects`, and section 4's input to the similarity decision |
| T6.5 two-stage trigger | Not addressed. The trigger decides what becomes an anchor; this holds them once chosen |
| T6.8 query the graph | R1, R4, `best_anchor_for` |
| S3 pruning with a real solver | Section 6: a drop-in replacement for `prune`, with greedy as the baseline |
| M8 gaze picks the instance | R4 is the edge-level information the gaze feature is compared against |

Since 2026-09-29 these tasks are split into sub-tasks in `task-tree.html`, following the stages in
HiCo-Nav's `docs/cmg_construction_pipeline.md`. The parts this document governs: **T6.3a** moves the
prototype into the source tree (D-MG4), **T6.4c** and **T6.4d** write through `merge_objects`,
`observe` and `check_invariants`, **T6.4f** is the greedy `prune` and settles `kappa` (D-MG1), and
**T6.4** settles D-MG2 on the recorded drive.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-21 | Claude (Opus 5) + Zongzhe | Created. Specifies the anchor-object graph for M6 ahead of T6.3: requirements traced to the M6 acceptance text, the case against copying upstream's two-set edge storage, the merge-threshold finding that bears on M6's stated pose risk, the interface, the multicover pruning and its redundancy parameter, and five open decisions. Proposed only, nothing implemented in `src/`. No task changed state, so `next-steps-map.html` was not edited. |
| 2026-09-29 | Claude (Opus 5.5) + Zongzhe | §9: noted the M6 split into sub-tasks and which of them carry D-MG1, D-MG2 and D-MG4. No design change. |
| 2026-10-05 | Claude (Opus 5.5) + Zongzhe | §7 and D-MG4: the prototype moved to `memory_graph/` (T6.3a), with the S2 to S10 stage code beside it. The folder and its name are provisional: D-MG4 is open and the name changes on integration into the navigation module. Replaced the stale `OWNED_PREFIXES` references with the `is_owned` rule. No design change. |
| 2026-10-05 | Claude (Opus 5.5) + Zongzhe | §3: counter-evidence from the HiCo-Nav reference docs against both inferred divergence paths, tagged `[unverified]` pending T6.1. §8: D-MG5 notes the reference docs ask for save and load. Added what the prototype does not cover and the S13 subset check result. |
| 2026-10-05 | Claude (Opus 5.5) + Zongzhe | T6.1 checked §3 and §4 against upstream source at `ffc1517`. §3: both divergence paths do not occur upstream, replaced the counter-evidence note with `[code]` findings, and the case now rests on R4, R5, R7. §4: arithmetic confirmed, retagged `[code]`. §8: D-MG3 licence half settled (PuLP MIT, CBC EPL-2.0). |
| 2026-10-05 | Claude (Opus 5.5) + Zongzhe | §8: D-MG3 settled. Greedy pruning in M6, the solver stays stretch goal S3, with the reasons and the condition for reopening. |
| 2026-10-07 | Claude (Opus 5.5) + Zongzhe | §8: recorded three decisions with how to change each later. D-MG6 detector is SAM 3, D-MG7 image feature follows upstream (open_clip ViT-B-32), D-MG8 matching is greedy. D-MG9 (loop closure) added as open. |
| 2026-10-07 | Claude (Opus 5.5) + Zongzhe | §8 D-MG7: the encoder is built (`clip_encoder.py`) and tested with the real model on a Mac CPU. Not yet run on the lab box GPU or on real photos, so T6.3f stays open. |
| 2026-10-07 | Claude (Opus 5.5) + Zongzhe | §8 D-MG7: recorded the precision decision. CLIP runs in float32, not the bfloat16 that SAM 3 switches on. Corrected an earlier line that called SAM 3's setting process-wide: it is per thread. |
| 2026-10-07 | Claude (Opus 5.5) + Zongzhe | §8 D-MG7: precision decision reversed to follow upstream, float16 on a GPU. The float32 note rested on an unchecked claim that upstream used float32. Upstream uses `torch.amp.autocast("cuda")` (`map/map_utils.py:77`, `:85`). Also recorded: the encoder gained `encode_text`, and its tests are grouped by upstream's four uses of CLIP. |
| 2026-10-07 | Claude (Opus 5.5) + Zongzhe | §8: D-MG9 settled. Object points are stored in world coordinates, as upstream, decided without waiting for T5.7. The row records the reasons, the two results that would reopen it, and how to switch to anchor-relative storage. The cited nav files were read on the Mac and on the lab box (`~/rcp-Gappler` at `3dde592`). T6.4c is no longer blocked. |
| 2026-10-07 | Claude (Opus 5.5) + Zongzhe | T6.4c built: `memory_graph/object_store.py` holds the object entries next to the graph and applies S10's matches (S11). §7 notes that the store keeps entries the graph has dropped. No design change. |
