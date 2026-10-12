"""S13: periodic clean-up (T6.4f). Denoise the objects, prune redundant anchors.

Two kinds of clutter build up as photos come in:

    stray points   Each merge joins a new cloud to an object's cloud. A few
                   wrong points per photo (a mask that spilled onto the wall)
                   stay for good, because merging never removes points.
    extra photos   The same objects get photographed again and again. Most of
                   those photos show nothing that another kept photo does not.

So every cfg.cleanup_every_photos stored photos:

    1. every object's cloud is voxel-downsampled and cut to its largest
       cluster, and its box is refitted (ObjectStore.denoise)
    2. anchors are pruned: the fewest photos are kept such that every object
       is still seen by min(kappa, photos that saw it) of them. kappa is
       cfg.prune_kappa. The rest are deleted, records and edges.

Objects are never deleted here, only photos. The rule in step 2 keeps every
object at least one photo.

Upstream: Map.periodic_cleanup_objects (map.py:965), denoising at
pointcloud.py:787, pruning at map.py:915.

Differences from upstream, on purpose:
  - Pruning is the greedy multicover in AnchorObjectGraph.prune. Upstream
    solves the same problem exactly with PuLP and CBC, with no time limit.
    Decided 2026-10-05, D-MG3 in docs/MEMORY_GRAPH_DESIGN.md.
  - kappa is a config value. Upstream writes 1 at the call site.
  - So is the interval. Upstream hardcodes 10.
  - Of two photos that are equally useful, the one with the better view of
    its objects is kept. Upstream's solver has no preference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from memory_graph.anchor_object_graph import AnchorId, ObjectId
from memory_graph.anchor_store import AnchorStore
from memory_graph.object_store import ObjectStore


@dataclass
class CleanupReport:
    """What one clean-up did."""

    objects_denoised: List[ObjectId] = field(default_factory=list)
    points_removed: int = 0
    anchors_before: int = 0
    anchors_evicted: List[AnchorId] = field(default_factory=list)

    @property
    def anchors_after(self) -> int:
        return self.anchors_before - len(self.anchors_evicted)


def denoise_objects(objects: ObjectStore, report: Optional[CleanupReport] = None) -> CleanupReport:
    """Step 1: denoise every entry."""
    report = report if report is not None else CleanupReport()
    for obj in objects.ids():
        removed = objects.denoise(obj)
        if removed:
            report.objects_denoised.append(obj)
            report.points_removed += removed
    return report


VIEW_COST_RANGE = 0.001


def view_cost(objects: ObjectStore, anchor: AnchorId) -> float:
    """The price of keeping a photo, for the pruning step. Between 1 and
    1.001, lower for a photo with better views of its objects. The range is
    that narrow so the price only decides between photos that would cover the
    same number of objects: more objects always wins.

    A photo's view of an object is good if it is the object's best view, or
    close to it: view quality divided by the best view quality that object has.
    """
    graph = objects.graph
    shown = graph.objects_of(anchor)
    if not shown:
        return 1.0 + VIEW_COST_RANGE
    total = 0.0
    for obj in shown:
        best = max(graph.sighting(a, obj).view_quality() for a in graph.anchors_of(obj))
        total += graph.sighting(anchor, obj).view_quality() / best if best > 0 else 1.0
    return 1.0 + VIEW_COST_RANGE * (1.0 - total / len(shown))


def prune_anchors(
    objects: ObjectStore, anchors: AnchorStore, kappa: int, report: Optional[CleanupReport] = None
) -> CleanupReport:
    """Step 2: keep the fewest photos that still show every object
    min(kappa, photos that saw it) times, and delete the rest."""
    if anchors.graph is not objects.graph:
        raise ValueError("the object store and the anchor store must share one graph")
    report = report if report is not None else CleanupReport()
    report.anchors_before = len(anchors)
    costs = {anchor: view_cost(objects, anchor) for anchor in objects.graph.anchors()}
    objects.graph.prune(kappa=kappa, cost=costs.__getitem__)
    report.anchors_evicted = anchors.drop_pruned()
    return report


class PeriodicCleanup:
    """Counts stored photos and runs the clean-up every cfg.cleanup_every_photos.

        cleanup = PeriodicCleanup(objects, anchors)
        ...
        if anchors.add(obs, dets, cands, ids) is not None:
            report = cleanup.photo_stored()      # None, except every N-th time
    """

    def __init__(self, objects: ObjectStore, anchors: AnchorStore) -> None:
        if anchors.graph is not objects.graph:
            raise ValueError("the object store and the anchor store must share one graph")
        self.objects = objects
        self.anchors = anchors
        self.cfg = objects.cfg
        self.photos_since_cleanup = 0

    def photo_stored(self) -> Optional[CleanupReport]:
        """Call once for each photo stored as an anchor. Runs the clean-up when
        it is due and returns its report, else returns None."""
        self.photos_since_cleanup += 1
        if self.photos_since_cleanup < self.cfg.cleanup_every_photos:
            return None
        return self.run()

    def run(self) -> CleanupReport:
        """The clean-up, now. Also restarts the count."""
        self.photos_since_cleanup = 0
        report = denoise_objects(self.objects)
        return prune_anchors(self.objects, self.anchors, self.cfg.prune_kappa, report)
