#!/usr/bin/env python3
"""The segmentation service: owns the only SAM 3 and answers Segment requests (T2.1).

A caller sends one rgb8 image and one prompt, optionally with aligned depth and CameraInfo.
The reply lists every detection, best score first (segmentation_interfaces/srv/Segment.srv).
The service keeps nothing between calls apart from the loaded model, and knows nothing about
the arm, the glasses or the base: picking one detection is the caller's job.

    source shared_services/shared_services_env.sh
    python shared_services/segmentation/segmentation_service.py

It refuses to start if another segmentation service already answers on the same ROS channel, so
SAM 3 is never loaded twice. Start it once, on its own: launchers start only their client.

Requests are answered one at a time, in order (one thread), so the GPU runs one SAM 3 call at
a time. The maths is in segmentation_logic.py. Settings: shared_services_config.yaml, and the
service name in shared/global_config.yaml `services:`.
"""

import sys
import time

import numpy as np
import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node
from segmentation_interfaces.msg import Detection as DetectionMsg
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import Image, RegionOfInterest

from gappler_common import config
from segmentation_logic import Detection, depth_in_metres, detections_from_sam3

CFG = config("shared_services", "segmentation_service")
SERVICE_NAME = CFG["services"]["segmentation_segment"]

# numpy type of one depth pixel, by ROS encoding. The units are in segmentation_logic.py.
DEPTH_DTYPE = {"16UC1": np.uint16, "mono16": np.uint16, "32FC1": np.float32}


def image_to_array(msg: Image, dtype, channels: int) -> np.ndarray:
    """An Image message's pixels as an array, H x W (x channels). Copes with padded rows."""
    itemsize = np.dtype(dtype).itemsize
    if msg.is_bigendian and itemsize > 1:
        raise ValueError(f"{msg.encoding} image is big-endian, which is not supported")
    row_bytes = msg.width * channels * itemsize
    if msg.step < row_bytes or len(msg.data) < msg.step * msg.height:
        raise ValueError(
            f"{msg.encoding} image data is too short for {msg.width}x{msg.height} "
            f"(step {msg.step}, {len(msg.data)} bytes)"
        )
    rows = np.frombuffer(msg.data, np.uint8, msg.step * msg.height).reshape(msg.height, msg.step)
    pixels = np.ascontiguousarray(rows[:, :row_bytes]).view(dtype)
    shape = (msg.height, msg.width, channels) if channels > 1 else (msg.height, msg.width)
    return pixels.reshape(shape)


def read_request(request: Segment.Request):
    """The request's rgb array, depth in metres (or None) and K (or None). Raises on bad input."""
    if not request.prompt.strip():
        raise ValueError("empty prompt: say what to look for")
    image = request.image
    if image.encoding != "rgb8":
        raise ValueError(f"image encoding {image.encoding!r} not supported, send rgb8")
    rgb = image_to_array(image, np.uint8, 3)

    depth_m = None
    depth = request.depth
    if depth.width:
        if depth.encoding not in DEPTH_DTYPE:
            raise ValueError(
                f"depth encoding {depth.encoding!r} not supported, "
                f"expected one of {sorted(DEPTH_DTYPE)}"
            )
        if (depth.width, depth.height) != (image.width, image.height):
            raise ValueError(
                f"depth is {depth.width}x{depth.height} but the image is "
                f"{image.width}x{image.height}: send depth aligned to the image"
            )
        depth_m = depth_in_metres(image_to_array(depth, DEPTH_DTYPE[depth.encoding], 1),
                                  depth.encoding)
    k = list(request.camera_info.k)
    return rgb, depth_m, k


def detection_to_msg(det: Detection, header) -> DetectionMsg:
    msg = DetectionMsg()
    msg.mask = Image(header=header, height=det.mask.shape[0], width=det.mask.shape[1],
                     encoding="mono8", step=det.mask.shape[1],
                     data=det.mask.astype(np.uint8).tobytes())
    msg.score = det.score
    x, y, w, h = det.bbox
    msg.bbox = RegionOfInterest(x_offset=x, y_offset=y, width=w, height=h)
    msg.area_px = det.area_px
    msg.u, msg.v = det.u, det.v
    msg.depth_m = det.depth_m
    msg.has_point = det.point is not None
    if det.point is not None:
        msg.point = Point(x=det.point[0], y=det.point[1], z=det.point[2])
    return msg


def load_sam3(min_score: float):
    """The real model. Imported here so tests with a stand-in need neither torch nor SAM 3."""
    from config import ModelPaths  # aria/aria_app, on PYTHONPATH via shared_services_env.sh
    from services.object_recognition.sam3_model import SAM3Model

    # SAM 3 drops results below its own threshold, so a request can raise min_score above this
    # but not lower it.
    return SAM3Model(checkpoint_path=str(ModelPaths.SAM3_PATH), confidence_threshold=min_score)


def another_server_running(node: Node, timeout_sec: float = 3.0, name: str = SERVICE_NAME) -> bool:
    """True if something already answers on the service name. Waits up to timeout_sec for discovery."""
    probe = node.create_client(Segment, name)
    try:
        return probe.wait_for_service(timeout_sec=timeout_sec)
    finally:
        node.destroy_client(probe)


class SegmentationService(Node):
    def __init__(self, model=None, min_score=None, max_detections=None):
        super().__init__("segmentation_service")
        self.min_score = CFG["min_score"] if min_score is None else min_score
        self.max_detections = CFG["max_detections"] if max_detections is None else max_detections
        if model is None:
            self.get_logger().info("Loading SAM 3...")
            model = load_sam3(self.min_score)
        self.model = model
        self.create_service(Segment, SERVICE_NAME, self.segment)
        self.get_logger().info(f"Segmentation service ready on {SERVICE_NAME}")

    def segment(self, request: Segment.Request, response: Segment.Response) -> Segment.Response:
        start = time.monotonic()
        response.header = request.image.header
        try:
            rgb, depth_m, k = read_request(request)
            state = self.model.process_text_prompt(rgb, request.prompt.strip())
            found = detections_from_sam3(
                state,
                request.min_score or self.min_score,
                request.max_detections or self.max_detections,
                depth_m,
                k,
            )
        except Exception as e:  # a bad request or a model failure is an answer, never a crash
            response.success = False
            response.message = f"{type(e).__name__}: {e}"
            self.get_logger().warn(f"Segment failed: {response.message}")
            return response
        response.detections = [detection_to_msg(d, request.image.header) for d in found]
        response.success = True
        response.inference_ms = (time.monotonic() - start) * 1000.0
        return response


def main():
    rclpy.init()
    # One service, one SAM 3: refuse before loading the model if another copy already answers.
    probe = rclpy.create_node("segmentation_service_guard")
    running = another_server_running(probe)
    probe.destroy_node()
    if running:
        print(f"Not starting: a segmentation service already answers on {SERVICE_NAME} "
              "on this ROS channel. Its callers use that one.", file=sys.stderr)
        rclpy.try_shutdown()
        sys.exit(1)
    node = SegmentationService()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
