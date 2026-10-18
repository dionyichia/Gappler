#!/usr/bin/env python3
"""Project recorded LiDAR scans onto recorded colour images (visual pre-check).

Read-only by-eye check of the staged LiDAR->camera extrinsic before any visual
replay claim: for each of --count scans spread through the bag, the
nearest-in-time colour image is fetched and every scan point in front of the
camera is painted on it, coloured by depth. FAST-LIVO2's own state estimation
is not involved and no timing correction is applied (the staged offsets are
all 0.0; none exists).

Projection: p_cam = Rcl * p_lidar + Pcl (the pinned consumer's semantics,
vio.cpp:38-39, 58-59), then the plumb_bob form with the four coefficients the
pinned loader reads (k1 k2 p1 p2; cam_d4/k3 is not read by pinhole_camera.h:40
and is not applied here). Points with depth <= preprocess.blind are dropped,
mirroring the mapper's range gate (preprocess.cpp:194); the LiDAR->IMU
extrinsic and all SLAM state are irrelevant to this static projection.

The --lio file must be the visual one: img_en=1 carrying the reviewed nominal
Rcl/Pcl (check_replay_configs.check_mode decides). The diagnostic file's
placeholder extrinsic is refused: projecting with it would be meaningless.

Requires the lab ROS environment (rosbag2_py, livox_ros_driver2, sensor_msgs);
everything else is stdlib. Run on the lab box:

    source /opt/ros/humble/setup.bash
    source ~/rcp-Gappler/install_nav/setup.bash
    python3 project_scan.py --bag-dir <bag-dir> \
        --lio replay/config/t35b_proof3_visual.yaml \
        --camera replay/config/t35b_proof3_camera.yaml --out projection

Output: overlay_<k>_scan<idx>_t<seconds>s.png per pair (background dimmed 50%,
points full brightness, near = blue -> far = red on the 5th-95th depth
percentile) plus one PROJ line per overlay on stdout.

Exit codes: 0 = overlays written; 2 = refused input (message starts with FAIL).
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import struct
import sys
import zlib
from pathlib import Path

from check_replay_configs import check_mode, yaml_section

LIDAR = "/livox/lidar"
IMAGE = "/camera/camera/color/image_raw"

# Background dimming table for the PNG (bytes.translate is C-speed).
_DARKEN = bytes(int(value * 0.5) for value in range(256))

# Depth colour ramp: near = blue -> cyan -> green -> yellow -> far = red.
_COLOR_STOPS = ((0, 0, 255), (0, 255, 255), (0, 255, 0), (255, 255, 0), (255, 0, 0))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stamp_ns(stamp) -> int:  # builtin_interfaces/Time
    return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)


def require_visual(section: dict) -> None:
    """Raise ValueError unless the section is the visual run with nominal Rcl/Pcl."""
    mode, failures = check_mode(section)
    if mode != "visual" or failures:
        detail = failures[0] if failures else f"detected mode {mode!r}"
        raise ValueError(
            "projection needs the visual config (img_en=1, reviewed nominal "
            f"Rcl/Pcl): {detail}"
        )


def read_camera(section: dict, width: int, height: int) -> tuple[tuple, tuple]:
    """Return ((fx, fy, cx, cy), (k1, k2, p1, p2)) from the camera section."""
    if section.get("cam_width") != width or section.get("cam_height") != height:
        raise ValueError(
            f"cam_width/height {section.get('cam_width')}x{section.get('cam_height')} "
            f"!= image {width}x{height}"
        )

    def number(key: str) -> float:
        value = section.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{key} missing or not a number: {value!r}")
        return float(value)

    intrinsics = (number("cam_fx"), number("cam_fy"), number("cam_cx"), number("cam_cy"))
    distortion = (number("cam_d0"), number("cam_d1"), number("cam_d2"), number("cam_d3"))
    return intrinsics, distortion


def project_points(
    points,
    rcl: list,
    pcl: list,
    intrinsics: tuple,
    distortion: tuple,
    width: int,
    height: int,
    min_depth: float,
) -> list[tuple[float, float, float]]:
    """Project LiDAR-frame points; return in-frame (u, v, depth) tuples."""
    fx, fy, cx, cy = intrinsics
    k1, k2, p1, p2 = distortion
    projected = []
    for x, y, z in points:
        cam_x = rcl[0] * x + rcl[1] * y + rcl[2] * z + pcl[0]
        cam_y = rcl[3] * x + rcl[4] * y + rcl[5] * z + pcl[1]
        cam_z = rcl[6] * x + rcl[7] * y + rcl[8] * z + pcl[2]
        if cam_z <= min_depth:
            continue
        xn = cam_x / cam_z
        yn = cam_y / cam_z
        r2 = xn * xn + yn * yn
        radial = 1.0 + k1 * r2 + k2 * r2 * r2
        xd = xn * radial + 2.0 * p1 * xn * yn + p2 * (r2 + 2.0 * xn * xn)
        yd = yn * radial + p1 * (r2 + 2.0 * yn * yn) + 2.0 * p2 * xn * yn
        u = fx * xd + cx
        v = fy * yd + cy
        if 0.0 <= u < width and 0.0 <= v < height:
            projected.append((u, v, cam_z))
    return projected


def depth_normalized(depths: list[float]) -> list[float]:
    """Normalise depths to 0..1 over their 5th-95th percentiles (clamped)."""
    if not depths:
        return []
    ordered = sorted(depths)
    count = len(ordered)
    lo = ordered[int(5 / 100.0 * (count - 1) + 0.5)]
    hi = ordered[int(95 / 100.0 * (count - 1) + 0.5)]
    if hi <= lo:
        return [0.0 for _ in depths]
    return [min(max((depth - lo) / (hi - lo), 0.0), 1.0) for depth in depths]


def depth_color(normalized: float) -> tuple[int, int, int]:
    """Map a 0..1 value onto the blue->cyan->green->yellow->red ramp."""
    t = min(max(normalized, 0.0), 1.0) * (len(_COLOR_STOPS) - 1)
    index = min(int(t), len(_COLOR_STOPS) - 2)
    fraction = t - index
    low, high = _COLOR_STOPS[index], _COLOR_STOPS[index + 1]
    return tuple(
        int(round(low[channel] + (high[channel] - low[channel]) * fraction))
        for channel in range(3)
    )


def write_png(path: Path, width: int, height: int, rgb, level: int = 6) -> None:
    """Write an 8-bit RGB PNG (stdlib only: zlib + struct). `level` is zlib's.

    The default level keeps evidence overlays byte-for-byte reproducible;
    live_preview.py passes level=1 to keep its periodic render cheap.
    """
    if len(rgb) != width * height * 3:
        raise ValueError(f"pixel payload {len(rgb)} != {width}x{height}x3 bytes")
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None) per scanline
        raw += rgb[y * width * 3 : (y + 1) * width * 3]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        body = tag + payload
        return (
            struct.pack(">I", len(payload))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), level))
        + chunk(b"IEND", b"")
    )


def nearest_index(target: int, stamps: list[int]) -> int | None:
    """Index of the stamp nearest to target; ties resolve to the earlier one."""
    if not stamps:
        return None
    position = bisect.bisect_left(stamps, target)
    best = None
    best_delta = None
    for candidate in (position - 1, position):
        if 0 <= candidate < len(stamps):
            delta = abs(stamps[candidate] - target)
            if best is None or delta < best_delta:
                best = candidate
                best_delta = delta
    return best


def spread_indices(count_total: int, count: int) -> list[int]:
    """`count` indices evenly spread over range(count_total), endpoints included."""
    if count_total <= 0:
        return []
    count = min(count, count_total)
    if count == 1:
        return [(count_total - 1) // 2]
    return [
        (k * (count_total - 1) * 2 + (count - 1)) // ((count - 1) * 2)
        for k in range(count)
    ]


def _open_reader(bag_dir: Path):
    import rosbag2_py  # noqa: PLC0415

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    return reader


def read_bag_index(bag_dir: Path) -> dict:
    """Pass 1: header stamps of all LiDAR scans and images, in bag order."""
    from rclpy.serialization import deserialize_message  # noqa: PLC0415
    from livox_ros_driver2.msg import CustomMsg  # noqa: PLC0415
    from sensor_msgs.msg import Image  # noqa: PLC0415

    reader = _open_reader(bag_dir)
    scan_stamps: list[int] = []
    image_stamps: list[int] = []
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic == LIDAR:
            scan_stamps.append(_stamp_ns(deserialize_message(data, CustomMsg).header.stamp))
        elif topic == IMAGE:
            image_stamps.append(_stamp_ns(deserialize_message(data, Image).header.stamp))
    return {"scan_stamps": scan_stamps, "image_stamps": image_stamps}


def read_bag_payload(bag_dir: Path, scans_wanted: set, images_wanted: set) -> dict:
    """Pass 2: full data for the wanted scan/image indices (same bag order)."""
    from rclpy.serialization import deserialize_message  # noqa: PLC0415
    from livox_ros_driver2.msg import CustomMsg  # noqa: PLC0415
    from sensor_msgs.msg import Image  # noqa: PLC0415

    reader = _open_reader(bag_dir)
    scans: dict[int, list] = {}
    images: dict[int, dict] = {}
    scan_index = 0
    image_index = 0
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic == LIDAR:
            if scan_index in scans_wanted:
                message = deserialize_message(data, CustomMsg)
                scans[scan_index] = [
                    (float(point.x), float(point.y), float(point.z))
                    for point in message.points
                ]
            scan_index += 1
        elif topic == IMAGE:
            if image_index in images_wanted:
                message = deserialize_message(data, Image)
                if message.encoding != "rgb8":
                    raise ValueError(f"image encoding {message.encoding!r} != 'rgb8'")
                images[image_index] = {
                    "width": int(message.width),
                    "height": int(message.height),
                    "step": int(message.step),
                    "stamp": _stamp_ns(message.header.stamp),
                    "data": bytes(message.data),
                }
            image_index += 1
    return {"scans": scans, "images": images}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bag-dir", required=True, type=Path, help="rosbag2 directory (sqlite3 storage)")
    parser.add_argument("--lio", required=True, type=Path, help="fastlivo_mapping visual params YAML")
    parser.add_argument("--camera", required=True, type=Path, help="parameter_blackboard params YAML")
    parser.add_argument("--out", type=Path, default=Path("projection"), help="output directory (default: projection)")
    parser.add_argument("--count", type=int, default=8, help="overlays to produce, spread through the bag (default 8)")
    parser.add_argument("--stride", type=int, default=1, help="use every Nth point of each scan (default 1)")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be >= 1")
    if args.stride < 1:
        parser.error("--stride must be >= 1")

    try:
        lio = yaml_section(args.lio, "laserMapping")
        cam = yaml_section(args.camera, "parameter_blackboard")
        require_visual(lio)
    except ValueError as error:
        print(f"FAIL {error}")
        return 2
    blind = lio.get("preprocess.blind")
    if isinstance(blind, bool) or not isinstance(blind, (int, float)) or blind <= 0:
        print(f"FAIL preprocess.blind {blind!r} is not a positive number")
        return 2
    rcl = [float(value) for value in lio["extrin_calib.Rcl"]]
    pcl = [float(value) for value in lio["extrin_calib.Pcl"]]
    for path in (args.lio, args.camera):
        print(f"INPUT {path.name} sha256={_sha256(path)}")
    print("VISUAL img_en=1, reviewed nominal Rcl/Pcl (T5.4 chain + M2); not calibrated")

    index = read_bag_index(args.bag_dir)
    scan_stamps = index["scan_stamps"]
    image_stamps = index["image_stamps"]
    print(f"BAG scans={len(scan_stamps)} images={len(image_stamps)}")
    if not scan_stamps or not image_stamps:
        print("FAIL bag has no LiDAR scans or no images")
        return 2

    picks = spread_indices(len(scan_stamps), args.count)
    pairs = [(scan_i, nearest_index(scan_stamps[scan_i], image_stamps)) for scan_i in picks]
    payload = read_bag_payload(args.bag_dir, set(picks), {image_i for _, image_i in pairs})

    first_image = payload["images"][pairs[0][1]]
    try:
        intrinsics, distortion = read_camera(cam, first_image["width"], first_image["height"])
    except ValueError as error:
        print(f"FAIL {error}")
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    first_stamp = scan_stamps[0]
    for k, (scan_i, image_i) in enumerate(pairs):
        scan_stamp = scan_stamps[scan_i]
        image = payload["images"][image_i]
        width, height, step = image["width"], image["height"], image["step"]
        t_relative = (scan_stamp - first_stamp) / 1e9
        delta_ms = (image["stamp"] - scan_stamp) / 1e6
        print(
            f"PAIR {k:02d} scan={scan_i} image={image_i} "
            f"t=+{t_relative:.1f}s delta_ms={delta_ms:+.1f}"
        )

        points = payload["scans"][scan_i][:: args.stride]
        projected = project_points(
            points, rcl, pcl, intrinsics, distortion, width, height, float(blind)
        )

        compact = bytearray()
        for y in range(height):
            compact += image["data"][y * step : y * step + width * 3]
        pixels = bytearray(bytes(compact).translate(_DARKEN))
        norms = depth_normalized([depth for _, _, depth in projected])
        for i in sorted(range(len(projected)), key=lambda i: -projected[i][2]):
            u, v, _ = projected[i]
            r, g, b = depth_color(norms[i])
            p = (int(v) * width + int(u)) * 3
            pixels[p] = r
            pixels[p + 1] = g
            pixels[p + 2] = b

        name = f"overlay_{k:02d}_scan{scan_i:04d}_t{t_relative:.1f}s.png"
        path = args.out / name
        write_png(path, width, height, pixels)
        if projected:
            depth_lo = min(depth for _, _, depth in projected)
            depth_hi = max(depth for _, _, depth in projected)
            depth_range = f"[{depth_lo:.2f},{depth_hi:.2f}]"
        else:
            depth_range = "[]"
        print(
            f"PROJ {k:02d} points={len(points)} drawn={len(projected)} "
            f"depth_m={depth_range} file={path}"
        )

    print(f"DONE {len(pairs)} overlays -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
