"""Every tuning constant of the memory graph, in one place (T6.3a).

Defaults are HiCo-Nav's values from cfg/hm3d.yaml at commit ffc1517, or the
constant upstream hardcodes, unless the comment says otherwise. Upstream ran in
a simulator with a 120 degree, 640x640 camera. Ours is a D455, so expect T6.4
to retune several of these on the recorded drive.

Override from a dict or a YAML file:

    cfg = MemoryGraphConfig.from_dict({"sim_threshold": 0.7})
    cfg = MemoryGraphConfig.load("my_overrides.yaml")    # needs PyYAML

An unknown key is an error, so a typo cannot silently fall back to a default.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace
from typing import Any, Mapping, Tuple


@dataclass(frozen=True)
class MemoryGraphConfig:
    # ---- S2 detection filtering -------------------------------------------
    bg_classes: Tuple[str, ...] = ("wall", "floor", "ceiling", "carpet", "rug", "bath mat")
    skip_bg: bool = True
    # A box smaller than this fraction of the image area is dropped.
    min_box_area_ratio: float = 0.0001
    # Below this confidence a detection is dropped, unless its label is a target.
    confidence_threshold: float = 0.3

    # ---- S3 anchor gate ---------------------------------------------------
    # Upstream hardcodes 1 m and 45 degrees (map.py:513).
    gate_translation_m: float = 1.0
    gate_rotation_rad: float = math.pi / 4

    # ---- S4 and S5 masks --------------------------------------------------
    # Erode each mask by one pixel (keep a pixel only if its 3x3 block is set).
    erode_masks: bool = True
    # A mask is dropped if its area is below min(ratio * H * W, threshold px).
    mask_area_threshold_px: int = 25
    mask_area_ratio: float = 0.0001
    # A mask is dropped if its IoU with an already kept mask is above this.
    mask_iou_threshold: float = 0.9
    # Box j counts as inside box i when overlap / area_j > inner and
    # overlap / area_i < outer. Then mask j is cut out of mask i.
    # Upstream hardcodes 0.8 and 0.7 (map_utils.py:295).
    contain_inner_ratio: float = 0.8
    contain_outer_ratio: float = 0.7

    # ---- S6 image feature -------------------------------------------------
    # Crop padding per side as a fraction of the box's width and height.
    # Not upstream: upstream pads a fixed 20 px, which does not scale with
    # resolution. 0.1 is a starting guess, tuned in T6.4.
    crop_pad_ratio: float = 0.1

    # ---- S7 back-projection -----------------------------------------------
    # A mask with fewer valid depth pixels than this gives no object.
    min_points: int = 16
    # Cap on points per object before the pose transform (every k-th point).
    max_points: int = 5000

    # ---- S8 point-cloud cleanup and 3D box --------------------------------
    voxel_size_m: float = 0.02
    dbscan_remove_noise: bool = True
    dbscan_eps_m: float = 0.1
    dbscan_min_points: int = 10
    # If the largest cluster has fewer points than this, keep the cloud as is.
    dbscan_min_cluster_keep: int = 5
    # A candidate whose box is smaller than this is dropped (pointcloud.py:138).
    min_box_volume_m3: float = 1e-6

    # ---- S9 range filter --------------------------------------------------
    # Objects whose box centre is further than this from the camera are dropped.
    # Upstream's 6 m comes from simulated depth. Check it against the D455.
    max_object_distance_m: float = 6.0

    # ---- S10 association --------------------------------------------------
    # A candidate point "overlaps" an object if the object has a point this close.
    # Upstream hardcodes 2.5 cm (pointcloud.py:672).
    match_radius_m: float = 0.025
    # score = (1 + phys_bias) * overlap + (1 - phys_bias) * appearance
    phys_bias: float = 0.5
    # A candidate merges into its best object only above this score.
    sim_threshold: float = 0.6
    # "greedy": upstream. Each candidate takes its best object, so two
    #           candidates from one photo can merge into the same object.
    # "one_to_one": each object takes at most one candidate per photo.
    # Decided 2026-10-07: greedy (D-MG8 in docs/MEMORY_GRAPH_DESIGN.md). T6.4 may
    # compare the two on the recorded drive.
    association_mode: str = "greedy"

    def __post_init__(self) -> None:
        if self.association_mode not in ("greedy", "one_to_one"):
            raise ValueError(f"association_mode must be 'greedy' or 'one_to_one', got {self.association_mode!r}")
        if not 0.0 <= self.phys_bias <= 1.0:
            raise ValueError("phys_bias must be in [0, 1]")
        for name in ("voxel_size_m", "dbscan_eps_m", "match_radius_m", "gate_translation_m"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> "MemoryGraphConfig":
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(values) - known)
        if unknown:
            raise KeyError(f"unknown memory graph config keys: {unknown}")
        values = dict(values)
        if "bg_classes" in values:
            values["bg_classes"] = tuple(values["bg_classes"])
        return replace(cls(), **values)

    @classmethod
    def load(cls, path: str) -> "MemoryGraphConfig":
        import yaml  # only needed for this path

        with open(path) as f:
            return cls.from_dict(yaml.safe_load(f) or {})
