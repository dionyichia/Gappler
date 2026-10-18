#!/usr/bin/env python3
"""Live read-only capture preview: colour frame + LiDAR-in-camera overlay.

For scene aiming before and eyes-on checks during a T3.5 sensor capture: a
read-only subscriber (it cannot alter a recording) keeps the newest colour
frame and Livox CustomMsg scan, and every --period seconds writes into --out:

    latest_frame.png    newest colour frame as received (no processing)
    latest_overlay.png  same frame dimmed 50% with scan points projected on it,
                        coloured by depth (blue near -> red far), using the
                        provisional reviewed nominal Rcl/Pcl (T5.4 chain + M2,
                        not calibrated: by eye only, same math as project_scan)
    stats.txt           the last stats block that was printed
    preview.html        self-refreshing page with both images and the stats

plus one stats block per render on stdout: message totals and arrival rates
over --window seconds, per-topic freshness (since= LiDAR arrival age, age=
image/IMU stamp age; over 1 s is flagged STALE), in-FOV point count, depth
summary, depth bands, and a 3x3 region grid so a lone bottom sliver of
returns is obvious at a glance. preprocess.blind drops points the mapper
would drop.

Cost: rclpy's conversion of one 20k-point CustomMsg costs ~130 ms, so the
scan is subscribed raw and deserialized once per render (a normal
subscription saturates a core at 10 Hz and starves every topic -- measured in
the 2026-10-18 dry run); points decode once per render and PNGs are written
at zlib level 1. --period and --stride trade refresh rate and point coverage
for less load.

This preview is for aiming and gross checks. The pilot go/no-go remains the
offline audit of the recorded bag (analyze_bag.py + project_scan.py).

Run on the lab box (same environment as the capture):

    source /opt/ros/humble/setup.bash
    source ~/rcp-Gappler/install_nav/setup.bash
    python3 live_preview.py --lio replay/config/t35b_proof3_visual.yaml \
        --camera replay/config/t35b_proof3_camera.yaml --out preview

View it from the Mac while the preview runs (second Mac terminal):

    ssh -J nvidia@100.118.250.28 rcp2026@192.168.1.100 \\
        -L 8099:127.0.0.1:8099 'python3 -m http.server 8099 --bind 127.0.0.1'
    then open http://127.0.0.1:8099/preview.html on the Mac

Exit codes: 0 = clean Ctrl+C; 2 = refused input (message starts with FAIL).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import sys
import time
from collections import deque
from pathlib import Path

from project_scan import (
    depth_color,
    depth_normalized,
    project_points,
    read_camera,
    require_visual,
    write_png,
)
from check_replay_configs import yaml_section

LIDAR = "/livox/lidar"
IMAGE = "/camera/camera/color/image_raw"
CAMERA_INFO = "/camera/camera/color/camera_info"
IMU = "/livox/imu"

STALE_S = 1.0
BANDS = (
    ("<0.5", 0.5),
    ("0.5-1", 1.0),
    ("1-3", 3.0),
    ("3-8", 8.0),
    (">=8", float("inf")),
)

# Background dimming table for the overlay (bytes.translate is C-speed).
_DARKEN = bytes(int(value * 0.5) for value in range(256))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config(lio_path: Path, camera_path: Path) -> dict:
    """Read the visual laserMapping section and the camera fallback; ValueError on refusal."""
    lio = yaml_section(lio_path, "laserMapping")
    camera = yaml_section(camera_path, "parameter_blackboard")
    require_visual(lio)
    blind = lio.get("preprocess.blind")
    if isinstance(blind, bool) or not isinstance(blind, (int, float)) or blind <= 0:
        raise ValueError(f"preprocess.blind {blind!r} is not a positive number")
    return {
        "rcl": [float(value) for value in lio["extrin_calib.Rcl"]],
        "pcl": [float(value) for value in lio["extrin_calib.Pcl"]],
        "blind": float(blind),
        "camera": camera,
        "lio_sha256": _sha256(lio_path),
        "camera_sha256": _sha256(camera_path),
    }


def to_rgb_bytes(data: bytes, encoding: str, width: int, height: int) -> bytes:
    """Return width*height*3 packed RGB bytes from an Image payload."""
    expected = width * height * 3
    if encoding == "rgb8":
        payload = bytes(data[:expected])
    elif encoding == "bgr8":
        payload = bytearray(data[:expected])
        payload[0::3], payload[2::3] = payload[2::3], payload[0::3]
        payload = bytes(payload)
    else:
        raise ValueError(f"unsupported image encoding {encoding!r}")
    if len(payload) != expected:
        raise ValueError(f"image payload {len(payload)} != {width}x{height}x3 bytes")
    return payload


def decode_points(points, stride: int) -> list:
    """CustomMsg points -> (x, y, z) tuples, subsampled by stride.

    Called once per render, not once per message: decoding all 20k points of
    every scan in the callback costs a full core at 10 Hz.
    """
    return [(float(p.x), float(p.y), float(p.z)) for p in points[::stride]]


def overlay_rgb(rgb: bytes, width: int, height: int, projected: list) -> bytes:
    """Dim the frame 50% and paint (u, v, depth) points bright, near=blue -> far=red."""
    pixels = bytearray(bytes(rgb).translate(_DARKEN))
    norms = depth_normalized([depth for _, _, depth in projected])
    for i in sorted(range(len(projected)), key=lambda i: -projected[i][2]):
        u, v, _ = projected[i]
        r, g, b = depth_color(norms[i])
        p = (int(v) * width + int(u)) * 3
        pixels[p] = r
        pixels[p + 1] = g
        pixels[p + 2] = b
    return bytes(pixels)


def region_counts(projected: list, width: int, height: int) -> list:
    """Count in-frame points per cell of a row-major 3x3 grid."""
    cells = [0] * 9
    for u, v, _ in projected:
        row = min(int(v) * 3 // height, 2)
        col = min(int(u) * 3 // width, 2)
        cells[row * 3 + col] += 1
    return cells


def band_counts(depths: list) -> list:
    """Count depths per range band, ordered near to far."""
    counts = [0] * len(BANDS)
    for depth in depths:
        for index, (_, upper) in enumerate(BANDS):
            if depth < upper:
                counts[index] += 1
                break
        else:
            counts[-1] += 1
    return [(BANDS[index][0], counts[index]) for index in range(len(BANDS))]


def _percentile(ordered: list, fraction: float) -> float:
    return ordered[int(fraction * (len(ordered) - 1) + 0.5)]


def format_stats(stats: dict) -> str:
    """Render one human-readable stats block. `since` = arrival-based (LiDAR)."""
    def rate(key: str) -> str:
        value = stats.get(key)
        return "n/a" if value is None else f"{value:.2f}"

    def age(key: str) -> str:
        value = stats.get(key)
        if value is None:
            return "n/a"
        flag = " STALE" if abs(value) > STALE_S else ""
        return f"{value:+.3f}s{flag}"

    def since(key: str) -> str:
        value = stats.get(key)
        if value is None:
            return "n/a"
        flag = " STALE" if value > STALE_S else ""
        return f"{value:+.3f}s{flag}"

    depth = stats.get("depth")
    depth_text = (
        "n/a" if depth is None else f"min={depth[0]:.2f} p50={depth[1]:.2f} max={depth[2]:.2f}"
    )
    lines = [
        f"RENDER {stats['seq']} t=+{stats['elapsed_s']:.1f}s "
        f"{stats['width']}x{stats['height']} stride={stats['stride']} "
        f"blind={stats['blind']:.2f}m",
        f"  scan  hz={rate('scan_hz')} since={since('scan_since_s')} total={stats['scans']}",
        f"  image hz={rate('image_hz')} age={age('image_age_s')} total={stats['images']} "
        f"(intrinsics: {stats['intrinsics_from']})",
        f"  imu   hz={rate('imu_hz')} age={age('imu_age_s')} total={stats['imus']}",
        f"  IN_FOV points={stats['points']} of={stats['scan_points']} "
        f"drawn={stats['drawn']} depth_m {depth_text}",
        "  bands " + " ".join(f"{label}={count}" for label, count in stats["bands"]),
    ]
    regions = stats["regions"]
    for row in range(3):
        chunk = regions[row * 3 : row * 3 + 3]
        lines.append(f"  regions row{row} [" + " ".join(str(count) for count in chunk) + "]")
    return "\n".join(lines)


def render_html(seq: int, period_s: float, stats_text: str) -> str:
    """Self-refreshing page: both PNGs (cache-busted by seq) plus the stats block."""
    period_ms = max(int(round(period_s * 1000.0)), 250)
    stats_html = html.escape(stats_text)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>FAST-LIVO capture preview</title>
<style>
  :root {{ color-scheme: dark; }}
  body {{ background: #101114; color: #e8e8ea; margin: 16px;
         font: 13px/1.5 ui-monospace, Menlo, Consolas, monospace; }}
  h1 {{ font-size: 15px; font-weight: 600; margin: 0 0 12px; }}
  h1 .note {{ color: #9aa0a6; font-weight: 400; }}
  .row {{ display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }}
  figure {{ margin: 0; }}
  img {{ display: block; width: 640px; max-width: 100%;
        border: 1px solid #2a2d33; border-radius: 6px; }}
  figcaption {{ color: #9aa0a6; font-size: 12px; margin-top: 4px; }}
  pre {{ background: #17181c; border: 1px solid #2a2d33; border-radius: 6px;
        padding: 10px; overflow: auto; white-space: pre; }}
  .note {{ color: #9aa0a6; }}
</style>
</head>
<body>
<h1>FAST-LIVO capture preview <span class="note">render #{seq}, every {period_s:.1f} s</span></h1>
<div class="row">
  <figure>
    <img src="latest_frame.png?v={seq}" alt="latest colour frame">
    <figcaption>camera — newest colour frame</figcaption>
  </figure>
  <figure>
    <img src="latest_overlay.png?v={seq}" alt="LiDAR points on the colour frame">
    <figcaption>LiDAR on camera — provisional nominal extrinsics, by eye only</figcaption>
  </figure>
</div>
<pre>{stats_html}</pre>
<p class="note">read-only subscribers; the pilot go/no-go is the offline audit of the recorded bag.</p>
<script>setTimeout(() => location.reload(), {period_ms});</script>
</body>
</html>
"""


class Rates:
    """Arrival-rate meter: one sliding window of arrival times per key."""

    def __init__(self, window_s: float):
        self.window_s = float(window_s)
        self.times: dict = {}

    def tick(self, key: str, now_s: float) -> None:
        entries = self.times.setdefault(key, deque())
        entries.append(now_s)
        self._expire(key, now_s)

    def _expire(self, key: str, now_s: float) -> None:
        entries = self.times.get(key)
        while entries and now_s - entries[0] > self.window_s:
            entries.popleft()

    def hz(self, key: str, now_s: float) -> float | None:
        self._expire(key, now_s)
        entries = self.times.get(key)
        if not entries or len(entries) < 2:
            return None
        span = entries[-1] - entries[0]
        if span <= 0.0:
            return None
        return (len(entries) - 1) / span


class LivePreview:
    """Read-only rclpy node: newest frame + scan -> PNGs, stats, self-refreshing HTML."""

    def __init__(self, node, args, config: dict):
        from rclpy.qos import (
            DurabilityPolicy,
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )
        from rclpy.serialization import deserialize_message
        from sensor_msgs.msg import CameraInfo, Image, Imu
        from livox_ros_driver2.msg import CustomMsg

        self.node = node
        self.args = args
        self.config = config
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.rates = Rates(args.window)
        self.start_s = time.monotonic()
        self.seq = 0
        self.got = {"scan": 0, "image": 0, "imu": 0}
        self.scan = None
        self.image = None
        self.info = None
        self.imu_stamp_ns = None
        self.intrinsics = None
        self.distortion = None
        self.intrinsics_from = "config"
        self.step_warned = False
        self._deserialize = deserialize_message
        self._scan_type = CustomMsg

        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,  # not the sensor preset's 5: a ~0.3 s render stalls the single
            reliability=ReliabilityPolicy.BEST_EFFORT,  # executor, and depth 5 then
            durability=DurabilityPolicy.VOLATILE,  # drops camera/IMU samples every render
        )
        # 921 kB images fragment, and under a render stall best-effort loses whole
        # samples at the socket level (depth cannot help); reliable retransmits.
        # Reliable + volatile is the mapper's own convention (playback_qos.yaml).
        qos_image = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=100,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        # Raw scan subscription: rclpy's conversion of one 20k-point CustomMsg
        # costs ~130 ms, so a normal subscription saturates a core at 10 Hz and
        # silently throttles every topic. Raw mode copies the payload cheaply;
        # the render deserializes the newest one (0.5 Hz).
        node.create_subscription(CustomMsg, args.topic_lidar, self.on_scan, qos, raw=True)
        node.create_subscription(Image, args.topic_image, self.on_image, qos_image)
        node.create_subscription(CameraInfo, args.topic_info, self.on_info, qos)
        node.create_subscription(Imu, args.topic_imu, self.on_imu, qos)
        node.create_timer(args.period, self.on_timer)

    @staticmethod
    def _stamp_ns(stamp) -> int:
        return int(stamp.sec) * 1_000_000_000 + int(stamp.nanosec)

    def on_scan(self, payload: bytes) -> None:
        # Raw subscription: keep the serialized payload and its arrival time.
        # Decoding it here would cost a full core at 10 Hz (rclpy conversion).
        self.scan = {"payload": payload, "arrival": time.monotonic()}
        self.got["scan"] += 1
        self.rates.tick("scan", time.monotonic())

    def on_image(self, msg) -> None:
        self.image = {
            "data": msg.data,  # keep the sequence as delivered; no extra copy
            "width": int(msg.width),
            "height": int(msg.height),
            "step": int(msg.step),
            "encoding": msg.encoding,
            "stamp_ns": self._stamp_ns(msg.header.stamp),
        }
        self.got["image"] += 1
        self.rates.tick("image", time.monotonic())

    def on_info(self, msg) -> None:
        self.info = {"k": [float(value) for value in msg.k], "d": [float(value) for value in msg.d]}

    def on_imu(self, msg) -> None:
        self.imu_stamp_ns = self._stamp_ns(msg.header.stamp)
        self.got["imu"] += 1
        self.rates.tick("imu", time.monotonic())

    def _now_ns(self) -> int:
        return self.node.get_clock().now().nanoseconds

    def _resolve_intrinsics(self, width: int, height: int) -> None:
        if self.info and len(self.info["k"]) >= 9 and self.info["k"][0] > 0.0:
            k = self.info["k"]
            d = (self.info["d"] + [0.0, 0.0, 0.0, 0.0])[:4]
            self.intrinsics = (k[0], k[4], k[2], k[5])
            self.distortion = (d[0], d[1], d[2], d[3])
            self.intrinsics_from = "camera_info"
            return
        self.intrinsics, self.distortion = read_camera(self.config["camera"], width, height)
        self.intrinsics_from = "config"

    def _age_s(self, stamp_ns: int | None) -> float | None:
        if stamp_ns is None:
            return None
        return (self._now_ns() - stamp_ns) / 1e9

    def on_timer(self) -> None:
        now_s = time.monotonic()
        if self.scan is None and self.image is None:
            print(f"WAIT scans={self.got['scan']} images={self.got['image']} "
                  f"imus={self.got['imu']}", flush=True)
            return

        image = self.image
        if image is None or self.scan is None:
            which = "image" if image is None else "scan"
            print(f"WAIT no {which} yet scans={self.got['scan']} "
                  f"images={self.got['image']}", flush=True)
            return

        width, height, step = image["width"], image["height"], image["step"]
        if step != width * 3 and not self.step_warned:
            print(f"WARN image step {step} != width*3 {width * 3}: payload may be padded",
                  flush=True)
            self.step_warned = True
        try:
            rgb = to_rgb_bytes(image["data"], image["encoding"], width, height)
            if self.intrinsics is None:
                self._resolve_intrinsics(width, height)
        except ValueError as error:
            print(f"FAIL {error}", flush=True)
            return

        try:
            scan_msg = self._deserialize(self.scan["payload"], self._scan_type)
        except (ValueError, TypeError, IndexError) as error:
            print(f"FAIL scan decode: {error}", flush=True)
            return

        points = decode_points(scan_msg.points, self.args.stride)
        projected = project_points(
            points,
            self.config["rcl"],
            self.config["pcl"],
            self.intrinsics,
            self.distortion,
            width,
            height,
            self.config["blind"],
        )
        depths = sorted(depth for _, _, depth in projected)

        self.seq += 1
        elapsed = now_s - self.start_s
        stats = {
            "seq": self.seq,
            "elapsed_s": elapsed,
            "width": width,
            "height": height,
            "stride": self.args.stride,
            "blind": self.config["blind"],
            "scans": self.got["scan"],
            "images": self.got["image"],
            "imus": self.got["imu"],
            "scan_hz": self.rates.hz("scan", now_s),
            "image_hz": self.rates.hz("image", now_s),
            "imu_hz": self.rates.hz("imu", now_s),
            "scan_since_s": now_s - self.scan["arrival"],
            "image_age_s": self._age_s(image["stamp_ns"]),
            "imu_age_s": self._age_s(self.imu_stamp_ns),
            "points": len(points),
            "scan_points": int(scan_msg.point_num),
            "drawn": len(projected),
            "depth": (
                None if not depths
                else (depths[0], _percentile(depths, 0.5), depths[-1])
            ),
            "bands": band_counts(depths),
            "regions": region_counts(projected, width, height),
            "intrinsics_from": self.intrinsics_from,
        }
        text = format_stats(stats)

        write_png(self.out / "latest_frame.png", width, height, rgb, level=1)
        write_png(self.out / "latest_overlay.png", width, height,
                  overlay_rgb(rgb, width, height, projected), level=1)
        (self.out / "stats.txt").write_text(text + "\n")
        (self.out / "preview.html").write_text(render_html(self.seq, self.args.period, text))
        print(text, flush=True)


def run_live(args: argparse.Namespace, config: dict) -> int:
    import rclpy
    from rclpy.executors import ExternalShutdownException

    rclpy.init()
    node = rclpy.create_node("t35_capture_preview")
    try:
        LivePreview(node, args, config)
    except (ImportError, AttributeError) as error:
        node.destroy_node()
        rclpy.shutdown()
        print(f"FAIL ROS message types unavailable: {error}")
        return 2
    print(f"LIVE {args.topic_lidar} {args.topic_image} {args.topic_info} {args.topic_imu}",
          flush=True)
    print(f"OUT {Path(args.out).resolve()} period={args.period:.1f}s window={args.window:.1f}s",
          flush=True)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl+C, or SIGTERM already shut the context down (rclpy's own handler)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print("DONE preview stopped", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lio", required=True, type=Path, help="fastlivo_mapping visual params YAML")
    parser.add_argument("--camera", required=True, type=Path, help="parameter_blackboard params YAML")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument("--period", type=float, default=2.0, help="render period seconds (default 2.0)")
    parser.add_argument("--window", type=float, default=10.0, help="rate window seconds (default 10.0)")
    parser.add_argument("--stride", type=int, default=1, help="use every Nth scan point (default 1)")
    parser.add_argument("--topic-lidar", default=LIDAR)
    parser.add_argument("--topic-image", default=IMAGE)
    parser.add_argument("--topic-info", default=CAMERA_INFO)
    parser.add_argument("--topic-imu", default=IMU)
    args = parser.parse_args()
    if args.period <= 0.0:
        parser.error("--period must be > 0")
    if args.window <= 0.0:
        parser.error("--window must be > 0")
    if args.stride < 1:
        parser.error("--stride must be >= 1")

    try:
        config = load_config(args.lio, args.camera)
    except (ValueError, KeyError, TypeError) as error:
        print(f"FAIL {error}")
        return 2
    for path in (args.lio, args.camera):
        print(f"INPUT {path.name} sha256={_sha256(path)}")
    print(f"VISUAL img_en=1, reviewed nominal Rcl/Pcl (T5.4 chain + M2); not calibrated")
    print(f"Rcl={config['rcl']} Pcl={config['pcl']} blind={config['blind']}")
    return run_live(args, config)


if __name__ == "__main__":
    sys.exit(main())
