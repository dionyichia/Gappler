"""Bipartite incidence graph between visual anchors and 3D objects.

This is the data structure HiCo-Nav's `map/` package builds by hand out of two
independent `Set[int]` fields (`Keyframe.objects_3d` and `Object3D.observers`).
Here the edge is stored once and both lookup directions are derived from it, so
the two directions cannot disagree.

Stdlib only, on purpose: this runs at bench level L0-L2 with no ROS and no
solver dependency.

Vocabulary, matching the paper (HiCo-Nav section III-B):
  anchor  - a selected RGB keyframe, a compact visual memory unit
  object  - a 3D point cloud plus a semantic feature
  edge    - "this anchor observed this object"
  kappa   - how many anchors we want to keep per object (paper's greek k)
  r_j     - the coverage requirement actually imposed on object j,
            min(kappa, degree(j)); see `coverage_requirements`
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, FrozenSet, Iterable, Iterator, List, Optional, Set, Tuple

AnchorId = int
ObjectId = int
Edge = Tuple[AnchorId, ObjectId]


@dataclass(frozen=True)
class Sighting:
    """What one anchor recorded about one object. The per-edge payload.

    Upstream has nowhere to put any of this: an edge there is a bare integer in
    a set, so "which anchor gives the best view of this object" is unanswerable.
    """

    detections: int = 1          # times this object was matched in this anchor
    mask_pixels: int = 0         # apparent size in that anchor's image
    confidence: float = 0.0      # detector confidence for that sighting
    occluded_fraction: float = 0.0

    def view_quality(self) -> float:
        """Rough "how useful is this image for asking a VLM about this object".

        Deliberately simple. The point of the design is that there is a place
        for this number at all, not that this particular formula is right.
        """
        return self.confidence * (1.0 - self.occluded_fraction) * float(self.mask_pixels)

    def combined_with(self, other: "Sighting") -> "Sighting":
        """Fuse two sightings that collide when objects merge."""
        return Sighting(
            detections=self.detections + other.detections,
            mask_pixels=max(self.mask_pixels, other.mask_pixels),
            confidence=max(self.confidence, other.confidence),
            occluded_fraction=min(self.occluded_fraction, other.occluded_fraction),
        )


class InvariantViolation(RuntimeError):
    pass


class AnchorObjectGraph:
    """Bipartite incidence index with atomic mutation.

    The edge dict is the single source of truth. `_by_anchor` and `_by_object`
    are private caches that only the four mutating methods touch, so no caller
    can update one direction and forget the other.
    """

    __slots__ = ("_edges", "_by_anchor", "_by_object")

    def __init__(self) -> None:
        self._edges: Dict[Edge, Sighting] = {}
        self._by_anchor: Dict[AnchorId, Set[ObjectId]] = defaultdict(set)
        self._by_object: Dict[ObjectId, Set[AnchorId]] = defaultdict(set)

    # ---------------------------------------------------------------- mutate

    def observe(self, anchor: AnchorId, obj: ObjectId, sighting: Optional[Sighting] = None) -> None:
        """Record that `anchor` observed `obj`. Repeat calls fuse the sighting."""
        key = (anchor, obj)
        new = sighting if sighting is not None else Sighting()
        if key in self._edges:
            new = self._edges[key].combined_with(new)
        self._edges[key] = new
        self._by_anchor[anchor].add(obj)
        self._by_object[obj].add(anchor)

    def remove_anchor(self, anchor: AnchorId) -> int:
        """Evict an anchor and every edge touching it. Returns edges removed.

        This is what ILP pruning calls. Upstream's equivalent unwinds the edge
        from the anchor side only; here there is no anchor side to unwind
        separately.
        """
        removed = 0
        for obj in self._by_anchor.pop(anchor, set()):
            del self._edges[(anchor, obj)]
            peers = self._by_object[obj]
            peers.discard(anchor)
            if not peers:
                del self._by_object[obj]
            removed += 1
        return removed

    def remove_object(self, obj: ObjectId) -> int:
        removed = 0
        for anchor in self._by_object.pop(obj, set()):
            del self._edges[(anchor, obj)]
            peers = self._by_anchor[anchor]
            peers.discard(obj)
            if not peers:
                del self._by_anchor[anchor]
            removed += 1
        return removed

    def merge_objects(self, surviving: ObjectId, absorbed: ObjectId) -> None:
        """Fold `absorbed` into `surviving`, moving all its edges.

        `Object3D.merge` upstream unions `observers` on the surviving node, but
        nothing was found that rewrites the anchors pointing at the absorbed id.
        Doing both halves here is the whole point.
        """
        if surviving == absorbed:
            return
        for anchor in list(self._by_object.get(absorbed, ())):
            moved = self._edges[(anchor, absorbed)]
            self.observe(anchor, surviving, moved)
        self.remove_object(absorbed)

    # ----------------------------------------------------------------- query

    def objects_of(self, anchor: AnchorId) -> FrozenSet[ObjectId]:
        return frozenset(self._by_anchor.get(anchor, ()))

    def anchors_of(self, obj: ObjectId) -> FrozenSet[AnchorId]:
        return frozenset(self._by_object.get(obj, ()))

    def sighting(self, anchor: AnchorId, obj: ObjectId) -> Optional[Sighting]:
        return self._edges.get((anchor, obj))

    def degree(self, obj: ObjectId) -> int:
        """|{a_i : (a_i, o_j) in E}| - the count inside the paper's min()."""
        return len(self._by_object.get(obj, ()))

    def anchors(self) -> FrozenSet[AnchorId]:
        return frozenset(self._by_anchor)

    def objects(self) -> FrozenSet[ObjectId]:
        return frozenset(self._by_object)

    def best_anchor_for(self, obj: ObjectId) -> Optional[AnchorId]:
        """The edge attribute payoff: pick the image that shows `obj` best."""
        cands = self._by_object.get(obj)
        if not cands:
            return None
        return max(cands, key=lambda a: self._edges[(a, obj)].view_quality())

    def __len__(self) -> int:
        return len(self._edges)

    def __iter__(self) -> Iterator[Edge]:
        return iter(self._edges)

    # ------------------------------------------------------------ invariants

    def check_invariants(self) -> List[str]:
        """Return a list of violations. Empty list means consistent.

        Upstream cannot offer this, because with two hand-kept sets there is no
        third thing to check them against.
        """
        problems: List[str] = []
        for (anchor, obj) in self._edges:
            if obj not in self._by_anchor.get(anchor, ()):
                problems.append(f"edge ({anchor},{obj}) missing from anchor index")
            if anchor not in self._by_object.get(obj, ()):
                problems.append(f"edge ({anchor},{obj}) missing from object index")
        for anchor, objs in self._by_anchor.items():
            if not objs:
                problems.append(f"anchor {anchor} present with no objects")
            for obj in objs:
                if (anchor, obj) not in self._edges:
                    problems.append(f"anchor index holds dangling ({anchor},{obj})")
        for obj, anchors in self._by_object.items():
            if not anchors:
                problems.append(f"object {obj} present with no anchors")
            for anchor in anchors:
                if (anchor, obj) not in self._edges:
                    problems.append(f"object index holds dangling ({anchor},{obj})")
        return problems

    # -------------------------------------------------------------- pruning

    def coverage_requirements(self, kappa: int) -> Dict[ObjectId, int]:
        """r_j = min(kappa, degree(j)) for every object.

        The clamp is what keeps the program feasible: an object seen once can
        never satisfy a demand of three, and one such object would make the
        whole ILP infeasible rather than just its own constraint.
        """
        if kappa < 1:
            raise ValueError("kappa must be at least 1")
        return {obj: min(kappa, len(anchors)) for obj, anchors in self._by_object.items()}

    def prune(
        self,
        kappa: int = 1,
        cost: Optional[Callable[[AnchorId], float]] = None,
        apply: bool = True,
    ) -> Tuple[Set[AnchorId], Set[AnchorId]]:
        """Weighted set multicover by greedy. Returns (kept, evicted).

        Greedy picks the anchor with the best unmet-demand-per-unit-cost until
        every r_j is met. Standard H(n) approximation, no solver dependency. An
        exact PuLP path can replace this body without changing the signature.
        """
        demand = self.coverage_requirements(kappa)
        cost_of = cost or (lambda _a: 1.0)
        kept: Set[AnchorId] = set()
        available = set(self._by_anchor)

        while any(d > 0 for d in demand.values()):
            best, best_score = None, 0.0
            for anchor in available:
                gain = sum(1 for obj in self._by_anchor[anchor] if demand.get(obj, 0) > 0)
                if gain == 0:
                    continue
                score = gain / max(cost_of(anchor), 1e-9)
                if score > best_score:
                    best, best_score = anchor, score
            if best is None:
                break                      # demand unsatisfiable, clamp guards this
            kept.add(best)
            available.discard(best)
            for obj in self._by_anchor[best]:
                if demand.get(obj, 0) > 0:
                    demand[obj] -= 1

        evicted = set(self._by_anchor) - kept
        if apply:
            for anchor in evicted:
                self.remove_anchor(anchor)
        return kept, evicted

    def incidence(self) -> Dict[AnchorId, FrozenSet[ObjectId]]:
        """The `keyframe_to_objs` argument an external ILP wants."""
        return {a: frozenset(objs) for a, objs in self._by_anchor.items()}
