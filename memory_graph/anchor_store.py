"""S12: store each accepted photo as an anchor (T6.4d).

An anchor is the photo itself, kept so it can be looked at again later: the
image, the depth, the intrinsics and the pose. A later step can draw a box on
the stored image and lift it to 3D with the stored depth and intrinsics, the
same way S7 does (upstream's keyframe_2d_to_3d).

The anchor-object edges are already in the graph when a photo gets here.
ObjectStore made them in S11, through `observe`. This file adds the record on
the anchor side and checks that record and graph agree.

Upstream: map.py:866 and resize_camera in map_utils.py:18.

Differences from upstream, on purpose:
  - Depth is resized with nearest-neighbour. Upstream uses bilinear, which
    invents depths halfway between an object and the wall behind it.
  - The field of view is 2 atan(W / (2 fx)). Upstream stores 2 atan(W / fx).
  - Width and height are named, so they cannot be swapped. Upstream passes
    (height, width) to a function that takes (width, height).
  - Each anchor keeps the box of every object it shows, on the stored image.
  - A photo that ends up linked to no object is not stored. Upstream stores it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from memory_graph.anchor_object_graph import AnchorId, AnchorObjectGraph, ObjectId
from memory_graph.config import MemoryGraphConfig
from memory_graph.stage_types import Candidate, Detections, Observation


# ---------------------------------------------------------------- resizing
#
# A pixel's centre sits at its integer coordinate, as in geometry.camera_rays.
# So pixel u covers [u - 0.5, u + 0.5), and a resize by s maps u to
# s * (u + 0.5) - 0.5. The intrinsics, the boxes and the sampling below all use
# this one mapping.

def _source_coords(n_out: int, n_in: int) -> np.ndarray:
    """Where each output pixel centre falls in the input, as a float index."""
    return (np.arange(n_out, dtype=np.float64) + 0.5) * (n_in / n_out) - 0.5


def resize_nearest(image: np.ndarray, height: int, width: int) -> np.ndarray:
    """Each output pixel takes the value of the nearest input pixel. No value
    is blended, so depth edges stay sharp and 0 stays 0."""
    h, w = image.shape[:2]
    rows = np.clip(np.rint(_source_coords(height, h)), 0, h - 1).astype(np.int64)
    cols = np.clip(np.rint(_source_coords(width, w)), 0, w - 1).astype(np.int64)
    return image[rows][:, cols]


def resize_bilinear(image: np.ndarray, height: int, width: int) -> np.ndarray:
    """Blend the four nearest input pixels. For colour only, never for depth."""
    h, w = image.shape[:2]
    y = np.clip(_source_coords(height, h), 0, h - 1)
    x = np.clip(_source_coords(width, w), 0, w - 1)
    y0 = np.floor(y).astype(np.int64)
    x0 = np.floor(x).astype(np.int64)
    y1 = np.minimum(y0 + 1, h - 1)
    x1 = np.minimum(x0 + 1, w - 1)
    wy = (y - y0).reshape(-1, 1, *([1] * (image.ndim - 2)))
    wx = (x - x0).reshape(1, -1, *([1] * (image.ndim - 2)))
    src = image.astype(np.float64)
    top = src[y0][:, x0] * (1 - wx) + src[y0][:, x1] * wx
    bottom = src[y1][:, x0] * (1 - wx) + src[y1][:, x1] * wx
    out = top * (1 - wy) + bottom * wy
    if np.issubdtype(image.dtype, np.integer):
        out = np.rint(out)
    return out.astype(image.dtype)


def resize_intrinsics(K: np.ndarray, scale_x: float, scale_y: float) -> np.ndarray:
    """The intrinsics of the resized image."""
    out = np.array(K, dtype=np.float64, copy=True)
    out[0, 0] *= scale_x
    out[1, 1] *= scale_y
    out[0, 1] *= scale_x
    out[0, 2] = scale_x * (K[0, 2] + 0.5) - 0.5
    out[1, 2] = scale_y * (K[1, 2] + 0.5) - 0.5
    return out


def resize_boxes(xyxy: np.ndarray, scale_x: float, scale_y: float) -> np.ndarray:
    """Boxes moved onto the resized image."""
    out = np.asarray(xyxy, dtype=np.float64).reshape(-1, 4).copy()
    out[:, [0, 2]] = scale_x * (out[:, [0, 2]] + 0.5) - 0.5
    out[:, [1, 3]] = scale_y * (out[:, [1, 3]] + 0.5) - 0.5
    return out


# ---------------------------------------------------------------- the record

@dataclass
class AnchorRecord:
    """One stored photo. Everything here is at the stored size, which is not
    the size the camera gave."""

    id: AnchorId               # the photo's frame_id
    rgb: np.ndarray            # uint8 (h, w, 3), RGB order
    depth: np.ndarray          # float32 (h, w), metres, 0 = invalid
    K: np.ndarray              # (3, 3) intrinsics of the stored image
    T_world_cam: np.ndarray    # (4, 4) camera-to-world
    detections: Detections     # boxes on the stored image, no masks
    timestamp: float = 0.0
    # Sum over this photo's objects of similarity to the task, set by the caller
    # (T6.7a). 0 when no task is set.
    task_score: float = 0.0
    # The box of each object this photo shows, xyxy on the stored image. If two
    # detections went to one object, the box around both.
    object_boxes: Dict[ObjectId, np.ndarray] = field(default_factory=dict)

    @property
    def size(self) -> Tuple[int, int]:
        """(height, width) of the stored image."""
        return self.depth.shape

    @property
    def fov_x(self) -> float:
        """Horizontal field of view in radians: 2 atan(W / (2 fx))."""
        return 2.0 * math.atan(self.depth.shape[1] / (2.0 * self.K[0, 0]))

    @property
    def fov_y(self) -> float:
        return 2.0 * math.atan(self.depth.shape[0] / (2.0 * self.K[1, 1]))

    @property
    def labels(self) -> frozenset:
        """Every label detected in this photo."""
        return frozenset(self.detections.label)

    def project(self, point_world: Sequence[float]) -> Optional[np.ndarray]:
        """The pixel (u, v) on the stored image where a world point appears.
        None if the point is behind the camera. The pixel may be off the image."""
        R, t = self.T_world_cam[:3, :3], self.T_world_cam[:3, 3]
        cam = R.T @ (np.asarray(point_world, dtype=np.float64) - t)
        if cam[2] <= 0:
            return None
        uvw = self.K @ cam
        return uvw[:2] / uvw[2]


def _union(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.array([min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])])


# ---------------------------------------------------------------- the store

class AnchorStore:
    """Every anchor record. Shares the graph with the ObjectStore.

    Two calls change the graph's edges from outside this class, and each has a
    matching call here so the records follow:
        ObjectStore.merge_objects(a, b)   then   AnchorStore.merge_objects(a, b)
        graph.prune(...)                  then   AnchorStore.drop_pruned()
    `check_invariants` reports it if either was forgotten.
    """

    def __init__(self, cfg: MemoryGraphConfig, graph: AnchorObjectGraph) -> None:
        self.cfg = cfg
        self.graph = graph
        self._anchors: Dict[AnchorId, AnchorRecord] = {}

    # ----------------------------------------------------------------- query

    def __len__(self) -> int:
        return len(self._anchors)

    def __contains__(self, anchor: AnchorId) -> bool:
        return anchor in self._anchors

    def get(self, anchor: AnchorId) -> AnchorRecord:
        return self._anchors[anchor]

    def ids(self) -> List[AnchorId]:
        return sorted(self._anchors)

    def stored_size(self, height: int, width: int) -> Tuple[int, int]:
        """(height, width) a photo of this size is stored at. A config value of
        0 keeps the camera's own size on that side."""
        return (self.cfg.anchor_height or height, self.cfg.anchor_width or width)

    # ---------------------------------------------------------------- mutate

    def add(
        self,
        obs: Observation,
        dets: Detections,
        candidates: Sequence[Candidate],
        object_ids: Sequence[ObjectId],
        raw_detections: Optional[Detections] = None,
        task_score: float = 0.0,
    ) -> Optional[AnchorRecord]:
        """S12 for one photo. Call it after ObjectStore.integrate, with
        `anchor=obs.frame_id` there.

        `dets` are the detections the candidates were built from (after S5).
        `object_ids[i]` is the entry candidate i went to, which is what
        `integrate` returns. `raw_detections`, if given, are stored in place of
        `dets`: upstream keeps S1's output, from before any filtering.

        Returns None and stores nothing if the photo is linked to no object.
        """
        anchor = obs.frame_id
        if anchor in self._anchors:
            raise ValueError(f"anchor {anchor} is already stored")
        if len(object_ids) != len(candidates):
            raise ValueError("object_ids must have one item per candidate")
        if not candidates:
            return None
        linked = self.graph.objects_of(anchor)
        if set(object_ids) != set(linked):
            raise ValueError(
                f"anchor {anchor}: the graph links objects {sorted(linked)} but "
                f"{sorted(set(object_ids))} were passed. Run ObjectStore.integrate first, "
                "with anchor=obs.frame_id"
            )

        h, w = obs.depth.shape
        new_h, new_w = self.stored_size(h, w)
        sx, sy = new_w / w, new_h / h
        kept = raw_detections if raw_detections is not None else dets
        record = AnchorRecord(
            id=anchor,
            rgb=resize_bilinear(obs.rgb, new_h, new_w),
            depth=resize_nearest(obs.depth, new_h, new_w),
            K=resize_intrinsics(obs.K, sx, sy),
            T_world_cam=np.array(obs.T_world_cam, dtype=np.float64, copy=True),
            detections=Detections(
                xyxy=resize_boxes(kept.xyxy, sx, sy), conf=kept.conf.copy(),
                class_id=kept.class_id.copy(), label=list(kept.label),
            ),
            timestamp=obs.timestamp,
            task_score=float(task_score),
        )
        boxes = resize_boxes(dets.xyxy, sx, sy)
        for cand, obj in zip(candidates, object_ids):
            box = boxes[cand.detection_index]
            seen = record.object_boxes.get(obj)
            record.object_boxes[obj] = box if seen is None else _union(seen, box)
        self._anchors[anchor] = record
        return record

    def remove(self, anchor: AnchorId) -> None:
        """Delete an anchor and its edges."""
        self.graph.remove_anchor(anchor)
        del self._anchors[anchor]

    def drop_pruned(self) -> List[AnchorId]:
        """Delete the record of every anchor the graph no longer holds. Call it
        after `graph.prune`. Returns the ids dropped."""
        gone = sorted(set(self._anchors) - self.graph.anchors())
        for anchor in gone:
            del self._anchors[anchor]
        return gone

    def merge_objects(self, surviving: ObjectId, absorbed: ObjectId) -> None:
        """Follow ObjectStore.merge_objects: boxes of the absorbed object now
        belong to the survivor."""
        if surviving == absorbed:
            return
        for record in self._anchors.values():
            box = record.object_boxes.pop(absorbed, None)
            if box is None:
                continue
            seen = record.object_boxes.get(surviving)
            record.object_boxes[surviving] = box if seen is None else _union(seen, box)

    # ------------------------------------------------------------ invariants

    def check_invariants(self) -> List[str]:
        """Violations between the records and the graph. Empty means consistent.
        The graph's own check is not repeated here: ObjectStore runs it."""
        problems: List[str] = []
        for anchor in sorted(self.graph.anchors() - set(self._anchors)):
            problems.append(f"graph holds anchor {anchor} that has no record")
        for anchor, record in self._anchors.items():
            linked = self.graph.objects_of(anchor)
            if not linked:
                problems.append(f"anchor {anchor} has a record but no objects")
            elif set(record.object_boxes) != set(linked):
                problems.append(
                    f"anchor {anchor} has boxes for {sorted(record.object_boxes)} "
                    f"but the graph links {sorted(linked)}"
                )
            if record.rgb.shape[:2] != record.depth.shape:
                problems.append(f"anchor {anchor} has rgb and depth of different sizes")
        return problems
