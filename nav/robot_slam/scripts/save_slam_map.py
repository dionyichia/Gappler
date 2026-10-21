#!/usr/bin/env python3
"""Explicit graph/image snapshot; never enables hardware or overwrites old maps."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid



def validate_snapshot(folder: Path, width: int, height: int, resolution: float) -> None:
    """Check graph availability, relative image reference, metadata and PGM length."""
    import yaml
    for name in ("completed_map.posegraph", "completed_map.data", "current_map.yaml", "current_map.pgm"):
        file = folder / name
        if not file.is_file() or file.stat().st_size == 0:
            raise ValueError(f"missing/empty snapshot file: {file}")
    metadata = yaml.safe_load((folder / "current_map.yaml").read_text())
    if not isinstance(metadata, dict) or metadata.get("image") != "current_map.pgm":
        raise ValueError("snapshot image must reference current_map.pgm relatively")
    if not math.isclose(float(metadata["resolution"]), resolution, rel_tol=1e-6):
        raise ValueError("snapshot resolution differs from source map")
    origin = metadata.get("origin")
    if not isinstance(origin, list) or len(origin) != 3 or not all(math.isfinite(float(v)) for v in origin):
        raise ValueError("invalid map origin")
    data = (folder / "current_map.pgm").read_bytes()
    # Nav2's P5 writer emits ASCII tokens/comments followed by one raster delimiter.
    header = re.match(rb"P5\s+(?:#[^\n]*\n\s*)*(\d+)\s+(\d+)\s+(\d+)(?:\r\n|\s)", data)
    if header is None:
        raise ValueError("unexpected PGM header")
    actual_width, actual_height, maximum = map(int, header.groups())
    if (actual_width, actual_height, maximum) != (width, height, 255):
        raise ValueError("PGM dimensions/maxval differ from source map")
    if len(data) - header.end() != width * height:
        raise ValueError("PGM raster length differs from dimensions")


def publish_snapshot(partial: Path, final: Path) -> None:
    """Reserve a new destination exclusively; report success only after all moves."""
    final.mkdir()  # refuses even an empty existing directory; no overwrite flag
    # Manifest is the completion marker; leave it until the payload files moved.
    for file in sorted(partial.iterdir(), key=lambda file: file.name == "manifest.json"):
        file.rename(final / file.name)
    partial.rmdir()  # only our now-empty staging directory


def stop_image_saver(child) -> None:
    """Finish cleanup of our separate group despite repeated termination signals."""
    handlers = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(child.pid, sig)
            except ProcessLookupError:
                break
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                continue
        child.wait(timeout=3)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--namespace", default="/")
    parser.add_argument("--map-topic", default="/map")
    parser.add_argument("--stationary", action="store_true", help="operator confirms chassis stationary and command sources stopped")
    args = parser.parse_args()
    if not args.stationary:
        parser.error("--stationary acknowledgment required; this tool cannot stop the chassis")
    if not re.fullmatch(r"/(?:[A-Za-z_][A-Za-z0-9_]*(?:/[A-Za-z_][A-Za-z0-9_]*)*)?", args.namespace):
        parser.error("namespace must be an absolute ROS namespace without trailing slash")
    if not args.map_topic.startswith("/"):
        parser.error("map topic must be absolute")
    import rclpy
    import yaml
    from rclpy.signals import SignalHandlerOptions
    from rclpy.qos import QoSProfile, DurabilityPolicy
    from rcl_interfaces.srv import GetParameters
    from rcl_interfaces.msg import ParameterType
    from nav_msgs.msg import OccupancyGrid
    from slam_toolbox.srv import Pause, SerializePoseGraph

    namespace = args.namespace.rstrip("/")
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"interrupted by signal {signum}")

    previous_handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    rclpy.init(args=[], signal_handler_options=SignalHandlerOptions.NO)
    node = rclpy.create_node("save_slam_snapshot_" + uuid.uuid4().hex[:8], start_parameter_services=False)
    paused_by_us = False
    partial = None

    def call(name, kind, request):
        client = node.create_client(kind, namespace + "/slam_toolbox/" + name)
        try:
            if not client.wait_for_service(timeout_sec=8):
                raise RuntimeError(f"service unavailable: {name}")
            future = client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=15)
            if not future.done() or future.result() is None:
                raise RuntimeError(f"service timeout: {name}; remote action may have completed")
            return future.result()
        finally:
            node.destroy_client(client)

    def parameters():
        client = node.create_client(GetParameters, namespace + "/slam_toolbox/get_parameters")
        try:
            if not client.wait_for_service(timeout_sec=8):
                raise RuntimeError("SLAM parameters unavailable")
            request = GetParameters.Request()
            request.names = ["mode", "paused_new_measurements", "map_update_interval", "map_name"]
            future = client.call_async(request)
            rclpy.spin_until_future_complete(node, future, timeout_sec=5)
            if not future.done() or future.result() is None or len(future.result().values) != 4:
                raise RuntimeError("SLAM parameter read failed")
            return future.result().values
        finally:
            node.destroy_client(client)

    try:
        mode, paused, interval, map_name = parameters()
        if mode.type != ParameterType.PARAMETER_STRING or mode.string_value != "mapping":
            raise RuntimeError("refused: SLAM Toolbox must be in mapping mode")
        if paused.type != ParameterType.PARAMETER_BOOL:
            raise RuntimeError("refused: cannot establish measurement-pause state")
        expected_topic = map_name.string_value
        if not expected_topic.startswith("/"):
            expected_topic = namespace + "/" + expected_topic
        if map_name.type != ParameterType.PARAMETER_STRING or args.map_topic != expected_topic:
            raise RuntimeError("refused: image topic does not match mapper map_name")
        delay = interval.double_value
        if interval.type != ParameterType.PARAMETER_DOUBLE or not math.isfinite(delay) or not 0 < delay <= 10:
            raise RuntimeError("refused: unsupported map update interval")
        received = []
        node.create_subscription(OccupancyGrid, args.map_topic,
                                 lambda message: received.append((time.monotonic(), message)),
                                 QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL))
        if not paused.bool_value:
            # Pause is a toggle, not an idempotent setter. One operator/saver only.
            paused_by_us = True
            response = call("pause_new_measurements", Pause, Pause.Request())
            if not response.status or not parameters()[1].bool_value:
                raise RuntimeError("could not pause mapping measurements")
        # A transient sample can be old. Require another publication after a
        # full raster interval while paused, spinning rather than queuing data.
        after = time.monotonic() + delay + 0.1
        deadline = after + 2 * delay + 5
        while time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
            if len(received) >= 2 and received[-1][0] >= after:
                break
        else:
            raise RuntimeError("refused: no refreshed map raster while paused")
        source = received[-1][1]
        if source.info.width == 0 or source.info.height == 0:
            raise RuntimeError("refused: mapper exposes no usable map")
        root = args.output_root.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        name = "session-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
        partial = root / (".partial-" + name)
        partial.mkdir()
        request = SerializePoseGraph.Request()
        request.filename = str(partial / "completed_map")
        response = call("serialize_map", SerializePoseGraph, request)
        if response.result != response.RESULT_SUCCESS:
            raise RuntimeError(f"graph serialization failed: result={response.result}")
        command = ["ros2", "run", "nav2_map_server", "map_saver_cli", "-f", str(partial / "current_map"),
                   "--ros-args", "-r", f"map:={args.map_topic}", "-p", "save_map_timeout:=5.0",
                   "-p", "map_subscribe_transient_local:=true"]
        child = subprocess.Popen(command, start_new_session=True)
        try:
            if child.wait(timeout=15) != 0:
                raise RuntimeError("image saver failed")
        finally:
            stop_image_saver(child)
        validate_snapshot(partial, source.info.width, source.info.height, source.info.resolution)
        metadata = yaml.safe_load((partial / "current_map.yaml").read_text())
        origin = source.info.origin
        expected_origin = (origin.position.x, origin.position.y, 2 * math.atan2(origin.orientation.z, origin.orientation.w))
        if not all(math.isclose(float(actual), expected, abs_tol=1e-5)
                   for actual, expected in zip(metadata["origin"], expected_origin)):
            raise ValueError("image origin differs from source map")
        manifest = {"frame": source.header.frame_id, "width": source.info.width, "height": source.info.height,
                    "resolution": source.info.resolution, "namespace": args.namespace, "map_topic": args.map_topic,
                    "map_stamp": [source.header.stamp.sec, source.header.stamp.nanosec],
                    "sha256": {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in partial.iterdir()}}
        (partial / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        final = root / name
        publish_snapshot(partial, final)
    except BaseException:
        if partial is not None:
            print(f"Snapshot failed; inspect retained staging/destination under {partial.parent}; do not use it", file=sys.stderr)
        raise
    finally:
        # Keep cleanup bounded but uninterrupted; only our saver ignores repeat
        # signals here. This does not affect hardware or other processes.
        for sig in previous_handlers:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if paused_by_us:
                # Re-read rather than blindly toggle if state changed externally.
                if parameters()[1].bool_value:
                    response = call("pause_new_measurements", Pause, Pause.Request())
                    if not response.status or parameters()[1].bool_value:
                        raise RuntimeError("mapping remains paused; operator intervention required")
        finally:
            node.destroy_node()
            rclpy.try_shutdown()
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
    print("SAVED_SNAPSHOT=" + str(final), flush=True)


if __name__ == "__main__":
    main()
