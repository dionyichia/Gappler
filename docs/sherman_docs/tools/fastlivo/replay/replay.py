"""Single-use offline smoke replay. ROS imports occur only inside main()."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import time
import traceback
from replay_progress import (CallbackTracker, callback_patterns, drain_state,
                               expected_callbacks, playback_rate, prestart_allowance,
                               reconcile_imu, reconcile_rows, terminal_message_gap)

ROOT = Path("/tmp/t59")
DEFAULT_MAPPER_CONFIG = "bright_screen_wall.yaml"
DEFAULT_CAMERA_CONFIG = "camera_pinhole.yaml"
OUTPUTS = {"odom": ("/aft_mapped_to_init", "nav_msgs/msg/Odometry"),
           "cloud": ("/cloud_registered", "sensor_msgs/msg/PointCloud2"),
           "rgb": ("/rgb_img", "sensor_msgs/msg/Image")}
INPUT_TYPES = {"lidar": "livox_ros_driver2/msg/CustomMsg",
               "imu": "sensor_msgs/msg/Imu",
               "image": "sensor_msgs/msg/Image"}
VIO_OUTPUT = "rgb"


def reviewed_configs(environ: dict) -> tuple:
    """Staged config basenames: the wrapper copies both into /tmp/t59 unchanged."""
    names = []
    for key, default in (("T35_MAPPER_CONFIG", DEFAULT_MAPPER_CONFIG),
                         ("T35_CAMERA_CONFIG", DEFAULT_CAMERA_CONFIG)):
        name = environ.get(key, default)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.yaml", name or ""):
            raise ValueError("config name must be a plain staged YAML basename: " + key)
        names.append(name)
    return tuple(names)


def inputs_from_params(params: dict) -> dict:
    """Played topics are the mapper's own config values, so a staged mismatch shows."""
    inputs = {params["common.lid_topic"]: INPUT_TYPES["lidar"],
              params["common.imu_topic"]: INPUT_TYPES["imu"]}
    if params["common.img_en"]:
        inputs[params["common.img_topic"]] = INPUT_TYPES["image"]
    return inputs


def outputs_from_params(params: dict) -> dict:
    """img_en=0 selects ONLY_LIO: no /rgb_img output exists to require."""
    if params["common.img_en"]:
        return dict(OUTPUTS)
    return {key: value for key, value in OUTPUTS.items() if key != VIO_OUTPUT}


def valid_pose(position: list, quaternion: list) -> bool:
    """Reject nonfinite poses and quaternions outside a 1% unit-norm tolerance."""
    return (len(position) == 3 and len(quaternion) == 4
            and all(math.isfinite(v) for v in position + quaternion)
            and abs(math.sqrt(sum(v * v for v in quaternion)) - 1) <= 0.01)


def valid_cloud(message) -> tuple:
    """Check every XYZ coordinate, respecting field types, byte order and row padding.

    Returns (valid, reason, nonfinite_count, point_count). Reasons distinguish
    empty clouds, malformed layouts and nonfinite coordinates so two publisher
    paths emitting different clouds can be told apart in the report.
    """
    try:
        if message.width <= 0 or message.height <= 0 or message.point_step <= 0:
            return False, "empty_or_nonpositive_dimensions", 0, 0
        if (message.row_step < message.width * message.point_step
                or len(message.data) < message.row_step * message.height):
            return False, "row_layout_too_short", 0, message.width * message.height
        fields = [field for field in message.fields if field.name in ("x", "y", "z")]
        if len(fields) != 3 or {field.name for field in fields} != {"x", "y", "z"}:
            return False, "missing_xyz_fields", 0, message.width * message.height
        readers = []
        endian = ">" if message.is_bigendian else "<"
        for field in fields:
            if field.count != 1 or field.datatype not in (7, 8):
                return False, "bad_xyz_field_type", 0, message.width * message.height
            reader = struct.Struct(endian + ("f" if field.datatype == 7 else "d"))
            if field.offset < 0 or field.offset + reader.size > message.point_step:
                return False, "xyz_offset_outside_point_step", 0, message.width * message.height
            readers.append((field.offset, reader))
        data = memoryview(message.data)
        bad = 0
        total = message.width * message.height
        for row in range(message.height):
            for col in range(message.width):
                base = row * message.row_step + col * message.point_step
                for offset, reader in readers:
                    if not math.isfinite(reader.unpack_from(data, base + offset)[0]):
                        bad += 1
                        break
        if bad:
            return False, "nonfinite_xyz", bad, total
        return True, "ok", 0, total
    except (AttributeError, TypeError, ValueError, struct.error, OverflowError):
        return False, "exception_during_check", 0, 0


def valid_image(message) -> bool:
    """The reviewed source emits BGR8, three bytes per pixel plus possible row padding."""
    return (message.encoding == "bgr8" and message.width > 0 and message.height > 0
            and message.step >= message.width * 3
            and len(message.data) >= message.step * message.height)


def player_log_failures(lines) -> list:
    """Humble may report playback exceptions yet return zero; logs are part of EOF proof."""
    failures = []
    for line in lines:
        if re.search(r"\b(?:ERROR|FATAL)\b|Failed to play:|Failed to publish message", line, re.I):
            failures.append("player diagnostic: " + line.strip()[:1000])
            if len(failures) >= 20:
                break
    return failures


def bag_expectation(metadata: dict) -> dict:
    """Read ROS 2 metadata timing/counts/topics without importing YAML outside the runtime."""
    info = metadata["rosbag2_bagfile_information"]
    start = info["starting_time"]["nanoseconds_since_epoch"]
    duration = info["duration"]["nanoseconds"]
    count = info["message_count"]
    if any(type(value) is not int for value in (start, duration, count)):
        raise ValueError("bag metadata timing/counts must be integers")
    if start < 0 or duration <= 0 or count <= 0:
        raise ValueError("bag metadata must describe a nonempty positive-duration recording")
    topics = {}
    for entry in info["topics_with_message_count"]:
        name = entry["topic_metadata"]["name"]
        number = entry["message_count"]
        if not isinstance(name, str) or type(number) is not int or number < 0 or name in topics:
            raise ValueError("bag metadata must describe each topic once with a nonnegative count")
        topics[name] = number
    if sum(topics.values()) != count:
        raise ValueError("bag metadata topic counts do not sum to the message count")
    return {"start": start / 1e9, "end": (start + duration) / 1e9,
            "duration": duration / 1e9, "message_count": count, "topics": topics,
            "tolerance": 0.25}


def clock_complete(clock: dict, expected: dict) -> bool:
    """Require first/last clock within 0.25 simulated seconds of metadata bounds."""
    first, last = clock["first"], clock["last"]
    return (first is not None and last is not None and not clock["backward"]
            and math.isfinite(first) and math.isfinite(last) and last > first
            and abs(first - expected["start"]) <= expected["tolerance"]
            and abs(last - expected["end"]) <= expected["tolerance"]
            and last - first >= expected["duration"] - 2 * expected["tolerance"])


def group_exists(pgid: int) -> bool:
    """A reaped leader does not imply its recorded process group has disappeared."""
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def cleanup_groups(children: dict) -> list:
    """Reap leaders and wait for whole owned groups at each bounded escalation phase."""
    errors = []
    for sig, seconds in ((signal.SIGINT, 5), (signal.SIGTERM, 3), (signal.SIGKILL, 2)):
        for proc in children.values():
            proc.poll()
        live = [proc for proc in children.values() if group_exists(proc.pid)]
        if not live:
            break
        if sig == signal.SIGKILL:
            errors.append("cleanup required SIGKILL for groups: " + str([p.pid for p in live]))
        for proc in live:
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass
            except OSError as error:
                errors.append(f"cleanup group {proc.pid}: {error}")
        end = time.monotonic() + seconds
        while True:
            for proc in children.values():
                proc.poll()
            if not any(group_exists(proc.pid) for proc in children.values()):
                break
            if time.monotonic() >= end:
                break
            time.sleep(0.1)
    for name, proc in children.items():
        proc.poll()
        if group_exists(proc.pid):
            errors.append(f"cleanup surviving group: {name} pgid={proc.pid}")
    return errors


def intentional_returncode(code) -> bool:
    """Requested shutdown must not hide crashes, force kills or unknown exit status."""
    return code in (0, -signal.SIGINT, -signal.SIGTERM)


def new_stream() -> dict:
    return {"count": 0, "first": None, "last": None, "invalid": 0}


def observe(stream: dict, stamp: float, valid: bool) -> None:
    """Count only advancing valid stamps; backward stamps invalidate the run."""
    if not valid or not math.isfinite(stamp) or stamp <= 0:
        stream["invalid"] += 1
    elif stream["last"] is not None and stamp < stream["last"]:
        stream["invalid"] += 1
    elif stream["last"] is None or stamp > stream["last"]:
        if stream["first"] is None:
            stream["first"] = stamp
        stream["last"] = stamp
        stream["count"] += 1


def verdict(streams: dict, visual_count: int, eof: bool, errors: list, outputs=None,
            require_visual: bool = True) -> str:
    """A passing smoke test is not quantitative trajectory/visual accuracy proof."""
    if (errors or set(streams) != set(OUTPUTS if outputs is None else outputs)
            or any(s["invalid"] for s in streams.values())):
        return "FAIL"
    sufficient = all(s["count"] >= 10 and s["first"] is not None
                     and s["last"] - s["first"] >= 5 for s in streams.values())
    visual = visual_count >= 2 or not require_visual
    return "PASS" if eof and sufficient and visual else "INCONCLUSIVE"


def collect_graph(node, edges: list) -> list:
    """Include unexpected topics and preserve discovery errors for diagnosis."""
    expected = {topic: (typ, pub, sub) for topic, typ, pub, sub in edges}
    topics = set(expected)
    rows = []
    try:
        topics.update(topic for topic, _ in node.get_topic_names_and_types())
    except Exception as error:
        rows.append({'topic': None, 'error': f'{type(error).__name__}: {error}'})
    for topic in sorted(topics):
        typ, pub, sub = expected.get(topic, (None, None, None))
        row = {'topic': topic, 'expected_type': typ,
               'expected_publisher': pub, 'expected_subscriber': sub}
        for key, query in (('publishers', node.get_publishers_info_by_topic),
                           ('subscribers', node.get_subscriptions_info_by_topic)):
            try:
                row[key] = [{'node': endpoint.node_name, 'type': endpoint.topic_type,
                             'reliability': str(endpoint.qos_profile.reliability),
                             'durability': str(endpoint.qos_profile.durability)}
                            for endpoint in query(topic)]
            except Exception as error:
                row[key] = [{'error': f'{type(error).__name__}: {error}'}]
        rows.append(row)
    return rows


def finalize_report(report: dict, started: float, diagnostic_captured: bool) -> None:
    """Final supervisor gate: cleanup/coverage failures cannot be hidden by EOF."""
    report['elapsed_wall_seconds'] = time.monotonic() - started
    errors = report['errors']
    if report['elapsed_wall_seconds'] > 600:
        errors.append('total supervisor time including cleanup exceeded 600 seconds')
    # The player can leave the bag's final sample unacknowledged at EOF. Allow
    # exactly that stamp, only when it postdates the last LiDAR callback, and
    # record it; every other gap keeps failing coverage.
    lidar_topic = report.get('input_lidar_topic')
    allowed = (terminal_message_gap(report.get('input_callbacks') or {}, lidar_topic)
               if lidar_topic else None)
    if allowed:
        report['terminal_message_lost'] = allowed
    for topic, row in report.get('input_callbacks', {}).items():
        if allowed and topic == allowed['topic']:
            continue
        if row['missing'] or row['unexpected']:
            errors.append(f"input callback coverage {topic}: missing={row['missing']} unexpected={row['unexpected']}")
    if report['mode'] == 'paused_diagnostic':
        report['diagnostic_captured'] = diagnostic_captured
        report['verdict'] = 'DIAGNOSTIC_CAPTURED' if diagnostic_captured and not errors else 'FAIL'
        report['claim'] = 'paused graph/package observation only; no playback or localization acceptance'
    else:
        if not report.get('input_callbacks'):
            errors.append('input callback coverage unavailable')
        report['verdict'] = verdict(report['streams'], report['positive_visual_retrievals'],
                                    report['eof'], errors,
                                    outputs=report.get('expected_outputs'),
                                    require_visual=report.get('require_visual', True))
    if report['verdict'] == 'INCONCLUSIVE':
        report['reason'] = ('normal EOF/output counts/span and positive visual retrieval gate not satisfied'
                            if report.get('require_visual', True) else
                            'normal EOF/output counts/span gate not satisfied (img_en=0: no visual gate)')


def main() -> int:
    """Supervise owned process groups, retaining evidence even on startup errors."""
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    started = time.monotonic()
    deadline = started + 590  # Reserve existing 5s/3s/2s cleanup inside 600s total.
    children, handles, errors = {}, [], []
    streams = {}  # Filled from the staged mapper config once its values are read.
    report = {"streams": streams, "errors": errors, "processes": {},
              "image_id": os.environ.get("T59_IMAGE_ID"), "sha256": {},
              "limits": {"total_wall_seconds": 600, "operational_wall_seconds": 590,
                         "cleanup_reserve_seconds": 10, "startup_phase_seconds": 60},
              "claim": "offline smoke only; no accuracy or hardware acceptance"}
    report["monitor"] = {"cloud_validation": "every XYZ via stdlib struct; not a realtime benchmark",
                         "cloud_validation_wall_seconds": 0.0}
    diagnostic = os.environ.get('T35_PAUSED_DIAGNOSTIC', '0') == '1'
    diagnostic_captured = False
    report['mode'] = 'paused_diagnostic' if diagnostic else 'replay'
    eof, player_exit_zero, node, ros = False, False, None, None
    clock = {"first": None, "last": None, "backward": False}
    expected_bag = None
    tracker = None
    next_progress = started
    next_scan = started
    phase = 'startup'
    report["clock"] = clock
    report['estimator_completion_proven'] = False
    report['input_callback_claim'] = 'pinned log stamps/counts at microsecond resolution; not estimator consumption'
    intentional = set()

    def interrupted(number, _frame):
        raise RuntimeError(f"supervisor received signal {number}")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, interrupted)

    def launch(name: str, command: list) -> None:
        stdout = (evidence / (name + ".stdout.log")).open("wb")
        stderr = (evidence / (name + ".stderr.log")).open("wb")
        handles.extend([stdout, stderr])
        proc = subprocess.Popen(command, stdout=stdout, stderr=stderr,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        children[name] = proc
        report["processes"][name] = {"argv": command, "pid": proc.pid}

    def health(allow_eof: bool = False) -> None:
        nonlocal next_progress, next_scan
        if time.monotonic() >= deadline:
            raise TimeoutError("590-second operational deadline exceeded; 10 seconds reserved for cleanup; no retry")
        for name, proc in children.items():
            code = proc.poll()
            if code is not None and not (allow_eof and name == "player" and code == 0):
                raise RuntimeError(f"unexpected {name} exit {code}")
        now = time.monotonic()
        if tracker is not None and now >= next_scan:
            tracker.update(evidence / 'mapper.stderr.log')
            next_scan = now + 1
        if now >= next_progress:
            counts = {} if tracker is None else {
                name: sum(seen.values()) for name, seen in tracker.observed.items()}
            print(json.dumps({'phase': phase, 'wall_seconds': round(now - started, 1),
                              'clock': clock['last'], 'callback_counts': counts,
                              'output_counts': {key: value['count'] for key, value in streams.items()}}),
                  flush=True)
            next_progress = now + 10

    def wait_until(predicate, description: str, seconds: float = 60) -> None:
        end = min(deadline, time.monotonic() + seconds)
        while time.monotonic() < end:
            health()
            ros.spin_once(node, timeout_sec=0.1)
            if predicate():
                return
        raise TimeoutError("readiness timeout: " + description)

    def call(future, description: str):
        wait_until(future.done, description)
        return future.result()

    try:
        if os.getuid() != 10001 or os.getgid() != 10001:
            raise RuntimeError("runtime must be UID:GID 10001:10001")
        mapper_config, camera_config = reviewed_configs(os.environ)
        report["mapper_config"], report["camera_config"] = mapper_config, camera_config
        for filename in (mapper_config, camera_config,
                         "playback_qos.yaml", "replay.py", "replay_progress.py"):
            report["sha256"][filename] = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
        with Path("/fast_livo_ws/src/fast_livo/Log/.t59-write-check").open("w") as probe:
            probe.write("UID10001 writable\n")

        print('Startup: loading ROS Python libraries (before readiness polling).', flush=True)
        import yaml
        import rclpy
        from ament_index_python.packages import get_package_prefix
        from rclpy.parameter import Parameter, parameter_value_to_python
        from rcl_interfaces.srv import GetParameters
        from rclpy.qos import (qos_profile_sensor_data, qos_check_compatible,
                               QoSCompatibility, ReliabilityPolicy, DurabilityPolicy)
        from nav_msgs.msg import Odometry
        from sensor_msgs.msg import Image, PointCloud2
        from rosgraph_msgs.msg import Clock
        from rosbag2_interfaces.srv import Resume

        ros = rclpy
        expected_bag = bag_expectation(yaml.safe_load((ROOT / "bag/metadata.yaml").read_text()))
        report["expected_bag"] = expected_bag
        rate = playback_rate(os.environ.get('T35_REPLAY_RATE', '0.25'), expected_bag['duration'])
        report['playback_rate'] = rate
        params = yaml.safe_load((ROOT / mapper_config).read_text())['laserMapping']['ros__parameters']
        report['input_lidar_topic'] = params['common.lid_topic']
        inputs = inputs_from_params(params)
        outputs = outputs_from_params(params)
        for key in outputs:
            streams[key] = new_stream()
        report['inputs'] = sorted(inputs)
        report['expected_outputs'] = sorted(outputs)
        report['require_visual'] = bool(params['common.img_en'])
        if not params['common.img_en']:
            report['claim'] += '; img_en=0 selects ONLY_LIO: no camera input or visual-fusion claim'
        if not diagnostic:
            databases = list((ROOT / 'bag').glob('*.db3'))
            if len(databases) != 1:
                raise ValueError('callback accounting requires the reviewed single-file SQLite bag')
            tracker = CallbackTracker(expected_callbacks(
                databases[0], inputs, params['time_offset.img_time_offset'],
                image_topic=params['common.img_topic']), callback_patterns(params))
            inventory = expected_bag['topics']
            if set(inputs) - set(inventory):
                raise ValueError('mapper input topics are absent from the bag metadata')
            unplayed = {name: inventory[name] for name in inventory if name not in inputs}
            report['unplayed_bag_topics'] = unplayed
            accounted = (sum(sum(counts.values()) for counts in tracker.expected.values())
                         + sum(unplayed.values()))
            if accounted != expected_bag['message_count']:
                raise ValueError('SQLite callback expectations plus unplayed topics differ from metadata message count')
        print('Startup: initializing ROS context and monitor node.', flush=True)
        ros.init()
        node = ros.create_node("t59_monitor", parameter_overrides=[Parameter("use_sim_time", value=True)])
        camera_yaml = yaml.safe_load((ROOT / camera_config).read_text())
        expected = camera_yaml.get("parameter_blackboard", camera_yaml.get("/**", {}))["ros__parameters"]
        required = ["cam_model", "cam_width", "cam_height", "scale", "cam_fx", "cam_fy",
                    "cam_cx", "cam_cy", "cam_d0", "cam_d1", "cam_d2", "cam_d3"]
        if expected["cam_model"] != "Pinhole":
            raise ValueError("only reviewed Pinhole camera path supported")
        for key in required[1:]:
            value = expected[key]
            wanted = int if key in ("cam_width", "cam_height") else float
            if type(value) is not wanted or not math.isfinite(value):
                raise ValueError("wrong camera parameter type/value: " + key)
            if key in ("cam_width", "cam_height", "scale", "cam_fx", "cam_fy") and value <= 0:
                raise ValueError("nonpositive camera parameter: " + key)

        def executable(package, name):
            return str(Path(get_package_prefix(package)) / "lib" / package / name)

        launch("camera", [executable("demo_nodes_cpp", "parameter_blackboard"), "--ros-args",
                          "-r", "__node:=parameter_blackboard", "--params-file",
                           str(ROOT / camera_config), "-p", "use_sim_time:=true"])
        camera = node.create_client(GetParameters, "/parameter_blackboard/get_parameters")
        wait_until(camera.service_is_ready, "camera parameter service")
        request = GetParameters.Request()
        request.names = required
        response = call(camera.call_async(request), "camera parameter values")
        values = [parameter_value_to_python(value) for value in response.values]
        if len(values) != len(required) or any(type(actual) is not type(expected[key])
                                               or actual != expected[key]
                                               for key, actual in zip(required, values)):
            raise ValueError("camera server does not contain exact staged Pinhole parameters")
        report["camera_parameters"] = dict(zip(required, values))

        # Raw images are pre-decoded offline into the raw bag: no republish
        # process, whose upstream shutdown segfaults (T3.5 GDB evidence).
        launch("mapper", [executable("fast_livo", "fastlivo_mapping"), "--ros-args",
                          "-r", "__node:=laserMapping", "--params-file",
                          str(ROOT / mapper_config), "-p", "use_sim_time:=true"])

        def stamp(message):
            return message.header.stamp.sec + message.header.stamp.nanosec * 1e-9

        def clock_cb(message):
            value = message.clock.sec + message.clock.nanosec * 1e-9
            if clock["first"] is None:
                clock["first"] = value
            if clock["last"] is not None and value < clock["last"]:
                clock["backward"] = True
            clock["last"] = value

        def receive(kind, message):
            if kind == "odom":
                p, q = message.pose.pose.position, message.pose.pose.orientation
                valid = valid_pose([p.x, p.y, p.z], [q.x, q.y, q.z, q.w])
            elif kind == "cloud":
                validation_started = time.monotonic()
                valid, reason, bad, total = valid_cloud(message)
                report["monitor"]["cloud_validation_wall_seconds"] += time.monotonic() - validation_started
                reasons = report["monitor"].setdefault("cloud_reasons", {})
                entry = reasons.setdefault(reason, {"clouds": 0, "bad_points": 0, "total_points": 0})
                entry["clouds"] += 1
                entry["bad_points"] += bad
                entry["total_points"] += total
                if valid:
                    pass
                elif (reason == "empty_or_nonpositive_dimensions" and total == 0
                        and len(message.data) == 0 and len(message.fields) == 0):
                    # Pinned source, publish_frame_world: in LIVO mode the LIO
                    # branch fills no message, so every LIO frame emits a
                    # default-empty heartbeat. Neutral: neither valid output
                    # nor a defect, but counted and reported separately.
                    heartbeats = report["monitor"].setdefault("cloud_heartbeats", 0)
                    report["monitor"]["cloud_heartbeats"] = heartbeats + 1
                    return
                if reason != "ok":
                    first_bad = report["monitor"].setdefault("cloud_first_bad", [])
                    if len(first_bad) < 5:
                        first_bad.append({"reason": reason, "bad_points": bad,
                                          "total_points": total,
                                          "width": message.width, "height": message.height,
                                          "point_step": message.point_step,
                                          "row_step": message.row_step,
                                          "data_bytes": len(message.data),
                                          "fields": [(f.name, f.datatype, f.offset, f.count)
                                                     for f in message.fields]})
            else:
                valid = valid_image(message)
            # All three source publishers stamp node->now(); no sensor-header rewrites.
            value = stamp(message)
            if clock["last"] is not None and abs(value - clock["last"]) > 2:
                valid = False
            observe(streams[kind], value, valid)

        subscriptions = [node.create_subscription(Clock, "/clock", clock_cb, qos_profile_sensor_data)]
        for key, cls in (("odom", Odometry), ("cloud", PointCloud2), ("rgb", Image)):
            if key in outputs:
                subscriptions.append(node.create_subscription(
                    cls, OUTPUTS[key][0], lambda message, kind=key: receive(kind, message),
                    qos_profile_sensor_data))

        launch("player", ["ros2", "bag", "play", str(ROOT / "bag"), "--clock", "100",
                          "--rate", str(rate), "--start-paused", "--disable-keyboard-controls",
                          "--qos-profile-overrides-path", str(ROOT / "playback_qos.yaml")])

        edges = [(topic, typ, "rosbag2_player", "laserMapping")
                 for topic, typ in inputs.items()]
        edges += [(topic, typ, "laserMapping", "t59_monitor") for topic, typ in outputs.values()]
        edges += [("/clock", "rosgraph_msgs/msg/Clock", "rosbag2_player", "t59_monitor")]

        def graph_ready():
            checked = []
            for topic, typ, publisher, subscriber in edges:
                pubs = [p for p in node.get_publishers_info_by_topic(topic)
                        if p.node_name == publisher and p.topic_type == typ]
                subs = [s for s in node.get_subscriptions_info_by_topic(topic)
                        if s.node_name == subscriber and s.topic_type == typ]
                if not pubs or not subs:
                    return False
                for pub in pubs:
                    if topic in inputs and (pub.qos_profile.reliability != ReliabilityPolicy.RELIABLE
                                            or pub.qos_profile.durability != DurabilityPolicy.VOLATILE):
                        return False
                    for sub in subs:
                        compatibility, _ = qos_check_compatible(pub.qos_profile, sub.qos_profile)
                        if compatibility != QoSCompatibility.OK:
                            return False
                checked.append({"topic": topic, "type": typ, "publisher": publisher,
                                "subscriber": subscriber, "publisher_qos": str(pubs[0].qos_profile),
                                "subscriber_qos": str(subs[0].qos_profile)})
            report["matched_edges"] = checked
            return True

        if diagnostic:
            # Observe current wiring while leaving the player paused.
            diagnostic_end = min(deadline, time.monotonic() + 20)
            while time.monotonic() < diagnostic_end:
                health()
                ros.spin_once(node, timeout_sec=0.1)
            report['graph_snapshot'] = collect_graph(node, edges)
            if any(row.get('error') or any('error' in endpoint
                       for key in ('publishers', 'subscribers')
                       for endpoint in row.get(key, []))
                   for row in report['graph_snapshot']):
                errors.append('graph snapshot contains query failures; diagnostic is incomplete')
            packages = subprocess.run(
                ['dpkg-query', '-W', 'ros-humble-image-transport',
                 'ros-humble-compressed-image-transport'],
                capture_output=True, text=True, timeout=10)
            report['image_transport_packages'] = {
                'returncode': packages.returncode, 'stdout': packages.stdout,
                'stderr': packages.stderr}
            diagnostic_captured = True
            report['playback_resumed'] = False

        if not diagnostic:
            try:
                wait_until(graph_ready, "all exact input/output graph edges and QoS")
            except TimeoutError:
                report['graph_snapshot'] = collect_graph(node, edges)
                raise
            resume = node.create_client(Resume, "/rosbag2_player/resume")
            wait_until(resume.service_is_ready, "paused player resume service")
            if expected_bag['duration'] / rate + 120 > deadline - time.monotonic():
                raise ValueError('remaining wall budget cannot fit requested playback and 120s drain')
            call(resume.call_async(Resume.Request()), "resume response")
            report['playback_resumed'] = True
            phase = 'playback'
            report["resumed_wall_offset"] = time.monotonic() - started
            while children["player"].poll() is None:
                health(allow_eof=True)
                ros.spin_once(node, timeout_sec=0.1)
            health(allow_eof=True)
            player_exit_zero = children["player"].returncode == 0
            phase = 'callback_drain'
            print('Player EOF: waiting for terminal sensor callbacks and five quiet log seconds; not estimator completion.',
                  flush=True)
            drain = min(deadline, time.monotonic() + 120)
            last_activity = time.monotonic()
            signature = None
            imu_allowance = prestart_allowance(
                sum(tracker.expected[params['common.imu_topic']].values()),
                expected_bag['duration'])
            gap_checked, terminal_gap = 0.0, None
            while True:
                health(allow_eof=True)
                ros.spin_once(node, timeout_sec=0.1)
                current = tuple((path.stat().st_size, path.stat().st_mtime_ns)
                                for path in (evidence / 'mapper.stdout.log', evidence / 'mapper.stderr.log'))
                now = time.monotonic()
                if current != signature:
                    signature, last_activity = current, now
                if now - gap_checked >= 1:
                    terminal_gap = terminal_message_gap(
                        reconcile_rows(tracker, params['common.imu_topic'], imu_allowance),
                        params['common.lid_topic'])
                    gap_checked = now
                state = drain_state(now, drain, last_activity,
                                    tracker.tails_seen() or terminal_gap is not None)
                if state != 'waiting':
                    report['callback_drain'] = {'state': state, 'max_seconds': 120,
                                                'quiet_seconds': 5, 'estimator_completion_proven': False}
                    if terminal_gap:
                        report['callback_drain']['terminal_message_gap'] = terminal_gap
                    if state == 'timeout':
                        errors.append('callback drain timed out; terminal callbacks/log inactivity not established')
                    break
            report["clock"] = clock
            if clock["backward"]:
                errors.append("clock moved backward")
            if clock["last"] is None or clock["first"] is None or clock["last"] <= clock["first"]:
                errors.append("clock did not advance")
    except Exception as error:
        errors.append(f"{type(error).__name__}: {error}")
        (evidence / "exception.log").write_text(traceback.format_exc())
    finally:
        # Prevent a second signal interrupting evidence/owned-group cleanup.
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, signal.SIG_IGN)
        for name, proc in children.items():
            code = proc.poll()
            if code is None:
                intentional.add(name)
            elif name != "player" or code != 0 or not player_exit_zero:
                errors.append(f"{name} exited before requested cleanup: {code}")
        try:
            errors.extend(cleanup_groups(children))
        except Exception as error:
            errors.append(f"process-group cleanup exception: {error}")
        for name, proc in children.items():
            report["processes"][name].update(returncode=proc.poll(),
                                            cleanup_requested=name in intentional)
            if proc.poll() is None:
                errors.append(f"{name} did not exit after SIGKILL")
            elif name in intentional and not intentional_returncode(proc.returncode):
                errors.append(f"{name} abnormal return code during cleanup: {proc.returncode}")
        for handle in handles:
            handle.close()
        if tracker is not None:
            tracker.update(evidence / 'mapper.stderr.log')
            # Pinned imu_cbk silently drops IMU before the first lidar callback;
            # a bounded strict startup prefix is reconciled separately in
            # reconcile_rows. Anything else stays missing and fails the run.
            if expected_bag is None:
                report['input_callbacks'] = tracker.summary()
            else:
                imu_topic = params['common.imu_topic']
                allowance = prestart_allowance(
                    sum(tracker.expected[imu_topic].values()), expected_bag['duration'])
                report['input_callbacks'] = reconcile_rows(tracker, imu_topic, allowance)
        # Inspect only finalized regular files, never a PIPE or still-running player.
        diagnostics = []
        for suffix in ("stdout", "stderr"):
            player_log = evidence / f"player.{suffix}.log"
            if player_log.exists():
                with player_log.open(errors="replace") as source:
                    diagnostics.extend(player_log_failures(source))
        errors.extend(diagnostics)
        complete = expected_bag is not None and clock_complete(clock, expected_bag)
        if player_exit_zero and not complete:
            errors.append("player exited 0 without clock covering metadata bounds within 0.25 simulated seconds")
        eof = player_exit_zero and complete and not diagnostics
        try:
            if node is not None:
                node.destroy_node()
            if ros is not None and ros.ok():
                ros.shutdown()
        except Exception as error:
            errors.append(f"ROS cleanup: {error}")
        visual_count = 0
        logfile = evidence / "mapper.stdout.log"
        if logfile.exists():
            with logfile.open(errors="replace") as source:
                for line in source:
                    match = re.search(r"\[ VIO \] Retrieve (\d+) points from visual sparse map", line)
                    visual_count += bool(match and int(match.group(1)) > 0)
        report.update(eof=eof, positive_visual_retrievals=visual_count)
        finalize_report(report, started, diagnostic_captured)
        (evidence / "result.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        print(json.dumps(report, allow_nan=False), flush=True)
    return 0 if report["verdict"] in ("PASS", "DIAGNOSTIC_CAPTURED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
