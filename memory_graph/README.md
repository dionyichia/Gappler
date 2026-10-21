# memory_graph

The robot's memory of a room: the objects it has seen, and the photos that saw them.

This README is a guide for reading the code. It walks through three files, in the order the
data flows through them:

1. [`object_store.py`](#walkthrough-object_storepy): the objects.
2. [`anchor_store.py`](#walkthrough-anchor_storepy): the kept photos.
3. [`target_finder.py`](#walkthrough-target_finderpy): the question a planner asks.

The list of every file and the pipeline stage each one covers is at the top
of [`__init__.py`](__init__.py). The design and its open decisions are in
[`docs/MEMORY_GRAPH_DESIGN.md`](../docs/MEMORY_GRAPH_DESIGN.md).

To run the tests, from the repo root:

```bash
./bench/memory_graph_tests.sh
```

## Words used here

| Word | Meaning |
|---|---|
| object | One physical thing in the room, built up from every time it was seen. It has a 3D box, a label and a feature. |
| anchor | One photo the robot kept, with its depth image, camera settings and camera position. |
| edge | "This anchor saw this object". The graph is the set of all edges. |
| feature | A list of numbers that describes how something looks or what a sentence means. Two features that point the same way mean similar things. |
| task | One instruction, such as "find a chair". |
| target class | A class name the instruction asks for, such as `chair`. |
| related class | A class name likely to be near a target, such as `table`. |
| task score | How well an object matches the instruction, from -1 to 1. It is the cosine between the object's feature and the instruction's feature. |
| candidate | One detection from one photo, already lifted into 3D: a point cloud, a box, a label and a feature. Not yet known to be a new object or an old one. |
| sighting | One time an object was seen. Each candidate that goes into an object adds one. |
| point cloud | A set of 3D points on an object's surface, in the map frame. |
| intrinsics | The camera's focal lengths and image centre, written `K`. They turn a 3D point in front of the camera into a pixel, and back. |
| pose | Where the camera was and which way it faced when it took a photo. |

## One photo, start to end

This is how the three files meet. `obs` is one photo with depth and pose, and `dets` are the
things detected in it, with masks.

```python
candidates = build_candidates(obs, dets, cfg, features)          # geometry.py: lift to 3D
ids = objects.integrate(candidates, anchor=obs.frame_id)         # object_store.py
record = anchors.add(obs, dets, candidates, ids)                 # anchor_store.py
if record is not None:
    cleanup.photo_stored()                                       # cleanup.py, every N photos

hits = finder.find()                                             # target_finder.py, when asked
```

The order of the middle two lines matters. `integrate` makes the edges between this photo and
its objects. `add` then checks that those edges exist and refuses the photo if they do not.

## Walkthrough: `object_store.py`

The file answers: **the robot saw something. Is it new, or one it already knows? Then update
the memory.**

It has two parts. `ObjectEntry` is one object. `ObjectStore` holds all of them.

### 1. `ObjectEntry`, one object

| Field | Meaning |
|---|---|
| `id` | Its number. Never reused, even after the object is merged away. |
| `points`, `colors` | Its point cloud, in the map frame. |
| `box` | A 3D box around the cloud. |
| `labels`, `confs`, `anchor_ids` | Three lists with one item per sighting: what the detector called it, how sure it was, and which photo it came from. |
| `clip_sum`, `clip_count` | The sum of the features of all sightings, and how many there were. |
| `task_score` | How well it matches the current instruction. The store sets it. Do not set it by hand. |

Three values are worked out from those fields each time you ask, so they cannot go stale:

- **`sightings`** is the length of `labels`.
- **`label`** is the label most sightings gave. A tie goes to the label seen first.
- **`clip`** is the average feature, scaled to length 1.

### 2. `integrate`, the main function

Called once per photo with that photo's candidates. It does two things:

1. **Match.** It asks `associate` (in [`association.py`](association.py)) which stored object
   each candidate is, or whether it is new. The match uses how much the two point clouds
   overlap and how alike the two features are.
2. **Apply.** It hands the answers to `apply`.

It returns the object id each candidate ended up in.

### 3. `apply`, insert or merge

For each candidate:

- **New:** `_insert` makes an entry with a fresh id.
- **Matched:** `_fuse_cloud` joins the candidate's points to the entry's cloud, thins the
  result with a voxel grid so it cannot grow without limit, and refits the box.

Then, in both cases, `_add_sighting`:

1. appends the label, the confidence and the photo id,
2. adds the feature to `clip_sum`,
3. records the edge "this photo saw this object" in the graph,
4. moves the entry in the label index if its majority label changed,
5. works out the task score again.

All of a photo's matches are decided before any is applied. So two new things in one photo
never merge with each other.

### 4. `merge_objects`, two entries turn out to be one

Sometimes the store holds two entries for one physical thing. `merge_objects(surviving,
absorbed)` folds one into the other: clouds joined, lists joined, features added, edges moved.
The absorbed id is gone for good.

Nothing calls this yet. It is there for a later clean-up step. Whoever calls it must also tell
the other two holders of object ids:

```python
objects.merge_objects(surviving, absorbed)
anchors.merge_objects(surviving, absorbed)
finder.merge_objects(surviving, absorbed)
```

### 5. `denoise`, removing stray points

Merging only ever adds points. A mask that spilled onto the wall leaves a few wrong points in
the cloud for good. `denoise(id)` thins the cloud, keeps the largest connected clump, and
refits the box. If that would leave almost nothing, it changes nothing. [`cleanup.py`](cleanup.py)
calls it for every object every few photos.

### 6. The task: `set_task`, `target_ids`, `related_ids`, `ranked_by_task`

- **`set_task(task)`** starts a new instruction and works out every entry's task score again.
- **`target_ids()`** and **`related_ids()`** return the objects whose label is a target or a
  related class. They read the label index, so an object leaves when its label changes.
- **`ranked_by_task(ids)`** sorts ids by task score, highest first.

### 7. `check_invariants`, the self-check

Returns a list of things that are wrong. An empty list means the store is consistent. It checks
the graph, that every entry's three lists have the same length, that the label index matches
the labels, and that no task score is stale. The tests call it after every change.

### One thing that surprises people

An entry can have no photo left. Pruning removes photos, never objects. So the list of all
objects is `objects.ids()`, not the graph's `objects()`, which only knows objects that still
have a photo.

### See it run

Read `test_ten_views_give_one_entry` in
[`tests/test_object_store.py`](tests/test_object_store.py). Ten views of one panel go in. One
entry comes out, with ten labels and a cloud that stopped growing.

## Walkthrough: `anchor_store.py`

The file answers: **which photos did the robot keep, and what can be done with one later?**

A kept photo is called an anchor. It is kept so it can be looked at again: shown to a person
or a model, or used to work out where something in it is in 3D. That second use is why the
depth image and the camera intrinsics are stored with it.

It has three parts: the resize functions, `AnchorRecord` (one photo) and `AnchorStore` (all of
them).

### 1. The resize functions

Photos are stored smaller than the camera gives them, 448 by 448 by default
(`anchor_height`, `anchor_width` in [`config.py`](config.py)). Four things have to shrink
together, or they stop agreeing with each other:

| Function | What it resizes | How |
|---|---|---|
| `resize_bilinear` | The colour image | Blends the four nearest pixels. |
| `resize_nearest` | The depth image | Copies the nearest pixel. Never blends. |
| `resize_intrinsics` | The camera intrinsics `K` | Scales the focal lengths and the image centre. |
| `resize_boxes` | Boxes drawn on the image | Scales the corners. |

Depth is never blended, because blending invents distances. At the edge of a chair, half way
between "chair at 1.5 m" and "wall at 3 m" is 2.25 m, where there is nothing.

All four use one rule for where a pixel is, written in the comment above `_source_coords`.

### 2. `AnchorRecord`, one stored photo

| Field | Meaning |
|---|---|
| `id` | The photo's frame id. |
| `rgb`, `depth` | The colour and depth images, at the stored size. |
| `K` | The intrinsics of the stored image, not of the camera's original image. |
| `T_world_cam` | The camera's pose. |
| `detections` | What was detected in the photo, with boxes on the stored image. |
| `object_boxes` | For each object this photo shows, its box on the stored image. |
| `task_score` | How relevant the photo is to the instruction. The caller sets it. |

And three things it can work out:

- **`project(point)`** takes a 3D point in the map and returns the pixel where it appears on
  this photo, or `None` if the point is behind the camera.
- **`fov_x`, `fov_y`** are the camera's angles of view.
- **`labels`** is the set of labels detected in the photo.

### 3. `add`, the main function

Called once per photo, after `objects.integrate`. In order:

1. **Refuse a repeat.** The same frame id twice is an error.
2. **Stop if there is nothing to link.** A photo with no candidates is not stored, and `add`
   returns `None`.
3. **Check the edges.** The graph must already link this photo to exactly the objects passed
   in. If not, `integrate` was skipped or given a different id, and `add` raises an error.
4. **Resize** the images, the intrinsics and the detection boxes.
5. **Record each object's box.** If two detections in the photo went to the same object, the
   box around both is kept.
6. **Store the record** and return it.

### 4. Keeping records in step with the graph

The edges live in the graph, and other code changes them. Each such change has a matching call
here:

| What happened | Call |
|---|---|
| A photo should go, edges and record | `remove(anchor_id)` |
| The graph pruned photos | `drop_pruned()` deletes the records of photos the graph no longer has |
| Two object entries were merged | `merge_objects(surviving, absorbed)` moves the boxes to the survivor |

### 5. `check_invariants`, the self-check

It reports a photo in the graph with no record, a record with no objects, and a record whose
boxes are for different objects than the graph links. That is how a forgotten call from the
table above gets noticed.

### See it run

Read `test_invariants_hold_and_centres_land_in_their_boxes` in
[`tests/test_anchor_store.py`](tests/test_anchor_store.py). It stores five photos of two
objects. Then, for every photo and every object in it, it projects the object's 3D centre
onto the stored photo and checks the pixel is inside the object's box. That one check only
passes if the resized image, intrinsics, boxes and pose all agree.

## Walkthrough: `target_finder.py`

The file answers one question for the planner: **what should the robot go to?**

It has two parts. `TargetHit` is the answer. `TargetFinder` produces answers.

### What exists before this file runs

| Thing | File | What it holds |
|---|---|---|
| The object store | [`object_store.py`](object_store.py) | Every object: its 3D box, its label and its task score. |
| The anchor store | [`anchor_store.py`](anchor_store.py) | Every kept photo, and where each object appears on it. |
| The task | [`task.py`](task.py) | The instruction, the target classes and the related classes. |

`TargetFinder` stores no map data of its own. It reads from those three. The only thing it
keeps is the list of rejected objects.

### How it is used

```python
finder = TargetFinder(objects, anchors)

hits = finder.find()               # targets first, best score first
# The robot drives to hits[0]. It turns out to be the wrong thing.
finder.reject(hits[0].object_id)

hits = finder.find()               # that object is no longer in the list
```

### 1. `TargetHit`, the answer

One hit is one object worth going to. It is a plain record.

| Field | Meaning |
|---|---|
| `object_id`, `label` | Which object, and what it is called. |
| `kind` | `"target"` or `"related"`. |
| `task_score` | How well it matches the instruction. |
| `position`, `extent` | The centre and the side lengths of its 3D box, in metres, in the map frame. This is what a planner drives to. |
| `sightings` | How many times it has been seen. |
| `anchor_id`, `box_on_anchor` | The best stored photo of it, and where it is on that photo. This is for showing a person or a model. Both are `None` if no photo of it is left. |

A hit is a copy. If the map changes later, a hit you already hold does not.

### 2. `find`, the main function

It does this, in order:

1. Ask the object store for the ids of all objects with a target label.
2. Remove the rejected ones.
3. Sort what is left by task score, highest first.
4. Turn each id into a `TargetHit`.
5. Do steps 1 to 4 again for related labels, and put those after the targets.

So a related object never comes before a target, whatever its score. With no task set, the
list is empty. `find(include_related=False)` returns targets only.

An object's label is the one most of its sightings gave it. If later photos change that label,
the object can stop being a target.

### 3. `best_anchor`, picking the photo

For one object, it takes every photo that saw it and still has a stored record. It picks the
one with the highest view quality. View quality is the detector's confidence times the
object's size in that photo. If two photos are equal, the newest wins. If no photo is left, it
returns `None`.

### 4. `reject`, the write-back

The robot drove to a hit and it was the wrong thing. `reject(id)` adds that id to the rejected
list, and `find` skips it from then on.

Without this the robot loops: it is sent to an object, finds it is wrong, asks again, and is
sent to the same object.

### 5. Three helpers that keep the rejected list correct

| Function | What it does | Why |
|---|---|---|
| `_follow_task` | Runs at the start of `find` and `reject`. If the instruction has changed, it empties the list. | An object that was wrong for "find a chair" may be right for "find a sofa". New class sets for the same instruction keep the list. |
| `merge_objects` | If a rejected object was merged into another entry, the surviving entry becomes rejected. | Two entries sometimes turn out to be one physical thing. It is still the wrong thing. |
| `check_invariants` | Reports any rejected id that no longer exists. | This is how a forgotten `merge_objects` call gets noticed. |

`merge_objects` is not called for you. Whoever merges two entries has to make the three calls
shown in the `object_store.py` walkthrough.

### 6. `_hit`

It fills in a `TargetHit` from the object's entry and its best photo. Nothing else.

### See it run

Read `test_the_robot_runs_out_of_candidates_instead_of_looping` in
[`tests/test_target_finder.py`](tests/test_target_finder.py). It shows the whole loop in a few
lines: find, go to the first hit, reject it, find again, until the list is empty.

### What this file does not do

- It does not choose the target and related classes. They are given to the task.
  `ClassExpander` in [`reasoning.py`](reasoning.py) chooses them from the instruction (T6.7b).
- It does not lift a box drawn on a stored photo into 3D. No task covers that yet.
- It does not pick photos to search when nothing matches.
- It differs from HiCo-Nav's version in five ways, listed at the top of
  [`target_finder.py`](target_finder.py).
