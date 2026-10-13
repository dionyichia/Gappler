# memory_graph

The robot's memory of a room: the objects it has seen, and the photos that saw them.

This README is a guide for reading the code. It has one walkthrough so far,
`target_finder.py`. The list of every file and the pipeline stage each one covers is at the top
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

`merge_objects` is not called for you. Whoever merges two entries has to make three calls:

```python
objects.merge_objects(surviving, absorbed)
anchors.merge_objects(surviving, absorbed)
finder.merge_objects(surviving, absorbed)
```

### 6. `_hit`

It fills in a `TargetHit` from the object's entry and its best photo. Nothing else.

### See it run

Read `test_the_robot_runs_out_of_candidates_instead_of_looping` in
[`tests/test_target_finder.py`](tests/test_target_finder.py). It shows the whole loop in a few
lines: find, go to the first hit, reject it, find again, until the list is empty.

### What this file does not do

- It does not choose the target and related classes. They are given to the task. Choosing them
  from the instruction is task T6.7b.
- It does not lift a box drawn on a stored photo into 3D. No task covers that yet.
- It does not pick photos to search when nothing matches.
- It differs from HiCo-Nav's version in five ways, listed at the top of
  [`target_finder.py`](target_finder.py).
