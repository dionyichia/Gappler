import logging
import pickle
import threading
import time
from multiprocessing.synchronize import Event
from typing import Any, Dict, Optional, Tuple

import numpy as np
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String, UInt8MultiArray

from config import AudioStreamingPipelineConfig, ModelPaths, ROS2Topics
from services.ros.image_helper import ImageHelper
from services.ros.realman_camera_subscriber import RealmanCameraSubscriber
from services.ros.ros_publisher import ROSPublisher
from services.ros.ros_subscriber import ROSSubscriber

logger = logging.getLogger(__name__)


class ObjectRecognitionPipeline:
    """Handles image processing with mask generation."""

    def __init__(self):
        from services.object_recognition.sam3_model import (
            SAM3Model,  # Lazy import to prevent SAM3 from disrupting the initialization of cv2
        )

        self.current_prompt: Optional[str] = None
        self.is_processing = False
        self.model = SAM3Model(
            checkpoint_path=ModelPaths.SAM3_PATH,
            confidence_threshold=0.5,
        )

    def generate_mask(self, image: np.ndarray, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Generate segmentation mask for given image and text prompt.

        Args:
            image: Input image as numpy array
            prompt: Text prompt for segmentation

        Returns:
            inference_state: Dictionary containing masks, boxes, and scores, or None
        """
        print(f"\nGenerating mask for prompt: '{prompt}'")

        inference_state = self.model.process_text_prompt(image, prompt)

        masks = inference_state.get("masks")
        if masks is None or len(masks) == 0:
            logger.debug("No objects detected")
            return None
        logger.debug(f"Found {len(masks)} object(s)")
        del inference_state["backbone_out"]
        del inference_state["masks_logits"]
        return inference_state

    def process_prompt(self, prompt: str):
        """Start processing with a new prompt."""
        if self.current_prompt == prompt:
            return
        self.current_prompt = prompt
        self.is_processing = True
        logger.info(f"Started processing with prompt: '{prompt}'")

    def stop_processing(self):
        """Stop current processing."""
        self.is_processing = False
        self.current_prompt = None
        logger.info("Stopped image processing")


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


class Listener:
    """Manages ROS subscriptions and the main processing loop."""

    def __init__(self, quit_event: Event):
        self._quit_event = quit_event
        self.processor = ObjectRecognitionPipeline()

        self._aria_feed = CameraFeed()
        self._ros_feed = CameraFeed()

        self._aria_camera_subscriber = ROSSubscriber("Aria_RGB_camera_subscriber")
        self._ros_camera_subscriber = RealmanCameraSubscriber("RGB_camera_subscriber")
        self._prompt_subscriber = ROSSubscriber("Aria_audio_prompt_subscriber")

        self._aria_camera_subscriber.subscribe(
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
            self._on_aria_image,
        )
        self._ros_camera_subscriber.subscribe_color_feed(self._on_ros_image)
        self._prompt_subscriber.subscribe(
            String, ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value, self._on_prompt
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._aria_camera_subscriber)
        self._executor.add_node(self._ros_camera_subscriber)
        self._executor.add_node(self._prompt_subscriber)

        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        self.inference_publisher = ROSPublisher(
            "object_recognition_inference_publisher",
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
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

    def _on_prompt(self, msg: String) -> None:
        """Handle an incoming audio prompt from ROS."""
        command = msg.data.strip().lower()
        if command == AudioStreamingPipelineConfig.STOP_KEYWORD:
            if self.processor.is_processing:
                self.processor.stop_processing()
        elif command:
            self.processor.process_prompt(command)

    def run(self):
        logger.info("Listener started. Waiting for commands...")

        last_aria_id = None
        last_ros_id = None
        last_prompt = None

        try:
            while not self._quit_event.is_set():
                if not self.processor.is_processing:
                    time.sleep(0.1)
                    continue

                aria_image, aria_id = self._aria_feed.get()
                ros_image, ros_id = self._ros_feed.get()
                current_prompt = self.processor.current_prompt

                prompt_changed = current_prompt != last_prompt
                aria_fresh = aria_image is not None and aria_id != last_aria_id
                ros_fresh = ros_image is not None and ros_id != last_ros_id

                if not (prompt_changed or aria_fresh or ros_fresh):
                    time.sleep(0.05)
                    continue

                try:
                    aria_masks = (
                        self.processor.generate_mask(aria_image, current_prompt)
                        if aria_image is not None
                        else None
                    )
                    ros_masks = (
                        self.processor.generate_mask(ros_image, current_prompt)
                        if ros_image is not None
                        else None
                    )

                    last_aria_id = aria_id
                    last_ros_id = ros_id
                    last_prompt = current_prompt

                    self._publish_results(aria_image, aria_masks, ros_image, ros_masks)

                except Exception as e:
                    logger.error(f"Error during mask generation: {e}", exc_info=True)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.cleanup()

    def _publish_results(
        self,
        aria_image: Optional[np.ndarray],
        aria_masks: Optional[Dict[str, Any]],
        ros_image: Optional[np.ndarray],
        ros_masks: Optional[Dict[str, Any]],
    ):
        try:
            aria_compressed = ros_compressed = None

            if aria_image is not None:
                success, aria_compressed = ImageHelper.compress_image(image=aria_image)
                if not success:
                    logger.warning("Failed to encode Aria image for publishing")
                    aria_compressed = None

            if ros_image is not None:
                success, ros_compressed = ImageHelper.compress_image(image=ros_image)
                if not success:
                    logger.warning("Failed to encode ROS image for publishing")
                    ros_compressed = None

            payload = pickle.dumps(
                {
                    "aria": {"image": aria_compressed, "inference_state": aria_masks},
                    "ros": {"image": ros_compressed, "inference_state": ros_masks},
                }
            )

            msg = UInt8MultiArray()
            msg.data = payload
            self.inference_publisher.publish(msg)

            logger.debug(f"Payload size: {len(payload) / 1024:.1f} KB")

        except Exception as e:
            logger.error(f"Error publishing results: {e}")

    def cleanup(self):
        self._executor.shutdown()
        self._spin_thread.join(timeout=2.0)
        logger.info("Cleanup complete")


def generate_mask(aria_streaming_started: Event, quit_event: Event):
    logger.info("Starting Listener for image processing...")
    listener = Listener(quit_event=quit_event)
    listener.run()


if __name__ == "__main__":
    import multiprocessing

    aria_streaming_started = multiprocessing.Event()
    quit_event = multiprocessing.Event()
    generate_mask(aria_streaming_started, quit_event)
