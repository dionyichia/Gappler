import logging
import pickle
import threading
import time
from multiprocessing.synchronize import Event
from typing import Any, Dict, Optional, Tuple

import numpy as np
from geometry_msgs.msg import Point
from rclpy.executors import MultiThreadedExecutor
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String, UInt8MultiArray

from config import AudioStreamingPipelineConfig, ModelPaths, ROS2Topics
from services.ros.image_helper import ImageHelper
from services.ros.ros_publisher import ROSPublisher
from services.ros.ros_subscriber import ROSSubscriber

logger = logging.getLogger(__name__)


class ObjectRecognitionPipeline:
    """Handles image processing with mask generation."""

    def __init__(self):
        from services.sam3_model import (
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
            print("No objects detected")
            return None

        print(f"Found {len(masks)} object(s)")
        del inference_state["backbone_out"]
        del inference_state["masks_logits"]
        return inference_state

    def process_prompt(self, prompt: str):
        """Start processing with a new prompt."""
        if self.current_prompt == prompt:
            return
        self.current_prompt = prompt
        self.is_processing = True
        print(f"Started processing with prompt: '{prompt}'")

    def stop_processing(self):
        """Stop current processing."""
        self.is_processing = False
        self.current_prompt = None
        print("Stopped image processing")


class Listener:
    """Manages ROS subscriptions and the main processing loop."""

    def __init__(self, quit_event: Event, image_topic: str, should_use_gaze: bool):
        self._quit_event = quit_event
        self.processor = ObjectRecognitionPipeline()
        self._image: Optional[np.ndarray] = None
        self._image_id: int = 0  # increments on every new frame
        self._image_lock = threading.Lock()
        self._gaze_estimate: Optional[Tuple[float, float]] = None

        self._rgb_subscriber = ROSSubscriber("RGB_camera_subscriber")
        self._prompt_subscriber = ROSSubscriber("Aria_audio_prompt_subscriber")

        self._rgb_subscriber.subscribe(CompressedImage, image_topic, self._on_image)
        self._prompt_subscriber.subscribe(
            String, ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value, self._on_prompt
        )

        self._executor = MultiThreadedExecutor()
        self._executor.add_node(self._rgb_subscriber)
        self._executor.add_node(self._prompt_subscriber)

        if should_use_gaze:
            self._gaze_estimate_subscriber = ROSSubscriber("gaze_estimate_subscriber")
            self._gaze_estimate_subscriber.subscribe(
                Point,
                ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
                self._on_gaze_estimate,
            )
            self._executor.add_node(self._gaze_estimate_subscriber)

        self._spin_thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._spin_thread.start()

        self.inference_publisher = ROSPublisher(
            "object_recognition_inference_publisher",
            UInt8MultiArray,
            ROS2Topics.RGB_CAMERA_WITH_OBJECT_MASKS.value,
        )

    def _on_image(self, msg: CompressedImage) -> None:
        """Decode and cache the latest frame, bumping the ID so the loop knows it's fresh."""
        try:
            frame = ImageHelper.uncompress_image(msg.data)

            if frame is None:
                print("Received empty or all-black frame, skipping")
                return

            with self._image_lock:
                self._image = frame
                self._image_id += 1

        except Exception as e:
            print(f"Error decoding image: {e}")

    def _on_prompt(self, msg: String) -> None:
        """Handle an incoming audio prompt from ROS."""
        command = msg.data.strip().lower()

        if command == AudioStreamingPipelineConfig.STOP_KEYWORD:
            if self.processor.is_processing:
                self.processor.stop_processing()
        elif command:
            self.processor.process_prompt(command)

    def _on_gaze_estimate(self, msg: Point) -> None:
        self._gaze_estimate = msg.x, msg.y

    def _get_current_image(self) -> Tuple[Optional[np.ndarray], int]:
        """Returns a copy of the latest image and its ID."""
        with self._image_lock:
            if self._image is None:
                return None, -1
            return self._image.copy(), self._image_id

    def run(self):
        """Main processing loop — runs until interrupted."""
        print("Listener started. Waiting for commands...")

        last_processed_image_id = None
        last_processed_prompt = None

        try:
            while not self._quit_event.is_set():
                if not self.processor.is_processing:
                    time.sleep(0.1)
                    continue

                image, image_id = self._get_current_image()
                current_prompt = self.processor.current_prompt

                if image is None or (
                    image_id == last_processed_image_id
                    and current_prompt == last_processed_prompt
                ):
                    time.sleep(0.05)
                    continue

                try:
                    inference_state = self.processor.generate_mask(
                        image, current_prompt
                    )
                    last_processed_image_id = image_id
                    last_processed_prompt = current_prompt
                    self._publish_results(image, inference_state)
                except Exception as e:
                    print(f"Error during mask generation: {e}")

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

    def _publish_results(
        self,
        image: np.ndarray,
        inference_state: Optional[Dict[str, Any]],
    ):
        """Publish compressed image and inference_state together as a single message pair."""
        try:
            success, buffer = ImageHelper.compress_image(image=image)
            if not success:
                print("Failed to encode image for publishing")
                return

            payload = pickle.dumps(
                {"image": buffer.tobytes(), "inference_state": inference_state}
            )

            msg = UInt8MultiArray()
            msg.data = payload
            self.inference_publisher.publish(msg)

            logger.debug(f"Image size: {len(buffer) / 1024:.1f} KB")
            logger.debug(f"Payload size: {len(payload) / 1024:.1f} KB")

        except Exception as e:
            print(f"Error publishing results: {e}")

    def cleanup(self):
        """Shut down the executor and join the spin thread."""
        self._executor.shutdown()
        self._spin_thread.join(timeout=2.0)
        print("Cleanup complete")


def generate_mask(
    quit_event: Event,
    image_topic: str = ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
    should_use_gaze: bool = False,
):
    print("Starting Listener for image processing...")
    listener = Listener(
        quit_event=quit_event, image_topic=image_topic, should_use_gaze=should_use_gaze
    )
    listener.run()


if __name__ == "__main__":
    import multiprocessing

    quit_event = multiprocessing.Event()
    generate_mask(quit_event)
