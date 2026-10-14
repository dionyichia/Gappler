"""Is this recording good enough for the memory graph? (T6.2a)

Run it on a rosbag2 folder straight after a lab drive (T6.2), before anyone
leaves the lab. A bad drive found the same day costs one more drive. Found a
week later, it costs a lab visit.

    python -m memory_graph.recording_check <bag folder>

It reads the bag with the `rosbags` library, so it needs no ROS and runs on a
Mac, the Orin or the lab box. What a recording must contain, and why, is in
memory_graph/RECORDING_SPEC.md. Each check here is one line of that spec.

Every check gives PASS, WARN or FAIL. FAIL means the memory graph cannot use
the recording as it is. WARN means it can, but something is worth a look.
Exit code: 0 no FAIL, 1 at least one FAIL, 2 the bag could not be read.

The images are not decoded, except a sample of depth images for the valid
pixel count. Timestamps come from each message's header, read straight from
the first bytes of the message.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from memory_graph.replay_loader import nearest_in_time, rigid_transform

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"

DEPTH_ENCODINGS = ("16UC1", "mono16", "32FC1")
COLOR_ENCODINGS = ("rgb8", "bgr8")
IMAGE = "sensor_msgs/msg/Image"
CAMERA_INFO = "sensor_msgs/msg/CameraInfo"
TF = "tf2_msgs/msg/TFMessage"


@dataclass(frozen=True)
class RecordingSpec:
    """What a usable recording looks like. Defaults follow RECORDING_SPEC.md.

    The camera topics assume nav/robot_slam/launch/base_camera.launch.py:
    namespace `base_camera`, camera name `base_d455`, with aligned depth on.
    """

    color_topic: str = "/base_camera/base_d455/color/image_raw"
    depth_topic: str = "/base_camera/base_d455/aligned_depth_to_color/image_raw"
    info_topic: str = "/base_camera/base_d455/color/camera_info"
    lidar_topic: str = "/livox/lidar"
    map_frame: str = "map"
    odom_frame: str = "odom"
    base_frame: str = "robot_base_link"

    min_image_hz: float = 5.0          # the anchor gate needs a photo every ~0.2 s while driving
    max_image_gap_s: float = 1.0       # a longer gap means the driver or the disk fell behind
    min_lidar_hz: float = 5.0          # the MID-360 runs at 10 Hz
    max_pair_dt_s: float = 0.02        # colour and depth within this, as TumSequence's max_dt
    min_paired_fraction: float = 0.9
    max_odom_dt_s: float = 0.05        # odom -> base sample within this of the photo
    max_map_dt_s: float = 0.5          # map -> odom changes slowly, so a wider window
    min_posed_fraction: float = 0.9
    min_valid_depth_fraction: float = 0.5   # median share of pixels with a reading
    depth_samples: int = 30
    min_path_m: float = 10.0
    revisit_radius_m: float = 1.0      # "back where it was" means within this
    revisit_after_s: float = 30.0      # ...after at least this long away
    min_revisit_fraction: float = 0.1  # share of photos taken at a revisited place


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class Report:
    bag: Path
    checks: List[Check] = field(default_factory=list)
    facts: Dict[str, str] = field(default_factory=dict)

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name, status, detail))

    @property
    def failed(self) -> bool:
        return any(c.status == FAIL for c in self.checks)

    def text(self) -> str:
        lines = [f"Recording: {self.bag}"]
        lines += [f"  {k}: {v}" for k, v in self.facts.items()]
        lines.append("")
        lines += [f"{c.status:4}  {c.name}: {c.detail}" for c in self.checks]
        n_fail = sum(c.status == FAIL for c in self.checks)
        n_warn = sum(c.status == WARN for c in self.checks)
        lines.append("")
        lines.append(f"{n_fail} FAIL, {n_warn} WARN, {len(self.checks) - n_fail - n_warn} PASS")
        return "\n".join(lines)


# ---------------------------------------------------------------- reading


def header_stamp(raw: bytes) -> float:
    """A header's stamp in seconds, from a CDR message whose first field is a
    std_msgs/Header (Image, CameraInfo, PointCloud2, Livox CustomMsg).

    CDR starts with 4 bytes of encapsulation, the second of which says the byte
    order (1 little-endian, 0 big-endian). The stamp's sec (int32) and nanosec
    (uint32) follow.
    """
    order = "<" if raw[1] == 1 else ">"
    sec, nanosec = struct.unpack_from(order + "iI", raw, 4)
    return sec + nanosec * 1e-9


@dataclass
class _TopicData:
    msgtype: str
    stamps: List[float] = field(default_factory=list)
    samples: List[object] = field(default_factory=list)


def _edge_key(parent: str, child: str) -> Tuple[str, str]:
    return parent.lstrip("/"), child.lstrip("/")


def read_bag(path: Path, spec: RecordingSpec):
    """Header stamps for the image, info and LiDAR topics, a sample of
    deserialised messages for each, every /tf edge sample and every static edge."""
    from rosbags.highlevel import AnyReader
    from rosbags.typesys import Stores, get_typestore

    wanted = {spec.color_topic, spec.depth_topic, spec.info_topic, spec.lidar_topic}
    topics: Dict[str, _TopicData] = {}
    tf: Dict[Tuple[str, str], List[Tuple[float, np.ndarray]]] = {}
    static: Dict[Tuple[str, str], np.ndarray] = {}
    with AnyReader([path], default_typestore=get_typestore(Stores.ROS2_HUMBLE)) as reader:
        info = {
            "duration": f"{reader.duration * 1e-9:.1f} s",
            "messages": str(reader.message_count),
            "topics": str(len(reader.topics)),
        }
        conns = [c for c in reader.connections if c.topic in wanted or c.msgtype == TF]
        counts = {c.topic: c.msgcount for c in conns}
        sample_every = {
            spec.depth_topic: max(1, counts.get(spec.depth_topic, 1) // max(spec.depth_samples, 1)),
            spec.color_topic: max(1, counts.get(spec.color_topic, 1) // 5),
            spec.info_topic: max(1, counts.get(spec.info_topic, 1) // 5),
        }
        for conn, _, raw in reader.messages(connections=conns):
            if conn.msgtype == TF:
                msg = reader.deserialize(raw, conn.msgtype)
                for t in msg.transforms:
                    tr, q = t.transform.translation, t.transform.rotation
                    T = rigid_transform((tr.x, tr.y, tr.z), (q.x, q.y, q.z, q.w))
                    key = _edge_key(t.header.frame_id, t.child_frame_id)
                    if conn.topic == "/tf_static":
                        static[key] = T
                    else:
                        tf.setdefault(key, []).append((t.header.stamp.sec + t.header.stamp.nanosec * 1e-9, T))
                continue
            data = topics.setdefault(conn.topic, _TopicData(conn.msgtype))
            data.stamps.append(header_stamp(raw))
            every = sample_every.get(conn.topic)
            if every and (len(data.stamps) - 1) % every == 0:
                data.samples.append(reader.deserialize(raw, conn.msgtype))
    info["size on disk"] = f"{sum(f.stat().st_size for f in path.rglob('*') if f.is_file()) / 1e9:.2f} GB"
    return info, topics, tf, static


# ---------------------------------------------------------------- checks


def _rate(stamps: Sequence[float]) -> Tuple[float, float]:
    """Mean rate in Hz and the longest gap in seconds."""
    s = np.sort(np.asarray(stamps, dtype=np.float64))
    if len(s) < 2 or s[-1] <= s[0]:
        return 0.0, float("inf")
    return (len(s) - 1) / (s[-1] - s[0]), float(np.max(np.diff(s)))


def check_streams(report: Report, spec: RecordingSpec, topics: Dict[str, _TopicData]) -> None:
    for name, topic, min_hz, msgtypes in (
        ("colour images", spec.color_topic, spec.min_image_hz, (IMAGE,)),
        ("aligned depth", spec.depth_topic, spec.min_image_hz, (IMAGE,)),
        ("camera info", spec.info_topic, spec.min_image_hz, (CAMERA_INFO,)),
        ("LiDAR", spec.lidar_topic, spec.min_lidar_hz, None),
    ):
        data = topics.get(topic)
        if data is None:
            report.add(name, FAIL, f"{topic} is not in the bag")
            continue
        if msgtypes and data.msgtype not in msgtypes:
            report.add(name, FAIL, f"{topic} is {data.msgtype}, expected {' or '.join(msgtypes)}")
            continue
        hz, gap = _rate(data.stamps)
        detail = f"{topic}, {len(data.stamps)} messages, {hz:.1f} Hz, longest gap {gap:.2f} s, {data.msgtype}"
        if hz < min_hz:
            report.add(name, FAIL, detail + f". Needs at least {min_hz:g} Hz")
        elif name != "LiDAR" and gap > spec.max_image_gap_s:
            report.add(name, WARN, detail + f". Gaps over {spec.max_image_gap_s:g} s mean dropped frames")
        else:
            report.add(name, PASS, detail)


def check_images(report: Report, spec: RecordingSpec, topics: Dict[str, _TopicData]) -> None:
    color, depth, info = (topics.get(t) for t in (spec.color_topic, spec.depth_topic, spec.info_topic))
    if not (color and color.samples and depth and depth.samples):
        report.add("image format", FAIL, "no colour or depth images to inspect")
        return
    c, d = color.samples[0], depth.samples[0]
    problems = []
    if c.encoding not in COLOR_ENCODINGS:
        problems.append(f"colour encoding {c.encoding}, expected {' or '.join(COLOR_ENCODINGS)}")
    if d.encoding not in DEPTH_ENCODINGS:
        problems.append(f"depth encoding {d.encoding}, expected {' or '.join(DEPTH_ENCODINGS)}")
    report.add("image format", FAIL if problems else PASS,
               "; ".join(problems) or f"colour {c.width}x{c.height} {c.encoding}, depth {d.encoding}")

    # Aligned depth has the colour image's size and the colour camera's frame.
    # Raw depth has the depth camera's own frame, and usually another size.
    if (d.width, d.height) != (c.width, c.height) or d.header.frame_id != c.header.frame_id:
        report.add("depth aligned to colour", FAIL,
                   f"depth {d.width}x{d.height} in {d.header.frame_id!r}, colour {c.width}x{c.height} "
                   f"in {c.header.frame_id!r}. Turn on align_depth.enable in the camera launch")
    else:
        report.add("depth aligned to colour", PASS, f"same size and frame, {c.header.frame_id!r}")

    valid = [_valid_fraction(m) for m in depth.samples if m.encoding in DEPTH_ENCODINGS]
    if valid:
        med = float(np.median(valid))
        status = PASS if med >= spec.min_valid_depth_fraction else FAIL
        report.add("depth coverage", status,
                   f"median {med:.0%} of pixels have a reading over {len(valid)} sampled frames"
                   + ("" if status == PASS else f". Needs {spec.min_valid_depth_fraction:.0%}"))

    if not (info and info.samples):
        return
    i = info.samples[0]
    k = np.asarray(i.k, dtype=np.float64).reshape(3, 3)
    if (i.width, i.height) != (c.width, c.height) or k[0, 0] <= 0 or k[1, 1] <= 0:
        report.add("intrinsics", FAIL, f"camera info {i.width}x{i.height}, fx {k[0, 0]:g}, fy {k[1, 1]:g}, "
                                       f"colour {c.width}x{c.height}")
    else:
        dist = np.asarray(i.d, dtype=np.float64)
        note = "" if not dist.any() else f". Distortion {i.distortion_model} is not zero, and the loader does not undistort"
        report.add("intrinsics", WARN if note else PASS,
                   f"fx {k[0, 0]:.1f}, fy {k[1, 1]:.1f}, cx {k[0, 2]:.1f}, cy {k[1, 2]:.1f}" + note)


def _valid_fraction(msg) -> float:
    dtype = np.float32 if msg.encoding == "32FC1" else np.uint16
    if msg.is_bigendian:
        dtype = np.dtype(dtype).newbyteorder(">")
    row = msg.step // np.dtype(dtype).itemsize
    img = np.frombuffer(bytes(msg.data), dtype=dtype).reshape(msg.height, row)[:, :msg.width]
    ok = np.isfinite(img) & (img > 0)
    return float(np.count_nonzero(ok)) / max(img.size, 1)


def static_chain(static: Dict[Tuple[str, str], np.ndarray], start: str, goal: str) -> Optional[List[str]]:
    """Frames from `start` down to `goal` through static edges, or None."""
    children: Dict[str, List[str]] = {}
    for parent, child in static:
        children.setdefault(parent, []).append(child)
    path, todo, seen = {start: [start]}, [start], {start}
    while todo:
        frame = todo.pop()
        if frame == goal:
            return path[frame]
        for nxt in children.get(frame, []):
            if nxt not in seen:
                seen.add(nxt)
                path[nxt] = path[frame] + [nxt]
                todo.append(nxt)
    return None


def check_poses(report: Report, spec: RecordingSpec, topics, tf, static) -> Optional[np.ndarray]:
    """Can every photo get a pose? Returns the base positions in the map frame,
    one per posed photo, as (N, 4): time, x, y, z. None if there are none."""
    color = topics.get(spec.color_topic)
    camera_frame = color.samples[0].header.frame_id.lstrip("/") if color and color.samples else None
    if camera_frame:
        chain = static_chain(static, spec.base_frame, camera_frame)
        if chain:
            report.add("camera mount", PASS, " -> ".join(chain)
                       + ". Recorded mount only. The calibrated one (T5.5) replaces it on replay")
        else:
            report.add("camera mount", WARN,
                       f"no static chain {spec.base_frame} -> {camera_frame} in /tf_static. "
                       "Replay can still use the calibrated mount, but check the camera launch ran")

    missing = [f"{p} -> {c}" for p, c in ((spec.map_frame, spec.odom_frame), (spec.odom_frame, spec.base_frame))
               if (p, c) not in tf]
    if missing:
        report.add("poses", FAIL, f"no {', '.join(missing)} in /tf. Was localisation running?")
        return None
    if not color or not color.stamps:
        return None

    def series(key):
        samples = sorted(tf[key], key=lambda s: s[0])
        return np.array([s[0] for s in samples]), [s[1] for s in samples]

    t_mo, T_mo = series((spec.map_frame, spec.odom_frame))
    t_ob, T_ob = series((spec.odom_frame, spec.base_frame))
    photos = np.sort(np.asarray(color.stamps))
    i_mo = nearest_in_time(t_mo, photos, spec.max_map_dt_s)
    i_ob = nearest_in_time(t_ob, photos, spec.max_odom_dt_s)
    ok = (i_mo >= 0) & (i_ob >= 0)
    frac = float(np.mean(ok))
    detail = (f"{np.count_nonzero(ok)} of {len(photos)} photos have {spec.odom_frame} -> {spec.base_frame} "
              f"within {spec.max_odom_dt_s:g} s and {spec.map_frame} -> {spec.odom_frame} within {spec.max_map_dt_s:g} s")
    report.add("poses", PASS if frac >= spec.min_posed_fraction else FAIL,
               detail + ("" if frac >= spec.min_posed_fraction else f". Needs {spec.min_posed_fraction:.0%}"))
    if not ok.any():
        return None
    rows = [(t, *(T_mo[a] @ T_ob[b])[:3, 3]) for t, a, b, good in zip(photos, i_mo, i_ob, ok) if good]
    return np.array(rows)


def check_route(report: Report, spec: RecordingSpec, track: Optional[np.ndarray]) -> None:
    """Did the base drive far enough, and come back to places it had seen?

    The merge test (T6.4) needs objects seen twice from different times, so the
    route has to pass the same places again.
    """
    if track is None or len(track) < 2:
        report.add("route", FAIL, "no posed photos, so no route")
        return
    t, xyz = track[:, 0], track[:, 1:]
    length = float(np.sum(np.linalg.norm(np.diff(xyz, axis=0), axis=1)))
    span = xyz.max(axis=0) - xyz.min(axis=0)
    report.add("route length", PASS if length >= spec.min_path_m else FAIL,
               f"{length:.1f} m driven, area {span[0]:.1f} x {span[1]:.1f} m"
               + ("" if length >= spec.min_path_m else f". Needs {spec.min_path_m:g} m"))

    from scipy.spatial import cKDTree

    tree = cKDTree(xyz[:, :2])
    revisited = 0
    for i, near in enumerate(tree.query_ball_point(xyz[:, :2], spec.revisit_radius_m)):
        if any(t[i] - t[j] >= spec.revisit_after_s for j in near):
            revisited += 1
    frac = revisited / len(xyz)
    report.add("revisits", PASS if frac >= spec.min_revisit_fraction else WARN,
               f"{frac:.0%} of photos were taken within {spec.revisit_radius_m:g} m of a place "
               f"passed at least {spec.revisit_after_s:g} s earlier"
               + ("" if frac >= spec.min_revisit_fraction else
                  f". The merge test needs repeat sightings, aim for {spec.min_revisit_fraction:.0%}"))


def check_recording(path: Path, spec: RecordingSpec = RecordingSpec()) -> Report:
    report = Report(Path(path))
    info, topics, tf, static = read_bag(Path(path), spec)
    report.facts.update(info)
    check_streams(report, spec, topics)
    check_images(report, spec, topics)
    track = check_poses(report, spec, topics, tf, static)
    check_route(report, spec, track)
    return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("bag", type=Path, help="the rosbag2 folder")
    defaults = RecordingSpec()
    for name in ("color_topic", "depth_topic", "info_topic", "lidar_topic", "map_frame", "odom_frame", "base_frame"):
        parser.add_argument("--" + name.replace("_", "-"), default=getattr(defaults, name))
    args = parser.parse_args(argv)
    spec = replace(defaults, **{k: v for k, v in vars(args).items() if k != "bag"})
    try:
        report = check_recording(args.bag, spec)
    except Exception as exc:  # noqa: BLE001 -- any read error means the same thing here
        print(f"Cannot read {args.bag}: {exc}", file=sys.stderr)
        return 2
    print(report.text())
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
