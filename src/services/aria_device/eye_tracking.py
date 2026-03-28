"""
Real-time eye tracking inference and visualization for Project Aria glasses.

This module provides functions to:
- Initialize eye-tracking models and camera calibration
- Perform real-time gaze inference
- Visualize gaze projections on RGB images
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import torch
from projectaria_eyetracking.inference import infer
from projectaria_tools.core.calibration import CameraCalibration, DeviceCalibration
from projectaria_tools.core.mps import EyeGaze
from projectaria_tools.core.mps.utils import get_gaze_vector_reprojection

from config import (
    AriaConfig,
    EyeTrackingConfig,
    ModelPaths,
    Settings,
)
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
        checkpoint_path = ModelPaths.EYETRACKING_MODEL_BASE_PATH / "weights.pth"
        config_path = ModelPaths.EYETRACKING_MODEL_BASE_PATH / "config.yaml"

        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Model weights not found: {checkpoint_path}")
        if not config_path.exists():
            raise FileNotFoundError(f"Model config not found: {config_path}")

        return checkpoint_path, config_path

    @staticmethod
    def load_model(device: str):
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


class EyeTrackingPipeline:
    """Main pipeline for real-time eye tracking and visualization."""

    def __init__(
        self,
        device_calibration: DeviceCalibration,
        rgb_camera_calibration: CameraCalibration,
        device: str = Settings.DEVICE,
    ):
        """
        Initialize eye-tracking pipeline.

        Args:
            device_calibration: Device calibration of aria glasses
            rgb_camera_calibration: RGB camera
            device: Device for inference ('cuda' or 'cpu')
        """
        self.device_calibration = device_calibration
        self.rgb_camera_calibration = rgb_camera_calibration
        self.device = device
        self.model = EyeTrackingModelLoader.load_model(device)

    def predict_eye_gaze(
        self,
        eye_image: np.ndarray,
    ) -> Optional[GazeEstimate]:
        """
        Predict eye gaze from eye-tracking camera image.

        Args:
            eye_image: Eye camera image as numpy array

        Returns:
            GazeEstimate with predictions and uncertainty, or None if prediction fails
        """
        if len(eye_image) == 0:
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
            )
        except Exception as e:
            logger.error(f"Gaze prediction failed: {e}")
            return None

    def project_gaze(
        self,
        gaze_estimate: GazeEstimate,
        depth_m: float = EyeTrackingConfig.DEFAULT_DEPTH_M,
    ) -> Optional[Tuple[float, float]]:
        """
        Project gaze vector to RGB image coordinates.

        Args:
            gaze_dict: GazeEstimate with yaw and pitch attributes
            depth_m: Assumed depth for projection in meters

        Returns:
            (x, y) pixel coordinates or None if projection fails
        """
        if not gaze_estimate:
            logger.warning("Invalid gaze data for projection")
            return None

        try:
            # Create EyeGaze object
            eye_gaze = EyeGaze
            eye_gaze.yaw = gaze_estimate.yaw
            eye_gaze.pitch = gaze_estimate.pitch

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
