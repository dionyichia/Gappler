#!/usr/bin/env python3
"""Strict one-pass audit for T3.5 capture-profile bags; the exit code is the verdict.

Audits bags recorded with the T3.5 sensor profile:
    /livox/lidar                        livox_ros_driver2/msg/CustomMsg
    /livox/imu                          sensor_msgs/msg/Imu
    /camera/camera/color/image_raw      sensor_msgs/msg/Image      (rgb8)
    /camera/camera/color/camera_info    sensor_msgs/msg/CameraInfo

Invariants (any violation prints FAIL and exits 1):
  * every topic present; header stamps strictly increasing per topic
    (no backwards and no duplicate stamps)
  * LiDAR: point_num == len(points); timebase == header (<= 1 ms); all XYZ
    finite; every offset_time within the scan budget (<= 120 ms)
  * IMU: all six gyro/accel components finite
  * image: a single geometry/encoding/frame variant; len(data) == step * height
  * CameraInfo: a single calibration variant (K/D/R/P/model/size/frame);
    plumb_bob has |D| == 5; calibration values finite
  * image and CameraInfo carry identical stamp multisets and counts

Reported, not asserted: zero-range returns (x == y == z == 0), per-scan point
ordering, receipt-minus-header lags (host-side bag timestamps, not sensor
synchronisation) and IMU means. Zero-range returns are a driver characteristic
of this capture profile, not an integrity failure.

Streams the bag; holds only header stamps, receipts and a few scalars.
Run on the lab host with the nav overlay sourced (for livox_ros_driver2 msgs):
    source /opt/ros/humble/setup.bash
    source ~/rcp-Gappler/install_nav/setup.bash
    python3 analyze_bag.py <bag_uri>
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CameraInfo, Image, Imu
from livox_ros_driver2.msg import CustomMsg

NS = 1_000_000_000
LIDAR = "/livox/lidar"
IMU = "/livox/imu"
IMAGE = "/camera/camera/color/image_raw"
CAMINFO = "/camera/camera/color/camera_info"
TYPEMAP = {LIDAR: CustomMsg, IMU: Imu, IMAGE: Image, CAMINFO: CameraInfo}
MAX_OFFSET_NS = 120_000_000  # nominal 100 ms scan; overshoot budget + headroom
MAX_TIMEBASE_DIFF_NS = 1_000_000  # one millisecond


def stamp_ns(header) -> int:
    return header.stamp.sec * NS + header.stamp.nanosec


class Audit:
    """Collects invariant violations; empty list == PASS."""

    def __init__(self) -> None:
        self.failures: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("uri", help="rosbag2 directory (sqlite3 storage)")
    args = parser.parse_args()

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=args.uri, storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )

    audit = Audit()
    stamps: dict[str, list[int]] = {t: [] for t in TYPEMAP}
    receipts: dict[str, list[int]] = {t: [] for t in TYPEMAP}

    lid_points = 0
    lid_zero = 0
    lid_unsorted = 0
    lid_pnum_min: int | None = None
    lid_pnum_max = 0
    lid_off_min: int | None = None
    lid_off_max = 0
    lid_lines_max = 0
    tb_diff_max = 0
    lid_frames: set[str] = set()
    lid_ids: set[int] = set()

    imu_bad = 0
    gyro_sum = np.zeros(3)
    gyro_sq = np.zeros(3)
    accel_sum = np.zeros(3)
    accel_sq = np.zeros(3)
    imu_identity_orientation = True

    img_variants: set[tuple] = set()
    ci_variants: set[tuple] = set()

    lid_index = imu_index = img_index = ci_index = 0

    while reader.has_next():
        topic, data, t_ns = reader.read_next()
        if topic not in TYPEMAP:
            continue
        msg = deserialize_message(data, TYPEMAP[topic])
        header_ns = stamp_ns(msg.header)
        stamps[topic].append(header_ns)
        receipts[topic].append(int(t_ns))

        if topic == LIDAR:
            n = len(msg.points)
            if msg.point_num != n:
                audit.fail(
                    f"lidar point_num mismatch msg#{lid_index}: field "
                    f"{msg.point_num} != {n} decoded"
                )
            xs = np.array([p.x for p in msg.points])
            ys = np.array([p.y for p in msg.points])
            zs = np.array([p.z for p in msg.points])
            offs = np.array([p.offset_time for p in msg.points], dtype=np.int64)
            if not (np.isfinite(xs).all() and np.isfinite(ys).all() and np.isfinite(zs).all()):
                audit.fail(f"lidar msg#{lid_index}: non-finite XYZ")
            lid_points += n
            lid_zero += int(np.count_nonzero((xs == 0.0) & (ys == 0.0) & (zs == 0.0)))
            if n:
                if not np.all(np.diff(offs) >= 0):
                    lid_unsorted += 1
                off_max = int(offs.max())
                lid_off_min = int(offs.min()) if lid_off_min is None else min(lid_off_min, int(offs.min()))
                lid_off_max = max(lid_off_max, off_max)
                if off_max > MAX_OFFSET_NS:
                    audit.fail(
                        f"lidar msg#{lid_index}: offset_time {off_max} ns "
                        f"beyond {MAX_OFFSET_NS} ns scan budget"
                    )
                lid_lines_max = max(lid_lines_max, max((p.line for p in msg.points), default=0))
            pnum = msg.point_num
            lid_pnum_min = pnum if lid_pnum_min is None else min(lid_pnum_min, pnum)
            lid_pnum_max = max(lid_pnum_max, pnum)
            tb_diff_max = max(tb_diff_max, abs(int(msg.timebase) - header_ns))
            lid_frames.add(msg.header.frame_id)
            lid_ids.add(msg.lidar_id)
            lid_index += 1
        elif topic == IMU:
            w, a = msg.angular_velocity, msg.linear_acceleration
            vals = np.array([w.x, w.y, w.z, a.x, a.y, a.z])
            if not np.isfinite(vals).all():
                imu_bad += 1
            else:
                gyro_sum += vals[:3]
                gyro_sq += vals[:3] ** 2
                accel_sum += vals[3:]
                accel_sq += vals[3:] ** 2
            q = msg.orientation
            if (q.x, q.y, q.z, q.w) != (0.0, 0.0, 0.0, 1.0):
                imu_identity_orientation = False
            imu_index += 1
        elif topic == IMAGE:
            if len(msg.data) != msg.step * msg.height:
                audit.fail(
                    f"image msg#{img_index}: payload {len(msg.data)} bytes "
                    f"!= step*height {msg.step * msg.height}"
                )
            img_variants.add(
                (msg.encoding, msg.height, msg.width, msg.step,
                 msg.is_bigendian, msg.header.frame_id, len(msg.data))
            )
            img_index += 1
        else:  # CAMINFO
            ci_variants.add(
                (msg.distortion_model, msg.height, msg.width, msg.header.frame_id,
                 tuple(msg.k), tuple(msg.d), tuple(msg.r), tuple(msg.p))
            )
            if msg.distortion_model == "plumb_bob" and len(msg.d) != 5:
                audit.fail(
                    f"caminfo msg#{ci_index}: plumb_bob with |D|={len(msg.d)}, expected 5"
                )
            if not (np.isfinite(msg.k).all() and np.isfinite(msg.d).all()
                    and np.isfinite(msg.r).all() and np.isfinite(msg.p).all()):
                audit.fail(f"caminfo msg#{ci_index}: non-finite calibration value")
            ci_index += 1

    counts = {t: len(stamps[t]) for t in TYPEMAP}
    print(
        f"COUNTS lidar={counts[LIDAR]} imu={counts[IMU]} "
        f"image={counts[IMAGE]} caminfo={counts[CAMINFO]}"
    )

    # Per-topic stamp, gap and receipt-lag checks.
    s_lidar = np.array(stamps[LIDAR], dtype=np.int64)
    for topic, label in ((LIDAR, "LIDAR"), (IMU, "IMU"),
                         (IMAGE, "IMAGE"), (CAMINFO, "CAMINFO")):
        s = np.array(stamps[topic], dtype=np.int64)
        r = np.array(receipts[topic], dtype=np.int64)
        if s.size == 0:
            audit.fail(f"no messages on topic {topic}")
            continue
        back = int(np.count_nonzero(np.diff(s) < 0))
        dup = int(np.count_nonzero(np.diff(s) == 0))
        if back or dup:
            audit.fail(
                f"{label.lower()} header stamps not strictly increasing: "
                f"{back} backwards, {dup} duplicates"
            )
        span_s = (int(s[-1]) - int(s[0])) / NS
        if s.size >= 2:
            gaps_ms = np.diff(s) / 1e6
            rate = (s.size - 1) / span_s if span_s > 0 else float("nan")
            print(
                f"{label}_HEADER span_s={span_s:.6f} "
                f"max_gap_ms={gaps_ms.max():.3f} "
                f"median_gap_ms={float(np.median(gaps_ms)):.3f} rate_hz={rate:.2f}"
            )
        else:
            print(f"{label}_HEADER span_s={span_s:.6f} (single message)")
        lag_ms = (r - s) / 1e6
        print(
            f"{label}_RECEIPT lag_median_ms={float(np.median(lag_ms)):.3f} "
            f"lag_max_ms={lag_ms.max():.3f} lag_min_ms={lag_ms.min():.3f}"
        )

    if counts[LIDAR]:
        zero_pct = 100.0 * lid_zero / max(lid_points, 1)
        print(
            f"LIDAR_POINTS total={lid_points} zero_range={lid_zero} "
            f"({zero_pct:.2f}%) point_num={lid_pnum_min}..{lid_pnum_max}"
        )
        print(
            f"LIDAR_TIMING timebase_header_max_abs_ms={tb_diff_max / 1e6:.6f} "
            f"offsets_ns={lid_off_min if lid_off_min is not None else 0}..{lid_off_max} "
            f"unsorted_scans={lid_unsorted}/{counts[LIDAR]} lines_max={lid_lines_max}"
        )
        print(f"LIDAR_FRAMES {sorted(lid_frames)} lidar_ids={sorted(lid_ids)}")
        if tb_diff_max > MAX_TIMEBASE_DIFF_NS:
            audit.fail(
                f"lidar timebase differs from header by "
                f"{tb_diff_max / 1e6:.3f} ms (> 1 ms)"
            )

    if counts[IMU]:
        if imu_bad:
            audit.fail(f"imu non-finite gyro/accel samples: {imu_bad}")
        n_ok = counts[IMU] - imu_bad
        if n_ok:
            gyro_mean = gyro_sum / n_ok
            accel_mean = accel_sum / n_ok
            gyro_std = np.sqrt(np.maximum(gyro_sq / n_ok - gyro_mean ** 2, 0.0))
            print(
                f"IMU_MEANS gyro_mean=({gyro_mean[0]:.4f},{gyro_mean[1]:.4f},"
                f"{gyro_mean[2]:.4f}) rad/s gyro_std=({gyro_std[0]:.4f},"
                f"{gyro_std[1]:.4f},{gyro_std[2]:.4f}) accel_mean=("
                f"{accel_mean[0]:.5f},{accel_mean[1]:.5f},{accel_mean[2]:.5f}) "
                f"|accel_mean|={np.linalg.norm(accel_mean):.5f} (units not asserted)"
            )
        print(f"IMU_ORIENTATION identity_throughout={imu_identity_orientation}")

    if img_variants:
        print(f"IMAGE_VARIANTS n={len(img_variants)} {sorted(img_variants)}")
        if len(img_variants) > 1:
            audit.fail("image geometry/encoding/frame variant drift")
    if ci_variants:
        print(f"CAMINFO_VARIANTS n={len(ci_variants)}")
        if len(ci_variants) > 1:
            audit.fail("caminfo calibration drift (K/D/R/P or size/frame changed)")
        model, h, w, frame, k, d, r, p = sorted(ci_variants)[0]
        print(f"CAMINFO model={model} {w}x{h} frame={frame}")
        print(f"CAMINFO K={list(k)}")
        print(f"CAMINFO D={list(d)}")
        print(f"CAMINFO R={list(r)}")
        print(f"CAMINFO P={list(p)}")

    # Image/CameraInfo pairing: identical stamp multisets.
    s_img = np.array(stamps[IMAGE], dtype=np.int64)
    s_ci = np.array(stamps[CAMINFO], dtype=np.int64)
    if s_img.size != s_ci.size:
        audit.fail(f"image/caminfo count mismatch: {s_img.size} vs {s_ci.size}")
    elif s_img.size and not np.array_equal(np.sort(s_img), np.sort(s_ci)):
        audit.fail("image/caminfo stamp multisets differ")

    if all(counts[t] for t in TYPEMAP):
        first = {t: stamps[t][0] for t in TYPEMAP}
        print(
            f"CROSS first_header_deltas_ms imu={(first[IMU] - first[LIDAR]) / 1e6:.3f} "
            f"image={(first[IMAGE] - first[LIDAR]) / 1e6:.3f} "
            f"caminfo={(first[CAMINFO] - first[LIDAR]) / 1e6:.3f}"
        )

    if audit.failures:
        for failure in audit.failures:
            print(f"FAIL {failure}")
        print(f"ANALYSIS_FAILED failures={len(audit.failures)}")
        return 1
    print("ANALYSIS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
