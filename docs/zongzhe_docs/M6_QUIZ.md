# M6 quiz: what each memory_graph component does

A self-test on the built parts of the memory graph (`memory_graph/`), in pipeline order.
Each round has the questions, a model answer read from the code, the feedback on my answer, and
any problems in the code the round turned up.

Started 2026-10-14, on branch `t6.4f-periodic-cleanup` (commit `1d4f154`).

- Round 1: S0 to S6, from a recording to a feature vector
- Round 2: S7 to S11, from masks to object entries
- Round 3: S12, S13, the task and the query
- Overall: what to revisit

---

## Round 1: S0 to S6

### Q1. `replay_loader.py` (S0)

**Question.** What does it produce for each frame, in what units and conventions? Which four
mistakes does it guard against?

**Model answer.** It produces an `Observation` (`stage_types.py:19`) per frame:

| Field | Convention |
|---|---|
| `rgb` | uint8 (H, W, 3), RGB order, not BGR |
| `depth` | float32 (H, W), metres along the optical axis, 0 means no reading |
| `K` | 3x3 intrinsics of the colour image |
| `T_world_cam` | 4x4 camera-to-world |
| `frame_id`, `timestamp` | unique id, capture time in seconds |

The four mistakes, each handled in one place:

1. BGR from OpenCV: `to_observation(bgr=True)` flips the channels.
2. Depth in sensor units: `depth_to_metres` divides by a scale you must pass (1000 for the D455,
   5000 for TUM). Zero, negative, NaN and infinite readings all become 0.
3. World-to-camera passed as the pose: `rigid_transform` builds camera-to-world from the
   camera's position and orientation. A source that gives the inverse must be inverted first.
4. A frame conversion applied twice: the pose is composed once, in `to_observation`, as
   `T_world_base @ T_base_cam` (`replay_loader.py:107-109`). `_check_rigid` also refuses any
   matrix that is not a rotation plus a translation.

**My answer.** The four mistakes: right. The output: the fields I listed (`timestamp`,
`rgb_path`, `depth_path`, `T_world_cam`) are `TumFrame`, the index of files the TUM reader builds
first (`replay_loader.py:156`). The output every later stage sees is `Observation`, which holds
the images themselves, not paths.

### Q2. `detection_filter.py` (S2)

**Question.** The three drop rules, the exemption, why `targets` is an argument, and the
upstream bug.

**Model answer.** A detection is dropped if:

1. its label is a background class (`wall`, `floor`, `ceiling`, ...) and `cfg.skip_bg` is on,
2. its box covers less than `cfg.min_box_area_ratio` of the image (a fraction, not pixels),
3. its confidence is below `cfg.confidence_threshold` (0.3) and its label is not a target.

Targets are kept at any confidence. `targets` is an argument because it changes with every task.

**The upstream bug, in plain terms.** A detection is spread over several parallel arrays: boxes,
confidences, labels, masks. Item 3 in each array is the same detection. Upstream sorts the
detections into a new list by confidence, then uses positions in that sorted list to pick items
from the original, unsorted arrays. If the input was not already sorted, position 3 in the
sorted list is not position 3 in the original, so a detection ends up with another detection's
box or label. Here `sort_by_confidence` reorders every array together, once, with `take`
(`stage_types.py:69`), so they cannot drift apart.

**My answer.** Correct on the rules and the reason for `targets`. Small point: rule 2 is a ratio
of the image area, `min_box_area_ratio`.

### Q3. `anchor_gate.py` (S3)

**Question.** When does it accept, when does it reject outright, and why does a rejection matter?

**Model answer.** `should_accept` (`anchor_gate.py:23`):

1. No labels left after S2: reject.
2. No photo accepted yet (`last_accepted is None`): accept.
3. The camera moved more than `gate_translation_m` (1 m) or turned more than
   `gate_rotation_rad` (45 degrees) since the last accepted photo: accept.
4. A target or related class is in view: accept.
5. Otherwise reject.

`AnchorGate.commit` moves `last_accepted` only once the photo is actually stored (end of S12),
so a photo the gate passed but S12 refused does not count as the last accepted one.

A rejected photo skips the rest of the pipeline. That keeps the graph sparse (fewer anchors)
and saves compute on every later stage.

**My answer.** Mostly right. One correction: "first photo" means the first photo ever accepted,
not the first photo of a label. The gate does not track labels. I also left out the
commit-only-on-store rule.

### Q4. `masks.py` and `sam3_adapter.py` (S4, S5)

**Question.** Why erode by one pixel? What does `sam3_adapter.py` merge?

**Model answer.** `erode_one_pixel` keeps a pixel only if its whole 3x3 neighbourhood is in the
mask, which removes a one-pixel rim. The reason: pixels on a mask's edge sit on depth jumps. At
the edge of a chair, the depth reading may be the wall behind it. Back-projected, those pixels
land on the wall and give the object's point cloud long tails.

S5 (`clean_masks`) then drops tiny masks and near-duplicates (IoU above 0.9 with a more confident
mask kept earlier), and cuts a contained object out of its container: the cup out of the table.

SAM 3 takes a text prompt and returns boxes, scores and masks in one call, so S1 (detection) and
S4 (segmentation) are one step. Upstream runs YOLO-World for boxes, then MobileSAM for masks.

**My answer.** The SAM 3 part: right. The erosion part: I described what it does, not why. Also
it is one pixel, not two.

### Q5. `image_feature.py` and `clip_encoder.py` (S6)

**Question.** How does a detection become a feature vector? Why two files? How does the padding
differ from upstream's?

**Model answer.** `image_features` (`image_feature.py:55`) does three steps:

1. `padded_crops` cuts each box out of the photo, widened on each side by `crop_pad_ratio`
   (10%) of the box's own size, clamped to the image.
2. The encoder turns the crops into vectors. The real one is `OpenClipEncoder`, open_clip
   ViT-B-32.
3. `l2_normalise` scales each vector to length 1, so a dot product between two is their cosine.

Two files, because the encoder needs torch and the rest does not. `image_feature.py` takes any
object with an `encode` method, so it runs and is tested at bench L0 with a stand-in, and the
model can be swapped.

Upstream pads a fixed 20 px. On a higher-resolution camera, or for a large object, 20 px is a
smaller share of the box, so the crop has less surrounding context. A ratio gives the same share
of context whatever the resolution or the object size.

**My answer.** Mostly right. The encoder is one of three steps, not the whole thing: cropping and
normalising happen outside it. The second reason for the split (no torch needed for the rest) was
missing.

### Round 1 score

About 3.5 of 5. Strong on the guarded mistakes, the filter rules and SAM 3. To revisit: the
`Observation` fields, why erosion matters, and the gate's "first photo" rule.

### Code issues found in round 1

These are for review. None has been changed.

1. **The gate saves less than its docstring says, now that SAM 3 is the detector.**
   `anchor_gate.py:3` says a rejected photo skips everything from S4 on. But the gate needs the
   labels after S2, and SAM 3 produces masks (S4) in the same call as the boxes (S1)
   (`sam3_adapter.py:97`). So by the time the gate rejects a photo, the expensive segmentation
   has already run. A rejection now saves S5 to S12, not S4. This is what T6.5b's cheap
   always-on detector is meant to fix: the gate should run on the cheap detector's labels, before
   SAM 3. Worth correcting the docstring now and noting it in T6.5.
2. **The target-at-any-confidence rule is a no-op with SAM 3's default threshold.** The wrapper
   cuts at 0.5 before S2 sees anything, which is above `confidence_threshold` (0.3). A target at
   0.4 never reaches S2 to be rescued. Already noted in `sam3_adapter.py:28-35` as open. It should
   be settled in T6.3d's lab-box run, by building the wrapper with a low threshold.
3. **One SAM 3 call per vocabulary phrase re-encodes the image each time**
   (`sam3_adapter.py:97`). With 20 classes, that is 20 image encodings per photo. The processor
   can encode once (`set_image`) and take each phrase after (`set_text_prompt`). Already noted as
   not measured. Worth measuring in T6.5b alongside the cheap detector's cost.
4. **`frame_id` restarts at 0 for each TUM sequence** (`replay_loader.py:226`), while
   `Observation` says it is "never reset" (`stage_types.py:26`). Loading two recordings into one
   graph would give repeated ids, and `AnchorStore.add` refuses a repeat. Harmless with one
   recording. A `frame_id_offset` argument on `TumSequence` would fix it if it is ever needed.

---


## Round 2: S7 to S11

### Q6. `geometry.py` (S7, S8, S9)

**Question.** Walk a mask from pixels to a `Candidate`. Name the cloud cleanup steps and what each
removes. What must depth mean for `camera_rays` to be right? Why no Open3D?

**Model answer.** `build_candidates` (`geometry.py:177`) runs these steps for each mask.

**S7, back-projection: pixels become 3D points.** A pixel only tells you a direction. The depth
image tells you how far along that direction the surface is. Together they give a 3D point.

1. `camera_rays` turns every pixel (u, v) with depth z into a point in the camera's own frame:
   `x = (u - cx) z / fx`, `y = (v - cy) z / fy`, `z = depth`. Here `fx`, `fy`, `cx`, `cy` come
   from `K`. In words: how far the pixel is from the image centre, scaled by how far away the
   surface is.
2. `back_project` keeps only pixels inside the mask with a valid depth (not 0). Fewer than
   `min_points` (16): the mask is dropped. More than `max_points` (5000): every k-th point is kept.
3. `transform_points` moves the points from the camera frame into the map frame with
   `T_world_cam`. Now points from different photos can be compared.

**S8, cleanup and box.**

| Step | What it does | What it removes |
|---|---|---|
| `voxel_downsample` | Cuts space into 2 cm cubes and keeps one averaged point per occupied cube | Uneven density and excess points. Close-up views no longer outweigh far ones |
| `largest_cluster` (DBSCAN) | Groups points that are within 10 cm of each other, keeps the largest group | Stray clumps: mask spill onto the wall behind, depth noise. Can also cut off thin parts such as chair legs |
| `fit_box` | Box aligned with the cloud's main directions (PCA) | Nothing. Then a box under `min_box_volume_m3` is dropped |

**S9, range.** `within_range` drops a candidate whose box centre is more than
`max_object_distance_m` (6 m) from the camera, because far depth readings are noisy.

Depth must be distance along the optical axis (the camera's straight-ahead direction), not
distance along each pixel's ray. Open3D is not used because numpy and scipy already do the job
and the project already depends on them, so there is one package fewer to install on each machine.

**My answer.** The order of S8 and S9 was right, and so were the depth meaning and the Open3D
reason. One mix-up: S7 back-projects *pixels*, not voxels. Voxels only appear in S8. I also left
out the `min_points` drop and the box volume check.

### Q7. `association.py`, overlap (S10)

**Question.** How is overlap computed? Which two cheap checks skip most pairs?

**Model answer.** Overlap is the fraction of the candidate's points that have a stored object's
point within `match_radius_m` (2.5 cm). Two cheap checks run first, in this order
(`association.py:61`):

1. **A k-d tree on object centres.** Only objects whose centre is within reach of the
   candidate's centre are looked at: the candidate's half-diagonal plus the largest object
   half-diagonal. Far-away objects are never visited at all.
2. **A separating-axis test on the two 3D boxes** (`boxes_intersect`). If the boxes do not touch,
   overlap is 0 with no point-by-point work.

Only pairs that pass both get the expensive part: a k-d tree on the object's points and a
nearest-neighbour query for every candidate point.

**My answer.** The overlap definition and the box test were right. I missed the k-d tree on
centres, which is the main reason this version is cheaper than upstream's all-pairs loop. The
"no points gives 0" rule is a guard against an edge case, not a cheap check.

### Q8. `association.py`, decision (S10)

**Question.** The formula, why appearance alone cannot match, greedy against one-to-one, and
which was chosen.

**Model answer.**

```
score = (1 + phys_bias) * overlap + (1 - phys_bias) * appearance
```

`appearance` is the cosine between the two image features. With `phys_bias = 0.5` this is
`1.5 * overlap + 0.5 * appearance`. Appearance is at most 1, so with zero overlap the score is at
most 0.5. The match threshold `sim_threshold` is 0.6, so a match always needs some 3D overlap.
Two identical-looking chairs in different places therefore stay two objects.

- `greedy`: each candidate takes its best-scoring object above the threshold. Two candidates
  from one photo can take the same object.
- `one_to_one`: the Hungarian algorithm finds the best overall assignment in which each object
  takes at most one candidate.

Greedy was chosen (D-MG8, 2026-10-07), as upstream does it.

**My answer.** The 0.5 against 0.6 reasoning and the choice were right. Two gaps: I did not write
the formula, and I wrote "greedy" for both modes. The second one is `one_to_one`.

### Q9. `object_store.py` (S11)

**Question.** No match, match, what `_add_sighting` updates, and why decide all matches first.

**Model answer.**

- **No match:** `_insert` creates an entry with a fresh id. Ids are never reused, even after a
  merge.
- **Match:** `_fuse_cloud` stacks the candidate's points onto the entry's cloud, voxel-downsamples
  the result so it cannot grow without limit, and refits the box.

Then `_add_sighting` (`object_store.py:266`), in both cases:

1. appends the label, the confidence and the anchor id,
2. adds the unit feature to `clip_sum` and counts it,
3. records the edge "this photo saw this object" in the graph, with a `Sighting` payload,
4. moves the entry in the label index if its majority label changed,
5. recomputes the task score.

All matches are decided before any is applied because they are scored against the store as it
was before the photo. A new entry made from candidate 1 is not a column when candidate 2 is
scored, so two new things in one photo never merge with each other.

**My answer.** Right on all three parts. One wording fix: a match is fused with the stored
*entry's* cloud, not with earlier candidates. Four more things `_add_sighting` updates: see
items 2 to 5 above.

### Q10. `object_store.py`, derived values

**Question.** How are `sightings`, `label` and `clip` worked out, and why on request?

**Model answer.**

- `sightings` is `len(labels)`.
- `label` is the most common label. A tie goes to the label seen first.
- `clip` is `clip_sum` scaled to length 1. That is the average of the unit features, made unit
  again.

They are worked out on request so they cannot go stale. Each is a function of the lists that
are actually stored. No second copy exists that a sighting or a `merge_objects` call could
forget to update.

**My answer.** The definitions were right. On the reason I was close: the point is not that they
are "dynamic" but that a stored copy could fall out of step with the lists, and a computed one
cannot. Missed the tie rule.

### Round 2 score

About 3.5 of 5. Strong on overlap, the 0.5 against 0.6 point and S11. To revisit: what S7 does
(pixels to points), the k-d tree prefilter, and writing out the score formula.

### Code issues found in round 2

None changed.

1. **A small object can be absorbed into its container on geometry alone** [inferred].
   Overlap is one-sided: the share of the *candidate's* points near the stored object. Say the
   table is seen in photo A but the cup on it is not detected. Then the table's mask includes the
   cup's pixels, and the table entry's cloud contains the cup's points. In photo B the cup is
   detected. Nearly all its points are near the table cloud, so overlap is close to 1 and the
   score is at least 1.5. The cup merges into the table and never becomes its own object. Nothing
   in S10 checks that the labels agree. `subtract_contained` (S5) only helps when both are
   detected in the same photo. Upstream behaves the same. Worth a deliberate test in T6.4 against
   T6.4e's ground truth. Possible fixes: a label check, or an overlap that also asks what share
   of the *stored* object's points the candidate covers.
2. **One large object weakens the prefilter for every candidate** (`association.py:74`). `reach`
   is the largest half-diagonal of all objects. One long wall-like object, or an entry inflated
   by stray points before S13 denoises it, widens the search for every candidate, and the k-d
   tree step degrades towards all pairs. Results stay correct, because the box test still runs.
   This only costs speed. A per-object check, or querying with each object's own radius, would
   keep it tight.
3. **The range check runs after the most expensive cleanup step** (`geometry.py:198-210`). DBSCAN
   is a Python loop. It runs on every cloud, and only then are clouds beyond 6 m dropped. Checking
   the raw cloud's centre against the range before `clean_cloud` would skip DBSCAN for far
   objects. The final box-centre check could stay as it is. Minor.
4. **`appearance_matrix` is a double Python loop** (`association.py:94`). With unit features it
   is one matrix product. Minor at today's object counts.

---

## Round 3: S12, S13, the task and the query

### Q11. `anchor_store.py` (S12)

**Question.** The four things resized together and how. Why depth is never blended. The order of
checks in `add`, and why it refuses a photo whose edges are not in the graph.

**Model answer.** Photos are stored at 448 x 448. Four things shrink together, or they stop
agreeing with each other:

| What | Function | How |
|---|---|---|
| Colour image | `resize_bilinear` | Blends the four nearest pixels |
| Depth image | `resize_nearest` | Copies the nearest pixel, never blends |
| Intrinsics `K` | `resize_intrinsics` | Scales the focal lengths and the image centre |
| Detection and object boxes | `resize_boxes` | Scales the corners |

Depth is never blended because blending invents distances. At the edge of a chair, between
"chair at 1.5 m" and "wall at 3 m", a blend gives 2.25 m, where there is nothing. A colour blend
only gives a slightly soft edge, which is harmless.

`add` (`anchor_store.py:193`) checks, in order:

1. the frame id is not already stored, else an error,
2. there is one object id per candidate, else an error,
3. there is at least one candidate, else it returns `None` and stores nothing,
4. the graph links this photo to exactly the objects passed in, else an error.

Then it resizes, records each object's box (the union of boxes if two detections went to one
object) and stores the record.

Check 4 exists because the edges are written by `ObjectStore.integrate`, before `add` runs. If
they are missing or different, `integrate` was skipped or given a different anchor id. Storing
the photo anyway would leave a record that the graph does not know about. Failing loudly catches
the call-order bug at the moment it happens.

**My answer.** The order of checks and the reason for the last one: right. Two gaps. I named
two of the four by method ("nearest, bilinear") instead of by what they resize. My reason for
not blending depth was circular; the reason is that a blend invents a distance where there is
no surface. Check 2 is "one id per candidate", not "more than one item per candidate".

### Q12. `anchor_object_graph.py`

**Question.** What is stored instead of upstream's two sets, what does that prevent, and what is a
`Sighting` for?

**Model answer.** Upstream keeps `Keyframe.objects_3d` and `Object3D.observers`, two sets that
must be kept in step by hand. Here each edge `(anchor, object)` is stored once, in `_edges`, and
both lookups (`objects_of`, `anchors_of`) are indexes kept in step by the same few methods. So
the two directions cannot disagree, and `check_invariants` has a third thing to check them
against. One concrete payoff: `merge_objects` moves every edge of the absorbed object.
Upstream unions the observers but leaves the anchors pointing at the absorbed id.

A `Sighting` is the payload on one edge: what one photo recorded about one object. It holds the
detection count, mask size in pixels, confidence and occluded fraction. Its use is
`view_quality()`, confidence x (1 - occluded) x mask pixels. That number picks an object's best
photo (`TargetFinder.best_anchor`) and decides which photo to keep when pruning
(`cleanup.view_cost`). Upstream's edge is a bare id in a set, so it cannot answer "which photo
shows this object best".

**My answer.** Right on the edge store. I described a `Sighting` but not what it is used for:
view quality, for the best photo and for pruning.

### Q13. `cleanup.py` (S13)

**Question.** The two steps, kappa and r_j, why the min, whether objects can be deleted, and how
it differs from upstream.

**Model answer.** Every `cleanup_every_photos` stored photos:

1. **Denoise every object** (`ObjectStore.denoise`): voxel downsample, keep the largest DBSCAN
   cluster, refit the box. If fewer than `denoise_min_points` would be left, the object is not
   changed. This removes the stray points that merging piles up, since merging only adds.
2. **Prune anchors**: keep the fewest photos such that every object is still seen by r_j of
   them, and delete the rest, records and edges.

kappa (`prune_kappa`) is the number of photos you would *like* to keep per object, a minimum
coverage, not a maximum. Many objects end up with more, because a kept photo shows several
objects. r_j = min(kappa, degree(j)), where degree is how many photos saw object j. Without the
min, an object seen once could never be covered by three photos. That one object would make the
whole problem unsolvable, not just its own part.

Objects are never deleted. Every object keeps at least one photo, because r_j is at least 1.

Differences from upstream:

- **The main one:** pruning is a greedy set multicover (`AnchorObjectGraph.prune`). Upstream
  solves the same problem exactly with PuLP and the CBC solver, with no time limit (D-MG3).
  Greedy is close to optimal, needs no solver, and its run time is predictable.
- Between two photos that cover equally, the one with better views is kept (`view_cost`, a
  price between 1 and 1.001). Upstream has no preference.
- kappa and the interval are config values. Upstream writes 1 and 10 in the code.

**My answer.** Right on objects not being deleted and on the config values. Four gaps:

- Denoising also keeps the largest cluster. It is not only a downsample and box refit.
- kappa is a minimum coverage, not "photos kept per object" or a maximum.
- It is solved by greedy here, not an ILP. The ILP is upstream's.
- I missed the main difference from upstream, greedy against an exact solver, and the
  view-quality tie-break.

### Q14. `task.py`

**Question.** What a `TaskContext` holds, how the score is computed and when it is recomputed,
why one encoder, and whether a class can be both a target and related.

**Model answer.** A `TaskContext` is frozen. It holds the instruction text, its feature (the
instruction encoded by `OpenClipEncoder.encode_text`, unit length), the target classes and the
related classes.

An object's task score is the cosine between the object's average image feature and the task
feature, from -1 to 1, and 0 with no feature. It is recomputed:

- for every object when `ObjectStore.set_task` is called,
- for one object each time it gets a sighting (`_add_sighting`) or absorbs another
  (`merge_objects`), because its average feature changed.

One encoder, because a cosine only means something between two vectors in the same space.
CLIP is trained so that a photo of a chair and the words "a chair" point the same way. A
different model's vectors have no such relation. `score` raises an error if the lengths differ,
but two models with the same output length would pass silently.

A class cannot be both. `related` has `targets` subtracted from it in `__post_init__`, so
target wins.

**My answer.** Right on the contents, the cosine and "target wins". Two gaps. I missed that the
score is also recomputed on every sighting and merge, not only on `set_task`, and I did not
answer the one-encoder question. Wording: it is the set difference `related - targets`.

### Q15. `target_finder.py`

**Question.** The order of hits, how the best photo is picked, what `reject` solves, and when the
rejected list is emptied.

**Model answer.** `find` returns two groups: **all targets first, then all related objects**,
with rejected objects left out. Within each group, the highest task score comes first. So a
related object never comes before a target, whatever its score. With no task set, the list is
empty.

`best_anchor` looks at every photo that saw the object and still has a stored record. It picks
the highest view quality (confidence x mask pixels). A tie goes to the newest photo, the
highest frame id.

`reject` stops a loop. Without it, the robot drives to an object, finds it is wrong, asks again
and is sent to the same object forever.

The list is emptied automatically by `_follow_task`, which runs at the start of `find` and
`reject`. It compares the current instruction with the one the list was made for. A new
instruction empties it. New class sets for the same instruction keep it. A rejected object that
is merged into another entry makes that entry rejected.

**My answer.** Right on best photo and `reject`. Two gaps. I missed the two groups: targets
always come before related objects. And the list is emptied by `_follow_task` on its own, not
by a call to `clear_rejected`.

### Round 3 score

About 3 of 5. Strong on the graph's edge store and `reject`. To revisit: kappa as a minimum and
greedy against upstream's exact solver, the two groups in `find`, and when the task score is
recomputed.

### Code issues found in round 3

None changed.

1. **A repeated frame id corrupts the object store before `add` refuses it**
   (`anchor_store.py:210`). The order is `integrate` first, then `add`. `integrate` has already
   fused the candidates into objects, appended sightings and added edges by the time `add` sees
   the repeat and raises. The objects now count those sightings twice, and the edges fused into
   the old photo's edges. The duplicate check should happen before `integrate`, or `integrate`
   should refuse an anchor id the graph already holds. This links to round 1 issue 4:
   `TumSequence` restarts frame ids at 0, which is exactly how a repeat would arrive.
2. **Two "best photo" functions that answer differently.**
   `AnchorObjectGraph.best_anchor_for` (`anchor_object_graph.py:156`) and
   `TargetFinder.best_anchor` (`target_finder.py:105`) both pick an object's best photo. The
   graph's version has no tie rule and does not check that the photo still has a record. Nothing
   calls the graph's version now, so it is a trap for the next caller. Remove it, or have
   `best_anchor` call it with a filter.
3. **The rejected list is tied to the instruction's text** (`target_finder.py:144`). The same
   sentence given again as a new task, for example "find a chair" after the chairs were moved,
   keeps the old rejections. Minor. A task id on `TaskContext` would separate the two.

---

## Overall: what to revisit

Total about 10 of 15. The pipeline order and most "what does it do" answers are solid. The gaps
are mostly about *why*:

- **Why erosion matters** (Q4) and **why depth is never blended** (Q11). Both come from one fact:
  depth jumps at object edges, and anything that mixes the two sides invents a surface.
- **S7 back-projection** (Q6): pixel plus depth plus `K` gives a 3D point, then `T_world_cam`
  moves it into the map.
- **The S10 score formula** (Q8) and the k-d tree prefilter (Q7).
- **Pruning** (Q13): kappa is a minimum, r_j = min(kappa, degree) keeps it solvable, and it is
  solved greedily here and exactly, with a solver, upstream.
- **`find`'s two groups** (Q15) and **when task scores are recomputed** (Q14).

### All code issues, ranked

| # | Issue | Where | Kind |
|---|---|---|---|
| 1 | A repeated frame id corrupts the store before `add` refuses it | `anchor_store.py:210` | Correctness |
| 2 | A small object can merge into its container on geometry alone [inferred] | `association.py:61` | Correctness, test in T6.4 |
| 3 | The gate runs after SAM 3 has already made masks | `anchor_gate.py:3` | Docstring now, design in T6.5b |
| 4 | SAM 3's 0.5 threshold makes the target-at-any-confidence rule a no-op | `sam3_adapter.py:28` | Settle in T6.3d |
| 5 | `TumSequence` restarts frame ids at 0 | `replay_loader.py:226` | Correctness with more than one recording |
| 6 | Two best-photo functions that disagree | `anchor_object_graph.py:156` | Cleanup |
| 7 | One SAM 3 image encoding per vocabulary phrase | `sam3_adapter.py:97` | Speed, measure in T6.5b |
| 8 | Prefilter radius set by the largest object | `association.py:74` | Speed |
| 9 | DBSCAN runs before the range check | `geometry.py:198` | Speed, minor |
| 10 | `appearance_matrix` double loop | `association.py:94` | Speed, minor |
| 11 | Rejected list keyed on instruction text | `target_finder.py:144` | Minor |
