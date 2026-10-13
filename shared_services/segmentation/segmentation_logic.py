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

# Depth encodings the service accepts: (numpy type of one pixel, metres per unit). 16UC1 and
# mono16 are millimetres and 32FC1 is metres, the ROS convention (REP 118), which the RealSense
# driver follows. Add an encoding here and the service accepts it.
DEPTH_ENCODINGS = {"16UC1": (np.uint16, 0.001), "mono16": (np.uint16, 0.001),
                   "32FC1": (np.float32, 1.0)}


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
    """A depth image in metres, as float32. 0 and NaN still mean "no reading".

    The encoding must be in DEPTH_ENCODINGS: the service's read_request refuses any other.
    """
    return depth.astype(np.float32) * DEPTH_ENCODINGS[encoding][1]


def median_depth(depth_m: np.ndarray, mask: np.ndarray, min_valid_fraction: float = 0.0) -> float:
    """Median of the valid readings under the mask, in metres. NaN if fewer than
    min_valid_fraction of the mask's pixels have a reading, or none do.

    A RealSense pixel with no reading is 0, so 0 is skipped along with NaN. The median, not the
    mean, because the worst readings sit at the mask's edges: pixels that slipped onto the table
    behind, and "flying pixels" whose depth lands between object and background. They are a
    minority, so the median ignores them where the mean would be pulled toward them.

    The median only works while they are a minority. An object closer than the camera's minimum
    range has no readings of its own, so the few left are background: the wrist camera reported
    a box at 0.15 m as 1.26 m (T1.24 3b, 2026-10-13). min_valid_fraction gives NaN instead.
    """
    if depth_m.shape != mask.shape:
        raise ValueError(f"depth is {depth_m.shape}, mask is {mask.shape}")
    values = depth_m[mask]
    total = values.size
    values = values[np.isfinite(values) & (values > 0)]
    if values.size == 0 or values.size < min_valid_fraction * total:
        return math.nan
    return float(np.median(values))


def back_project(u: float, v: float, z: float, k: Sequence[float]) -> Tuple[float, float, float]:
    """Pixel (u, v) at depth z metres -> (x, y, z) in the camera's optical frame.

    k is CameraInfo.k, the 3x3 intrinsics matrix flattened row by row. Pinhole model:
    x right, y down, z out of the lens.
    """
    # ponytail: lens distortion (CameraInfo.d) is ignored and K is used as the driver reports it.
    # The error is likely a few mm near the image edges [inferred]. If grasps near the edges miss,
    # recalibrate the intrinsics and undistort (u, v) first, e.g. with cv2.undistortPoints.
    fx, cx, fy, cy = k[0], k[2], k[4], k[5]
    return ((u - cx) * z / fx, (v - cy) * z / fy, z)


def has_intrinsics(k: Optional[Sequence[float]]) -> bool:
    """False for a missing or all-zero K, which is how a request says "no camera_info"."""
    return k is not None and k[0] != 0 and k[4] != 0


def centroid_on_mask(det: Detection) -> bool:
    """True if the centroid pixel lies on the mask.

    False for a ring or L-shaped object, whose centroid can fall in a hole or a corner. The depth
    is still the object's (the median under the mask), so the 3D point then floats in empty space
    at the object's distance. AnyGrasp uses the mask and is not affected. Anything that aims at
    the centroid, like the grasp state machine via /object_centroid_2d, is.
    """
    return bool(det.mask[int(round(det.v)), int(round(det.u))])


def describe_mask(
    mask: np.ndarray,
    score: float,
    depth_m: Optional[np.ndarray] = None,
    k: Optional[Sequence[float]] = None,
    min_valid_fraction: float = 0.0,
) -> Optional[Detection]:
    """One mask -> a Detection. None for an empty mask, which has no centroid.

    The point is the centroid pixel at the median depth under the mask, not the object's own
    centre. centroid_on_mask says when the two differ.
    """
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
        det.depth_m = median_depth(depth_m, mask, min_valid_fraction)
        if has_intrinsics(k) and not math.isnan(det.depth_m):
            det.point = back_project(det.u, det.v, det.depth_m, k)
    return det


def detections_from_sam3(
    state: Mapping[str, Any],
    min_score: float,
    max_detections: int,
    depth_m: Optional[np.ndarray] = None,
    k: Optional[Sequence[float]] = None,
    min_valid_fraction: float = 0.0,
) -> List[Detection]:
    """SAM 3's result for one image -> Detections, best score first.

    state is what SAM3Model.process_text_prompt returns: "masks" (N, 1, H, W) or (N, H, W),
    "scores" (N,). Scores below min_score and empty masks are dropped, and at most
    max_detections are kept. Depth and the 3D point are filled in only when depth_m is given
    (and K, for the point), and only where at least min_valid_fraction of the mask has depth.
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
        det = describe_mask(masks[i], scores[i], depth_m, k, min_valid_fraction)
        if det is not None:
            found.append(det)
            if len(found) == max_detections:
                break
    return found
