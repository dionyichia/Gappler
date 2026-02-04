"""
Real-time eye tracking inference and visualization for Project Aria glasses.

This module provides functions to:
- Initialize eye-tracking models and camera calibration
- Perform real-time gaze inference
- Visualize gaze projections on RGB images
"""

import logging
from pathlib import Path
from time import sleep
from typing import Dict, List, Optional, Tuple

import aria.sdk as aria
import cv2
import numpy as np
import torch
from PIL import Image, ImageDraw
from projectaria_tools.core.calibration import CameraCalibration, DeviceCalibration
from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.mps.utils import get_gaze_vector_reprojection

from config import AriaConfig, EyeTrackingParams, ModelPaths, VisualizationConfig
from models.projectaria_eyetracking.projectaria_eyetracking.inference import infer
from schemas.gaze_estimate import GazeEstimate

logger = logging.getLogger(__name__)


class EyeTrackingModelLoader:
    """Handles loading and validation of eye-tracking model files."""

    @staticmethod
    def validate_model_files() -> Tuple[Path, Path]:
        """
        Validate that required model files exist.

        Returns:
            Tuple of (checkpoint_path, config_path)

        Raises:
            FileNotFoundError: If required files are missing
        """
        checkpoint_path = ModelPaths.MODEL_BASE_PATH / "weights.pth"
        config_path = ModelPaths.MODEL_BASE_PATH / "config.yaml"

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Model weights not found: {checkpoint_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"Model config not found: {config_path}")

        return checkpoint_path, config_path

    @staticmethod
    def load_model(device: str = "cuda") -> infer.EyeGazeInference:
        """
        Load the eye-tracking inference model.

        Args:
            device: Device to run inference on ('cuda' or 'cpu')

        Returns:
            Initialized EyeGazeInference model

        Raises:
            FileNotFoundError: If model files are missing
            RuntimeError: If model loading fails
        """
        checkpoint_path, config_path = EyeTrackingModelLoader.validate_model_files()

        logger.info("Loading eye-tracking model...")
        try:
            model = infer.EyeGazeInference(
                str(checkpoint_path), str(config_path), device
            )
            logger.info("Eye-tracking model loaded successfully")
            return model
        except Exception as e:
            logger.error(f"Failed to load eye-tracking model: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e


class GazePredictor:
    """Handles gaze prediction from eye images."""

    def __init__(self, model: infer.EyeGazeInference, device: str = "cuda"):
        """
        Initialize gaze predictor.

        Args:
            model: Trained eye gaze inference model
            device: Device for inference ('cuda' or 'cpu')
        """
        self.model = model
        self.device = device

    def predict(
        self, eye_image: np.ndarray, timestamp_ms: int
    ) -> Optional[GazeEstimate]:
        """
        Predict eye gaze from eye-tracking camera image.

        Args:
            eye_image: Eye camera image as numpy array
            timestamp_ms: Timestamp in milliseconds

        Returns:
            GazeEstimate with predictions and uncertainty, or None if prediction fails
        """
        if eye_image is None:
            logger.warning("No eye image provided for prediction")
            return None

        try:
            # Convert to tensor and predict
            img_tensor = torch.tensor(eye_image, device=self.device)
            preds, lower, upper = self.model.predict(img_tensor)

            # Convert to numpy
            preds_np = preds.detach().cpu().numpy()
            lower_np = lower.detach().cpu().numpy()
            upper_np = upper.detach().cpu().numpy()

            return GazeEstimate(
                yaw=float(preds_np[0][0]),
                pitch=float(preds_np[0][1]),
                yaw_lower=float(lower_np[0][0]),
                pitch_lower=float(lower_np[0][1]),
                yaw_upper=float(upper_np[0][0]),
                pitch_upper=float(upper_np[0][1]),
                timestamp_ms=timestamp_ms,
            )
        except Exception as e:
            logger.error(f"Gaze prediction failed: {e}")
            return None


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


class GazeProjector:
    """Handles projection of gaze vectors onto camera images."""

    def __init__(
        self,
        device_calibration: DeviceCalibration,
        rgb_camera_calibration: CameraCalibration,
    ):
        """
        Initialize gaze projector.

        Args:
            device_calibration: Device calibration data
            rgb_camera_calibration: RGB camera calibration data
        """
        self.device_calibration = device_calibration
        self.rgb_camera_calibration = rgb_camera_calibration

    def project_gaze(
        self,
        gaze_dict: Dict[str, float],
        depth_m: float = EyeTrackingParams.DEFAULT_DEPTH_M,
    ) -> Optional[Tuple[float, float]]:
        """
        Project gaze vector to RGB image coordinates.

        Args:
            gaze_dict: Dictionary with 'yaw' and 'pitch' keys
            depth_m: Assumed depth for projection in meters

        Returns:
            (x, y) pixel coordinates or None if projection fails
        """
        if not gaze_dict or "yaw" not in gaze_dict or "pitch" not in gaze_dict:
            logger.warning("Invalid gaze data for projection")
            return None

        try:
            # Create EyeGaze object
            eye_gaze = EyeGaze
            eye_gaze.yaw = gaze_dict["yaw"]
            eye_gaze.pitch = gaze_dict["pitch"]

            # Project to RGB image
            gaze_projection = get_gaze_vector_reprojection(
                eye_gaze=eye_gaze,
                stream_id_label=AriaConfig.RGB_STREAM_LABEL,
                device_calibration=self.device_calibration,
                camera_calibration=self.rgb_camera_calibration,
                depth_m=depth_m,
            )

            return gaze_projection
        except Exception as e:
            logger.error(f"Gaze projection failed: {e}")
            return None


class EyeTrackingPipeline:
    """Main pipeline for real-time eye tracking and visualization."""

    def __init__(self, device: str = "cuda"):
        """
        Initialize eye-tracking pipeline.

        Args:
            device: Device for inference ('cuda' or 'cpu')
        """
        self.device = device
        self.model = EyeTrackingModelLoader.load_model(device)
        self.predictor = GazePredictor(self.model, device)
        self.visualizer = GazeVisualizer()

    def process_frame(
        self,
        images_observer: Dict[str, np.ndarray],
        eye_tracking_camera_id: aria.CameraId,
        timestamp_observer: int,
    ) -> Tuple[Optional[Dict], Optional[List]]:
        """
        Process a single frame for eye tracking.

        Args:
            images_observer: Dictionary of camera images
            eye_tracking_camera_id: ID of eye-tracking camera
            timestamp_observer: Current timestamp in milliseconds

        Returns:
            Tuple of (gaze_dict, csv_row) or (None, None) if processing fails
        """
        if eye_tracking_camera_id not in images_observer:
            logger.warning("No eye-tracking data found in images_observer")
            sleep(1)
            return None, None

        eye_image = images_observer[eye_tracking_camera_id]
        gaze_estimate = self.predictor.predict(eye_image, timestamp_observer)

        if gaze_estimate is None:
            return None, None

        return gaze_estimate.to_dict(), gaze_estimate.to_csv_row()

    def visualize_gaze(
        self,
        device_calibration: DeviceCalibration,
        rgb_camera_calibration: CameraCalibration,
        images_observer: Dict[str, np.ndarray],
        gaze_dict: Dict[str, float],
    ) -> Tuple[Optional[Tuple[float, float]], Optional[np.ndarray]]:
        """
        Visualize gaze on RGB image.

        Args:
            device_calibration: Device calibration data
            rgb_camera_calibration: RGB camera calibration data
            images_observer: Dictionary of camera images
            gaze_dict: Dictionary with gaze predictions

        Returns:
            Tuple of (gaze_projection, image_with_gaze) or (None, None) if fails
        """
        rgb_camera_id = aria.CameraId.Rgb

        if rgb_camera_id not in images_observer or not gaze_dict:
            logger.warning("Missing RGB image or gaze data for visualization")
            return None, None

        rgb_image = images_observer[rgb_camera_id]

        # Project gaze
        projector = GazeProjector(device_calibration, rgb_camera_calibration)
        gaze_projection = projector.project_gaze(gaze_dict)

        if gaze_projection is None:
            return None, None

        # Draw gaze point
        image_with_gaze = self.visualizer.draw_gaze_point(rgb_image, gaze_projection)

        return gaze_projection, image_with_gaze
