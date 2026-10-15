#!/usr/bin/env python3
"""The aria client of the segmentation service (T2.1, T2.9).

Turns what you say and what you look at into what the arm looks for.

1. A word on /aria/audio/prompt becomes a Target on /grasp/target at once, which the grasp
   segmentation client reads. The stop word clears it.
   Each word also sends /manipulator/grasp_request, which opens the state machine's trigger gate
   (T1.25), so every time you ask is one grasp (T2.6). The stop word sends none.
2. If the glasses image and gaze are coming in, the newest glasses image is segmented with the
   same word, and the mask you look at is picked: the one under your gaze averaged over the last
   gaze_window_s, else the nearest within pick_radius_px (gaze_pick.py). A second Target with the
   same word follows, carrying that object's crop and mask as its reference. If nothing is near
   the gaze, the word alone stands.

Every word is sent, even a repeat, and /grasp/target is not latched. So if the grasp client
restarts, it looks for nothing until you say the word again: a restart never resumes an old
command on its own (Dion, 2026-10-13). A reply that comes back after any newer word, even the
same one, or the stop word is dropped, so it never brings an old target back.

Gaze arrives in the pixels of the published undistorted image (et_worker, T2.9).

    source aria/aria_env.sh && source install/local_setup.bash
    python aria/aria_app/services/aria_segmentation_client/aria_segmentation_client.py
"""

import time
from collections import deque

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import Point
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from segmentation_interfaces.msg import Target
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CompressedImage, Image
from std_msgs.msg import Empty, String

from config import VIDEO_QOS, AudioStreamingPipelineConfig, ROS2Topics
from gappler_common import config
from gaze_pick import mean_gaze, pick_mask

STOP_KEYWORD = AudioStreamingPipelineConfig.STOP_KEYWORD
CFG = config("aria", "aria_segmentation_client")
SERVICE_NAME = CFG["services"]["segmentation_segment"]


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
            Point, ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value, self.on_gaze, VIDEO_QOS)
        self.target_pub = self.create_publisher(Target, ROS2Topics.GRASP_TARGET.value, 10)
        self.request_pub = self.create_publisher(
            Empty, ROS2Topics.MANIPULATOR_GRASP_REQUEST.value, 10)
        self.service = self.create_client(Segment, SERVICE_NAME)
        self.prompt = ""
        self.words = 0                              # bumped by every word: is a reply still current
        self.image, self.image_at = None, -np.inf   # newest glasses image and when it came
        self.wait_until = -np.inf                   # segment the next image if it comes by then
        self.gaze = deque(maxlen=200)               # (time, x, y), ~20 s at 10 fps
        self.get_logger().info(
            f"Aria segmentation client ready: {ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value} "
            f"-> {ROS2Topics.GRASP_TARGET.value}")

    def on_image(self, msg: CompressedImage):
        self.image, self.image_at = msg, time.monotonic()
        if self.wait_until == -np.inf:
            return
        on_time, self.wait_until = self.image_at <= self.wait_until, -np.inf
        if on_time:
            self.segment(self.prompt)
        else:
            self.get_logger().info("No glasses image within image_wait_s: the word alone stands")

    def on_gaze(self, msg: Point):
        self.gaze.append((time.monotonic(), msg.x, msg.y))

    def on_prompt(self, msg: String):
        words = msg.data.strip().lower()
        if not words:
            return
        self.prompt = "" if words == STOP_KEYWORD else words
        self.words += 1
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

    def segment(self, prompt: str):
        """Ask the service about the newest glasses image. If that image is older than the gaze
        window, the gaze may not match it, so wait for the next one (on_image). Skipped, with the
        reason logged, when no glasses image or recent gaze has come, or the service is not up."""
        now, window = time.monotonic(), CFG["gaze_window_s"]
        if self.image is None:
            self.get_logger().info("No glasses image: the word alone is sent")
            return
        if now - self.image_at > window:
            self.wait_until = now + CFG["image_wait_s"]
            self.get_logger().info(f"Glasses image is {now - self.image_at:.1f} s old: "
                                   "waiting for the next one")
            return
        gaze = mean_gaze(self.gaze, now, window)
        if gaze is None:
            self.get_logger().info("No recent gaze: the word alone is sent")
            return
        if not self.service.service_is_ready():
            self.get_logger().warn(f"{SERVICE_NAME} not up: the word alone is sent")
            return
        header = self.image.header
        # publish_image encoded the RGB array as if it were BGR, so decoding gives RGB back
        rgb = cv2.imdecode(np.frombuffer(self.image.data, np.uint8), cv2.IMREAD_COLOR)
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
        i, dist = pick_mask(masks, *gaze, CFG["pick_radius_px"])
        if i is None:
            # ponytail: the word alone stands. T7.4 is to go back to navigation along the gaze ray
            self.get_logger().info(f"{len(masks)} found, none near the gaze (nearest {dist:.0f} px): "
                                   "the word alone stands")
            return
        det = response.detections[i]
        x, y, w, h = det.bbox.x_offset, det.bbox.y_offset, det.bbox.width, det.bbox.height
        target = Target(prompt=prompt, header=header,
                        reference=image_msg(rgb[y:y + h, x:x + w], "rgb8", header),
                        reference_mask=image_msg(masks[i][y:y + h, x:x + w], "mono8", header))
        self.target_pub.publish(target)
        self.get_logger().info(f"Looked at: {prompt!r} #{i + 1} of {len(masks)}, score "
                               f"{det.score:.2f}, {dist:.0f} px from the gaze, reference sent")


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
