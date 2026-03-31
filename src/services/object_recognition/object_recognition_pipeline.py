import logging
import pickle
import threading
import time
from multiprocessing.synchronize import Event
from typing import Any, Dict, Optional, Tuple

import numpy as np
import torch
from geometry_msgs.msg import Point
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String, UInt8MultiArray

from config import AudioStreamingPipelineConfig, ModelPaths, ROS2Topics
from services.ros.image_helper import ImageHelper
from services.ros.realman_camera_subscriber import RealmanCameraSubscriber
from services.ros.ros_publisher import ROSPublisher
from services.ros.ros_subscriber import ROSSubscriber

logger = logging.getLogger(__name__)

PROMPT = "phone"


class CameraFeed:
    """Holds the latest frame and a monotonic ID for one camera."""

    def __init__(self):
        self._image: Optional[np.ndarray] = None
        self._image_id: int = 0
        self._lock = threading.Lock()

    def update(self, frame: np.ndarray):
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

        # Lazy import to prevent SAM3 from disrupting the initialization of cv2
        from services.object_recognition.sam3_model import SAM3Model

        self.model = SAM3Model(
            checkpoint_path=ModelPaths.SAM3_PATH,
            confidence_threshold=0.5,
        )
        self.prompt = PROMPT

        self._aria_inference_state: Optional[Dict[str, Any]] = None

        self._aria_feed = CameraFeed()
        self._ros_feed = CameraFeed()
        self._gaze_point = None

        self._object_recognition_node = ROSSubscriber("object_recognition_node")
        self._ros_camera_subscriber = RealmanCameraSubscriber("RGB_camera_subscriber")

        self._ros_camera_subscriber.subscribe_color_feed(self._on_ros_image)

        self._object_recognition_node.subscribe(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_aria_image,
        )
        self._object_recognition_node.subscribe(
            String, ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value, self._on_prompt
        )
        self._object_recognition_node.subscribe(
            Point, ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value, self._on_gaze
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._object_recognition_node)
        self._executor.add_node(self._ros_camera_subscriber)

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

    def _on_aria_image(self, msg: CompressedImage) -> None:
        try:
            frame = ImageHelper.uncompress_image(msg.data)

            if frame is None:
                logger.warning("Received empty Aria frame, skipping")
                return
            self._aria_feed.update(frame)
        except Exception as e:
            print(f"Error decoding image: {e}")

    def _on_ros_image(self, frame: np.ndarray) -> None:
        if frame is None:
            logger.warning("Received empty ROS camera frame, skipping")
            return
        self._ros_feed.update(frame)

    def _on_gaze(self, msg: Point) -> None:
        self._gaze_point = (msg.x, msg.y)

    def _on_prompt(self, msg: String) -> None:
        """Handle an incoming audio prompt from ROS."""
        command = msg.data.strip().lower()
        if command == AudioStreamingPipelineConfig.STOP_KEYWORD:
            self.prompt = ""
            self._aria_inference_state = None
        elif command:
            if command != self.prompt:
                self._aria_inference_state = None
            self.prompt = command

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

    def run(self):
        logger.info("Object recognition pipeline started. Waiting for command...")

        last_aria_id = -1
        last_ros_id = -1

        try:
            while not self._quit_event.is_set():
                if not self.prompt:
                    time.sleep(0.1)
                    continue

                aria_image, aria_id = self._aria_feed.get()
                ros_image, ros_id = self._ros_feed.get()

                aria_locked = (
                    self._aria_inference_state is not None
                    and len(self._aria_inference_state.get("masks", [])) == 1
                )

                if (
                    aria_id != last_aria_id
                    and aria_image is not None
                    and not aria_locked
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
                        self._publish_inference(
                            self.aria_inference_publisher,
                            aria_image,
                            aria_inference_state,
                        )
                    last_aria_id = aria_id

                if ros_id != last_ros_id and ros_image is not None:
                    ros_inference_state = self._generate_mask(ros_image, self.prompt)
                    if ros_inference_state is not None:
                        masks = ros_inference_state.get("masks")
                        # TODO: Perform feature matching to see if it there is a valid pair compared to the original aria mask
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
    logger.info("Starting Listener for image processing...")
    listener = ObjectRecognitionPipeline(quit_event=quit_event)
    listener.run()


if __name__ == "__main__":
    import multiprocessing

    quit_event = multiprocessing.Event()
    listener = ObjectRecognitionPipeline(quit_event=quit_event)
    listener.run()
