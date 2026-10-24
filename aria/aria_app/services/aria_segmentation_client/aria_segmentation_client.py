#!/usr/bin/env python3
"""The aria client of the segmentation service (T2.1, T2.9).

Turns what you say and what you look at into what the arm looks for.

1. Each word on /aria/audio/prompt first sends an empty Target on /grasp/target, which clears
   the old target in the grasp segmentation client at once. After the gaze pick (2) comes one
   Target with the word, the crop of the object you looked at and its mask (the reference).
   Right after it comes /manipulator/grasp_request, which opens the state machine's trigger gate
   (T1.25), so every time you ask is one grasp (T2.6). The clear comes 1 to 3 s before the
   request, so the gate never opens while the old object is still being published.
   If nothing is picked, no Target follows and the arm does nothing: the grasp client waits for
   a reference (T8.9a, Dion 2026-10-24). The stop word sends only the empty Target.
2. The glasses image from when you spoke is segmented with the same word, and the mask you look
   at is picked by a vote (T2.19, T2.20):
   a. The gaze samples that arrived in the gaze_window_s ending speech_latency_s before the
      word came are the ones from when you spoke.
   b. Their glasses capture times pick the image: the one taken nearest the middle of them. If
      no image taken since the first of them has arrived yet, it waits up to
      matching_image_wait_s for one (images arrive 1 to 3 s late on the box).
   c. Every gaze sample taken within gaze_to_image_max_s of that image votes for the mask under
      it, else the nearest within pick_radius_px. The mask with at least vote_min_share of the
      votes wins (gaze_pick.py). That mask's crop is the Target's reference.

Every picked word is sent, even a repeat, and /grasp/target is not latched. So if the grasp client
restarts, it looks for nothing until you say the word again: a restart never resumes an old
command on its own (Dion, 2026-10-13). A reply that comes back after any newer word, even the
same one, or the stop word is dropped, so it never brings an old target back.

Gaze arrives in the pixels of the published undistorted image (et_worker, T2.9). Gaze and images
are stamped with their capture time on the glasses clock (T2.19). Arrival times only bridge the
word to the gaze, until T2.21 stamps the word too.

    source aria/aria_env.sh && source install/local_setup.bash
    python aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py
"""

import time
from collections import deque

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from segmentation_interfaces.msg import Target
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Empty, String

from config import VIDEO_QOS, AudioStreamingPipelineConfig, ROS2Topics
from gappler_common import config
from gaze_pick import vote

STOP_KEYWORD = AudioStreamingPipelineConfig.STOP_KEYWORD
CFG = config("aria", "aria_segmentation_client")
SERVICE_NAME = CFG["services"]["segmentation_segment"]
HISTORY_S = 20.0   # how long images and gaze are kept, by arrival time


def seconds(stamp) -> float:
    return stamp.sec + stamp.nanosec * 1e-9


def drop_older(history: deque, now: float) -> None:
    """Drop entries (arrival time, ...) that arrived more than HISTORY_S before now."""
    while history and history[0][0] < now - HISTORY_S:
        history.popleft()


def image_msg(array: np.ndarray, encoding: str, header=None) -> Image:
    """rgb8 (H x W x 3) or mono8 (H x W) numpy array -> sensor_msgs/Image."""
    array = np.ascontiguousarray(array, dtype=np.uint8)
    msg = Image(height=array.shape[0], width=array.shape[1], encoding=encoding,
                step=array.strides[0], data=array.tobytes())
    if header is not None:
        msg.header = header
    return msg


def mask_array(msg: Image) -> np.ndarray:
    """A Detection's mono8 mask -> bool H x W."""
    rows = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.step)
    return rows[:, :msg.width] > 0


class AriaSegmentationClient(Node):
    def __init__(self):
        super().__init__("aria_segmentation_client")
        self.create_subscription(
            String, ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value, self.on_prompt, 10)
        self.create_subscription(
            CompressedImage, ROS2Topics.RGB_CAMERA_UNDISTORTED.value, self.on_image, VIDEO_QOS)
        self.create_subscription(
            PointStamped, ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value, self.on_gaze, VIDEO_QOS)
        self.target_pub = self.create_publisher(Target, ROS2Topics.GRASP_TARGET.value, 10)
        self.request_pub = self.create_publisher(
            Empty, ROS2Topics.MANIPULATOR_GRASP_REQUEST.value, 10)
        self.service = self.create_client(Segment, SERVICE_NAME)
        self.prompt = ""
        self.words = 0                              # bumped by every word: is a reply still current
        self.word_at = -np.inf                      # when the newest word came
        self.wait_until = -np.inf      # waiting for an image from when you spoke, until then
        self.images = deque()          # (arrival, glasses time, CompressedImage), kept undecoded
        self.gaze = deque()            # (arrival, glasses time, x, y)
        self.get_logger().info(
            f"Aria segmentation client ready: {ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value} "
            f"-> {ROS2Topics.GRASP_TARGET.value}")

    def on_image(self, msg: CompressedImage):
        now = time.monotonic()
        self.images.append((now, seconds(msg.header.stamp), msg))
        drop_older(self.images, now)
        if self.wait_until != -np.inf:
            # past the wait, the nearest image is used even if it is from before you spoke
            self.segment(self.prompt, last_try=now > self.wait_until)

    def on_gaze(self, msg: PointStamped):
        now = time.monotonic()
        self.gaze.append((now, seconds(msg.header.stamp), msg.point.x, msg.point.y))
        drop_older(self.gaze, now)

    def on_prompt(self, msg: String):
        words = msg.data.strip().lower()
        if not words:
            return
        self.prompt = "" if words == STOP_KEYWORD else words
        self.words += 1
        self.word_at = time.monotonic()
        self.wait_until = -np.inf   # a new word or the stop word replaces any wait
        # Clear the old target at once, for a word and the stop word alike. The grasp client then
        # stops publishing the old object, so the grasp request sent after the pick cannot catch
        # one last centroid of it (T8.9a)
        clear = Target(prompt="")
        clear.header.stamp = self.get_clock().now().to_msg()
        self.target_pub.publish(clear)
        if self.prompt:
            self.get_logger().info(f"Heard {self.prompt!r}: old target cleared, picking what you look at")
            self.segment(self.prompt)
        else:
            self.get_logger().info("Target cleared")

    def segment(self, prompt: str, last_try: bool = False):
        """Ask the service about the glasses image from when you spoke (module docstring, 2).
        Waits (on_image) while no image taken since then has arrived. Skipped, with the reason
        logged, when no gaze from then, or near the image, has come, or the service is not up."""
        # from the word's arrival, not now: after an image wait, now is up to the wait later
        spoke, window = self.word_at - CFG["speech_latency_s"], CFG["gaze_window_s"]
        taken = [t for at, t, _, _ in self.gaze if spoke - window < at <= spoke]
        if not taken:
            self.wait_until = -np.inf
            self.get_logger().info("No gaze from when you spoke: no Target sent")
            return
        if not last_try and not any(t >= min(taken) for _, t, _ in self.images):
            if self.wait_until == -np.inf:
                self.wait_until = time.monotonic() + CFG["matching_image_wait_s"]
                self.get_logger().info("No glasses image from when you spoke yet: waiting")
            return
        self.wait_until = -np.inf
        middle = (min(taken) + max(taken)) / 2
        _, image_t, image = min(self.images, key=lambda i: abs(i[1] - middle))
        gaze = [(x, y) for _, t, x, y in self.gaze if abs(t - image_t) <= CFG["gaze_to_image_max_s"]]
        if not gaze:
            self.get_logger().info(f"No gaze within gaze_to_image_max_s of the nearest image, taken "
                                   f"{image_t - middle:+.1f} s from it: no Target sent")
            return
        if not self.service.service_is_ready():
            self.get_logger().warn(f"{SERVICE_NAME} not up: no Target sent")
            return
        self.get_logger().info(f"Image taken {image_t - middle:+.2f} s from the gaze while you "
                               f"spoke, {len(gaze)} gaze samples vote")
        header = image.header
        # publish_image encoded the RGB array as if it were BGR, so decoding gives RGB back
        rgb = cv2.imdecode(np.frombuffer(image.data, np.uint8), cv2.IMREAD_COLOR)
        future = self.service.call_async(Segment.Request(image=image_msg(rgb, "rgb8", header),
                                                         prompt=prompt))
        word = self.words
        future.add_done_callback(lambda f: self.on_reply(f, word, prompt, rgb, gaze, header))

    def on_reply(self, future, word: int, prompt: str, rgb: np.ndarray, gaze, header):
        if word != self.words:
            return   # a newer word, even the same one, or the stop word came in meanwhile
        response = future.result()
        if response is None or not response.success:
            reason = response.message if response is not None else "no reply"
            self.get_logger().warn(f"Segment failed ({reason}): no Target sent")
            return
        masks = [mask_array(d.mask) for d in response.detections]
        i, share, dist = vote(masks, gaze, CFG["pick_radius_px"], CFG["vote_min_share"])
        if i is None:
            # ponytail: nothing is sent. T2.18 is to ask the user, T7.4 to go back to
            # navigation along the gaze ray
            self.get_logger().info(f"{len(masks)} found, no clear vote from {len(gaze)} gaze samples "
                                   f"(best share {share:.2f}, distance {dist:.0f} px): "
                                   "no Target sent")
            return
        det = response.detections[i]
        # The box plus crop_margin_px (shared/global_config.yaml). The grasp client crops each
        # wrist mask the same way (cross_camera_mask_match_rule.crop_to_mask), so CLIP compares
        # like with like
        m = CFG["crop_margin_px"]
        x0, y0 = max(det.bbox.x_offset - m, 0), max(det.bbox.y_offset - m, 0)
        x1, y1 = det.bbox.x_offset + det.bbox.width + m, det.bbox.y_offset + det.bbox.height + m
        target = Target(prompt=prompt, header=header,
                        reference=image_msg(rgb[y0:y1, x0:x1], "rgb8", header),
                        reference_mask=image_msg(masks[i][y0:y1, x0:x1], "mono8", header))
        self.target_pub.publish(target)
        self.request_pub.publish(Empty())
        self.get_logger().info(f"Target: {prompt!r} #{i + 1} of {len(masks)}, score "
                               f"{det.score:.2f}, {share:.0%} of {len(gaze)} gaze samples, "
                               f"{dist:.0f} px from them, reference sent, grasp requested")


def main():
    rclpy.init()
    node = AriaSegmentationClient()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):   # Ctrl-C
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
