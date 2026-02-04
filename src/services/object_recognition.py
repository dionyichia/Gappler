import pickle
from time import sleep
from typing import Any, Dict, Optional

import numpy as np
import zmq

from config import ModelPaths, ZMQConfig, ZMQTopics
from services.sam3_model import SAM3Segmenter


class ImageProcessor:
    """Handles image processing with mask generation."""

    def __init__(self):
        self.current_prompt: Optional[str] = None
        self.is_processing = False
        self.model = SAM3Segmenter(
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
        if masks is not None and len(masks) > 0:
            print(f"Found {len(masks)} object(s)")
            return inference_state
        else:
            print("No objects detected")
            return None

    def start_processing(self, prompt: str):
        """Start processing with a new prompt."""
        self.current_prompt = prompt
        self.is_processing = True
        print(f"Started processing with prompt: '{prompt}'")

    def stop_processing(self):
        """Stop current processing."""
        self.is_processing = False
        self.current_prompt = None
        print("Stopped image processing")


class ZMQListener:
    """Manages ZMQ socket connections and message handling."""

    def __init__(self):
        self.context = zmq.Context()
        self._setup_sockets()
        self.processor = ImageProcessor()

    def _setup_sockets(self):
        """Initialize ZMQ sockets."""
        # Visual feed socket
        self.visual_socket = self.context.socket(zmq.SUB)
        self.visual_socket.setsockopt(zmq.CONFLATE, 1)  # Keep only latest message
        self.visual_socket.connect(ZMQConfig.VISUAL_FEED_ADDRESS)
        self.visual_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        self.visual_socket_output = self.context.socket(zmq.PUB)
        self.visual_socket_output.bind("tcp://localhost:5558")

        # Audio command socket
        self.audio_socket = self.context.socket(zmq.SUB)
        self.audio_socket.setsockopt(zmq.CONFLATE, 1)  # Keep only latest message
        self.audio_socket.connect("tcp://localhost:5557")  # Fixed: was tcp://*:5557
        self.audio_socket.setsockopt_string(zmq.SUBSCRIBE, "")

        # Set up poller for non-blocking receives
        self.poller = zmq.Poller()
        self.poller.register(self.audio_socket, zmq.POLLIN)
        self.poller.register(self.visual_socket, zmq.POLLIN)

    def _parse_image_data(self, message: bytes) -> Optional[np.ndarray]:
        """Parse image data from ZMQ message."""
        try:
            data = pickle.loads(message)
            topic = data["topic"]

            # Only process RGB camera images
            if topic != ZMQTopics.RGB_CAMERA_RAW:
                return None

            metadata = data["metadata"]
            image_buffer = data["image"]

            # Convert image back to original shape and dtype
            image = np.frombuffer(
                image_buffer, dtype=np.dtype(metadata["dtype"])
            ).reshape(metadata["shape"])

            return image

        except Exception as e:
            print(f"Error parsing image data: {e}")
            return None

    def _handle_audio_command(self, command: str):
        """Process audio commands to start/stop image processing."""
        command = command.strip().lower()

        # Define stop keywords
        stop_keywords = ["stop", "end", "quit", "cancel", "halt"]

        if command in stop_keywords:
            if self.processor.is_processing:
                self.processor.stop_processing()
        elif command:
            # Any non-empty, non-stop command starts new processing
            if self.processor.is_processing:
                print(f"Replacing current prompt with new one: '{command}'")
            self.processor.start_processing(command)

    def run(self):
        """Main event loop."""
        print("ZMQ Listener started. Waiting for commands...")

        try:
            while True:
                # Poll for messages with timeout
                socks = dict(self.poller.poll(timeout=100))

                # Check for audio commands
                if self.audio_socket in socks:
                    try:
                        command = self.audio_socket.recv_string(zmq.NOBLOCK)
                        self._handle_audio_command(command)
                    except zmq.Again:
                        pass

                # Process visual feed if currently active
                if self.processor.is_processing and self.visual_socket in socks:
                    try:
                        message = self.visual_socket.recv(zmq.NOBLOCK)
                        image = self._parse_image_data(message)

                        if image is not None:
                            inference_state = self.processor.generate_mask(
                                image, self.processor.current_prompt
                            )
                            message = pickle.dumps(
                                {
                                    "topic": ZMQTopics.RGB_WITH_OBJECT_MASKS,
                                    "inference_state": inference_state,
                                    "metadata": {
                                        "shape": image.shape,
                                        "dtype": str(image.dtype),
                                    },
                                    "image": image,
                                }
                            )
                            self.visual_socket_output.send(message)

                    except zmq.Again:
                        pass

                    # Small sleep to prevent CPU spinning
                    sleep(0.01)

        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up ZMQ resources."""
        self.visual_socket.close()
        self.audio_socket.close()
        self.context.term()
        print("Cleanup complete")


def generate_mask():
    print("Starting ZMQ Listener for image processing...")
    listener = ZMQListener()
    listener.run()


if __name__ == "__main__":
    generate_mask()
