"""S11: insert or merge (T6.4c). The objects, and the graph that links them to anchors.

S10 says which stored object each new candidate is, or that it is new. This file
applies that answer. A new candidate becomes an entry with a fresh id. A matched
one is fused into its entry (map.py:475, map_elements.py:139):

    points    joined, then voxel-downsampled, so the cloud stays bounded
    box       refitted to the joined cloud
    feature   the average over sightings, re-normalised
    label     the majority vote over every sighting's label

Every change to the anchor-object edges goes through AnchorObjectGraph's
`observe` and `merge_objects`, so both lookup directions stay in step.

Points are stored in world coordinates, as upstream (D-MG9 in
docs/MEMORY_GRAPH_DESIGN.md, decided 2026-10-07). A point is fixed in the map
frame when it is added, and nothing here moves it later. To keep that decision
changeable, each sighting records the anchor it came from (`anchor_ids`), so an
entry can be rebuilt from its anchors if their poses are ever corrected.

Differences from upstream, on purpose:
  - The feature is re-normalised after every merge. Upstream leaves the mean
    un-normalised, which is only safe with cosine similarity.
  - The per-label index is rebuilt when an entry's majority label changes.
    Upstream adds the new label and never removes the old one.
  - No DBSCAN here, as upstream (run_dbscan=False). That is S13 (T6.4f).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Set

import numpy as np

from memory_graph.anchor_object_graph import AnchorId, AnchorObjectGraph, ObjectId, Sighting
from memory_graph.association import associate
from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import fit_box, voxel_downsample
from memory_graph.stage_types import Candidate, OrientedBox


@dataclass
class ObjectEntry:
    """One physical object, fused from every sighting of it.

    `labels`, `confs` and `anchor_ids` have one item per sighting, in the order
    the sightings arrived.
    """

    id: ObjectId
    points: np.ndarray               # float (M, 3), world frame
    colors: np.ndarray               # float (M, 3), in [0, 1]
    box: OrientedBox
    labels: List[str] = field(default_factory=list)
    confs: List[float] = field(default_factory=list)
    anchor_ids: List[AnchorId] = field(default_factory=list)
    # Sum of the unit feature of every sighting that had one, and how many did.
    clip_sum: Optional[np.ndarray] = None
    clip_count: int = 0

    @property
    def sightings(self) -> int:
        return len(self.labels)

    @property
    def label(self) -> str:
        """The label most sightings gave. A tie goes to the label seen first."""
        return Counter(self.labels).most_common(1)[0][0]

    @property
    def clip(self) -> Optional[np.ndarray]:
        """The average feature over sightings, L2-normalised. None if no sighting
        carried a feature. All zeros if the features cancelled out exactly."""
        if self.clip_sum is None:
            return None
        norm = np.linalg.norm(self.clip_sum)
        return self.clip_sum / norm if norm > 0 else np.zeros_like(self.clip_sum)


def _unit(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


class ObjectStore:
    """Every object entry, the anchor-object graph, and an index by label."""

    def __init__(self, cfg: MemoryGraphConfig, graph: Optional[AnchorObjectGraph] = None) -> None:
        self.cfg = cfg
        self.graph = graph if graph is not None else AnchorObjectGraph()
        self._objects: Dict[ObjectId, ObjectEntry] = {}
        self._by_label: Dict[str, Set[ObjectId]] = defaultdict(set)
        self._next_id: ObjectId = 0          # never reused, even after a merge

    # ----------------------------------------------------------------- query

    def __len__(self) -> int:
        return len(self._objects)

    def __contains__(self, obj: ObjectId) -> bool:
        return obj in self._objects

    def get(self, obj: ObjectId) -> ObjectEntry:
        return self._objects[obj]

    def ids(self) -> List[ObjectId]:
        return sorted(self._objects)

    def entries(self) -> List[ObjectEntry]:
        """Every entry, in id order. The order S10's match columns refer to."""
        return [self._objects[i] for i in self.ids()]

    def ids_with_label(self, label: str) -> FrozenSet[ObjectId]:
        """Entries whose majority label is `label`."""
        return frozenset(self._by_label.get(label, ()))

    # ---------------------------------------------------------------- mutate

    def integrate(self, candidates: Sequence[Candidate], anchor: AnchorId) -> List[ObjectId]:
        """S10 then S11 for one photo. Returns the entry each candidate went to,
        in candidate order."""
        ids = self.ids()
        columns = associate(candidates, [self._objects[i] for i in ids], self.cfg)
        return self.apply(candidates, [None if c is None else ids[c] for c in columns], anchor)

    def apply(
        self, candidates: Sequence[Candidate], targets: Sequence[Optional[ObjectId]], anchor: AnchorId
    ) -> List[ObjectId]:
        """S11: `targets[i]` is the entry candidate i merges into, or None for a
        new entry. Returns the entry each candidate went to.

        All of one photo's matches are decided before any is applied, so two new
        candidates from the same photo never merge with each other here.
        """
        if len(targets) != len(candidates):
            raise ValueError("targets must have one item per candidate")
        unknown = sorted({t for t in targets if t is not None and t not in self._objects})
        if unknown:
            raise KeyError(f"no object entries with ids {unknown}")
        out: List[ObjectId] = []
        for cand, target in zip(candidates, targets):
            if target is None:
                target = self._insert(cand)
            else:
                self._fuse_cloud(self._objects[target], cand.points, cand.colors)
            self._add_sighting(self._objects[target], cand, anchor)
            out.append(target)
        return out

    def merge_objects(self, surviving: ObjectId, absorbed: ObjectId) -> None:
        """Fold one entry into another: two entries turned out to be one object.
        The absorbed entry's sightings and anchor edges move to the survivor."""
        if surviving == absorbed:
            return
        keep, gone = self._objects[surviving], self._objects[absorbed]
        old_label = keep.label
        self._fuse_cloud(keep, gone.points, gone.colors)
        keep.labels += gone.labels
        keep.confs += gone.confs
        keep.anchor_ids += gone.anchor_ids
        if gone.clip_sum is not None:
            keep.clip_sum = gone.clip_sum if keep.clip_sum is None else keep.clip_sum + gone.clip_sum
            keep.clip_count += gone.clip_count
        self.graph.merge_objects(surviving, absorbed)
        self._unindex(absorbed, gone.label)
        del self._objects[absorbed]
        self._reindex(keep, old_label)

    # ------------------------------------------------------------ invariants

    def check_invariants(self) -> List[str]:
        """Violations in the graph, the entries and the label index. Empty means
        consistent. An entry with no anchor left is allowed: pruning (S13)
        removes anchors, not objects."""
        problems = self.graph.check_invariants()
        for obj in sorted(self.graph.objects() - set(self._objects)):
            problems.append(f"graph holds object {obj} that has no entry")
        for obj, entry in self._objects.items():
            if not (len(entry.labels) == len(entry.confs) == len(entry.anchor_ids)):
                problems.append(f"object {obj} has unequal per-sighting lists")
            if obj not in self._by_label.get(entry.label, ()):
                problems.append(f"object {obj} missing from the label index under {entry.label!r}")
        for label, ids in self._by_label.items():
            for obj in ids:
                if obj not in self._objects or self._objects[obj].label != label:
                    problems.append(f"label index holds stale {label!r} -> {obj}")
        return problems

    # -------------------------------------------------------------- internal

    def _insert(self, cand: Candidate) -> ObjectId:
        obj = self._next_id
        self._next_id += 1
        self._objects[obj] = ObjectEntry(
            id=obj,
            points=np.asarray(cand.points, dtype=np.float64),
            colors=np.asarray(cand.colors, dtype=np.float64),
            box=cand.box,
        )
        return obj

    def _fuse_cloud(self, entry: ObjectEntry, points: np.ndarray, colors: np.ndarray) -> None:
        entry.points, entry.colors = voxel_downsample(
            np.vstack([entry.points, points]), np.vstack([entry.colors, colors]), self.cfg.voxel_size_m
        )
        entry.box = fit_box(entry.points)

    def _add_sighting(self, entry: ObjectEntry, cand: Candidate, anchor: AnchorId) -> None:
        old_label = entry.label if entry.labels else None
        entry.labels.append(cand.label)
        entry.confs.append(float(cand.conf))
        entry.anchor_ids.append(anchor)
        if cand.clip is not None:
            unit = _unit(cand.clip)
            entry.clip_sum = unit if entry.clip_sum is None else entry.clip_sum + unit
            entry.clip_count += 1
        self.graph.observe(anchor, entry.id, Sighting(mask_pixels=cand.mask_pixels, confidence=float(cand.conf)))
        self._reindex(entry, old_label)

    def _unindex(self, obj: ObjectId, label: str) -> None:
        self._by_label[label].discard(obj)
        if not self._by_label[label]:
            del self._by_label[label]

    def _reindex(self, entry: ObjectEntry, old_label: Optional[str]) -> None:
        if old_label is not None and old_label != entry.label:
            self._unindex(entry.id, old_label)
        self._by_label[entry.label].add(entry.id)
