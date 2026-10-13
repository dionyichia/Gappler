#!/usr/bin/env python3
"""The segmentation service: owns the only SAM 3 and answers Segment requests (T2.1).

A caller sends one rgb8 image and one prompt, optionally with aligned depth and CameraInfo.
The reply lists every detection, best score first (segmentation_interfaces/srv/Segment.srv).
The service keeps nothing between calls apart from the loaded model, and knows nothing about
the arm, the glasses or the base: picking one detection is the caller's job.

    source shared_services/shared_services_env.sh
    python shared_services/segmentation/segmentation_service.py

It refuses to start if another segmentation service is already on the same ROS channel, loading
or serving, so SAM 3 is never loaded twice. Start it once, on its own: launchers start only their client.

Requests are answered one at a time, in order (one thread), so the GPU runs one SAM 3 call at
a time. The maths is in segmentation_logic.py. Settings: shared_services_config.yaml, and the
service name in shared/global_config.yaml `services:`.
"""

import sys
import time

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import Point
from rclpy.node import Node
from segmentation_interfaces.msg import Detection as DetectionMsg
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import Image, RegionOfInterest

from gappler_common import config, path
from segmentation_logic import (DEPTH_ENCODINGS, Detection, centroid_on_mask, depth_in_metres,
                                detections_from_sam3)

CFG = config("shared_services", "segmentation_service")
SERVICE_NAME = CFG["services"]["segmentation_segment"]
NODE_NAME = "segmentation_service"

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
        if depth.encoding not in DEPTH_ENCODINGS:
            raise ValueError(
                f"depth encoding {depth.encoding!r} not supported, "
                f"expected one of {sorted(DEPTH_ENCODINGS)}"
            )
        if (depth.width, depth.height) != (image.width, image.height):
            raise ValueError(
                f"depth is {depth.width}x{depth.height} but the image is "
                f"{image.width}x{image.height}: send depth aligned to the image"
            )
        dtype = DEPTH_ENCODINGS[depth.encoding][0]
        depth_m = depth_in_metres(image_to_array(depth, dtype, 1), depth.encoding)
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


class Sam3:
    """SAM 3 for still images, built here so the service does not depend on any subsystem.
    Same settings as aria's wrapper (aria/aria_app/services/object_recognition/sam3_model.py),
    which goes once aria calls this service. Imported inside, so tests with a stand-in need
    neither torch nor SAM 3."""

    def __init__(self, weights: str, min_score: float):
        import os

        import sam3
        import torch
        from sam3 import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor

        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            # bfloat16 to reduce GPU memory, switched on once and never off. A `with` block per
            # call was tried (2026-10-13) and cost ~30% throughput: leaving the block clears
            # autocast's cache of bfloat16 weights, so every call re-casts all of SAM 3.
            # ponytail: autocast is per thread. It covers the main thread, where rclpy.spin runs
            # every callback. With a MultiThreadedExecutor, enter it in each worker thread too.
            # It also applies to anything else this process runs on the GPU.
            torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
        bpe = os.path.join(os.path.dirname(sam3.__file__), "assets/bpe_simple_vocab_16e6.txt.gz")
        model = build_sam3_image_model(bpe_path=bpe, load_from_HF=False, checkpoint_path=weights)
        # SAM 3 drops results below its own threshold, so a request can raise min_score above this
        # but not lower it.
        self.processor = Sam3Processor(model, confidence_threshold=min_score)

    def process_text_prompt(self, image: np.ndarray, prompt: str) -> dict:
        state = self.processor.set_image(image)   # runs the image encoder
        self.processor.reset_all_prompts(state)
        return self.processor.set_text_prompt(state=state, prompt=prompt)   # text + masks


def another_server_running(node: Node, timeout_sec: float = 3.0, name: str = NODE_NAME) -> bool:
    """True if a segmentation service node is already on the channel, loading or serving.

    Looks for the node name, not the service: the node appears before SAM 3 loads (~20 s) and the
    service only after, so a second start during loading is refused too. The service still
    appears only once it can answer, so wait_for_service keeps meaning "ready" for clients.
    Waits up to timeout_sec for discovery.
    """
    # ponytail: two starts within the same timeout_sec can both pass. An OS file lock would close
    # that, but only on one machine. Add one if it ever happens.
    deadline = time.monotonic() + timeout_sec
    while True:
        if any(n == name for n, _ in node.get_node_names_and_namespaces()):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)


class SegmentationService(Node):
    def __init__(self, model=None, min_score=None, max_detections=None):
        super().__init__(NODE_NAME)   # visible from here on, which the start-up guard relies on
        self.min_score = CFG["min_score"] if min_score is None else min_score
        self.max_detections = CFG["max_detections"] if max_detections is None else max_detections
        if model is None:
            self.get_logger().info("Loading SAM 3...")
            model = Sam3(str(path("sam3_weights")), self.min_score)
        self.model = model
        self.create_service(Segment, SERVICE_NAME, self.segment)
        self.get_logger().info(f"Segmentation service ready on {SERVICE_NAME}")

    def segment(self, request: Segment.Request, response: Segment.Response) -> Segment.Response:
        start = time.monotonic()
        response.header = request.image.header
        try:
            # SAM 3 was built at self.min_score and drops anything below it, so a lower request
            # would silently get nothing extra. Refuse it, and anything outside 0 to 1.
            if request.min_score and not self.min_score <= request.min_score <= 1:
                raise ValueError(f"min_score {request.min_score:g} out of range: send 0 for the "
                                 f"default, or {self.min_score:g} to 1")
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
        else:
            for d in found:
                if not centroid_on_mask(d):
                    self.get_logger().warn(
                        f"'{request.prompt.strip()}': centroid ({d.u:.0f}, {d.v:.0f}) is off the "
                        "mask (ring or L shape?), so its 3D point is not on the object. "
                        "Callers that aim at the centroid may aim at empty space.",
                        throttle_duration_sec=5.0)
            response.detections = [detection_to_msg(d, request.image.header) for d in found]
            response.success = True
        response.inference_ms = (time.monotonic() - start) * 1000.0   # failures are timed too
        return response


def main():
    rclpy.init()
    # One service, one SAM 3: refuse before loading the model if another copy is loading or serving.
    probe = rclpy.create_node("segmentation_service_guard")
    running = another_server_running(probe)
    probe.destroy_node()
    if running:
        print(f"Not starting: a {NODE_NAME} node is already on this ROS channel, loading or "
              f"answering on {SERVICE_NAME}. Its callers use that one.", file=sys.stderr)
        rclpy.try_shutdown()
        sys.exit(1)
    node = SegmentationService()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):   # Ctrl-C
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
