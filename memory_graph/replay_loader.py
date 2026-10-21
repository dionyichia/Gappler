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

There are two readers. TumSequence is for the TUM RGB-D benchmark's file layout
(Sturm et al., IROS 2012), which is also what ICL-NUIM ships in, and was how the
later stages were tested before any lab recording existed. FastLivoBag is for the
lab recording, which arrived as a FAST-LIVO hand-driven rosbag with colour, poses
and LiDAR but no depth image: it renders depth by projecting the registered LiDAR
cloud into the colour frame, so the frame still reaches to_observation as RGB-D.
The frames, directions and extrinsic it uses are recorded in
docs/zongzhe_docs/NOTE_fastlivo_bag_facts.md.

Poses are taken as given. Nothing here filters, smooths or interpolates them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional, Sequence, Tuple, Union

import numpy as np

from memory_graph.geometry import invert_rigid, project_cloud_to_depth
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
    the frames kept, plus first_frame_id. Observation.frame_id must never repeat
    within one graph, so to load a second recording after this one, start it at
    first_frame_id=len(first) (or higher).

    Reading the images needs OpenCV, which is imported on first use.
    """

    def __init__(
        self,
        root: Union[str, Path],
        K: np.ndarray = TUM_ROS_DEFAULT_K,
        depth_units_per_metre: float = TUM_DEPTH_UNITS_PER_METRE,
        max_dt: float = 0.02,
        T_base_cam: Optional[np.ndarray] = None,
        first_frame_id: int = 0,
    ) -> None:
        if first_frame_id < 0:
            raise ValueError(f"first_frame_id must be 0 or more, got {first_frame_id}")
        self.root = Path(root)
        self.first_frame_id = int(first_frame_id)
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
            image, depth, self.K, frame.T_world_cam, frame_id=self.first_frame_id + index, timestamp=frame.timestamp,
            depth_units_per_metre=self.depth_units_per_metre, bgr=True, T_base_cam=self.T_base_cam,
        )


# ---------------------------------------------------------------- FAST-LIVO bag

# The lab recording came as a FAST-LIVO hand-driven bag with no depth image, so
# depth is synthesised by projecting the registered LiDAR cloud into the colour
# frame. The frames, directions and numbers below are read off the bag and its
# config in docs/zongzhe_docs/NOTE_fastlivo_bag_facts.md. The three extrinsic
# arrays are defaults, not calibrated values (tape-level, 34 cm lever arm), so a
# later calibration overrides them through the constructor without a code change.

TOPIC_COLOR = "/camera/camera/color/image_raw"
TOPIC_CAMERA_INFO = "/camera/camera/color/camera_info"
TOPIC_ODOM = "/aft_mapped_to_init"           # body (aft_mapped) in world (camera_init)
TOPIC_CLOUD = "/cloud_registered"            # registered LiDAR, already in the world frame

# p_colour_optical = Rcl @ p_lidar + Pcl, so this 4x4 is camera-from-lidar.
RCL = (0.0, -1.0, 0.0, 0.0, 0.0, -1.0, 1.0, 0.0, 0.0)
PCL = (-0.0115, 0.3425, -0.03915)
# p_imu = R @ p_lidar + T, imu-from-lidar. R is identity here.
EXTRINSIC_R = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
EXTRINSIC_T = (-0.011, -0.02329, 0.04412)


def _rigid_from_rowmajor(r9: Sequence[float], t3: Sequence[float]) -> np.ndarray:
    """A 4x4 transform from a row-major 3x3 rotation and a 3-vector translation."""
    T = np.eye(4)
    T[:3, :3] = np.asarray(r9, dtype=np.float64).reshape(3, 3)
    T[:3, 3] = np.asarray(t3, dtype=np.float64)
    return T


def _cloud_xyz(msg) -> np.ndarray:
    """(N, 3) float64 xyz from a PointCloud2, dropping non-finite points.

    Reads the x, y, z fields by their byte offsets, so extra fields (rgb here)
    are ignored. Assumes float32 xyz and little-endian, which the Livox driver
    and FAST-LIVO both emit; anything else is refused rather than misread.
    """
    offsets = {f.name: (f.offset, f.datatype) for f in msg.fields}
    for name in ("x", "y", "z"):
        if name not in offsets or offsets[name][1] != 7:   # 7 is FLOAT32
            raise ValueError(f"cloud field {name!r} is missing or not float32")
    if msg.is_bigendian:
        raise ValueError("big-endian point clouds are not supported")
    n = int(msg.width) * int(msg.height)
    raw = np.frombuffer(msg.data, dtype=np.uint8).reshape(n, int(msg.point_step))

    def column(name: str) -> np.ndarray:
        off = offsets[name][0]
        return raw[:, off:off + 4].copy().view(np.float32).reshape(-1).astype(np.float64)

    xyz = np.stack([column("x"), column("y"), column("z")], axis=1)
    return xyz[np.isfinite(xyz).all(axis=1)]


@dataclass(frozen=True)
class FastLivoFrame:
    timestamp: float            # bag reception time of the colour image, seconds
    color_rowid: int            # the colour message's row, read on demand
    T_world_cam: np.ndarray     # camera-to-world, mount already composed in


class FastLivoBag:
    """A FAST-LIVO rosbag2 recording, read as Observations (T6.3b, LiDAR path).

    No depth image is recorded, so depth is rendered from the registered LiDAR
    cloud. For each colour image the loader finds the nearest odometry pose,
    composes the camera-to-world transform

        T_world_cam = T_world_imu @ T_imu_lidar @ inv(T_cam_lidar)

    and projects the cloud messages within a time window around the image into
    the colour frame (geometry.project_cloud_to_depth). Everything downstream
    then treats the frame as an ordinary RGB-D Observation.

    Only /cloud_registered is read, not /livox/lidar: it is standard PointCloud2
    already in the world frame, so no custom message type and no per-scan pose
    are needed. Poses and intrinsics are read up front; images and clouds are
    read per frame, so a multi-gigabyte bag is never held in memory at once.

    frame_id is the position among the frames kept, plus first_frame_id; as with
    TumSequence, start a second recording at first_frame_id = len(first) so ids
    never collide (T6.9). Reading the bag needs the `rosbags` package, imported
    on first use.
    """

    def __init__(
        self,
        db3_path: Union[str, Path],
        *,
        max_dt: float = 0.1,
        cloud_window_s: float = 0.1,
        first_frame_id: int = 0,
        rcl: Sequence[float] = RCL,
        pcl: Sequence[float] = PCL,
        extrinsic_r: Sequence[float] = EXTRINSIC_R,
        extrinsic_t: Sequence[float] = EXTRINSIC_T,
    ) -> None:
        if first_frame_id < 0:
            raise ValueError(f"first_frame_id must be 0 or more, got {first_frame_id}")
        if max_dt <= 0 or cloud_window_s < 0:
            raise ValueError("max_dt must be positive and cloud_window_s non-negative")
        self.db3_path = Path(db3_path)
        self.first_frame_id = int(first_frame_id)
        self.max_dt = float(max_dt)
        self.cloud_window_s = float(cloud_window_s)
        # camera-from-lidar, and the mount the camera pose needs: imu-from-lidar
        # times lidar-from-camera. inv(T_cam_lidar) is the step easy to drop.
        self._T_cam_lidar = _rigid_from_rowmajor(rcl, pcl)
        self._T_imu_lidar = _rigid_from_rowmajor(extrinsic_r, extrinsic_t)
        self._T_imu_cam = self._T_imu_lidar @ invert_rigid(self._T_cam_lidar)

        db = _BagDB(self.db3_path)
        try:
            self.K = db.deserialize(db.first_rowid(TOPIC_CAMERA_INFO), TOPIC_CAMERA_INFO).k.reshape(3, 3).astype(np.float64)
            odom = db.all(TOPIC_ODOM)
            odom_times = np.array([t for t, _ in odom], dtype=np.float64)
            odom_T = [self._pose_to_world_cam(db.deserialize(rowid, TOPIC_ODOM)) for _, rowid in odom]
            colour = db.all(TOPIC_COLOR)
        finally:
            db.close()

        colour_times = np.array([t for t, _ in colour], dtype=np.float64)
        pick = nearest_in_time(odom_times, colour_times, max_dt)
        self.frames: List[FastLivoFrame] = []
        for (t, rowid), p in zip(colour, pick):
            if p < 0:
                continue
            self.frames.append(FastLivoFrame(timestamp=t, color_rowid=rowid, T_world_cam=odom_T[p]))

    def _pose_to_world_cam(self, odom) -> np.ndarray:
        """Odometry (body in world) composed with the camera mount, camera-to-world."""
        p = odom.pose.pose.position
        q = odom.pose.pose.orientation
        T_world_imu = rigid_transform((p.x, p.y, p.z), (q.x, q.y, q.z, q.w))
        return T_world_imu @ self._T_imu_cam

    def __len__(self) -> int:
        return len(self.frames)

    def __iter__(self) -> Iterator[Observation]:
        return (self.observation(i) for i in range(len(self.frames)))

    def observation(self, index: int) -> Observation:
        frame = self.frames[index]
        db = _BagDB(self.db3_path)
        try:
            img = db.deserialize(frame.color_rowid, TOPIC_COLOR)
            if img.encoding != "rgb8":
                raise ValueError(f"expected rgb8 colour, got {img.encoding!r}")
            rows = db.rows_between(TOPIC_CLOUD, frame.timestamp - self.cloud_window_s,
                                   frame.timestamp + self.cloud_window_s)
            clouds = [_cloud_xyz(db.deserialize(rowid, TOPIC_CLOUD)) for _, rowid in rows]
        finally:
            db.close()
        image = np.frombuffer(img.data, dtype=np.uint8).reshape(int(img.height), int(img.step))
        image = image[:, : int(img.width) * 3].reshape(int(img.height), int(img.width), 3)
        world = np.concatenate(clouds, axis=0) if clouds else np.zeros((0, 3))
        depth = project_cloud_to_depth(world, frame.T_world_cam, self.K, image.shape[:2])
        return to_observation(
            image, depth, self.K, frame.T_world_cam, frame_id=self.first_frame_id + index,
            timestamp=frame.timestamp, depth_units_per_metre=1.0, bgr=False, T_base_cam=None,
        )


class _BagDB:
    """A thin reader over a rosbag2 sqlite3 file. Range and single-row queries by
    topic, with CDR deserialisation handed to the `rosbags` typestore."""

    def __init__(self, db3_path: Path) -> None:
        import sqlite3

        self._con = sqlite3.connect(f"file:{db3_path}?mode=ro", uri=True)
        self._topic_id = {name: tid for tid, name in self._con.execute("SELECT id, name FROM topics")}
        self._type = {name: typ for name, typ in self._con.execute("SELECT name, type FROM topics")}
        self._store = None

    def _store_(self):
        if self._store is None:
            from rosbags.typesys import Stores, get_typestore

            self._store = get_typestore(Stores.ROS2_HUMBLE)
        return self._store

    def all(self, topic: str) -> List[Tuple[float, int]]:
        """(timestamp seconds, rowid) for every message on `topic`, time-ordered."""
        tid = self._require(topic)
        rows = self._con.execute(
            "SELECT timestamp, id FROM messages WHERE topic_id = ? ORDER BY timestamp", (tid,))
        return [(ts * 1e-9, rowid) for ts, rowid in rows]

    def rows_between(self, topic: str, t0: float, t1: float) -> List[Tuple[float, int]]:
        tid = self._require(topic)
        rows = self._con.execute(
            "SELECT timestamp, id FROM messages WHERE topic_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp",
            (tid, int(t0 * 1e9), int(t1 * 1e9)))
        return [(ts * 1e-9, rowid) for ts, rowid in rows]

    def first_rowid(self, topic: str) -> int:
        tid = self._require(topic)
        row = self._con.execute(
            "SELECT id FROM messages WHERE topic_id = ? ORDER BY timestamp LIMIT 1", (tid,)).fetchone()
        if row is None:
            raise ValueError(f"no messages on {topic}")
        return int(row[0])

    def deserialize(self, rowid: int, topic: str):
        row = self._con.execute("SELECT data FROM messages WHERE id = ?", (rowid,)).fetchone()
        if row is None:
            raise ValueError(f"no message with row id {rowid}")
        return self._store_().deserialize_cdr(bytes(row[0]), self._type[topic])

    def _require(self, topic: str) -> int:
        if topic not in self._topic_id:
            raise ValueError(f"{topic} is not in the bag (has {sorted(self._topic_id)})")
        return self._topic_id[topic]

    def close(self) -> None:
        self._con.close()
