# The Cognitive Memory Graph is not stored as a graph, and what to do about it

**Session 2026-09-21. Branch `dev`. Reading session, no existing code changed.**

Follow-on from [`HICO_NAV_CLASS_DIAGRAM.md`](HICO_NAV_CLASS_DIAGRAM.md), which mapped HiCo-Nav's
`map/` package at commit `ffc1517`. This document records what that mapping implies, and proposes a
replacement data structure with a working prototype.

## The short answer

HiCo-Nav's memory graph has no graph in it. Each edge is stored twice, as two independent sets of
integers owned by two different classes, kept in agreement by hand across three write sites. That
arrangement has no way to store anything about an edge, and no way to check itself. Separately, the
anchor pruning step is implemented with its redundancy parameter set to 1, which turns the paper's
multicover into ordinary set cover and gives up the property the step existed to protect.

**This document is the session evidence. The design it fed is now a global doc,**
[`../MEMORY_GRAPH_DESIGN.md`](../MEMORY_GRAPH_DESIGN.md), specified against M6's acceptance
test and linked from `PROJECT_PLAN.md` at M6, T6.1 and S3. Read that one to decide anything.
Read this one for how the findings were reached and what was not verified.

A replacement is in [`prototypes/anchor_object_graph.py`](prototypes/anchor_object_graph.py), about
230 lines of stdlib Python, with 16 passing checks. It stores each edge once, makes eviction and
merge atomic, gives edges somewhere to carry a payload, and can verify its own consistency.

## Where these claims come from

I did not read HiCo-Nav's source in this session. It is not in this repository, and the
`../map/...` links in `HICO_NAV_CLASS_DIAGRAM.md` point into an external checkout.

- `[code]` here means the claim is taken from `HICO_NAV_CLASS_DIAGRAM.md`, which did read the
  source at `ffc1517` and cites lines. It is one step removed from the source.
- `[paper]` means it is from [`../hico-nav/PAPER_REPORT.md`](../hico-nav/PAPER_REPORT.md), which
  read the paper.
- `[inferred]` means it is reasoning from those two, and nothing has confirmed it.
- Numbers attributed to the prototype were measured on Zongzhe's Mac on 2026-09-21 and can be
  reproduced with the command in section 5.

Section 3 is the part most in need of checking against real source. It is reasoning about what an
arrangement permits, not a report of a bug anyone has seen.

---

## 1. What the pruning formula actually says

`[paper]` Anchor pruning is posed as a weighted set multicover and solved by integer linear
programming ([`../hico-nav/PAPER_REPORT.md`](../hico-nav/PAPER_REPORT.md) section 4.4):

```
minimise   sum_i  c_i * x_i                     over x_i in {0,1}
subject to sum over {i : (a_i,o_j) in E} x_i  >=  r_j      for every object o_j
where      r_j = min(kappa, |{a_i : (a_i,o_j) in E}|)
```

Read `x_i = 1` as "keep anchor i". The notation on the last line trips people up because the two
kinds of vertical bar mean different things in the same expression:

| Piece | Reads as |
|---|---|
| `(a_i, o_j) in E` | anchor `a_i` observed object `o_j`, so an edge exists |
| `{ a_i : ... }` | the set of all anchors `a_i` **such that** the above holds |
| `\| ... \|` | **how many** are in that set. This is a count, not an absolute value. |
| `min(kappa, ...)` | the smaller of `kappa` and that count |

In words: **keep `kappa` anchors for every object, unless the object was only ever seen by fewer
than `kappa` anchors, in which case keep all the ones it has.**

`kappa` is one global setting. `r_j` is worked out separately for each object, which is what the
subscript is for. `kappa` is a hyperparameter, meaning somebody chooses it. `r_j` is not, it is
derived from `kappa` and the graph's current shape and changes on every update.

### Why the clamp is there

Without `min`, an object seen exactly once would demand `kappa` anchors from a pool of one. In
integer programming an impossible constraint does not fail quietly for that one object, it makes the
**whole program** infeasible and the solver returns nothing. One briefly glimpsed mug would break
pruning for the entire graph.

The clamp makes every constraint satisfiable by construction, because keeping all of an object's
anchors is always allowed. `[inferred]` That is what lets the solver run unattended every 10 updates
with no branch for "no solution".

### Multicover against set cover

The only structural difference is the right hand side of the constraint.

| | Set cover | Weighted set multicover |
|---|---|---|
| Constraint | `sum x_i >= 1` per object | `sum x_i >= r_j`, varying per object |
| Objective | `min sum c_i x_i` | the same |
| Meaning | every object survives at least once | every object survives from up to `kappa` different anchors |

Set cover is the case `r_j = 1` for everything. Both are NP-hard and greedy approximates either
within `ln n`, so the choice is about what you want to keep, not about whether it can be solved.

"Weighted" and "multi" are independent. Weighted refers to the per-anchor costs `c_i`. `[paper]`
Uniform `c_i = 1` reduces the objective to minimising anchor count, and `c_i` can otherwise encode
anchor quality or viewpoint diversity.

## 2. What setting the redundancy to 1 gives up

`[code]` The implementation calls `filter_keyframe_with_ipl(object_ids, keyframe_to_objs, cost, r)`
with `r = 1`, so `r_j = min(1, degree) = 1` for every object. The clamp never binds and the
multicover is set cover. The `cost` argument survives, so the weighted axis is kept and the
multi axis is dropped.

`[inferred]` The thing being given up is specific. The consumer of these anchors is a vision
language model, and it consumes the anchor **images**. Under set cover an object is retained by
exactly one image. If that one view is oblique, distant, or half occluded, the object node still
exists in the graph but is useless for any visual question. Asking "is there a cup on that table"
needs a view that shows the tabletop. `kappa > 1` buys viewpoint redundancy, which is the property
the ILP was introduced to guarantee in the first place.

The cost of buying it back is smaller than it sounds. On a synthetic graph of 500 anchors and 300
objects, the prototype's greedy solver keeps 54 anchors at `kappa = 1` and 141 at `kappa = 3`. That
is 2.6 times the memory, while still evicting 72 percent of anchors.

**Open question.** `[unverified]` The config values traced in `HICO_NAV_CLASS_DIAGRAM.md` are
`sim_threshold`, `phys_bias` and `use_ilp_keyframe_pruning`, all from `cfg/hm3d.yaml`. `r` is not
among them, which suggests it is a literal at the call site rather than a setting anyone can change.
Worth confirming, because the difference matters: a value in a config file is a decision, a literal
`1` in a function call is often nobody's decision at all.

## 3. The graph edges are stored twice, with nothing owning the pair

`[code]` There is no `Edge` class and no graph library. The edge "anchor `a` observed object `o`"
lives in two places:

| Direction | Field | Written at |
|---|---|---|
| anchor to objects | `Keyframe.objects_3d : Set[int]` | `map.py:871`, construction |
| object to anchors | `Object3D.observers : Set[int]` | `map.py:798` insert, `map_elements.py:172` merge |

`delete_keyframe` (`map.py:420`) is recorded as the only place that unwinds an edge from the anchor
side.

**The access pattern does not need a graph, and that is the honest defence of this design.** Nothing
traverses it. Every query is one hop: which objects did this anchor see, which anchors saw this
object. There is no pathfinding, no connected components, no matching. The ILP wants an incidence
list and nothing more. A pair of integer sets is the right shape for that, and pulling in `networkx`
would be worse.

The problems are the two things the shape cannot do.

### 3a. There is no third thing to check the two sets against

`[inferred]` With a single stored edge, removal updates one place. With two sets, every mutation has
to touch both, and any path that touches one is a silent divergence. Two such paths are visible from
the write sites above. Neither is confirmed against source.

- **Anchor eviction.** Pruning deletes anchors constantly. Unless `delete_keyframe` also strips the
  anchor id from every `Object3D.observers` holding it, `observers` accumulates ids for keyframes
  that no longer exist.
- **Object merge.** `Object3D.merge` unions `observers` onto the surviving node. Nothing in the
  write sites above rewrites the anchor side, so anchors that saw the absorbed object may keep
  pointing at an object id that is gone.

`[inferred]` The reason this is worth caring about rather than shrugging at is that the stale value
is an integer, and a stale integer does not announce itself. A dead object reference raises or gets
collected. A dead id is indistinguishable from a live one until someone dereferences it, and some
code never dereferences, it counts:

```
r_j = min(kappa, |{a_i : (a_i, o_j) in E}|)
                  ^^^^^^^^^^^^^^^^^^^^^^ this is len(object.observers)
```

A ghost id inflates the degree, so `r_j` can be set higher than the number of anchors that actually
exist to satisfy it. That is not a slightly wrong answer, it is an infeasible program. The same set
feeds `TargetManager.compute_similarity_sum`.

This failure class is demonstrated in
[`prototypes/test_anchor_object_graph.py`](prototypes/test_anchor_object_graph.py), class
`TwoSetFailureModes`, which writes out the two-set arrangement and shows all three consequences.
That file demonstrates what the arrangement permits. It is not a copy of upstream code and proves
nothing about upstream.

### 3b. An edge cannot carry anything

`[inferred]` This is the ceiling that matters more in the long run. An edge here is a bare
membership fact. There is nowhere to record how **well** anchor `a` sees object `o`: the bounding
box within that anchor, the occluded fraction, the pixel area, the confidence of that particular
sighting, the timestamp.

Yet "which anchor gives the best view of this object" is the natural question when a vision language
model needs an image, and it is a property of the edge, not of either endpoint. The paper's `c_i` is
per anchor, so even the ILP's notion of quality is node level. If `kappa > 1` is ever restored, the
question of whether the retained views are **diverse** rather than three near duplicates is also an
edge property, with no slot to live in.

## 4. A related deduction about the merge rule

`[code]` Object association uses

```
agg_sim = (1 + phys_bias) * spatial_sim + (1 - phys_bias) * visual_sim
```

with `phys_bias = 0.5` and threshold `sim_threshold = 0.6`, both from `cfg/hm3d.yaml`. That is
`1.5 * spatial + 0.5 * visual`. The weights sum to 2, so this is not the convex combination the
paper's `s = lambda_1 * IoU + lambda_2 * CLIP` suggests.

`[inferred]` If both similarities lie in `[0,1]`, visual similarity alone contributes at most 0.5,
which is below the 0.6 threshold. **Two observations with no point cloud overlap can never be
merged, whatever CLIP says.** The consequence is that the same physical object approached from two
sides, with no overlapping points, becomes two nodes. There is no appearance based re-identification.

This assumption needs checking. `spatial_sim` comes from `compute_overlap_matrix_general`, and if it
is not normalised to `[0,1]` the arithmetic changes. `[code]` It is point cloud overlap, not the 3D
IoU the paper states.

## 5. The proposed structure

[`prototypes/anchor_object_graph.py`](prototypes/anchor_object_graph.py). Stdlib only, so it runs at
bench levels L0 to L2 with no ROS and no solver. Under `docs/`, so it is outside `OWNED_PREFIXES` in
`bench/_common.py` and cannot affect the bench until someone deliberately moves it.

```bash
cd docs/zongzhe_docs/prototypes && python3 -m unittest -v test_anchor_object_graph
```

16 checks, all passing as of 2026-09-21.

**The one design decision.** The edge dictionary `{(anchor_id, object_id): Sighting}` is the single
source of truth. The two direction indices are private caches that only the four mutating methods
touch. A caller cannot update one direction and forget the other, because a caller cannot reach the
indices at all.

| Method | What it is for |
|---|---|
| `observe(anchor, obj, sighting)` | record an edge, fusing the payload on repeat sightings |
| `remove_anchor(anchor)` | what pruning calls, atomic across both directions |
| `remove_object(obj)` | the mirror |
| `merge_objects(surviving, absorbed)` | moves every edge, fuses colliding payloads, then drops the absorbed id |
| `anchors_of` / `objects_of` / `degree` | the one-hop queries, which is all the pipeline ever asks |
| `best_anchor_for(obj)` | what edge attributes buy: pick the image that shows the object best |
| `coverage_requirements(kappa)` | `r_j = min(kappa, degree)` for every object, the clamp in one line |
| `prune(kappa, cost, apply)` | greedy weighted multicover, returns kept and evicted |
| `incidence()` | the `keyframe_to_objs` argument an external ILP wants |
| `check_invariants()` | returns a list of violations, empty when consistent |

Three points about that table.

**`check_invariants` is the part that does not exist upstream and cannot.** With two hand kept sets
there is no third record to check them against, so there is nothing to compare. With a stored edge
there is. A randomised check runs 3000 mixed operations and asserts consistency throughout.

**`prune` is greedy, not an ILP, on purpose.** Repeatedly take the anchor with the best unmet demand
per unit cost. Standard `ln n` approximation, no dependency. `[paper]`
[`../hico-nav/PAPER_REPORT.md`](../hico-nav/PAPER_REPORT.md) section 6.5 lists solver dependencies as
an open blocker, and the root `CLAUDE.md` says to prefer the portable option when the choice is
otherwise a wash. An exact PuLP path can replace the method body without changing the signature.

**`kappa` is a real argument with a default, not a literal at a call site.** If we decide on 1, that
should be a decision someone wrote down.

Measured at 500 anchors, 300 objects, 3597 edges, which is roughly a ten minute run at the paper's
observed rate of one anchor every one to two seconds:

| Operation | Time |
|---|---|
| build the whole graph | 5.9 ms |
| `check_invariants` | 0.8 ms |
| `prune(kappa=1)` | 13.7 ms, keeps 54 of 500 |
| `prune(kappa=3)` | 31.4 ms, keeps 141 of 500 |

`[inferred]` A consistency check costing under a millisecond at realistic scale can simply be run
after every prune in debug builds, which converts the entire class of bug in section 3a from
"silently wrong numbers" into "an assertion that fires".

## 6. What this means for Gappler

`[inferred]`

1. **Reimplementing this index is cheap and removes a bug class.** It is about 230 lines with no
   dependencies. Given that only the flat `object_dict` crosses HiCo-Nav's process boundary
   ([`HICO_NAV_CLASS_DIAGRAM.md`](HICO_NAV_CLASS_DIAGRAM.md) section 2), reimplementing the internals
   costs nothing in compatibility with anything.
2. **Decide `kappa` deliberately.** The measurements say redundancy is affordable. Setting it to 1
   because upstream did is not a reason.
3. **Edge attributes are the thing worth adding that upstream cannot.** "Which stored image best
   shows this object" is the question a VLM integration will ask constantly.
4. **This does not touch the open blockers.** The camera, FAST-LIVO2 and the extrinsic calibration
   in [`../hico-nav/PAPER_REPORT.md`](../hico-nav/PAPER_REPORT.md) section 6 are all still in front
   of any of this mattering. This is preparation, not progress against them.

## 7. Constants in this subsystem

`[code]` Collected because they are currently scattered across four sections of
`HICO_NAV_CLASS_DIAGRAM.md`, and anyone porting to a different sensor rig has to re-derive all of
them.

| Constant | Value | Controls | Where from |
|---|---|---|---|
| translation threshold | 1 m | anchor gate | `is_map_undate_needed`, `map.py:512` |
| rotation threshold | 45 degrees | anchor gate | `is_map_undate_needed`, `map.py:512` |
| `sim_threshold` | 0.6 | object merge acceptance | `cfg/hm3d.yaml` |
| `phys_bias` | 0.5 | spatial against visual weighting | `cfg/hm3d.yaml` |
| cleanup period | 10 updates | how often pruning runs | `periodic_cleanup_objects`, `map.py:964` |
| `kappa` / `r` | 1 | anchors retained per object | `[unverified]`, probably the call site |

## 8. For Dion

Three items, all in global docs, none acted on in this session because they rest on `[inferred]`
claims that want source confirmation first.

1. [`../hico-nav/PAPER_REPORT.md`](../hico-nav/PAPER_REPORT.md) section 4.4 states the paper's merge
   formula and ILP as though they were the implementation. Sections 2 and 4 above say the
   implementation differs on three counts: the merge weights are not convex, `spatial_sim` is
   overlap rather than 3D IoU, and the multicover runs with redundancy 1. A short "what the code
   actually does" subsection would stop the next reader inheriting the paper's version as fact.
2. The anchor gate's semantic arm is narrower in code than in the paper. `[code]` The paper fires on
   any new object, the code fires when a target or task relevant class appears. That makes the map
   task biased rather than a neutral scene memory, which bears on the scoping question in
   `../NEXT_STEPS.md` section 1.3.
3. Nothing here is a task in `../NEXT_STEPS.md` or `../PROJECT_PLAN.md` yet, so nothing was marked
   done and `next-steps-map.html` was not touched.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-21 | Claude (Opus 5) + Zongzhe | Created. Records the multicover notation, what redundancy 1 gives up, the two-set edge storage and its two inferred failure paths, the merge threshold deduction, and a prototype replacement structure with 16 passing checks. No existing code changed. |
| 2026-09-21 | Claude (Opus 5) + Zongzhe | Section 5's design promoted to the global doc `../MEMORY_GRAPH_DESIGN.md`, specified against M6's acceptance test and registered in `PROJECT_PLAN.md`. This document stays as the evidence behind it. |
