import logging
import pickle
import threading
import time
from multiprocessing.synchronize import Event
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch
from geometry_msgs.msg import Point
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup, ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String, UInt8MultiArray

from config import AudioStreamingPipelineConfig, ModelPaths, ROS2Topics
from services.feature_matching import FeatureMatcher
from services.object_recognition import SAM3Model
from services.ros import (
    ImageHelper,
    ROSPublisher,
    ROSSubscriber,
    subscribe_realsense_color_feed,
)

logger = logging.getLogger(__name__)

PROMPT = "mouse"


class CameraFeed:
    """Holds the latest frame and a monotonic ID for one camera."""

    def __init__(self):
        self._image: Optional[np.ndarray] = None
        self._image_id: int = 0
        self._lock = threading.Lock()

    def update(self, frame: np.ndarray) -> None:
        with self._lock:
            self._image = frame
            self._image_id += 1

    def get(self) -> Tuple[Optional[np.ndarray], int]:
        with self._lock:
            if self._image is None:
                return None, -1
            return self._image.copy(), self._image_id


class ObjectRecognitionPipeline:
    def __init__(self, quit_event: Event):
        self._quit_event = quit_event

        self.prompt = PROMPT
        self.model = SAM3Model(
            checkpoint_path=ModelPaths.SAM3_PATH,
            confidence_threshold=0.5,
        )

        self._aria_inference_state: Optional[Dict[str, Any]] = None
        self._aria_locked_image: Optional[np.ndarray] = None

        self._feature_matcher = FeatureMatcher()

        self._aria_feed = CameraFeed()
        self._ros_feed = CameraFeed()
        self._gaze_point: Optional[Tuple[float, float]] = None
        self._state_lock = threading.Lock()

        self._setup_ros_node()

    # ---------------------------------------------------------------------------
    # ROS setup
    # ---------------------------------------------------------------------------

    def _setup_ros_node(self) -> None:
        """Initialise the ROS node, subscriptions, executor, and publishers."""
        self._object_recognition_node = ROSSubscriber("object_recognition_node")

        image_cb_group = ReentrantCallbackGroup()
        state_cb_group = MutuallyExclusiveCallbackGroup()

        subscribe_realsense_color_feed(
            self._object_recognition_node,
            self._on_realsense_image,
            callback_group=image_cb_group,
        )
        self._object_recognition_node.subscribe(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_aria_image,
            callback_group=image_cb_group,
        )
        self._object_recognition_node.subscribe(
            String,
            ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value,
            self._on_prompt,
            callback_group=state_cb_group,
        )
        self._object_recognition_node.subscribe(
            Point,
            ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
            self._on_gaze,
            callback_group=state_cb_group,
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._object_recognition_node)
        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        self.aria_inference_publisher = ROSPublisher(
            "Aria_inference_publisher",
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
        )
        self.ros_inference_publisher = ROSPublisher(
            "ROS_inference_publisher",
            UInt8MultiArray,
            ROS2Topics.ROS_CAMERA_WITH_OBJECT_MASKS.value,
        )

    # ---------------------------------------------------------------------------
    # ROS callbacks
    # ---------------------------------------------------------------------------

    def _on_aria_image(self, msg: CompressedImage) -> None:
        try:
            frame = ImageHelper.uncompress_image(msg.data)

            if frame is None:
                logger.warning("Received empty Aria frame, skipping")
                return
            self._aria_feed.update(frame)
        except Exception as e:
            logger.error(f"Error decoding Aria image: {e}", exc_info=True)

    def _on_realsense_image(self, frame: np.ndarray) -> None:
        if frame is None:
            logger.warning("Received empty RealSense frame, skipping")
            return
        self._ros_feed.update(frame)

    def _on_gaze(self, msg: Point) -> None:
        with self._state_lock:
            self._gaze_point = (msg.x, msg.y)

    def _on_prompt(self, msg: String) -> None:
        """Handle an incoming audio transcription prompt from ROS."""
        command = msg.data.strip().lower()
        if not command:
            return
        with self._state_lock:
            if command == AudioStreamingPipelineConfig.STOP_KEYWORD:
                self.prompt = ""
                self._aria_inference_state = None
            elif command != self.prompt:
                self.prompt = command
                self._aria_inference_state = None

    def _generate_mask(
        self, image: np.ndarray, prompt: str
    ) -> Optional[Dict[str, Any]]:
        """
        Generate segmentation mask for given image and text prompt.

        Args:
            image: Input image as numpy array
            prompt: Text prompt for segmentation

        Returns:
            inference_state: Dictionary containing masks, boxes, and scores, or None
        """

        inference_state = self.model.process_text_prompt(image, prompt)
        masks = inference_state.get("masks")
        if masks is None or len(masks) == 0:
            logger.debug("No objects detected")
            return None
        logger.debug(f"Found {len(masks)} object(s)")
        return inference_state

    def _find_closest_mask(
        self, masks: list, gaze_point: Optional[Tuple[float, float]]
    ) -> Optional[int]:
        """
        Return the index of the mask closest to the gaze point.

        - If gaze_point is None, return index 0 (first mask).
        - If gaze_point falls inside a mask, return that mask immediately.
        - Otherwise return the mask whose edge is closest to the gaze point,
        measured as the minimum distance from the point to any True pixel
        on the mask boundary.
        """
        if gaze_point is None or len(masks) == 0:
            return 0

        gx, gy = int(round(gaze_point[0])), int(round(gaze_point[1]))

        for i, mask in enumerate(masks):
            m = mask.bool().squeeze()
            if 0 <= gy < m.shape[0] and 0 <= gx < m.shape[1]:
                if m[gy, gx].item():
                    return i

        best_idx = 0
        best_dist = float("inf")

        for i, mask in enumerate(masks):
            m = mask.bool().squeeze()
            ys, xs = torch.where(m)
            if len(ys) == 0:
                continue
            dists = (xs - gx).float() ** 2 + (ys - gy).float() ** 2
            min_dist = dists.min().item()
            if min_dist < best_dist:
                best_dist = min_dist
                best_idx = i

        return best_idx

    def _find_matching_ros_mask(
        self,
        aria_image: np.ndarray,
        aria_inference_state: Dict[str, Any],
        ros_image: np.ndarray,
        ros_inference_state: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Use feature matching to identify which ROS mask corresponds to the Aria mask.

        Steps:
          1. Find all matched keypoint pairs between the Aria and ROS frames.
          2. Keep only the Aria-side keypoints that fall inside the Aria mask.
          3. For each ROS mask, count how many of the corresponding ROS-side
             keypoints land inside it.
          4. Return a copy of ros_inference_state filtered to the best-matching
             mask, or None if no mask receives any hits.

        Args:
            aria_image: The Aria frame used when the Aria mask was computed.
            aria_inference_state: Locked Aria inference state (single mask).
            ros_image: Current ROS camera frame.
            ros_inference_state: ROS inference state with one or more masks.

        Returns:
            Filtered ros_inference_state with only the best mask, or None.
        """
        aria_masks = aria_inference_state.get("masks", [])
        ros_masks = ros_inference_state.get("masks", [])

        if not len(aria_masks) or not len(ros_masks):
            return None

        # Binary aria mask (H x W)
        aria_mask_np = aria_masks[0].squeeze(0).cpu().numpy() > 0
        aria_h, aria_w = aria_mask_np.shape

        try:
            match_result = self._feature_matcher.match_frames(aria_image, ros_image)
        except Exception as e:
            logger.error(f"Feature matching failed: {e}", exc_info=True)
            return None

        kp0 = match_result["keypoints0"]  # (N, 2) — aria keypoints
        kp1 = match_result["keypoints1"]  # (M, 2) — ros keypoints
        matches = match_result["matches"]  # (K, 2) — index pairs

        if len(matches) == 0:
            logger.debug("No feature matches found between Aria and ROS frames")
            return None

        # Matched keypoints in each frame
        matched_kp0 = kp0[matches[:, 0]].round().astype(int)  # (K, 2)
        matched_kp1 = kp1[matches[:, 1]].round().astype(int)  # (K, 2)

        # Retain only pairs whose Aria keypoint falls inside the Aria mask
        xs0, ys0 = matched_kp0[:, 0], matched_kp0[:, 1]
        valid = (ys0 >= 0) & (ys0 < aria_h) & (xs0 >= 0) & (xs0 < aria_w)
        valid[valid] = aria_mask_np[ys0[valid], xs0[valid]]

        filtered_kp1 = matched_kp1[
            valid
        ]  # ROS keypoints that correspond to the aria mask

        if len(filtered_kp1) == 0:
            logger.debug("No feature matches fall within the Aria mask")
            return None

        logger.debug(
            f"Feature matching: {len(filtered_kp1)}/{len(matches)} matches inside Aria mask"
        )

        # Count how many filtered ROS keypoints land in each ROS mask
        best_idx = None
        best_count = 0

        for i, ros_mask in enumerate(ros_masks):
            ros_mask_np = ros_mask.squeeze(0).cpu().numpy() > 0
            ros_h, ros_w = ros_mask_np.shape

            xs1, ys1 = filtered_kp1[:, 0], filtered_kp1[:, 1]
            in_bounds = (ys1 >= 0) & (ys1 < ros_h) & (xs1 >= 0) & (xs1 < ros_w)
            count = int(ros_mask_np[ys1[in_bounds], xs1[in_bounds]].sum())

            if count > best_count:
                best_count = count
                best_idx = i

        if best_idx is None or best_count == 0:
            logger.debug("No ROS mask matched the Aria mask via feature matching")
            return None

        logger.debug(
            f"Matched ROS mask idx={best_idx} with {best_count}/{len(filtered_kp1)} hits"
        )

        return {
            **ros_inference_state,
            "masks": [ros_masks[best_idx]],
            "scores": [ros_inference_state["scores"][best_idx]],
            "boxes": [ros_inference_state["boxes"][best_idx]],
        }

    def run(self):
        logger.info("Object recognition pipeline started. Waiting for command...")

        last_aria_id = -1
        last_ros_id = -1

        try:
            while not self._quit_event.is_set():
                prompt = self.prompt
                if not prompt:
                    time.sleep(0.1)
                    continue

                aria_image, aria_id = self._aria_feed.get()
                ros_image, ros_id = self._ros_feed.get()

                with self._state_lock:
                    prompt = self.prompt

                if (
                    aria_id != last_aria_id
                    and aria_image is not None
                    and not self._aria_inference_state
                ):
                    aria_inference_state = self._generate_mask(aria_image, self.prompt)
                    if aria_inference_state is not None:
                        masks = aria_inference_state.get("masks")
                        if len(masks) > 1:
                            best = self._find_closest_mask(masks, self._gaze_point)
                            aria_inference_state["masks"] = [masks[best]]
                            aria_inference_state["scores"] = [
                                aria_inference_state["scores"][best]
                            ]
                            aria_inference_state["boxes"] = [
                                aria_inference_state["boxes"][best]
                            ]
                            self._aria_inference_state = aria_inference_state
                        self._aria_locked_image = aria_image
                        self._publish_inference(
                            self.aria_inference_publisher,
                            aria_image,
                            aria_inference_state,
                        )
                    last_aria_id = aria_id

                if ros_id != last_ros_id and ros_image is not None:
                    ros_inference_state = self._generate_mask(ros_image, self.prompt)
                    if ros_inference_state is not None:
                        if (
                            self._aria_inference_state is not None
                            and self._aria_locked_image is not None
                        ):
                            matched = self._find_matching_ros_mask(
                                self._aria_locked_image,
                                self._aria_inference_state,
                                ros_image,
                                ros_inference_state,
                            )
                            if matched is not None:
                                ros_inference_state = matched
                        self._publish_inference(
                            self.ros_inference_publisher, ros_image, ros_inference_state
                        )
                    last_ros_id = ros_id

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        except Exception as e:
            logger.error(f"Error during mask generation: {e}", exc_info=True)
        finally:
            self.cleanup()

    def _publish_inference(
        self,
        ros_publisher: ROSPublisher,
        image: np.ndarray,
        inference_state: Dict[str, Any],
    ):
        """Compress and publish aria image + inference state."""
        try:
            success, compressed = ImageHelper.compress_image(image=image)
            if not success:
                logger.warning("Failed to encode Aria image for publishing")
                compressed = None

            state_to_publish = {
                k: v
                for k, v in inference_state.items()
                if k not in ("backbone_out", "masks_logits")
            }

            payload = pickle.dumps(
                {"image": compressed, "inference_state": state_to_publish}
            )
            msg = UInt8MultiArray()
            msg.data = payload

            logger.debug(f"Payload size: {len(payload) / 1024:.1f} KB")

            ros_publisher.publish(msg)
        except Exception as e:
            logger.error(f"Error publishing results: {e}")

    def cleanup(self):
        self._executor.shutdown()
        self._spin_thread.join(timeout=2.0)
        logger.info("Cleanup complete")


def generate_mask(aria_streaming_started: Event, quit_event: Event):
    listener = ObjectRecognitionPipeline(quit_event=quit_event)
    aria_streaming_started.wait()
    listener.run()


if __name__ == "__main__":
    import multiprocessing

    quit_event = multiprocessing.Event()
    listener = ObjectRecognitionPipeline(quit_event=quit_event)
    listener.run()
