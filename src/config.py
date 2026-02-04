"""Configuration constants for Aria streaming application."""

import ipaddress
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple

import aria.sdk as aria
import torch


@dataclass(frozen=True)
class Settings:
    """General application settings."""

    APP_NAME: str = "Renaissance Capstone Project"

    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

    LOG_DIR: str = "logs"
    LOG_LEVEL: str = logging.INFO

    SCRIPT_DIR = Path(__file__).resolve().parent
    PROJECT_ROOT = SCRIPT_DIR.parent

    SAVE_IMAGE_FLAG: bool = True


@dataclass(frozen=True)
class AriaConfig:
    ARIA_LOG_LEVEL: aria.Level = aria.Level.Info
    ARIA_STREAMING_PROFILE_NAME: str = "profile18"
    RGB_STREAM_LABEL: str = "camera-rgb"
    DEST_CALIBRATION_HEIGHT_PX: int = 1408
    DEST_CALIBRATION_WIDTH_PX: int = 1408
    DEST_CALIBRATION_FOCAL_LENGTH: int = 609
    ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = None
    # ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = ipaddress.IPv4Address()


@dataclass(frozen=True)
class ImageStreamProcessorConfig:
    """Streaming configuration constants."""

    CV2_WINDOW_NAME: str = "Meta Aria image"
    CV2_WINDOW_SIZE: Tuple[int, int] = (1024, 1024)
    CV2_WINDOW_POSITION: Tuple[int, int] = (50, 50)

    CAMERA_ID_MAP: Dict[int, str] = None
    EYE_GAZE_CSV_HEADERS: Tuple[str, ...] = None

    def __post_init__(self):
        if self.CAMERA_ID_MAP is None:
            object.__setattr__(self, "CAMERA_ID_MAP", {2: "rgbcam", 3: "eyetrack"})

        if self.EYE_GAZE_CSV_HEADERS is None:
            object.__setattr__(
                self,
                "EYE_GAZE_CSV_HEADERS",
                (
                    "tracking_timestamp_ms",
                    "yaw_rads_cpf",
                    "pitch_rads_cpf",
                    "depth_m_str",
                    "yaw_low_rads_cpf",
                    "pitch_low_rads_cpf",
                    "yaw_high_rads_cpf",
                    "pitch_high_rads_cpf",
                    "gaze_point_x",
                    "gaze_point_y",
                ),
            )


class ZMQTopics(Enum):
    """Available ZMQ topic types."""

    RGB_CAMERA_RAW = "0"
    RGB_CAMERA_UNDISTORTED = "1"
    RGB_CAMERA_WITH_GAZE_DETECTION = "2"
    EYE_TRACKING = "3"
    RGB_WITH_OBJECT_MASKS = "4"
    ALL = ""  # Empty string subscribes to all topics


@dataclass(frozen=True)
class ZMQConfig:
    """ZMQ communication configuration."""

    VISUAL_FEED_ADDRESS: str = "tcp://localhost:5556"
    AUDIO_COMMAND_ADDRESS: str = "tcp://localhost:5557"
    TOPICS = ZMQTopics


class ModelPaths:
    """Paths to model checkpoints and configurations."""

    SAM3_PATH: str = Settings.PROJECT_ROOT / "src/models/sam3/sam3.pt"
    MODEL_BASE_PATH = (
        Settings.PROJECT_ROOT
        / "src/models/projectaria_eyetracking/projectaria_eyetracking/inference/model/pretrained_weights/social_eyes_uncertainty_v1"
    )


class EyeTrackingParams:
    DEFAULT_DEPTH_M = 0.5


# Constants
class VisualizationConfig:
    """Configuration for gaze visualization."""

    GAZE_POINT_RADIUS = 20
    GAZE_POINT_COLOR = (0, 0, 255)  # Red in BGR
