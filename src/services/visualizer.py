"""
Aria Image Visualizer

A modular visualizer for Meta Aria camera images via ZMQ with SAM object detection support.
"""

import os

os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts"

# Delete if unused
# os.environ["QT_QUICK_BACKEND"] = "software"
# os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
# os.environ["MESA_GL_VERSION_OVERRIDE"] = "3.3"
# os.environ["DISPLAY"] = ":0"
# os.environ["QT_QPA_PLATFORM"] = "xcb"

import pickle
import sys
from dataclasses import dataclass
from multiprocessing.synchronize import Event
from pathlib import Path
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
import zmq
from PIL import Image, ImageDraw

from config import (
    VisualizationConfig,
    ZMQConfig,
    ZMQTopics,
)

# Add src directory to path
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))


# Constants
STATUS_PRINT_INTERVAL = 2  # seconds
DEFAULT_WINDOW_SIZE = (1024, 1024)
DEFAULT_WINDOW_POSITION = (50, 50)

# Color definitions (BGR format for OpenCV)
SAM_COLORS_BGR = [
    (0, 0, 255),  # red
    (255, 0, 0),  # blue
    (0, 255, 0),  # green
    (0, 255, 255),  # yellow
    (255, 255, 0),  # cyan
    (255, 0, 255),  # magenta
    (0, 165, 255),  # orange
    (128, 0, 128),  # purple
]


@dataclass
class VisualizerConfig:
    """Configuration for the Aria visualizer."""

    zmq_address: str = ZMQConfig.VISUAL_FEED_ADDRESS
    zmq_address_secondary: str = "tcp://localhost:5558"
    window_name: str = "Meta Aria image"
    window_size: Tuple[int, int] = DEFAULT_WINDOW_SIZE
    window_position: Tuple[int, int] = DEFAULT_WINDOW_POSITION
    filter_topic: Optional[ZMQTopics] = None


class ColorConverter:
    """Simple color converter without matplotlib dependency."""

    # Color name to BGR mapping
    COLOR_MAP = {
        "red": (0, 0, 255),
        "r": (0, 0, 255),
        "blue": (255, 0, 0),
        "b": (255, 0, 0),
        "green": (0, 255, 0),
        "g": (0, 255, 0),
        "yellow": (0, 255, 255),
        "y": (0, 255, 255),
        "cyan": (255, 255, 0),
        "c": (255, 255, 0),
        "magenta": (255, 0, 255),
        "m": (255, 0, 255),
        "orange": (0, 165, 255),
        "purple": (128, 0, 128),
        "white": (255, 255, 255),
        "w": (255, 255, 255),
        "black": (0, 0, 0),
        "k": (0, 0, 0),
    }

    @staticmethod
    def to_bgr(color: str) -> Tuple[int, int, int]:
        """
        Convert color name to BGR tuple.

        Args:
            color: Color name (e.g., 'red', 'blue', 'green')

        Returns:
            BGR tuple (B, G, R)
        """
        color_lower = color.lower()
        if color_lower in ColorConverter.COLOR_MAP:
            return ColorConverter.COLOR_MAP[color_lower]

        # Default to white if color not found
        print(f"Warning: Unknown color '{color}', defaulting to white")
        return (255, 255, 255)


class SAMVisualizer:
    """Handles visualization of SAM (Segment Anything Model) detection results."""

    def __init__(self, colors: list[Tuple[int, int, int]] = None):
        """
        Initialize SAM visualizer.

        Args:
            colors: List of BGR color tuples for different objects
        """
        self.colors = colors or SAM_COLORS_BGR

    def plot_results(self, img: np.ndarray, results: dict) -> np.ndarray:
        """
        Plot detection results on image.

        Args:
            img: Input image
            results: Detection results

        Returns:
            Image with plotted results
        """
        img_cv = img.copy()
        h, w = img_cv.shape[:2]

        if results is None:
            print("No results to plot")
            return img_cv

        if ("scores" not in results) or (len(results["scores"]) == 0):
            print("No objects detected to plot")
            return img_cv

        nb_objects = len(results["scores"])
        print(f"Found {nb_objects} object(s)")

        for i in range(nb_objects):
            color = self.colors[i % len(self.colors)]

            # Plot mask
            mask = results["masks"][i].squeeze(0).cpu().numpy()
            img_cv = self._plot_mask(img_cv, mask, color=color, alpha=0.5)

            # Plot bounding box
            prob = results["scores"][i].item()
            box = results["boxes"][i].cpu().numpy()
            img_cv = self._plot_bbox(
                img_cv, h, w, box, text=f"(id={i}, prob={prob:.2f})", color=color
            )

        return img_cv

    def _plot_mask(
        self,
        img: np.ndarray,
        mask: np.ndarray,
        color: Tuple[int, int, int],
        alpha: float = 0.5,
    ) -> np.ndarray:
        """
        Apply colored mask overlay to image.

        Args:
            img: Input image
            mask: Binary mask
            color: BGR color tuple (B, G, R)
            alpha: Transparency factor

        Returns:
            Image with mask overlay
        """
        im_h, im_w = mask.shape

        # Create colored mask
        colored_mask = np.zeros((im_h, im_w, 3), dtype=np.uint8)
        colored_mask[mask > 0] = color

        # Blend mask with original image
        mask_binary = (mask > 0).astype(np.uint8)
        for c in range(3):
            img[:, :, c] = np.where(
                mask_binary,
                img[:, :, c] * (1 - alpha) + colored_mask[:, :, c] * alpha,
                img[:, :, c],
            )

        return img

    def _plot_bbox(
        self,
        img: np.ndarray,
        img_height: int,
        img_width: int,
        box: np.ndarray,
        box_format: str = "XYXY",
        relative_coords: bool = False,
        color: Tuple[int, int, int] = (0, 0, 255),
        text: Optional[str] = None,
        thickness: int = 2,
    ) -> np.ndarray:
        """
        Draw bounding box on image.

        Args:
            img: Input image
            img_height: Image height
            img_width: Image width
            box: Bounding box coordinates
            box_format: Format of box coordinates (XYXY, XYWH, or CxCyWH)
            relative_coords: Whether coordinates are relative (0-1)
            color: BGR color tuple
            text: Optional text label
            thickness: Line thickness

        Returns:
            Image with bounding box
        """
        # Parse box coordinates based on format
        if box_format == "XYXY":
            x, y, x2, y2 = box
            w = x2 - x
            h = y2 - y
        elif box_format == "XYWH":
            x, y, w, h = box
        elif box_format == "CxCyWH":
            cx, cy, w, h = box
            x = cx - w / 2
            y = cy - h / 2
        else:
            raise ValueError(f"Invalid box_format: {box_format}")

        # Convert to absolute coordinates if needed
        if relative_coords:
            x *= img_width
            w *= img_width
            y *= img_height
            h *= img_height

        x, y, w, h = int(x), int(y), int(w), int(h)

        # Draw rectangle
        cv2.rectangle(img, (x, y), (x + w, y + h), color, thickness)

        # Draw text label if provided
        if text is not None:
            self._draw_text_with_background(img, text, (x, y), color)

        return img

    def _draw_text_with_background(
        self,
        img: np.ndarray,
        text: str,
        position: Tuple[int, int],
        bg_color: Tuple[int, int, int],
    ) -> None:
        """
        Draw text with background rectangle.

        Args:
            img: Image to draw on
            text: Text to draw
            position: (x, y) position
            bg_color: Background color (BGR tuple)
        """
        x, y = position
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )

        # Draw background rectangle
        cv2.rectangle(
            img,
            (x, y - text_height - baseline - 5),
            (x + text_width, y),
            bg_color,
            -1,
        )

        # Draw text in white
        cv2.putText(
            img, text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        )


class MenuOverlay:
    """Handles the camera topic selection menu overlay."""

    def __init__(self):
        """Initialize menu overlay."""
        self.menu_width = 400
        self.menu_height = 300
        self.font = cv2.FONT_HERSHEY_SIMPLEX

        self.topics = [
            ("1", "Topic 1 (RGB Camera Raw)", ZMQConfig.TOPICS.RGB_CAMERA_RAW),
            (
                "2",
                "Topic 2 (RGB Camera Undistorted)",
                ZMQConfig.TOPICS.RGB_CAMERA_UNDISTORTED,
            ),
            (
                "3",
                "Topic 3 (RGB with Gaze)",
                ZMQConfig.TOPICS.RGB_CAMERA_WITH_GAZE_DETECTION,
            ),
            (
                "4",
                "Topic 4 (RGB with Object Masks)",
                ZMQConfig.TOPICS.RGB_WITH_OBJECT_MASKS,
            ),
        ]

    def draw(
        self, base_image: np.ndarray, current_topic: Optional[ZMQTopics]
    ) -> np.ndarray:
        """
        Draw menu overlay on image.

        Args:
            base_image: Base image to draw menu on
            current_topic: Currently selected topic

        Returns:
            Image with menu overlay
        """
        image = base_image.copy()
        h, w = image.shape[:2]

        menu_x = (w - self.menu_width) // 2
        menu_y = (h - self.menu_height) // 2

        # Draw semi-transparent background
        image = self._draw_background(image, menu_x, menu_y)

        # Draw border
        cv2.rectangle(
            image,
            (menu_x, menu_y),
            (menu_x + self.menu_width, menu_y + self.menu_height),
            (200, 200, 200),
            2,
        )

        # Draw title
        self._draw_title(image, menu_x, menu_y)

        # Draw topic buttons
        self._draw_topic_buttons(image, menu_x, menu_y, current_topic)

        # Draw instructions
        self._draw_instructions(image, menu_x, menu_y)

        return image

    def _draw_background(
        self, image: np.ndarray, menu_x: int, menu_y: int
    ) -> np.ndarray:
        """Draw semi-transparent menu background."""
        overlay = image.copy()
        cv2.rectangle(
            overlay,
            (menu_x, menu_y),
            (menu_x + self.menu_width, menu_y + self.menu_height),
            (40, 40, 40),
            -1,
        )
        alpha = 0.85
        cv2.addWeighted(overlay, alpha, image, 1 - alpha, 0, image)
        return image

    def _draw_title(self, image: np.ndarray, menu_x: int, menu_y: int) -> None:
        """Draw menu title."""
        title = "Camera Topic Selection"
        title_size = cv2.getTextSize(title, self.font, 0.8, 2)[0]
        title_x = menu_x + (self.menu_width - title_size[0]) // 2
        title_y = menu_y + 40

        cv2.putText(
            image, title, (title_x, title_y), self.font, 0.8, (255, 255, 255), 2
        )

    def _draw_topic_buttons(
        self,
        image: np.ndarray,
        menu_x: int,
        menu_y: int,
        current_topic: Optional[ZMQTopics],
    ) -> None:
        """Draw topic selection buttons."""
        button_height = 50
        button_width = 350
        button_x = menu_x + 25
        start_y = menu_y + 80

        for i, (key, label, topic) in enumerate(self.topics):
            button_y = start_y + i * (button_height + 15)
            is_selected = current_topic == topic

            button_color = (60, 120, 200) if is_selected else (80, 80, 80)
            text_color = (255, 255, 255) if is_selected else (200, 200, 200)

            # Draw button background
            cv2.rectangle(
                image,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                button_color,
                -1,
            )

            # Draw button border
            cv2.rectangle(
                image,
                (button_x, button_y),
                (button_x + button_width, button_y + button_height),
                (150, 150, 150),
                2,
            )

            # Draw button text
            text = f"[{key}] {label}"
            text_size = cv2.getTextSize(text, self.font, 0.6, 1)[0]
            text_x = button_x + 15
            text_y = button_y + (button_height + text_size[1]) // 2

            cv2.putText(image, text, (text_x, text_y), self.font, 0.6, text_color, 1)

    def _draw_instructions(self, image: np.ndarray, menu_x: int, menu_y: int) -> None:
        """Draw menu instructions."""
        instructions = "Press 'M' to close menu | 'Q' to quit"
        inst_size = cv2.getTextSize(instructions, self.font, 0.5, 1)[0]
        inst_x = menu_x + (self.menu_width - inst_size[0]) // 2
        inst_y = menu_y + self.menu_height - 20

        cv2.putText(
            image, instructions, (inst_x, inst_y), self.font, 0.5, (180, 180, 180), 1
        )


class ZMQFrameReceiver:
    """Handles ZMQ connection and frame reception with concurrent socket polling."""

    def __init__(self, primary_address: str, secondary_address: Optional[str] = None):
        """
        Initialize ZMQ receiver.

        Args:
            primary_address: Primary ZMQ endpoint
            secondary_address: Optional secondary ZMQ endpoint
        """
        self.primary_address = primary_address
        self.secondary_address = secondary_address
        self.context: Optional[zmq.Context] = None
        self.primary_socket: Optional[zmq.Socket] = None
        self.secondary_socket: Optional[zmq.Socket] = None
        self.poller: Optional[zmq.Poller] = None

    def connect(self) -> None:
        """Establish ZMQ connections and configure poller for concurrent listening."""
        self.context = zmq.Context()
        self.poller = zmq.Poller()

        # Primary socket
        self.primary_socket = self.context.socket(zmq.SUB)
        self.primary_socket.setsockopt(zmq.CONFLATE, 1)
        self.primary_socket.connect(self.primary_address)
        self.primary_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.poller.register(self.primary_socket, zmq.POLLIN)
        print(f"Connected to {self.primary_address}")

        # Secondary socket (if provided)
        if self.secondary_address:
            self.secondary_socket = self.context.socket(zmq.SUB)
            self.secondary_socket.setsockopt(zmq.CONFLATE, 1)
            self.secondary_socket.connect(self.secondary_address)
            self.secondary_socket.setsockopt_string(zmq.SUBSCRIBE, "")
            self.poller.register(self.secondary_socket, zmq.POLLIN)
            print(f"Connected to {self.secondary_address}")

    def receive_frame(self, blocking: bool = True) -> Optional[dict]:
        """
        Receive a frame from any available ZMQ socket concurrently.

        Uses zmq.Poller to efficiently wait on multiple sockets simultaneously.
        Returns the first available frame from any socket.

        Args:
            blocking: Whether to block waiting for frames

        Returns:
            Frame data dictionary or None
        """
        if not self.poller:
            return None

        # Set timeout: None for blocking, short timeout for non-blocking
        timeout = None if blocking else 10  # 10ms for non-blocking

        # Poll all registered sockets concurrently
        sockets_with_data = dict(self.poller.poll(timeout))

        if not sockets_with_data:
            return None

        # Process frames from any socket that has data
        # Priority: primary socket first, then secondary
        for socket in [self.primary_socket, self.secondary_socket]:
            if socket and socket in sockets_with_data:
                try:
                    message = socket.recv(zmq.NOBLOCK)
                    return pickle.loads(message)
                except zmq.Again:
                    continue
                except Exception as e:
                    print(f"Error receiving frame: {e}")
                    continue

        return None

    def close(self) -> None:
        """Close ZMQ connections."""
        if self.poller:
            if self.primary_socket:
                self.poller.unregister(self.primary_socket)
            if self.secondary_socket:
                self.poller.unregister(self.secondary_socket)

        if self.primary_socket:
            self.primary_socket.close()
        if self.secondary_socket:
            self.secondary_socket.close()
        if self.context:
            self.context.term()


class AriaImageVisualizer:
    """Main visualizer for Aria camera images via ZMQ."""

    def __init__(self, config: VisualizerConfig = None):
        """
        Initialize the Aria image visualizer.

        Args:
            config: Visualizer configuration
        """
        self.config = config or VisualizerConfig()
        self.frame_receiver = ZMQFrameReceiver(
            self.config.zmq_address, self.config.zmq_address_secondary
        )
        self.sam_visualizer = SAMVisualizer()
        self.menu = MenuOverlay()

        self.running = False
        self.show_menu = False
        self.last_frame: Optional[np.ndarray] = None
        self.filter_topic = self.config.filter_topic

    def setup(self) -> None:
        """Initialize window and ZMQ connections."""
        self._setup_window()
        self.frame_receiver.connect()

    def _setup_window(self) -> None:
        """Initialize OpenCV window."""
        cv2.namedWindow(self.config.window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.config.window_name, *self.config.window_size)
        cv2.setWindowProperty(self.config.window_name, cv2.WND_PROP_TOPMOST, 1)
        cv2.moveWindow(self.config.window_name, *self.config.window_position)

    def process_frame(self, data: dict) -> Optional[np.ndarray]:
        """
        Process received frame data.

        Args:
            data: Dictionary containing image, topic, and metadata

        Returns:
            Processed image ready for display, or None if frame should be skipped
        """
        topic = data["topic"]

        # Filter by topic if specified
        if self.filter_topic is not None and topic != self.filter_topic:
            return None

        # Reconstruct image
        image_raw = data["image"]
        metadata = data["metadata"]

        image = np.frombuffer(image_raw, dtype=np.dtype(metadata["dtype"])).reshape(
            metadata["shape"]
        )

        # Handle SAM visualization
        if topic == ZMQTopics.RGB_WITH_OBJECT_MASKS:
            image = self.sam_visualizer.plot_results(image, data["inference_state"])

        # Validate frame
        if image.size == 0 or np.all(image == 0):
            print("Received empty or all-black frame, skipping")
            return None

        # Convert to BGR for OpenCV
        return cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

    def handle_keyboard_input(self, key: int) -> bool:
        """
        Handle keyboard input.

        Args:
            key: Key code

        Returns:
            False if should quit, True otherwise
        """
        ESC_KEY = 27
        if key == ESC_KEY or key == ord("q"):
            return False
        elif key == ord("m"):
            self.show_menu = not self.show_menu
            print(f"Menu {'opened' if self.show_menu else 'closed'}")
        elif key == ord("1"):
            self.filter_topic = ZMQConfig.TOPICS.RGB_CAMERA_RAW
            print("Switched to Topic 1 (RGB Raw)")
            self.show_menu = False
        elif key == ord("2"):
            self.filter_topic = ZMQConfig.TOPICS.RGB_CAMERA_UNDISTORTED
            print("Switched to Topic 2 (RGB Undistorted)")
            self.show_menu = False
        elif key == ord("3"):
            self.filter_topic = ZMQConfig.TOPICS.RGB_CAMERA_WITH_GAZE_DETECTION
            print("Switched to Topic 3 (RGB with Gaze)")
            self.show_menu = False
        elif key == ord("4"):
            self.filter_topic = ZMQConfig.TOPICS.RGB_WITH_OBJECT_MASKS
            print("Switched to Topic 4 (RGB with Object Masks)")
            self.show_menu = False

        return True

    def run(self) -> None:
        """Main loop to receive and display frames."""
        self.setup()
        print("Waiting for frames... (Press 'q' to quit, 'm' for menu)")
        self.running = True

        try:
            while self.running:
                # Receive frame
                data = self.frame_receiver.receive_frame(blocking=not self.show_menu)

                if data:
                    color_img = self.process_frame(data)
                    if color_img is not None:
                        self.last_frame = color_img

                # Display frame
                if self.last_frame is not None:
                    display_frame = self.last_frame.copy()

                    if self.show_menu:
                        display_frame = self.menu.draw(display_frame, self.filter_topic)

                    cv2.imshow(self.config.window_name, display_frame)

                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                if not self.handle_keyboard_input(key):
                    break

        except KeyboardInterrupt:
            print("\nInterrupted by user")
        except Exception as e:
            print(f"Error in main loop: {e}")
            raise
        finally:
            self.cleanup()

    def cleanup(self) -> None:
        """Clean up resources."""
        print("Cleaning up resources...")
        self.running = False

        try:
            self.frame_receiver.close()
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Error during cleanup: {e}")


def visualize_feed(quit_event: Event):
    """Entry point for the visualizer."""
    config = VisualizerConfig(filter_topic=ZMQConfig.TOPICS.RGB_CAMERA_RAW)
    visualizer = AriaImageVisualizer(config)
    visualizer.run()


if __name__ == "__main__":
    visualize_feed()


def visualize_gaze(
    self,
    rgb_image: np.ndarray,
    gaze_dict: Dict[str, float],
) -> Tuple[Optional[Tuple[float, float]], Optional[np.ndarray]]:
    """
    Visualize gaze on RGB image.

    Args:
        device_calibration: Device calibration data
        rgb_camera_calibration: RGB camera calibration data
        rgb_image: RGB Image
        gaze_dict: Dictionary with gaze predictions

    Returns:
        Tuple of (gaze_projection, image_with_gaze) or (None, None) if fails
    """

    if len(rgb_image) == 0 or not gaze_dict:
        return None, None

    # Project gaze
    gaze_projection = self.project_gaze(gaze_dict)

    if gaze_projection is None:
        return None, None

    # Draw gaze point
    image_with_gaze = self.visualizer.draw_gaze_point(rgb_image, gaze_projection)

    return gaze_projection, image_with_gaze


class GazeVisualizer:
    """Handles gaze point visualization on images."""

    @staticmethod
    def draw_gaze_point(
        image: np.ndarray,
        gaze_point: Tuple[float, float],
        radius: int = VisualizationConfig.GAZE_POINT_RADIUS,
        color: Tuple[int, int, int] = VisualizationConfig.GAZE_POINT_COLOR,
        use_pillow: bool = False,
    ) -> np.ndarray:
        """
        Draw gaze point on image.

        Args:
            image: Input image (numpy array or PIL Image)
            gaze_point: (x, y) pixel coordinates
            radius: Circle radius in pixels
            color: RGB color tuple (for PIL) or BGR (for OpenCV)
            use_pillow: If True, use PIL; otherwise use OpenCV

        Returns:
            Image with gaze point drawn
        """
        if gaze_point is None:
            return image

        x, y = int(gaze_point[0]), int(gaze_point[1])

        if use_pillow:
            return GazeVisualizer._draw_with_pillow(image, x, y, radius, color)
        else:
            return GazeVisualizer._draw_with_opencv(image, x, y, radius, color)

    @staticmethod
    def _draw_with_pillow(
        image: np.ndarray, x: int, y: int, radius: int, color: Tuple[int, int, int]
    ) -> Image.Image:
        """Draw gaze point using PIL."""
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        draw = ImageDraw.Draw(image)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=color if len(color) == 3 else color[:3],
        )
        return image

    @staticmethod
    def _draw_with_opencv(
        image: np.ndarray, x: int, y: int, radius: int, color: Tuple[int, int, int]
    ) -> np.ndarray:
        """Draw gaze point using OpenCV (faster for real-time)."""
        image_with_gaze = image.copy()
        cv2.circle(image_with_gaze, (x, y), radius, color, -1)
        return image_with_gaze
