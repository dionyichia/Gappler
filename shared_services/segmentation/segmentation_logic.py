"""The segmentation service's maths, with no ROS and no torch (T2.1 step 2).

segmentation_service.py turns a Segment request into numpy arrays, calls SAM 3, passes its
result through detections_from_sam3, and turns the Detections back into messages. Everything
in between lives here, so it can be tested on any machine with numpy:

    python -m unittest discover -s shared_services/segmentation -p "test_*.py"

The service serves every camera, so nothing here reads one camera's settings. Depth units come
from the image's own encoding, and the 3D point is in the optical frame of whichever camera
took the image.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, List, Mapping, Optional, Sequence, Tuple

import numpy as np

# Metres per depth unit, by ROS image encoding. 16UC1 is millimetres and 32FC1 is metres,
# the ROS convention (REP 118), which the RealSense driver follows.
DEPTH_SCALE_BY_ENCODING = {"16UC1": 0.001, "mono16": 0.001, "32FC1": 1.0}


@dataclass
class Detection:
    """One object SAM 3 found. Plain-Python twin of segmentation_interfaces/msg/Detection."""

    mask: np.ndarray                     # bool, H x W, True = object
    score: float                         # SAM 3 confidence, 0 to 1
    bbox: Tuple[int, int, int, int]      # x, y, width, height in pixels
    area_px: int                         # mask pixel count
    u: float                             # centroid pixel column
    v: float                             # centroid pixel row
    depth_m: float = math.nan            # median depth under the mask. NaN when unknown
    point: Optional[Tuple[float, float, float]] = None  # metres, camera optical frame


def as_numpy(value: Any) -> np.ndarray:
    """A numpy array from a numpy array, a list, or a torch tensor on any device.

    Same conversion as memory_graph/sam3_adapter.py, repeated here so the shared service does
    not depend on the memory graph. SAM 3 runs in bfloat16, which numpy cannot hold, so a
    floating tensor is widened to float32 first.
    """
    if hasattr(value, "detach"):  # a torch tensor
        value = value.detach()
        if value.is_floating_point():
            value = value.float()
        return value.cpu().numpy()
    return np.asarray(value)


def depth_in_metres(depth: np.ndarray, encoding: str) -> np.ndarray:
    """A depth image in metres, as float32. 0 and NaN still mean "no reading"."""
    if encoding not in DEPTH_SCALE_BY_ENCODING:
        raise ValueError(
            f"depth encoding {encoding!r} not supported, expected one of "
            f"{sorted(DEPTH_SCALE_BY_ENCODING)}"
        )
    return depth.astype(np.float32) * DEPTH_SCALE_BY_ENCODING[encoding]


def median_depth(depth_m: np.ndarray, mask: np.ndarray) -> float:
    """Median of the valid readings under the mask, in metres. NaN if there are none.

    A RealSense pixel with no reading is 0, so 0 is skipped along with NaN.
    """
    if depth_m.shape != mask.shape:
        raise ValueError(f"depth is {depth_m.shape}, mask is {mask.shape}")
    values = depth_m[mask]
    values = values[np.isfinite(values) & (values > 0)]
    return float(np.median(values)) if values.size else math.nan


def back_project(u: float, v: float, z: float, k: Sequence[float]) -> Tuple[float, float, float]:
    """Pixel (u, v) at depth z metres -> (x, y, z) in the camera's optical frame.

    k is CameraInfo.k, the 3x3 intrinsics matrix flattened row by row. Pinhole model:
    x right, y down, z out of the lens.
    """
    fx, cx, fy, cy = k[0], k[2], k[4], k[5]
    return ((u - cx) * z / fx, (v - cy) * z / fy, z)


def has_intrinsics(k: Optional[Sequence[float]]) -> bool:
    """False for a missing or all-zero K, which is how a request says "no camera_info"."""
    return k is not None and k[0] != 0 and k[4] != 0


def describe_mask(
    mask: np.ndarray,
    score: float,
    depth_m: Optional[np.ndarray] = None,
    k: Optional[Sequence[float]] = None,
) -> Optional[Detection]:
    """One mask -> a Detection. None for an empty mask, which has no centroid."""
    ys, xs = np.nonzero(mask)
    if xs.size == 0:
        return None
    x0, y0 = int(xs.min()), int(ys.min())
    det = Detection(
        mask=mask,
        score=float(score),
        bbox=(x0, y0, int(xs.max()) - x0 + 1, int(ys.max()) - y0 + 1),
        area_px=int(xs.size),
        u=float(xs.mean()),
        v=float(ys.mean()),
    )
    if depth_m is not None:
        det.depth_m = median_depth(depth_m, mask)
        if has_intrinsics(k) and not math.isnan(det.depth_m):
            det.point = back_project(det.u, det.v, det.depth_m, k)
    return det


def detections_from_sam3(
    state: Mapping[str, Any],
    min_score: float,
    max_detections: int,
    depth_m: Optional[np.ndarray] = None,
    k: Optional[Sequence[float]] = None,
) -> List[Detection]:
    """SAM 3's result for one image -> Detections, best score first.

    state is what SAM3Model.process_text_prompt returns: "masks" (N, 1, H, W) or (N, H, W),
    "scores" (N,). Scores below min_score and empty masks are dropped, and at most
    max_detections are kept. Depth and the 3D point are filled in only when depth_m is given
    (and K, for the point).
    """
    if state.get("masks") is None:
        return []
    masks = as_numpy(state["masks"])
    if masks.size == 0:
        return []
    masks = masks.reshape(len(masks), *masks.shape[-2:]) > 0
    scores = as_numpy(state["scores"]).astype(float).reshape(-1)
    if len(scores) != len(masks):
        raise ValueError(f"{len(masks)} masks but {len(scores)} scores")
    found = []
    for i in np.argsort(-scores, kind="stable"):
        if scores[i] < min_score:
            break
        det = describe_mask(masks[i], scores[i], depth_m, k)
        if det is not None:
            found.append(det)
            if len(found) == max_detections:
                break
    return found
