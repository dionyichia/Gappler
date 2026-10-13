"""The segmentation service with the real SAM 3, on a frame of the recorded box video (T2.1).

Run by bench/segmentation_service.sh, which has already proven the ROS channel is private and
empty. Reads one colour frame, the depth frame with the same stamp and the camera info straight
from the bag, starts segmentation_service.py, and calls it three times:

  image only          success, a box found, no depth, no 3D point
  image + depth + K   success, a box found, depth in range, a 3D point
  empty prompt        refused with a reason
  second service      a second copy refuses to start, before loading SAM 3

The numbers printed (inference time, score, area, depth) are the baseline for later changes.
Exit 0 = no FAIL, 1 = a FAIL. No camera, no arm: nothing can move.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import rclpy
    import rosbag2_py
    from rclpy.serialization import deserialize_message
    from segmentation_interfaces.srv import Segment
    from sensor_msgs.msg import CameraInfo, Image
except ImportError as e:
    print(f"SKIP: {e} -- source shared_services/shared_services_env.sh after ./build.sh")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / os.environ.get("BENCH_SEG_LOG", "log/bench_segmentation_service.txt")
BAG = os.environ.get("WRIST_CAMERA_BAG", str(REPO / "assets/recordings/wrist_camera"))
PROMPT = "box"           # the recording shows a hand holding a cardboard box
LOAD_SEC = 180.0         # SAM 3 loading on the GPU
CALL_SEC = 60.0
DEPTH_RANGE_M = (0.1, 3.0)
COLOR = "/camera/camera/color/image_raw"
DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
INFO = "/camera/camera/color/camera_info"


def stamp(msg):
    return (msg.header.stamp.sec, msg.header.stamp.nanosec)


def frame_from_bag():
    """The first colour frame with a depth frame of the same stamp, and the camera info."""
    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=BAG, storage_id="sqlite3"),
                rosbag2_py.ConverterOptions("cdr", "cdr"))
    types = {COLOR: Image, DEPTH: Image, INFO: CameraInfo}
    colors, depths, info = {}, {}, None
    while reader.has_next():
        topic, data, _ = reader.read_next()
        if topic not in types:
            continue
        msg = deserialize_message(data, types[topic])
        if topic == INFO:
            info = info or msg
        else:
            (colors if topic == COLOR else depths)[stamp(msg)] = msg
        both = sorted(set(colors) & set(depths))
        if both and info is not None:
            return colors[both[0]], depths[both[0]], info
    raise RuntimeError(f"no colour and depth frame with the same stamp in {BAG}")


def main():
    color, depth, info = frame_from_bag()
    print(f"frame: {color.width}x{color.height} {color.encoding}, depth {depth.encoding}")

    rclpy.init()
    node = rclpy.create_node("bench_segmentation_service")
    client = node.create_client(Segment, "/segmentation/segment")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "w")
    service = subprocess.Popen(
        [sys.executable, str(REPO / "shared_services/segmentation/segmentation_service.py")],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

    def call(req):
        future = client.call_async(req)
        rclpy.spin_until_future_complete(node, future, timeout_sec=CALL_SEC)
        if not future.done():
            raise RuntimeError(f"no reply in {CALL_SEC:.0f} s")
        return future.result()

    def request(prompt, with_depth):
        req = Segment.Request(prompt=prompt, image=color)
        if with_depth:
            req.depth, req.camera_info = depth, info
        return req

    results = []   # (tag, name, detail)
    try:
        end = time.time() + LOAD_SEC
        while not client.wait_for_service(timeout_sec=1.0):
            if service.poll() is not None or time.time() > end:
                raise RuntimeError(f"service not up in {LOAD_SEC:.0f} s "
                                   f"(exit {service.poll()}) -- see {LOG.name}")

        res = call(request(PROMPT, with_depth=False))
        ok = res.success and len(res.detections) > 0 and not res.detections[0].has_point
        best = res.detections[0] if res.detections else None
        results.append(("PASS " if ok else "FAIL ", "image only",
                        f"{len(res.detections)} found, best score {best.score:.3f}, "
                        f"area {best.area_px} px, {res.inference_ms:.0f} ms"
                        if best else f"success={res.success} {res.message!r}, nothing found"))

        res = call(request(PROMPT, with_depth=True))
        best = res.detections[0] if res.detections else None
        ok = (res.success and best is not None and best.has_point
              and DEPTH_RANGE_M[0] < best.depth_m < DEPTH_RANGE_M[1])
        results.append(("PASS " if ok else "FAIL ", "image + depth + K",
                        f"best at pixel ({best.u:.0f}, {best.v:.0f}), depth {best.depth_m:.3f} m, "
                        f"point ({best.point.x:.3f}, {best.point.y:.3f}, {best.point.z:.3f}) m "
                        f"in {res.header.frame_id}, {res.inference_ms:.0f} ms"
                        if best else f"success={res.success} {res.message!r}, nothing found"))

        res = call(request("", with_depth=False))
        ok = not res.success and "prompt" in res.message
        results.append(("PASS " if ok else "FAIL ", "empty prompt", f"refused: {res.message!r}"))

        start = time.time()
        second = subprocess.run(
            [sys.executable, str(REPO / "shared_services/segmentation/segmentation_service.py")],
            capture_output=True, text=True, timeout=LOAD_SEC)
        took = time.time() - start
        ok = (second.returncode == 1 and "Not starting" in second.stderr
              and "Loading SAM 3" not in second.stdout + second.stderr)
        results.append(("PASS " if ok else "FAIL ", "second service",
                        f"exit {second.returncode} after {took:.1f} s, SAM 3 not loaded"
                        if ok else f"exit {second.returncode} after {took:.1f} s: "
                        f"{(second.stderr or second.stdout)[-300:]!r}"))
    except RuntimeError as e:
        results.append(("FAIL ", "setup", str(e)))
    finally:
        if service.poll() is None:
            os.killpg(service.pid, signal.SIGINT)
        try:
            service.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(service.pid, signal.SIGKILL)
        log.close()
        node.destroy_node()
        rclpy.shutdown()

    for tag, name, detail in results:
        print(f"  [{tag}] {name:<20} {detail}")
    failed = any(tag.strip() == "FAIL" for tag, _, _ in results)
    print("RESULT: FAIL" if failed else "RESULT: PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
