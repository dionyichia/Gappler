"""Find targets (T6.8a): which stored objects answer the task, and where to look.

The question a planner asks the graph: "what should the robot go to?". The
answer is a list of hits. Each hit is one object whose label is a target or a
related class of the task, with its position, its task score, and the stored
photo that shows it best.

    finder = TargetFinder(objects, anchors)
    hits = finder.find()          # targets first, best score first
    ...the robot drives to hits[0] and it turns out to be wrong...
    finder.reject(hits[0].object_id)
    hits = finder.find()          # that object is gone from the list

`reject` is the write-back. Without it the robot drives to an object, finds it
is wrong, asks again and gets the same object, forever (upstream's
object_blacklist, map_elements.py:239, written at multi_level_perception.py:350).

Upstream: Map.find_target (map.py:280).

Differences from upstream, on purpose:
  - Hits are ranked by task score. Upstream returns them in set order, and its
    object score is always 0.
  - The photo is the one with the best view of the object (the edge's
    view_quality). Upstream takes the middle one of the sorted photo ids.
  - A rejection belongs to one instruction. A new instruction starts with an
    empty list. Upstream makes a new TargetManager per task, same effect.
  - A rejection follows a merge: if a rejected object turns out to be part of
    another entry, that entry is rejected. Upstream loses it.
  - An object with no stored photo left is still a hit, with no photo. Its
    position is still worth driving to. Upstream drops it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Set

import numpy as np

from memory_graph.anchor_object_graph import AnchorId, ObjectId
from memory_graph.anchor_store import AnchorStore
from memory_graph.object_store import ObjectStore

TARGET = "target"
RELATED = "related"


@dataclass(frozen=True)
class TargetHit:
    """One object worth going to. A copy of the values at the time of the
    call, so it does not change when the graph does."""

    object_id: ObjectId
    label: str
    kind: str                       # TARGET or RELATED
    task_score: float               # cos(object feature, task feature)
    position: np.ndarray            # (3,) centre of the object's 3D box, world frame, metres
    extent: np.ndarray              # (3,) full side lengths of that box, metres
    sightings: int
    # The stored photo that shows the object best, and the object's box on it,
    # xyxy in that photo's pixels. None if no photo of the object is left.
    anchor_id: Optional[AnchorId] = None
    box_on_anchor: Optional[np.ndarray] = None


class TargetFinder:
    """Answers `find` from an ObjectStore and an AnchorStore that share a graph,
    and holds the list of rejected objects.

    One call from outside needs a matching call here:
        ObjectStore.merge_objects(a, b)   then   TargetFinder.merge_objects(a, b)
    `check_invariants` reports it if that was forgotten.
    """

    def __init__(self, objects: ObjectStore, anchors: AnchorStore) -> None:
        if anchors.graph is not objects.graph:
            raise ValueError("the object store and the anchor store must share one graph")
        self.objects = objects
        self.anchors = anchors
        self._rejected: Set[ObjectId] = set()
        self._rejected_for: Optional[str] = None      # the instruction the list belongs to

    # ----------------------------------------------------------------- query

    @property
    def rejected(self) -> FrozenSet[ObjectId]:
        """Objects rejected under the current instruction."""
        self._follow_task()
        return frozenset(self._rejected)

    def find(self, include_related: bool = True) -> List[TargetHit]:
        """Every object of a target class, then every object of a related
        class, without the rejected ones. Within each group the highest task
        score comes first. Empty if no task is set."""
        self._follow_task()
        groups = [(TARGET, self.objects.target_ids())]
        if include_related:
            groups.append((RELATED, self.objects.related_ids()))
        hits: List[TargetHit] = []
        for kind, ids in groups:
            for obj in self.objects.ranked_by_task(ids - self._rejected):
                hits.append(self._hit(obj, kind))
        return hits

    def best_anchor(self, obj: ObjectId) -> Optional[AnchorId]:
        """The stored photo with the best view of `obj`, or None. Equal views
        go to the newest photo."""
        graph = self.objects.graph
        seen = [a for a in graph.anchors_of(obj) if a in self.anchors]
        if not seen:
            return None
        return max(seen, key=lambda a: (graph.sighting(a, obj).view_quality(), a))

    # ---------------------------------------------------------------- mutate

    def reject(self, obj: ObjectId) -> None:
        """The write-back: the robot went to `obj` and it was not what the task
        asked for. `find` leaves it out until the instruction changes."""
        self._follow_task()
        if obj not in self.objects:
            raise KeyError(f"no object entry with id {obj}")
        self._rejected.add(obj)

    def clear_rejected(self) -> None:
        self._rejected.clear()

    def merge_objects(self, surviving: ObjectId, absorbed: ObjectId) -> None:
        """Follow ObjectStore.merge_objects. If either half was rejected, the
        merged entry is: it is the same physical object."""
        if absorbed in self._rejected:
            self._rejected.discard(absorbed)
            self._rejected.add(surviving)

    # ------------------------------------------------------------ invariants

    def check_invariants(self) -> List[str]:
        """Empty means consistent. Only the rejected list is checked here: the
        stores have their own checks."""
        return [f"rejected object {obj} has no entry"
                for obj in sorted(self._rejected) if obj not in self.objects]

    # -------------------------------------------------------------- internal

    def _follow_task(self) -> None:
        """Empty the rejected list when the instruction has changed. New class
        sets for the same instruction keep it."""
        task = self.objects.task
        instruction = task.instruction if task is not None else None
        if instruction != self._rejected_for:
            self._rejected.clear()
            self._rejected_for = instruction

    def _hit(self, obj: ObjectId, kind: str) -> TargetHit:
        entry = self.objects.get(obj)
        anchor = self.best_anchor(obj)
        box = None if anchor is None else self.anchors.get(anchor).object_boxes.get(obj)
        return TargetHit(
            object_id=obj, label=entry.label, kind=kind, task_score=entry.task_score,
            position=np.array(entry.box.center, dtype=np.float64),
            extent=np.array(entry.box.extent, dtype=np.float64),
            sightings=entry.sightings,
            anchor_id=anchor, box_on_anchor=None if box is None else box.copy(),
        )
