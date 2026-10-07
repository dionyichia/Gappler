"""S0: a recording becomes posed observations (T6.3b).

Every later stage trusts what comes out of here: RGB in RGB order, depth in
metres with 0 as invalid, the colour camera's intrinsics, and a camera-to-world
pose. The four ways to get that wrong, from cmg_construction_pipeline.md S0, are
each handled in one place:

    BGR from OpenCV                      to_observation(bgr=True) flips it
    depth in sensor units                depth_to_metres, the scale is an argument
    world-to-camera passed as the pose   rigid_transform names the direction,
                                         and the done-when test catches a swap
    a frame conversion applied twice     the pose is composed once, in
                                         to_observation: T_world_base @ T_base_cam

The lab recording (T6.2) does not exist yet, so the one reader here is for the
TUM RGB-D benchmark's file layout (Sturm et al., IROS 2012), which is also what
ICL-NUIM ships in. A reader for the lab recording needs to do three things:
find the frames, read the files, and hand each frame to to_observation with the
D455's depth scale (1000 units per metre) and the camera mount transform.

Poses are taken as given. Nothing here filters, smooths or interpolates them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple, Union

import numpy as np

from memory_graph.stage_types import Observation

# ---------------------------------------------------------------- conversions


def depth_to_metres(raw: np.ndarray, units_per_metre: float) -> np.ndarray:
    """float32 metres, 0 where there is no reading.

    `raw` is the sensor's own depth image: uint16 with 1000 units per metre from
    a D455, 5000 from the TUM files, or already metres (units_per_metre = 1).
    Zero, negative, NaN and infinite readings all become 0.
    """
    if units_per_metre <= 0:
        raise ValueError("units_per_metre must be positive")
    depth = np.asarray(raw, dtype=np.float64) / units_per_metre
    depth[~np.isfinite(depth) | (depth <= 0)] = 0.0
    return depth.astype(np.float32)


def rigid_transform(translation: Sequence[float], quaternion_xyzw: Sequence[float]) -> np.ndarray:
    """A 4x4 transform from a position and a unit quaternion (x, y, z, w).

    If the pair is the camera's position and orientation in the world, the
    result is camera-to-world, which is what Observation wants. If a source
    gives the world's pose in the camera frame, invert the result first.
    """
    x, y, z, w = (float(v) for v in quaternion_xyzw)
    norm = np.sqrt(x * x + y * y + z * z + w * w)
    if norm < 1e-9:
        raise ValueError("quaternion has zero length")
    x, y, z, w = x / norm, y / norm, z / norm, w / norm
    T = np.eye(4)
    T[:3, :3] = [
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ]
    T[:3, 3] = translation
    return T


def _check_rigid(T: np.ndarray, name: str) -> np.ndarray:
    T = np.asarray(T, dtype=np.float64)
    if T.shape != (4, 4):
        raise ValueError(f"{name} must be 4x4, got {T.shape}")
    R = T[:3, :3]
    if not (np.allclose(R @ R.T, np.eye(3), atol=1e-6) and np.linalg.det(R) > 0
            and np.allclose(T[3], [0, 0, 0, 1])):
        raise ValueError(f"{name} is not a rotation plus a translation")
    return T


def to_observation(
    image: np.ndarray,
    depth_raw: np.ndarray,
    K: np.ndarray,
    T_world_base: np.ndarray,
    frame_id: int,
    timestamp: float = 0.0,
    *,
    depth_units_per_metre: float,
    bgr: bool,
    T_base_cam: Optional[np.ndarray] = None,
) -> Observation:
    """One recorded frame as an Observation. Every reader ends here.

    image: uint8 (H, W, 3). Say with `bgr` which channel order it is in.
    depth_raw: (H, W) in sensor units, aligned to the colour image.
    T_world_base: where localisation says the robot base is (base-to-world).
    T_base_cam: the camera mount, camera-to-base, OpenCV camera axes. Leave it
        out when the recorded pose is already the camera's.
    """
    image = np.asarray(image)
    if image.dtype != np.uint8 or image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"image must be uint8 (H, W, 3), got {image.dtype} {image.shape}")
    T = _check_rigid(T_world_base, "T_world_base")
    if T_base_cam is not None:
        T = T @ _check_rigid(T_base_cam, "T_base_cam")
    return Observation(
        rgb=np.ascontiguousarray(image[:, :, ::-1] if bgr else image),
        depth=depth_to_metres(depth_raw, depth_units_per_metre),
        K=np.asarray(K, dtype=np.float64).copy(),
        T_world_cam=T,
        frame_id=int(frame_id),
        timestamp=float(timestamp),
    )


# ---------------------------------------------------------------- TUM layout

# The benchmark's own advice for its registered depth images: use the ROS
# default intrinsics, with no undistortion. Its tool that makes point clouds
# uses these numbers.
TUM_ROS_DEFAULT_K = np.array([[525.0, 0.0, 319.5], [0.0, 525.0, 239.5], [0.0, 0.0, 1.0]])
TUM_DEPTH_UNITS_PER_METRE = 5000.0


def read_tum_list(path: Union[str, Path]) -> List[Tuple[float, List[str]]]:
    """A TUM text file as (timestamp, the rest of the line split on spaces).
    Lines starting with # and empty lines are skipped."""
    rows = []
    for line in Path(path).read_text().splitlines():
        parts = line.replace(",", " ").split()
        if not parts or parts[0].startswith("#"):
            continue
        rows.append((float(parts[0]), parts[1:]))
    return rows


def nearest_in_time(times: np.ndarray, wanted: np.ndarray, max_dt: float) -> np.ndarray:
    """For each wanted time, the index of the nearest entry of `times` (sorted,
    increasing), or -1 if the nearest is more than max_dt away."""
    times = np.asarray(times, dtype=np.float64)
    wanted = np.asarray(wanted, dtype=np.float64)
    if len(times) == 0:
        return np.full(len(wanted), -1, dtype=np.int64)
    right = np.clip(np.searchsorted(times, wanted), 0, len(times) - 1)
    left = np.clip(right - 1, 0, len(times) - 1)
    pick = np.where(np.abs(times[left] - wanted) <= np.abs(times[right] - wanted), left, right)
    pick[np.abs(times[pick] - wanted) > max_dt] = -1
    return pick.astype(np.int64)


@dataclass(frozen=True)
class TumFrame:
    timestamp: float            # of the colour image
    rgb_path: Path
    depth_path: Path
    T_world_cam: np.ndarray     # from groundtruth.txt, before any mount transform


class TumSequence:
    """A folder in the TUM RGB-D layout, read as Observations.

        rgb.txt          timestamp  rgb/<file>
        depth.txt        timestamp  depth/<file>      16-bit, 5000 units per metre
        groundtruth.txt  timestamp  tx ty tz qx qy qz qw   the colour camera in the world

    A colour image is used only if a depth image and a pose both exist within
    max_dt seconds of it. The cameras and the pose tracker are not synchronised,
    so the three never share a timestamp. frame_id is the frame's position among
    the frames kept, starting at 0.

    Reading the images needs OpenCV, which is imported on first use.
    """

    def __init__(
        self,
        root: Union[str, Path],
        K: np.ndarray = TUM_ROS_DEFAULT_K,
        depth_units_per_metre: float = TUM_DEPTH_UNITS_PER_METRE,
        max_dt: float = 0.02,
        T_base_cam: Optional[np.ndarray] = None,
    ) -> None:
        self.root = Path(root)
        self.K = np.asarray(K, dtype=np.float64)
        self.depth_units_per_metre = depth_units_per_metre
        self.T_base_cam = T_base_cam
        rgb = read_tum_list(self.root / "rgb.txt")
        depth = sorted(read_tum_list(self.root / "depth.txt"))
        poses = sorted(read_tum_list(self.root / "groundtruth.txt"))
        wanted = np.array([t for t, _ in rgb])
        depth_at = nearest_in_time(np.array([t for t, _ in depth]), wanted, max_dt)
        pose_at = nearest_in_time(np.array([t for t, _ in poses]), wanted, max_dt)
        self.frames: List[TumFrame] = []
        for (t, rest), d, p in zip(rgb, depth_at, pose_at):
            if d < 0 or p < 0:
                continue
            values = [float(v) for v in poses[p][1]]
            if len(values) != 7:
                raise ValueError(f"groundtruth.txt: expected 7 numbers after the timestamp, got {len(values)}")
            self.frames.append(TumFrame(
                timestamp=t,
                rgb_path=self.root / rest[0],
                depth_path=self.root / depth[d][1][0],
                T_world_cam=rigid_transform(values[:3], values[3:]),
            ))

    def __len__(self) -> int:
        return len(self.frames)

    def __iter__(self) -> Iterator[Observation]:
        return (self.observation(i) for i in range(len(self.frames)))

    def observation(self, index: int) -> Observation:
        import cv2  # only needed to read the image files

        frame = self.frames[index]
        image = cv2.imread(str(frame.rgb_path), cv2.IMREAD_COLOR)            # BGR
        depth = cv2.imread(str(frame.depth_path), cv2.IMREAD_UNCHANGED)      # uint16, untouched
        if image is None or depth is None:
            missing = frame.rgb_path if image is None else frame.depth_path
            raise FileNotFoundError(f"cannot read {missing}")
        return to_observation(
            image, depth, self.K, frame.T_world_cam, frame_id=index, timestamp=frame.timestamp,
            depth_units_per_metre=self.depth_units_per_metre, bgr=True, T_base_cam=self.T_base_cam,
        )
