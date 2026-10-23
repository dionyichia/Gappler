#!/usr/bin/env python3
"""Validate a staged FAST-LIVO2 replay config pair against the recorded bag.

Exit code is the verdict: CONFIG_OK (0) / CONFIG_FAILED (1) / usage refused (2).
Read-only, except --emit-identity, which writes one candidate snapshot file.

The pair under test is:
    config/t35b_proof3_lio.yaml     -> fastlivo_mapping node parameters
    config/t35b_proof3_visual.yaml  -> fastlivo_mapping parameters (visual mode)
    config/t35b_proof3_camera.yaml  -> parameter_blackboard node values
    (--lio selects the mapping file: the diagnostic or the visual one)

Checks, against the pinned consumer contract (T3.5_CONSUMER_CONTRACT.md):
  * bag identity: exactly the expected topics with their types, message counts
    and duration (byte hashes stay under EVIDENCE_*.sha256). The expectation is
    the frozen t35b_proof3 record by default, or a reviewed snapshot passed with
    --identity FILE for a bag recorded later. --emit-identity FILE writes a
    candidate snapshot from a bag and exits without checking anything; review
    and commit that JSON, then pass it back with --identity - it is the declared
    expectation, so a topic the snapshot blesses is no longer surprised on.
  * LiDAR routing: preprocess.lidar_type selects the branch matching the
    recorded lidar message type (1 -> CustomMsg, 8 -> PointCloud2) and
    common.livox_msg_type names the recorded package
  * camera: parameter_blackboard values equal the bag's CameraInfo K/D at full
    precision; image encoding/geometry equals the camera geometry
  * LiDAR sample: every point `line` satisfies the scan_line gate and all
    offset_time values stay within the scan budget (nanosecond timebase)
  * mode check: img_en declares the run - 0 = LiDAR-IMU diagnostic (extrinsic
    presence only), 1 = visual run whose Rcl/Pcl must equal the reviewed
    nominal composition (T5.4 chain + M2; provenance-labelled, not calibrated)
  * LiDAR->IMU extrinsic: extrin_calib.extrinsic_T/R must equal the reviewed
    value in every mode (the pinned fork's Mid-360 sign is wrong; pairs staged
    before that finding are noted, not failed - see
    T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md)
  * typo guard: every config key is a parameter the pinned consumer declares;
    known-inert keys are reported as notes, unknown keys fail

Requires the lab ROS environment (rosbag2_py, livox_ros_driver2, sensor_msgs):
    source /opt/ros/humble/setup.bash
    source ~/rcp-Gappler/install_nav/setup.bash
    python3 check_replay_configs.py --bag-dir <bag-dir> \
        --lio replay/config/t35b_proof3_lio.yaml \
        --camera replay/config/t35b_proof3_camera.yaml

For a bag recorded after the t35b_proof3 capture, first emit its candidate
identity (this needs --bag-dir only), review and commit the JSON, then check:
    python3 check_replay_configs.py --bag-dir <bag-dir> \
        --emit-identity replay/config/identity_<bag>.json
    python3 check_replay_configs.py --bag-dir <bag-dir> \
        --identity replay/config/identity_<bag>.json \
        --lio replay/config/<pair>_lio.yaml \
        --camera replay/config/<pair>_camera.yaml
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

NS = 1_000_000_000
LIDAR = "/livox/lidar"
IMU = "/livox/imu"
IMAGE = "/camera/camera/color/image_raw"
CAMINFO = "/camera/camera/color/camera_info"

# Frozen t35b_proof3 identity (EVIDENCE_t35b-capture.sha256 pins the bytes).
EXPECTED_TOPICS = {
    LIDAR: ("livox_ros_driver2/msg/CustomMsg", 740),
    IMU: ("sensor_msgs/msg/Imu", 14807),
    IMAGE: ("sensor_msgs/msg/Image", 2220),
    CAMINFO: ("sensor_msgs/msg/CameraInfo", 2220),
}
EXPECTED_DURATION_NS = 74_030_703_312
EXPECTED_MESSAGE_COUNT = 19_987

MAX_OFFSET_NS = 120_000_000  # same scan budget as analyze_bag.py

# Reviewed nominal LiDAR->camera extrinsic for the visual file (the diagnostic
# file keeps the fork's non-empty placeholder). Composed 2026-10-17 from the
# full chain (T3.5_CONSUMER_CONTRACT.md section 7): T_base<-livox = M2 retained
# mount (0.18, 0, 0.2; eye-estimated zero rotation); T_base<-colour_optical =
# the T5.4 as-fitted chain (screw 0.208, 0, 0.528 + Intel body +0.01115,
# +0.0475, +0.0145 + colour y -0.059 + optical rpy -pi/2, 0, -pi/2).
# p_cam = Rcl * p_lidar + Pcl (vio.cpp:38-39, 58-59). NOT calibrated: mount
# angles are eye-estimated and translation is tape-level. T5.5 owns the
# calibrated values; the projection check and T5.6 verify by image.
NOMINAL_RCL = (0.0, -1.0, 0.0, 0.0, 0.0, -1.0, 1.0, 0.0, 0.0)
NOMINAL_PCL = (-0.0115, 0.3425, -0.03915)

# Reviewed LiDAR->IMU extrinsic (extrin_calib.extrinsic_T/R), all modes: LIO uses
# it directly in both the diagnostic and the visual run. The pinned fork's
# Mid-360 profile ships the Livox manual's IMU-position numbers unnegated
# ([0.011, 0.02329, -0.04412]), but its own code applies them verbatim as
# p_imu = extrinsic_R * p_lidar + extrinsic_T (IMU_Processing.cpp:85-92, used at
# :528), which requires their negation. The fork is internally inconsistent on
# this point: its Avia profile does carry the negated manual value, and so does
# upstream FAST-LIO's mid360.yaml. Livox Mid-360 manual p.15: the IMU chip sits
# at (+11.0, +23.29, -44.12) mm in the point-cloud coordinates with axes
# matching that frame, and our driver publishes raw sensor-frame points
# (MID360_config.json extrinsic_parameter all-zero, pushed to the device as its
# install attitude), so the manual's numbers transfer unrotated. The fork has no
# online extrinsic estimation (`extrinsic_est_en` is absent from its source), so
# a wrong value is never corrected at runtime. Evidence and the confirming
# in-place-rotation test: T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md.
NOMINAL_LIDAR_IMU_T = (-0.011, -0.02329, 0.04412)
LIDAR_IMU_R = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)

# Config pairs staged before that defect was found. They stay byte-unchanged as
# the historical record of the T3.5a/T3.5c replays, so their known pre-correction
# sign is reported as a note, never as a failure. Retire this list only when
# those pairs are retired from the evidence record.
PRECORRECTION_PAIRS = frozenset({"t35b_proof3_lio.yaml", "t35b_proof3_visual.yaml"})

# Parameters the pinned consumer declares, generated mechanically from
# src/*.cpp (declare_parameter) at U-AMC/FAST-LIVO2-ROS2 @ a09599a288c56b832114d7ad9e898248a4111d9e.
# Re-generate with the regex declare_parameter<[^()]*>\(\s*"([^"]+)" over src/*.cpp
# (the [^()]* form is required to survive vector<double> / vector<int64_t> templates).
DECLARED = frozenset({
    "common.img_en",
    "common.img_topic",
    "common.imu_topic",
    "common.lid_topic",
    "common.lidar_en",
    "common.livox_msg_type",
    "common.ros_driver_bug_fix",
    "debug.frame_cnt",
    "debug.plot_time",
    "evo.pose_output_en",
    "evo.seq_name",
    "extrin_calib.Pcl",
    "extrin_calib.Rcl",
    "extrin_calib.extrinsic_R",
    "extrin_calib.extrinsic_T",
    "image_save.img_save_en",
    "image_save.interval",
    "imu.acc_cov",
    "imu.ba_bg_est_en",
    "imu.gravity_est_en",
    "imu.gyr_cov",
    "imu.imu_en",
    "imu.imu_int_frame",
    "lio.beam_err",
    "lio.dept_err",
    "lio.layer_init_num",
    "lio.max_layer",
    "lio.max_points_num",
    "lio.min_eigen_value",
    "lio.min_iterations",
    "lio.sigma_num",
    "lio.voxel_size",
    "local_map.half_map_size",
    "local_map.map_sliding_en",
    "local_map.sliding_thresh",
    "pcd_save.colmap_output_en",
    "pcd_save.filter_size_pcd",
    "pcd_save.interval",
    "pcd_save.pcd_save_en",
    "pcd_save.type",
    "preprocess.blind",
    "preprocess.feature_extract_enabled",
    "preprocess.filter_size_surf",
    "preprocess.hilti_en",
    "preprocess.lidar_type",
    "preprocess.point_filter_num",
    "preprocess.scan_line",
    "publish.blind_rgb_points",
    "publish.dense_map_en",
    "publish.pub_effect_point_en",
    "publish.pub_plane_en",
    "publish.pub_scan_num",
    "rolling_shutter.anchor_factor",
    "rolling_shutter.debug_print",
    "rolling_shutter.enable",
    "rolling_shutter.td_estimate_enable",
    "rolling_shutter.td_lambda",
    "rolling_shutter.td_min_jac_sq",
    "rolling_shutter.td_step_alpha",
    "rolling_shutter.td_step_cap",
    "rolling_shutter.tr_readout",
    "time_offset.exposure_time_init",
    "time_offset.img_time_offset",
    "time_offset.imu_time_offset",
    "time_offset.lidar_time_offset",
    "uav.gravity_align_en",
    "uav.imu_rate_odom",
    "vio.exposure_estimate_en",
    "vio.grid_n_height",
    "vio.grid_size",
    "vio.img_point_cov",
    "vio.inv_expo_cov",
    "vio.inverse_composition_en",
    "vio.max_iterations",
    "vio.normal_en",
    "vio.outlier_threshold",
    "vio.patch_pyrimid_level",
    "vio.patch_size",
    "vio.raycast_en",
})

# Declared by the consumer but documented as inert in this fork; reported, not failed.
KNOWN_INERT_LIO = frozenset({"imu.b_acc_cov", "imu.b_gyr_cov"})

# Built-in node parameters set through the params file.
BUILTIN = frozenset({"use_sim_time"})

# Keys read by the pinned camera loader (camera_loader.cpp:16-38).
CAMERA_DECLARED = frozenset({
    "cam_model", "cam_width", "cam_height", "scale",
    "cam_fx", "cam_fy", "cam_cx", "cam_cy",
    "cam_d0", "cam_d1", "cam_d2", "cam_d3",
})
# Carried for reference; the pinned loader never reads cam_d4 (pinhole_camera.h:40).
KNOWN_INERT_CAMERA = frozenset({"cam_d4"})

CAMERA_INT_KEYS = ("cam_width", "cam_height")
CAMERA_FLOAT_KEYS = (
    "scale", "cam_fx", "cam_fy", "cam_cx", "cam_cy",
    "cam_d0", "cam_d1", "cam_d2", "cam_d3",
)


class Audit:
    """Collects invariant violations; empty list == PASS."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.notes: list[str] = []

    def fail(self, message: str) -> None:
        self.failures.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def yaml_section(path: Path, root: str) -> dict:
    """Load path's root -> ros__parameters mapping; raises ValueError."""
    import yaml  # noqa: PLC0415

    document = yaml.safe_load(path.read_text())
    if not isinstance(document, dict) or set(document) != {root}:
        raise ValueError(f"{path}: expected a single root key {root!r}")
    node = document[root]
    if not isinstance(node, dict) or set(node) != {"ros__parameters"}:
        raise ValueError(f"{path}: expected {root}.ros__parameters mapping")
    section = node["ros__parameters"]
    if not isinstance(section, dict):
        raise ValueError(f"{path}: ros__parameters must be a mapping")
    return section


IDENTITY_SCHEMA = 1

# The expectation the checker compares a bag against. Two sources, one shape:
# the frozen t35b_proof3 record below (default, so the T3.5a/T3.5c box evidence
# stays reproducible), or a reviewed JSON snapshot for a bag recorded later.
# A snapshot is a *declared expectation*, not a measurement: whatever topic it
# lists stops being a surprise, so a human reviews it between --emit-identity
# and --identity. Byte hashes are never in here; EVIDENCE_*.sha256 pins those.
IDENTITY_KEYS = frozenset({"schema", "topics", "duration_ns", "message_count", "bag"})


def identity_from_bag(counts: dict, types: dict, duration_ns: int, message_count: int) -> dict:
    """Build a canonical identity snapshot from a bag's structural facts."""
    return {
        "schema": IDENTITY_SCHEMA,
        "topics": {
            name: {"type": types[name], "count": counts[name]} for name in sorted(counts)
        },
        "duration_ns": duration_ns,
        "message_count": message_count,
    }


def render_identity(identity: dict) -> str:
    """Deterministic serialisation, so two runs and two reviews diff cleanly."""
    return json.dumps(identity, indent=2, sort_keys=True) + "\n"


def load_identity(path: Path) -> dict:
    """Load and validate a reviewed snapshot; raises ValueError with the reason."""
    try:
        document = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: not JSON ({error})") from error
    if not isinstance(document, dict):
        raise ValueError(f"{path}: expected a JSON object")
    unknown = set(document) - IDENTITY_KEYS
    if unknown:
        raise ValueError(f"{path}: unknown keys {sorted(unknown)}")
    if document.get("schema") != IDENTITY_SCHEMA:
        raise ValueError(f"{path}: schema {document.get('schema')!r} != {IDENTITY_SCHEMA}")
    topics = document.get("topics")
    if not isinstance(topics, dict) or not topics:
        raise ValueError(f"{path}: topics must be a non-empty object")
    for name, entry in sorted(topics.items()):
        if not isinstance(entry, dict) or set(entry) != {"type", "count"}:
            raise ValueError(f"{path}: topic {name!r} must hold exactly a type and a count")
        if not isinstance(entry["type"], str) or not entry["type"]:
            raise ValueError(f"{path}: topic {name!r} type must be a non-empty string")
        count = entry["count"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"{path}: topic {name!r} count must be a non-negative integer")
    for key in ("duration_ns", "message_count"):
        value = document.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{path}: {key} must be a positive integer")
    bag = document.get("bag")
    if bag is not None and (not isinstance(bag, str) or not bag):
        raise ValueError(f"{path}: bag must be a non-empty string when present")
    return document


def write_identity(path: Path, identity: dict, force: bool = False) -> None:
    """Write a candidate snapshot, refusing to clobber a reviewed one silently."""
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; it is evidence - remove it deliberately, or pass force")
    path.write_text(render_identity(identity))


# Frozen t35b_proof3 identity (EVIDENCE_t35b-capture.sha256 pins the bytes),
# derived from the constants above so the two cannot drift apart.
FROZEN_T35B_IDENTITY = identity_from_bag(
    {name: spec[1] for name, spec in EXPECTED_TOPICS.items()},
    {name: spec[0] for name, spec in EXPECTED_TOPICS.items()},
    EXPECTED_DURATION_NS,
    EXPECTED_MESSAGE_COUNT,
)


def check_bag_identity(
    counts: dict, types: dict, duration_ns: int, message_count: int, expected: dict | None = None
) -> tuple[list[str], list[str]]:
    """Return (failures, notes) for the bag-identity expectations.

    expected=None means the frozen t35b_proof3 record; a snapshot dict means the
    reviewed expectation for a later bag.
    """
    declared = FROZEN_T35B_IDENTITY if expected is None else expected
    expected_topics = declared["topics"]
    failures: list[str] = []
    notes: list[str] = []
    expected_names = set(expected_topics)
    actual_names = set(counts)
    for name in sorted(expected_names - actual_names):
        failures.append(f"bag is missing expected topic {name}")
    for name in sorted(actual_names - expected_names):
        failures.append(f"bag has unexpected topic {name}")
    for name in sorted(expected_names & actual_names):
        expected_type = expected_topics[name]["type"]
        expected_count = expected_topics[name]["count"]
        actual_type = types.get(name)
        if actual_type != expected_type:
            failures.append(f"{name} type {actual_type} != expected {expected_type}")
        if counts[name] != expected_count:
            failures.append(f"{name} count {counts[name]} != expected {expected_count}")
    if duration_ns != declared["duration_ns"]:
        failures.append(f"duration {duration_ns} != expected {declared['duration_ns']}")
    if message_count != declared["message_count"]:
        failures.append(f"message_count {message_count} != expected {declared['message_count']}")
    if expected is None:
        notes.append(
            "identity is the frozen t35b_proof3 record; byte hashes are pinned "
            "separately by EVIDENCE_t35b-capture.sha256 - this check is structural"
        )
    else:
        notes.append(
            f"identity is the declared snapshot ({len(expected_topics)} topics); byte hashes are "
            "pinned separately by the bag's EVIDENCE_*.sha256 - this check is structural"
        )
    return failures, notes


def check_param_keys(
    section: dict, declared: frozenset, known_inert: frozenset
) -> tuple[list[str], list[str]]:
    """Typo guard: every key must be declared by the pinned consumer."""
    failures: list[str] = []
    notes: list[str] = []
    for key in sorted(section):
        if key in BUILTIN:
            continue
        if key in known_inert:
            notes.append(f"inert key carried for documentation: {key}")
        elif key not in declared:
            failures.append(f"config key the pinned consumer does not declare: {key}")
    return failures, notes


def check_blind_is_inert(section: dict) -> list[str]:
    """Note that preprocess.blind cannot act in the pinned source.

    The port reads the parameter into `blind` but never computes `blind_sqr`, the
    threshold every range gate actually compares against; upstream sets it right
    after the parameter block. A note, not a failure: the key is harmless, but the
    belief that a positive `blind` drops near-range returns is not established.
    """
    if "preprocess.blind" not in section:
        return []
    return [
        "preprocess.blind has no reliable effect in the pinned source: blind_sqr is read "
        "(preprocess.cpp:194, 227) but never assigned - the port dropped upstream's "
        "p_pre->blind_sqr = p_pre->blind * p_pre->blind (hku-mars/FAST-LIVO2 LIVMapper.cpp:116), "
        "so the gate threshold is an uninitialised member (finding F2, T3.5_CONFIG_SWEEP_20261019.md)"
    ]


def check_routing(lidar_type: int, livox_msg_type: str, recorded_type: str | None) -> list[str]:
    """The lidar_type branch must subscribe the recorded lidar message type."""
    failures: list[str] = []
    if lidar_type == 1:
        if livox_msg_type != "livox_ros_driver2":
            failures.append(
                f"livox_msg_type {livox_msg_type!r} != 'livox_ros_driver2' "
                "for the recorded CustomMsg bag"
            )
        if recorded_type != "livox_ros_driver2/msg/CustomMsg":
            failures.append(f"lidar_type 1 needs CustomMsg but bag has {recorded_type}")
    elif lidar_type == 8:
        if recorded_type != "sensor_msgs/msg/PointCloud2":
            failures.append(f"lidar_type 8 needs PointCloud2 but bag has {recorded_type}")
    else:
        failures.append(
            f"lidar_type {lidar_type}: the fork subscribes PointCloud2 for any "
            "non-AVIA value and this bag is not validated for that branch"
        )
    return failures


def check_scan_line(max_line: int | None, scan_line: object) -> list[str]:
    """Every point line must pass the avia_handler gate line < scan_line."""
    failures: list[str] = []
    if not isinstance(scan_line, int) or isinstance(scan_line, bool) or scan_line < 1:
        return [f"scan_line {scan_line!r} is not a positive integer"]
    if max_line is None:
        return ["no LiDAR points sampled for the scan_line gate"]
    if max_line >= scan_line:
        failures.append(
            f"sampled point line {max_line} >= scan_line {scan_line}: "
            "points would be silently dropped by avia_handler"
        )
    return failures


def check_offset_bounds(min_offset_ns: int | None, max_offset_ns: int | None) -> list[str]:
    """offset_time must be a non-negative nanosecond offset within the scan budget."""
    failures: list[str] = []
    if min_offset_ns is None or max_offset_ns is None:
        return ["no LiDAR points sampled for the offset_time budget"]
    if min_offset_ns < 0:
        failures.append(f"negative offset_time {min_offset_ns} ns")
    if max_offset_ns > MAX_OFFSET_NS:
        failures.append(
            f"offset_time {max_offset_ns} ns exceeds the {MAX_OFFSET_NS} ns scan budget"
        )
    return failures


def _exact(actual: object, expected: float) -> bool:
    return isinstance(actual, (float, int)) and not isinstance(actual, bool) and float(actual) == float(expected)


def check_camera_config(cam: dict, caminfo: dict, image: dict) -> tuple[list[str], list[str]]:
    """Camera values must equal the bag's CameraInfo at full precision."""
    failures: list[str] = []
    notes: list[str] = []

    if cam.get("cam_model") != "Pinhole":
        failures.append(f"cam_model {cam.get('cam_model')!r} != 'Pinhole'")
    if caminfo["model"] != "plumb_bob":
        notes.append(f"bag CameraInfo model is {caminfo['model']!r}, not plumb_bob")

    for key in CAMERA_INT_KEYS:
        if not isinstance(cam.get(key), int) or isinstance(cam.get(key), bool):
            failures.append(f"{key} must be an integer in the YAML")
    for key in CAMERA_FLOAT_KEYS:
        if not isinstance(cam.get(key), float):
            failures.append(f"{key} must be a float in the YAML")

    if isinstance(cam.get("scale"), float) and not cam["scale"] > 0:
        failures.append(f"scale {cam['scale']} is not positive")

    for key, index in (("cam_fx", 0), ("cam_cx", 2), ("cam_fy", 4), ("cam_cy", 5)):
        value = caminfo["k"][index]
        if not _exact(cam.get(key), value):
            failures.append(f"{key} {cam.get(key)!r} != CameraInfo K entry {value!r}")

    d = caminfo["d"]
    if len(d) != 5:
        failures.append(f"CameraInfo D has {len(d)} coefficients; plumb_bob must carry 5")
    else:
        for index in range(4):
            key = f"cam_d{index}"
            if not _exact(cam.get(key), d[index]):
                failures.append(f"{key} {cam.get(key)!r} != CameraInfo D[{index}] {d[index]!r}")
        if "cam_d4" in cam:
            if not _exact(cam["cam_d4"], d[4]):
                failures.append(f"cam_d4 {cam.get('cam_d4')!r} != CameraInfo D[4] {d[4]!r}")
            else:
                notes.append("cam_d4 (k3) carried for reference only; the pinned loader reads d0-d3")
        else:
            failures.append("cam_d4 absent: carry the true k3 for reference even though the loader ignores it")

    for key in CAMERA_INT_KEYS:
        image_dim = image["width"] if key == "cam_width" else image["height"]
        if cam.get(key) != image_dim or cam.get(key) != caminfo["width" if key == "cam_width" else "height"]:
            failures.append(
                f"{key} {cam.get(key)!r} != image/CameraInfo dimension {image_dim!r}"
            )
    if isinstance(cam.get("scale"), (float, int)) and not isinstance(cam.get("scale"), bool):
        scaled_width = cam.get("cam_width", 0) * cam["scale"]
        scaled_height = cam.get("cam_height", 0) * cam["scale"]
        if scaled_width != image["width"] or scaled_height != image["height"]:
            failures.append(
                f"camera internal geometry {scaled_width}x{scaled_height} != image "
                f"{image['width']}x{image['height']}: the viewer would take its resize path"
            )

    if image["encoding"] != "rgb8":
        failures.append(f"image encoding {image['encoding']!r} != 'rgb8' (cv_bridge bgr8 path not proven for it)")
    if image["step"] != image["width"] * 3:
        failures.append(f"image step {image['step']} != width*3 for a 3-channel encoding")
    return failures, notes


def check_camera_extrinsics(section: dict) -> list[str]:
    """Visual mode: staged Rcl/Pcl must carry exactly the reviewed nominal values.

    These are provenance-labelled working estimates (T5.4 chain + M2), not a
    target calibration; equality keeps an unreviewed edit out of the staged
    pair. T5.5 owns the calibrated replacement.
    """
    failures: list[str] = []
    for key, expected in (
        ("extrin_calib.Rcl", NOMINAL_RCL),
        ("extrin_calib.Pcl", NOMINAL_PCL),
    ):
        actual = section.get(key)
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            failures.append(
                f"{key}: expected {len(expected)} reviewed nominal values, got {actual!r}"
            )
            continue
        for index, (got, want) in enumerate(zip(actual, expected)):
            if isinstance(got, bool) or not isinstance(got, (int, float)):
                failures.append(f"{key}[{index}]={got!r} is not a number")
                break
            if abs(float(got) - want) > 1e-9:
                failures.append(
                    f"{key}[{index}]={got!r} != reviewed nominal {want!r} "
                    "(T5.4-chain composition; T5.5 owns calibrated values)"
                )
                break
    return failures


def check_lidar_imu_extrinsic(section: dict, retained: bool) -> tuple[list[str], list[str]]:
    """LiDAR->IMU extrinsic must equal the reviewed corrected value (all modes).

    retained=True marks a pair staged before the defect was found: its known
    pre-correction sign is reported as a note, never as a failure, so the
    historical T3.5a/T3.5c evidence keeps re-checking green.
    """
    failures: list[str] = []
    notes: list[str] = []
    for key, expected, what in (
        (
            "extrin_calib.extrinsic_T",
            NOMINAL_LIDAR_IMU_T,
            "reviewed LiDAR->IMU translation (Mid-360 manual p.15 position, negated "
            "for the code's p_imu = R * p_lidar + T form)",
        ),
        (
            "extrin_calib.extrinsic_R",
            LIDAR_IMU_R,
            "identity (the manual states the IMU axes match the point-cloud axes)",
        ),
    ):
        actual = section.get(key)
        mismatch: str | None = None
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            mismatch = f"{key}: expected {len(expected)} values, got {actual!r}"
        else:
            for index, (got, want) in enumerate(zip(actual, expected)):
                if isinstance(got, bool) or not isinstance(got, (int, float)):
                    mismatch = f"{key}[{index}]={got!r} is not a number"
                    break
                if abs(float(got) - want) > 1e-9:
                    mismatch = f"{key}[{index}]={got!r} != {want!r} {what}"
                    break
        if mismatch is None:
            continue
        if retained:
            notes.append(
                f"{mismatch} -- retained pre-correction pair; the pinned fork's Mid-360 sign, "
                "see T3.5_LIDAR_IMU_EXTRINSIC_FINDING.md (contract section 7, R2)"
            )
        else:
            failures.append(mismatch)
    return failures, notes


def check_mode(section: dict) -> tuple[str | None, list[str]]:
    """img_en declares the run mode; each mode has its own extrinsic contract.

    0 = LiDAR-IMU diagnostic (VIO does not run; the placeholder must simply be
    non-empty because the mapper loads it unconditionally), 1 = visual run
    (Rcl/Pcl must equal the reviewed nominal composition).
    """
    img_en = section.get("common.img_en")
    if isinstance(img_en, bool) or img_en not in (0, 1):
        return None, [f"common.img_en={img_en!r}: must be 0 (diagnostic) or 1 (visual run)"]
    if img_en == 0:
        failures: list[str] = []
        for key in ("extrin_calib.Rcl", "extrin_calib.Pcl"):
            value = section.get(key)
            if not isinstance(value, (list, tuple)) or not value:
                failures.append(
                    f"{key} must be non-empty: the mapper loads it unconditionally "
                    "(LIVMapper.cpp:186-187, 218)"
                )
        return "diagnostic", failures
    return "visual", check_camera_extrinsics(section)


def read_bag_metadata(bag_dir: Path) -> dict:
    """Structural facts straight from metadata.yaml - no message decoding."""
    import yaml  # noqa: PLC0415

    metadata = yaml.safe_load((bag_dir / "metadata.yaml").read_text())["rosbag2_bagfile_information"]
    counts: dict[str, int] = {}
    meta_types: dict[str, str] = {}
    for entry in metadata["topics_with_message_count"]:
        topic = entry["topic_metadata"]
        counts[topic["name"]] = entry["message_count"]
        meta_types[topic["name"]] = topic["type"]
    return {
        "counts": counts,
        "meta_types": meta_types,
        "duration_ns": metadata["duration"]["nanoseconds"],
        "message_count": metadata["message_count"],
    }


def print_bag_facts(bag: dict) -> None:
    """The bag's own structure; identical text in the check and emit paths."""
    print(
        f"BAG topics={len(bag['counts'])} duration_ns={bag['duration_ns']} "
        f"messages={bag['message_count']}"
    )
    for name in sorted(bag["counts"]):
        print(f"BAG_TOPIC {name} {bag['meta_types'][name]} count={bag['counts'][name]}")


def print_bag_sample(bag: dict, scan_line: object = None) -> None:
    """The bag's sampled scan/camera facts; identical text in both paths."""
    scan = bag["scan"]
    print(
        f"SCAN_SAMPLE scans={scan['scans']} points={scan['points']} "
        f"line=[{scan['min_line']},{scan['max_line']}] scan_line={scan_line} "
        f"offset_ns=[{scan['min_offset_ns']},{scan['max_offset_ns']}]"
    )
    caminfo = bag["caminfo"]
    image = bag["image"]
    if caminfo is None or image is None:
        print("CAMERA sample=absent")
        return
    print(
        f"CAMERA model={caminfo['model']} {caminfo['width']}x{caminfo['height']} "
        f"frame={caminfo['frame']} fx={caminfo['k'][0]!r} d4={caminfo['d'][4]!r}"
    )
    print(f"IMAGE encoding={image['encoding']} {image['width']}x{image['height']} step={image['step']}")


def read_bag(bag_dir: Path, sample_scans: int) -> dict:
    """Read the structural facts, first CameraInfo/Image and a LiDAR sample."""
    import rosbag2_py  # noqa: PLC0415
    from rclpy.serialization import deserialize_message  # noqa: PLC0415
    from sensor_msgs.msg import CameraInfo, Image  # noqa: PLC0415
    from livox_ros_driver2.msg import CustomMsg  # noqa: PLC0415

    facts = read_bag_metadata(bag_dir)
    counts = facts["counts"]
    meta_types = facts["meta_types"]

    reader = rosbag2_py.SequentialReader()
    reader.open(
        rosbag2_py.StorageOptions(uri=str(bag_dir), storage_id="sqlite3"),
        rosbag2_py.ConverterOptions("cdr", "cdr"),
    )
    topics = {t.name: t.type for t in reader.get_all_topics_and_types()}

    caminfo = None
    image = None
    scans = 0
    points = 0
    min_line: int | None = None
    max_line: int | None = None
    min_offset: int | None = None
    max_offset: int | None = None
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic == LIDAR and scans < sample_scans:
            msg = deserialize_message(data, CustomMsg)
            scans += 1
            points += msg.point_num
            for point in msg.points:
                line = int(point.line)
                min_line = line if min_line is None else min(min_line, line)
                max_line = line if max_line is None else max(max_line, line)
                offset = int(point.offset_time)
                min_offset = offset if min_offset is None else min(min_offset, offset)
                max_offset = offset if max_offset is None else max(max_offset, offset)
        elif topic == CAMINFO and caminfo is None:
            msg = deserialize_message(data, CameraInfo)
            caminfo = {
                "width": int(msg.width),
                "height": int(msg.height),
                "model": msg.distortion_model,
                "frame": msg.header.frame_id,
                "k": [float(v) for v in msg.k],
                "d": [float(v) for v in msg.d],
            }
        elif topic == IMAGE and image is None:
            msg = deserialize_message(data, Image)
            image = {
                "width": int(msg.width),
                "height": int(msg.height),
                "encoding": msg.encoding,
                "step": int(msg.step),
                "frame": msg.header.frame_id,
            }
        if scans >= sample_scans and caminfo is not None and image is not None:
            break

    return {
        "counts": counts,
        "meta_types": meta_types,
        "duration_ns": facts["duration_ns"],
        "message_count": facts["message_count"],
        "topics": topics,
        "caminfo": caminfo,
        "image": image,
        "scan": {
            "scans": scans,
            "points": points,
            "min_line": min_line,
            "max_line": max_line,
            "min_offset_ns": min_offset,
            "max_offset_ns": max_offset,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bag-dir", required=True, type=Path, help="rosbag2 directory (sqlite3 storage)")
    parser.add_argument("--lio", type=Path, help="fastlivo_mapping params YAML")
    parser.add_argument("--camera", type=Path, help="parameter_blackboard params YAML")
    parser.add_argument(
        "--identity",
        type=Path,
        help="reviewed bag-identity snapshot JSON (default: the frozen t35b_proof3 record)",
    )
    parser.add_argument(
        "--emit-identity", type=Path, help="write a candidate identity snapshot from --bag-dir and exit"
    )
    parser.add_argument("--sample-scans", type=int, default=20, help="LiDAR scans to sample (default 20)")
    args = parser.parse_args()

    if args.emit_identity is not None and args.identity is not None:
        print("FAIL --emit-identity and --identity are mutually exclusive")
        print("CONFIG_FAILED failures=1")
        return 2

    audit = Audit()

    if args.emit_identity is not None:
        bag = read_bag(args.bag_dir, args.sample_scans)
        print_bag_facts(bag)
        print_bag_sample(bag)
        candidate = identity_from_bag(
            bag["counts"], bag["meta_types"], bag["duration_ns"], bag["message_count"]
        )
        candidate["bag"] = args.bag_dir.name
        try:
            write_identity(args.emit_identity, candidate)
        except FileExistsError as error:
            print(f"FAIL {error}")
            print("CONFIG_FAILED failures=1")
            return 2
        print(
            f"IDENTITY_EMITTED {args.emit_identity} bag={candidate['bag']} "
            f"topics={len(candidate['topics'])} sha256={_sha256(args.emit_identity)}"
        )
        print(
            "REVIEW the snapshot (it becomes the declared expectation, not a measurement), commit it, "
            "then pass it back with --identity; nothing was checked in this mode"
        )
        return 0

    if args.lio is None or args.camera is None:
        print("FAIL --lio and --camera are required unless --emit-identity is given")
        print("CONFIG_FAILED failures=1")
        return 2

    expected: dict | None = None
    if args.identity is None:
        print("IDENTITY source=frozen_t35b_proof3 (the T3.5a/T3.5c capture)")
    else:
        try:
            expected = load_identity(args.identity)
        except ValueError as error:
            print(f"FAIL {error}")
            print("CONFIG_FAILED failures=1")
            return 1
        print(
            f"IDENTITY source={args.identity} bag={expected.get('bag')!r} "
            f"topics={len(expected['topics'])} sha256={_sha256(args.identity)}"
        )
        if expected.get("bag") and expected["bag"] != args.bag_dir.name:
            audit.note(
                f"snapshot was generated from bag {expected['bag']!r}, not {args.bag_dir.name!r} "
                "(copies get renamed; the counts must still match)"
            )

    try:
        lio = yaml_section(args.lio, "laserMapping")
        cam = yaml_section(args.camera, "parameter_blackboard")
    except ValueError as error:
        print(f"FAIL {error}")
        print("CONFIG_FAILED failures=1")
        return 1

    for path in (args.lio, args.camera):
        print(f"INPUT {path.name} sha256={_sha256(path)}")

    bag = read_bag(args.bag_dir, args.sample_scans)
    print_bag_facts(bag)

    failures, notes = check_bag_identity(
        bag["counts"], bag["meta_types"], bag["duration_ns"], bag["message_count"], expected
    )
    audit.failures.extend(failures)
    audit.notes.extend(notes)

    failures, notes = check_param_keys(lio, DECLARED, KNOWN_INERT_LIO)
    audit.failures.extend(failures)
    audit.notes.extend(notes)
    audit.notes.extend(check_blind_is_inert(lio))
    failures, notes = check_param_keys(cam, CAMERA_DECLARED, KNOWN_INERT_CAMERA)
    audit.failures.extend(failures)
    audit.notes.extend(notes)

    lidar_topic = lio.get("common.lid_topic")
    recorded_type = bag["topics"].get(lidar_topic) if isinstance(lidar_topic, str) else None
    audit.failures.extend(
        check_routing(lio.get("preprocess.lidar_type"), lio.get("common.livox_msg_type"), recorded_type)
    )
    if recorded_type is None:
        audit.fail("common.lid_topic is not a topic in the bag")
    for key, wanted in (("common.imu_topic", "sensor_msgs/msg/Imu"), ("common.img_topic", "sensor_msgs/msg/Image")):
        topic = lio.get(key)
        actual = bag["topics"].get(topic) if isinstance(topic, str) else None
        if actual != wanted:
            audit.fail(f"{key} {topic!r} has type {actual}, expected {wanted}")
    print(
        f"ROUTING lidar_type={lio.get('preprocess.lidar_type')} "
        f"livox_msg_type={lio.get('common.livox_msg_type')!r} recorded={recorded_type}"
    )

    scan = bag["scan"]
    audit.failures.extend(check_scan_line(scan["max_line"], lio.get("preprocess.scan_line")))
    audit.failures.extend(check_offset_bounds(scan["min_offset_ns"], scan["max_offset_ns"]))
    print_bag_sample(bag, scan_line=lio.get("preprocess.scan_line"))

    if bag["caminfo"] is None or bag["image"] is None:
        audit.fail("bag sample did not reach the first CameraInfo and Image")
    else:
        failures, notes = check_camera_config(cam, bag["caminfo"], bag["image"])
        audit.failures.extend(failures)
        audit.notes.extend(notes)

    mode, mode_failures = check_mode(lio)
    audit.failures.extend(mode_failures)
    if mode is not None:
        print(f"MODE {mode} (img_en={lio.get('common.img_en')})")
    if mode == "visual" and not mode_failures:
        print(
            "EXTRINSICS Rcl/Pcl = reviewed nominal composition (T5.4 chain + M2); "
            "not target-calibrated"
        )
    retained = args.lio.name in PRECORRECTION_PAIRS
    failures, notes = check_lidar_imu_extrinsic(lio, retained=retained)
    audit.failures.extend(failures)
    audit.notes.extend(notes)
    imu_rot = lio.get("extrin_calib.extrinsic_R")
    rot_text = "identity" if isinstance(imu_rot, (list, tuple)) and tuple(imu_rot) == LIDAR_IMU_R else repr(imu_rot)
    print(
        f"LIDAR_IMU extrinsic_T={lio.get('extrin_calib.extrinsic_T')!r} extrinsic_R={rot_text} "
        f"reviewed_T={list(NOMINAL_LIDAR_IMU_T)!r} retained_precorrection={retained}"
    )
    for key in ("time_offset.img_time_offset", "time_offset.imu_time_offset", "time_offset.lidar_time_offset"):
        value = lio.get(key)
        if value != 0.0:
            audit.fail(f"{key}={value!r} claims an unverifiable timing correction (no measured sync exists)")
        else:
            print(f"TIMEOFFSET {key}=0.0 (no correction claimed)")

    for note in audit.notes:
        print(f"NOTE {note}")
    if audit.failures:
        for failure in audit.failures:
            print(f"FAIL {failure}")
        print(f"CONFIG_FAILED failures={len(audit.failures)}")
        return 1
    print("CONFIG_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
