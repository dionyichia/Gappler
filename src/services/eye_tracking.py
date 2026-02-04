"""
Real-time eye tracking inference and visualization for Project Aria glasses.

This module provides functions to:
- Initialize eye-tracking models and camera calibration
- Perform real-time gaze inference
- Visualize gaze projections on RGB images
"""

from dataclasses import dataclass
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple

import aria
import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from projectaria_tools.core.calibration import CameraCalibration, DeviceCalibration
from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.mps.utils import get_gaze_vector_reprojection

from config import AriaConfig
from models.projectaria_eyetracking.projectaria_eyetracking.inference import infer

GAZE_POINT_RADIUS = 20
GAZE_POINT_COLOR = (0, 0, 255)  # Red in BGR
DEFAULT_DEPTH_M = 0.5

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
MODEL_BASE_PATH = (
    PROJECT_ROOT
    / "src/models/projectaria_eyetracking/projectaria_eyetracking/inference/model/pretrained_weights/social_eyes_uncertainty_v1"
)


@dataclass
class GazeEstimate:
    """Container for gaze estimation results with uncertainty bounds."""

    yaw: float
    pitch: float
    yaw_lower: float
    pitch_lower: float
    yaw_upper: float
    pitch_upper: float
    timestamp_ms: int
    depth_m: str = ""

    def to_csv_row(self) -> List:
        """Convert to CSV row format compatible with MPS eye gaze format."""
        return [
            self.timestamp_ms,
            self.yaw,
            self.pitch,
            self.depth_m,
            self.yaw_lower,
            self.pitch_lower,
            self.yaw_upper,
            self.pitch_upper,
        ]

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for easy access."""
        return {
            "yaw": self.yaw,
            "pitch": self.pitch,
            "yaw_lower": self.yaw_lower,
            "pitch_lower": self.pitch_lower,
            "yaw_upper": self.yaw_upper,
            "pitch_upper": self.pitch_upper,
        }


def initialize_eye_tracking_model(device: str = "cuda") -> infer.EyeGazeInference:
    """
    Initialize eye-tracking inference model and camera calibrations.

    Args:
        device: Device to run inference on ('cuda' or 'cpu')

    Returns:
        EyeTrackingSystem containing model and calibration data

    Raises:
        FileNotFoundError: If model weights or config files are missing
        RuntimeError: If VRS calibration file cannot be loaded
    """
    # Load eye-tracking model
    model_checkpoint_path = MODEL_BASE_PATH / "weights.pth"
    model_config_path = MODEL_BASE_PATH / "config.yaml"

    if not model_checkpoint_path.exists():
        raise FileNotFoundError(f"Model weights not found: {model_checkpoint_path}")
    if not model_config_path.exists():
        raise FileNotFoundError(f"Model config not found: {model_config_path}")

    inference_model = infer.EyeGazeInference(
        str(model_checkpoint_path), str(model_config_path), device
    )

    return inference_model


def predict_gaze(
    inference_model: infer.EyeGazeInference,
    eye_image: np.ndarray,
    timestamp_ms: int,
    device: str = "cuda",
) -> Optional[GazeEstimate]:
    """
    Predict eye gaze from eye-tracking camera image.

    Args:
        inference_model: Trained eye gaze inference model
        eye_image: Eye camera image as numpy array
        timestamp_ms: Timestamp in milliseconds
        device: Device for inference ('cuda' or 'cpu')

    Returns:
        GazeEstimate with predictions and uncertainty, or None if prediction fails
    """
    if eye_image is None:
        return None

    try:
        # Convert to tensor and predict
        img_tensor = torch.tensor(eye_image, device=device)
        preds, lower, upper = inference_model.predict(img_tensor)

        # Convert to numpy
        preds = preds.detach().cpu().numpy()
        lower = lower.detach().cpu().numpy()
        upper = upper.detach().cpu().numpy()

        return GazeEstimate(
            yaw=float(preds[0][0]),
            pitch=float(preds[0][1]),
            yaw_lower=float(lower[0][0]),
            pitch_lower=float(lower[0][1]),
            yaw_upper=float(upper[0][0]),
            pitch_upper=float(upper[0][1]),
            timestamp_ms=timestamp_ms,
        )
    except Exception as e:
        print(f"Gaze prediction failed: {e}")
        return None


def real_time_eyetracking(
    inference_model,
    images_observer: Dict[str, np.ndarray],
    eye_tracking_camera_id: str,
    timestamp_observer: int,
    device: str = "cuda",
):
    print(images_observer.keys())
    if eye_tracking_camera_id not in images_observer:
        print("No eye-tracking data found in images_observer")
        sleep(1)
        return None, None

    eye_image = images_observer[eye_tracking_camera_id]
    gaze_estimate = predict_gaze(inference_model, eye_image, timestamp_observer, device)

    if gaze_estimate is None:
        return None, None

    return gaze_estimate.to_dict(), gaze_estimate.to_csv_row()


def draw_gaze_point(
    image: np.ndarray,
    gaze_point: Tuple[float, float],
    radius: int = GAZE_POINT_RADIUS,
    color: Tuple[int, int, int] = GAZE_POINT_COLOR,
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
        # Convert to PIL if necessary
        if isinstance(image, np.ndarray):
            image = Image.fromarray(image)

        draw = ImageDraw.Draw(image)
        draw.ellipse(
            (x - radius, y - radius, x + radius, y + radius),
            fill=color if len(color) == 3 else color[:3],
        )
        return image
    else:
        # Use OpenCV (faster for real-time applications)
        image_with_gaze = image.copy()
        cv2.circle(image_with_gaze, (x, y), radius, color, -1)
        return image_with_gaze


def eye_tracking_visualization(
    device_calibration: DeviceCalibration,
    rgb_camera_calibration: CameraCalibration,
    images_observer: Dict[str, np.ndarray],
    value_mapping: Dict[str, float],
):
    rgb_camera_id = aria.CameraId.Rgb
    if rgb_camera_id not in images_observer or not value_mapping:
        return None, None

    rgb_image = images_observer[rgb_camera_id]

    try:
        # Create EyeGaze object for projection
        eye_gaze = EyeGaze
        eye_gaze.yaw = value_mapping["yaw"]
        eye_gaze.pitch = value_mapping["pitch"]

        # Project to RGB image
        gaze_projection = get_gaze_vector_reprojection(
            eye_gaze=eye_gaze,
            stream_id_label=AriaConfig.RGB_STREAM_LABEL,
            device_calibration=device_calibration,
            camera_calibration=rgb_camera_calibration,
            depth_m=DEFAULT_DEPTH_M,
        )

        image_with_gaze = draw_gaze_point(rgb_image, gaze_projection)
        return gaze_projection, image_with_gaze
    except Exception as e:
        print(f"Gaze projection failed: {e}")
        return None, None
