#!/usr/bin/env python3
"""The aria client of the segmentation service (T2.1, T2.9).

Turns what you say and what you look at into what the arm looks for.

1. A word on /aria/audio/prompt_stamped becomes a Target on /grasp/target at once, which the
   grasp segmentation client reads. The stop word clears it.
   Each word also sends /manipulator/grasp_request, which opens the state machine's trigger gate
   (T1.25), so every time you ask is one grasp (T2.6). The stop word sends none.
2. If the glasses image and gaze are coming in, the glasses image from when you spoke is
   segmented with the same word, and the mask you look at is picked by a vote (T2.19, T2.20):
   a. The word comes stamped with when you said it (T2.21). The gaze samples taken from
      gaze_before_word_s before the word started to when it ended are the ones from when you
      spoke.
   b. They pick the image: the one taken nearest the middle of them. If the gaze up to the
      word's end, or an image taken since the window's start, has not arrived yet, it waits up
      to matching_image_wait_s for them (images arrive 1 to 3 s late on the box).
   c. Every gaze sample taken within gaze_to_image_max_s of that image votes for the mask under
      it, else the nearest within pick_radius_px. The mask with at least vote_min_share of the
      votes wins (gaze_pick.py). A second Target with the same word follows,
   carrying that object's crop and mask as its reference. If nothing is near the gaze, the word
   alone stands.

Every word is sent, even a repeat, and /grasp/target is not latched. So if the grasp client
restarts, it looks for nothing until you say the word again: a restart never resumes an old
command on its own (Dion, 2026-10-13). A reply that comes back after any newer word, even the
same one, or the stop word is dropped, so it never brings an old target back.

Gaze arrives in the pixels of the published undistorted image (et_worker, T2.9). The word, the
gaze and the images are all stamped with their capture time on the glasses clock (T2.19, T2.21).

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
from segmentation_interfaces.msg import SpokenWord, Target
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Empty

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
            SpokenWord, ROS2Topics.AUDIO_PROMPT_STAMPED.value, self.on_prompt, 10)
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
        self.said = (-np.inf, -np.inf)              # glasses times the newest word started, ended
        self.wait_until = -np.inf      # waiting for an image from when you spoke, until then
        self.images = deque()          # (arrival, glasses time, CompressedImage), kept undecoded
        self.gaze = deque()            # (arrival, glasses time, x, y)
        self.get_logger().info(
            f"Aria segmentation client ready: {ROS2Topics.AUDIO_PROMPT_STAMPED.value} "
            f"-> {ROS2Topics.GRASP_TARGET.value}")

    def on_image(self, msg: CompressedImage):
        now = time.monotonic()
        self.images.append((now, seconds(msg.header.stamp), msg))
        drop_older(self.images, now)
        self.retry(now)

    def on_gaze(self, msg: PointStamped):
        now = time.monotonic()
        self.gaze.append((now, seconds(msg.header.stamp), msg.point.x, msg.point.y))
        drop_older(self.gaze, now)
        self.retry(now)

    def retry(self, now: float):
        """While waiting, try again. Past the wait, use what has come, even if it is from before
        you spoke."""
        if self.wait_until != -np.inf:
            self.segment(self.prompt, last_try=now > self.wait_until)

    def on_prompt(self, msg: SpokenWord):
        words = msg.word.strip().lower()
        if not words:
            return
        self.prompt = "" if words == STOP_KEYWORD else words
        self.words += 1
        self.said = (seconds(msg.header.stamp), seconds(msg.word_end))
        self.wait_until = -np.inf   # a new word or the stop word replaces any wait
        target = Target(prompt=self.prompt)
        target.header.stamp = self.get_clock().now().to_msg()
        self.target_pub.publish(target)
        if self.prompt:
            self.request_pub.publish(Empty())
            self.get_logger().info(f"Target: {self.prompt!r}, grasp requested")
            self.segment(self.prompt)
        else:
            self.get_logger().info("Target cleared")

    def segment(self, prompt: str, last_try: bool = False):
        """Ask the service about the glasses image from when you spoke (module docstring, 2).
        Waits (retry) while the gaze or the image from then has not arrived. Skipped, with the
        reason logged, when no gaze from then, or near the image, has come, or the service is
        not up."""
        if not self.gaze:
            self.wait_until = -np.inf
            self.get_logger().info("No gaze from the glasses: the word alone is sent")
            return
        start, end = self.said[0] - CFG["gaze_before_word_s"], self.said[1]
        missing = []
        if not any(t >= end for _, t, _, _ in self.gaze):
            missing.append("gaze")
        if not any(t >= start for _, t, _ in self.images):
            missing.append("glasses image")
        if missing and not last_try:
            if self.wait_until == -np.inf:
                self.wait_until = time.monotonic() + CFG["matching_image_wait_s"]
                self.get_logger().info(f"No {' or '.join(missing)} from when you spoke yet: waiting")
            return
        self.wait_until = -np.inf
        taken = [t for _, t, _, _ in self.gaze if start <= t <= end]
        if not taken or not self.images:
            self.get_logger().info(f"No {'gaze' if not taken else 'glasses image'} from when you "
                                   "spoke: the word alone stands")
            return
        middle = (min(taken) + max(taken)) / 2
        _, image_t, image = min(self.images, key=lambda i: abs(i[1] - middle))
        gaze = [(x, y) for _, t, x, y in self.gaze if abs(t - image_t) <= CFG["gaze_to_image_max_s"]]
        if not gaze:
            self.get_logger().info(f"No gaze within gaze_to_image_max_s of the nearest image, taken "
                                   f"{image_t - middle:+.1f} s from it: the word alone stands")
            return
        if not self.service.service_is_ready():
            self.get_logger().warn(f"{SERVICE_NAME} not up: the word alone is sent")
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
            self.get_logger().warn(f"Segment failed ({reason}): the word alone stands")
            return
        masks = [mask_array(d.mask) for d in response.detections]
        i, share, dist = vote(masks, gaze, CFG["pick_radius_px"], CFG["vote_min_share"])
        if i is None:
            # ponytail: the word alone stands. T2.18 is to ask the user, T7.4 to go back to
            # navigation along the gaze ray
            self.get_logger().info(f"{len(masks)} found, no clear vote from {len(gaze)} gaze samples "
                                   f"(best share {share:.2f}, distance {dist:.0f} px): "
                                   "the word alone stands")
            return
        det = response.detections[i]
        x, y, w, h = det.bbox.x_offset, det.bbox.y_offset, det.bbox.width, det.bbox.height
        target = Target(prompt=prompt, header=header,
                        reference=image_msg(rgb[y:y + h, x:x + w], "rgb8", header),
                        reference_mask=image_msg(masks[i][y:y + h, x:x + w], "mono8", header))
        self.target_pub.publish(target)
        self.get_logger().info(f"Looked at: {prompt!r} #{i + 1} of {len(masks)}, score "
                               f"{det.score:.2f}, {share:.0%} of {len(gaze)} gaze samples, "
                               f"{dist:.0f} px from them, reference sent")


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
