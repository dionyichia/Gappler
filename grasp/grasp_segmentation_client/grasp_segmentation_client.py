#!/usr/bin/env python3
"""The grasp client of the segmentation service (T2.1).

Feeds wrist camera frames to /segmentation/segment, picks one detection, and publishes the
three channels the arm already reads, with the same meaning as before:

  /camera/sam/mask      Image mono8, the chosen mask                  -> AnyGrasp, grasp_viz
  /object_centroid_2d   PointStamped: x pixel column, y pixel row,    -> grasp state machine
                        z median depth in metres
  /object_centroid      PointStamped, the 3D point in the camera      -> grasp_viz
                        optical frame

It is the only publisher of these three. Every message carries the camera frame's header, so a
reader can tell how old it is.

What to look for comes from /grasp/target (the aria client). Each word first sends an empty
Target, which stops the old target at once, then one Target after the gaze picked the object. That
one holds the word and a reference, a crop of the object in the glasses image. A Target without a
reference is not used: the client waits for one (T8.9a).

How the mask is picked (T8.9a). SAM 3 finds every object that fits the word. The client crops each
mask the way the aria client cropped the reference (box plus crop_margin_px), turns every crop and
the reference into a CLIP vector, and takes the mask whose vector is closest to the reference
(cosine score). The rule is cross_camera_mask_match_rule.py: no score of at least 0.56, or two
masks within 0.01 of each other, and nothing is published, so the arm waits instead of taking the
wrong object.

To test without the glasses, grasp_config.yaml sets a default prompt, used only while nothing
publishes on /grasp/target. With no reference, it takes the mask SAM 3 is most sure of.

Frames are sent one request at a time. While a request is out, newer frames replace the waiting
one, so the next request is always the newest frame. A request with no reply after
segment_timeout_s (the service died mid-call) is given up, so the client never stalls.

/manipulation/goal_pose is not published (decided 2026-10-08, off for now). Nav integration
adds it.

    source grasp/grasp_env.sh
    python grasp/grasp_segmentation_client/grasp_segmentation_client.py
"""

import math
import time

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from geometry_msgs.msg import PointStamped
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from segmentation_interfaces.msg import Target
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CameraInfo, Image

from cross_camera_mask_match_rule import crop_to_mask, pick_mask_pair
from gappler_common import config
from memory_graph.clip_encoder import OpenClipEncoder   # imports torch only when created
from memory_graph.image_feature import l2_normalise

CFG = config("grasp", "grasp_segmentation_client")
TOPICS = CFG["topics"]
SERVICE_NAME = CFG["services"]["segmentation_segment"]


def pick_detection(detections):
    """The detection to grasp: highest score, and on a tie the larger mask. None if empty."""
    return max(detections, key=lambda d: (d.score, d.area_px), default=None)


def image_array(msg: Image) -> np.ndarray:
    """An rgb8 (H x W x 3) or mono8 (H x W) sensor_msgs/Image as a numpy array."""
    channels = 3 if msg.encoding == "rgb8" else 1
    rows = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    pixels = rows[:, :msg.width * channels]
    return pixels.reshape(msg.height, msg.width, 3) if channels == 3 else pixels


def reference_scores(detections, rgb: np.ndarray, ref_vec: np.ndarray, encoder) -> np.ndarray:
    """The CLIP cosine score of each detection's crop against the reference: one row, one column
    per detection. An empty mask scores 0."""
    crops = [crop_to_mask(rgb, image_array(d.mask) > 0) for d in detections]
    vecs = l2_normalise(encoder.encode([rgb if c is None else c[0] for c in crops]))
    vecs[[c is None for c in crops]] = 0
    return ref_vec @ vecs.T


class GraspSegmentationClient(Node):
    def __init__(self, default_prompt=None, encoder=None):
        super().__init__("grasp_segmentation_client")
        # CLIP loads here, not on the first Target: it takes a few seconds and about 0.5 GB of GPU.
        # The weights download once, on first use (memory_graph/clip_encoder.py). Tests pass a stand-in.
        self.encoder = OpenClipEncoder() if encoder is None else encoder
        self.ref_vec = None          # CLIP vector of the Target's reference, None = no reference
        self.targets = 0             # bumped by every Target: is a reply still current
        prompt = CFG["default_prompt"] if default_prompt is None else default_prompt
        self.prompt = prompt.strip().lower()
        self.default_in_use = bool(self.prompt)   # dropped for good once the glasses speak
        self.camera_info = None
        self.waiting = None          # newest (rgb, depth) not yet sent
        self.future = None           # the request out now, None when none is
        self.sent_at = 0.0           # time.monotonic() when it was sent
        self.timeout_s = CFG["segment_timeout_s"]

        self.create_subscription(CameraInfo, TOPICS["wrist_camera_info"], self.on_camera_info, 1)
        self.create_subscription(Target, TOPICS["grasp_target"], self.on_target, 10)
        self.sync = ApproximateTimeSynchronizer(
            [Subscriber(self, Image, TOPICS["wrist_camera_color"]),
             Subscriber(self, Image, TOPICS["wrist_camera_aligned_depth"])],
            # The driver gives aligned depth the colour frame's own stamp: 598 of 598 pairs were
            # 0.0 ms apart on the lab box (2026-10-13). A small slop skips a colour frame whose
            # depth was dropped, instead of pairing it with a neighbour 33 ms off.
            queue_size=10, slop=0.01)
        self.sync.registerCallback(self.on_frames)

        self.service = self.create_client(Segment, SERVICE_NAME)
        self.mask_pub = self.create_publisher(Image, TOPICS["wrist_camera_object_mask"], 10)
        self.centroid_pub = self.create_publisher(PointStamped, TOPICS["object_centroid_2d"], 10)
        self.centroid_viz_pub = self.create_publisher(
            PointStamped, TOPICS["object_centroid_viz"], 10)

        source = f"default prompt {self.prompt!r} (testing only)" if self.default_in_use \
            else TOPICS["grasp_target"]
        self.get_logger().info(f"Grasp segmentation client ready, looking for: {source}")

    # ---- inputs ----
    def on_camera_info(self, msg: CameraInfo):
        if self.camera_info is None:
            self.camera_info = msg

    def on_target(self, msg: Target):
        self.default_in_use = False
        self.targets += 1
        self.prompt, self.ref_vec = "", None
        prompt = msg.prompt.strip().lower()
        if not prompt:
            self.get_logger().info("Target cleared")
            return
        if msg.reference.width == 0:
            self.get_logger().warn(f"Target {prompt!r} has no reference crop: waiting for one "
                                   "(T8.9a)")
            return
        try:
            self.ref_vec = l2_normalise(self.encoder.encode([image_array(msg.reference)]))
        except Exception as e:   # e.g. CUDA out of memory on the shared box
            self.get_logger().error(f"CLIP failed on the reference, target {prompt!r} dropped: {e}")
            return
        self.prompt = prompt
        self.get_logger().info(f"Target: {prompt!r}, with a reference crop")

    def on_frames(self, rgb: Image, depth: Image):
        self.waiting = (rgb, depth)
        self.send_if_ready()

    # ---- one request at a time ----
    def send_if_ready(self):
        if self.default_in_use and self.count_publishers(TOPICS["grasp_target"]) > 0:
            self.default_in_use = False
            self.prompt = ""
            self.targets += 1
            self.get_logger().info("Glasses client found: default prompt dropped")
        # rclpy futures never time out: if the service dies mid-call, this one is never completed.
        if self.future is not None and time.monotonic() - self.sent_at > self.timeout_s:
            self.get_logger().warn(f"No reply from {SERVICE_NAME} in {self.timeout_s:g} s, "
                                   "giving up on that request")
            self.future = None
        if self.future is not None or self.waiting is None or self.camera_info is None \
                or not self.prompt:
            return
        if not self.service.service_is_ready():
            return   # keep the frame, a newer one replaces it
        rgb, depth = self.waiting
        self.waiting = None
        request = Segment.Request(image=rgb, depth=depth, camera_info=self.camera_info,
                                  prompt=self.prompt, min_score=CFG["min_score"],
                                  max_detections=CFG["max_detections"])
        self.sent_at = time.monotonic()
        self.future = self.service.call_async(request)
        self.future.add_done_callback(
            lambda f, target=self.targets: self.on_reply(f, target, rgb))

    def on_reply(self, future, target: int, rgb: Image):
        if future is not self.future:
            return   # a late reply to a request already given up on
        self.future = None
        response = future.result()
        if target == self.targets:    # a reply from before the newest Target is dropped
            self.publish(response, rgb)
        self.send_if_ready()

    # ---- outputs ----
    def pick(self, detections, rgb: Image):
        """The detection to grasp, or None. With a reference, the one CLIP matches to it.
        Without (the test-only default prompt), the one SAM 3 is most sure of."""
        if self.ref_vec is None:
            return pick_detection(detections)
        if not detections:
            return None
        try:
            scores = reference_scores(detections, image_array(rgb), self.ref_vec, self.encoder)
        except Exception as e:   # e.g. CUDA out of memory on the shared box: skip this frame
            self.get_logger().error(f"CLIP failed on the wrist masks: {e}",
                                    throttle_duration_sec=2.0)
            return None
        pair = pick_mask_pair(scores, lambda rows: rows[0])
        if pair is None:
            self.get_logger().info(
                f"No mask matches the reference (scores {np.round(scores[0], 3).tolist()}): "
                "nothing sent", throttle_duration_sec=2.0)
            return None
        return detections[pair[1]]

    def publish(self, response: Segment.Response, rgb: Image):
        if response is None or not response.success:
            reason = response.message if response is not None else "no reply"
            self.get_logger().warn(f"Segment failed: {reason}")
            return
        det = self.pick(response.detections, rgb)
        if det is None:
            return
        det.mask.header = response.header
        self.mask_pub.publish(det.mask)
        if math.isnan(det.depth_m):
            return   # no valid depth under the mask: the arm gets no centroid
        centroid = PointStamped(header=response.header)
        centroid.point.x, centroid.point.y, centroid.point.z = det.u, det.v, det.depth_m
        self.centroid_pub.publish(centroid)
        if det.has_point:
            self.centroid_viz_pub.publish(PointStamped(header=response.header, point=det.point))


def main():
    rclpy.init()
    node = GraspSegmentationClient()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):   # Ctrl-C
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
