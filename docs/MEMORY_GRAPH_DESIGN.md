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

**No single source of truth (R2, R3, R5).** `[inferred]` Every mutation has to touch both sets, so
any path that touches one is a silent divergence, and there is no third record to check them
against. Two such paths are visible from the write sites above: anchor eviction, where the object
side may keep ids for anchors that are gone, and object merge, where anchors may keep pointing at
the absorbed id. Neither is confirmed against upstream source, and the point here is not to accuse
upstream of a bug. It is that the arrangement has no way to rule one out.

Stale values here are integers, and a stale integer does not announce itself. Some code never
dereferences it, it counts: the pruning requirement `r_j = min(kappa, degree)` is `len(observers)`.
A ghost id inflates the degree, so the solver can be asked for more anchors than exist. That is an
infeasible program rather than a slightly wrong answer.

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

`[inferred]` If both similarities lie in `[0,1]`, the visual term contributes at most 0.5, which is
below the 0.6 threshold. **Two sightings with no point-cloud overlap can never be merged, however
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

[`zongzhe_docs/prototypes/anchor_object_graph.py`](zongzhe_docs/prototypes/anchor_object_graph.py),
about 230 lines, stdlib only. It sits under `docs/` and so is outside `OWNED_PREFIXES` in
`bench/_common.py`: it cannot affect the bench until someone moves it deliberately, which is correct
for a prototype. When T6.3 starts, the code moves into `src/` and that prefix list gets updated.

```bash
cd docs/zongzhe_docs/prototypes && python3 -m unittest -v test_anchor_object_graph
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
| D-MG3 | Greedy, or a solver in M6 rather than as S3? | Greedy has no dependency and satisfies R7. A solver needs T6.1's licence check | T6.1 |
| D-MG4 | Where does the code live once it is real? | It is not a ROS node, it is a library used by one. `src/` needs a home for it, and `OWNED_PREFIXES` needs the entry | T6.3 |
| D-MG5 | Does the graph need to survive a restart? | M6 is offline and rebuilds from recordings, so no. M7 may differ | M7 planning |

**Unverified claims carried by this document.** Section 3's two divergence paths and section 4's
threshold arithmetic are `[inferred]` from a second-hand reading of upstream. T6.1 is "read the
upstream HiCo-Nav code" and is the natural place to confirm or kill them. If they turn out wrong,
section 3's case for our own structure weakens to R4 and R5 alone, which is still sufficient.

## 9. How this maps onto the M6 task tree

| Task | What this document gives it |
|---|---|
| T6.1 read upstream, settle solvers | Three specific claims to confirm (sections 3, 4), and D-MG3 |
| T6.3 build object entries | The structure they go into, and D-MG4 |
| T6.4 the merge test | R2, `merge_objects`, and section 4's input to the similarity decision |
| T6.5 two-stage trigger | Not addressed. The trigger decides what becomes an anchor; this holds them once chosen |
| T6.8 query the graph | R1, R4, `best_anchor_for` |
| S3 pruning with a real solver | Section 6: a drop-in replacement for `prune`, with greedy as the baseline |
| M8 gaze picks the instance | R4 is the edge-level information the gaze feature is compared against |

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-21 | Claude (Opus 5) + Zongzhe | Created. Specifies the anchor-object graph for M6 ahead of T6.3: requirements traced to the M6 acceptance text, the case against copying upstream's two-set edge storage, the merge-threshold finding that bears on M6's stated pose risk, the interface, the multicover pruning and its redundancy parameter, and five open decisions. Proposed only, nothing implemented in `src/`. No task changed state, so `next-steps-map.html` was not edited. |
