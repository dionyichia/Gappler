"""Configuration constants for Aria streaming application."""

import ipaddress
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import aria.sdk as aria
import torch

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass(frozen=True)
class Settings:
    """General application settings."""

    APP_NAME: str = "Renaissance Capstone Project"

    LOG_DIR: str = "logs"
    LOG_LEVEL: str = "DEBUG"

    SAVE_IMAGE_FLAG: bool = True


@dataclass(frozen=True)
class AriaConfig:
    ARIA_LOG_LEVEL: aria.Level = aria.Level.Info
    ARIA_STREAMING_PROFILE_NAME: str = "profile18"
    RGB_STREAM_LABEL: str = "camera-rgb"
    ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = None
    # ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = ipaddress.IPv4Address("")


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


@dataclass(frozen=True)
class AudioStreamProcessorConfig:
    CSV_FILEPATH: str = "output/audio/word_list.csv"


@dataclass(frozen=True)
class ZMQConfig:
    """ZMQ communication configuration."""

    PORT: str = "tcp://localhost:5556"
    TOPIC: str = "command"


@dataclass
class ModelConfig:
    """Configuration for AI models"""

    grounding_model: str = "IDEA-Research/grounding-dino-tiny"
    sam2_checkpoint: Path = Path("/checkpoints/sam2.1_hiera_large.pt")
    sam2_model_config: str = "configs/sam2.1/sam2.1_hiera_l.yaml"

    def __post_init__(self):
        # Enable optimizations for Ampere GPUs
        if DEVICE == "cuda" and torch.cuda.get_device_properties(0).major >= 8:
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

        # Enable bfloat16 autocast
        torch.autocast(device_type=DEVICE, dtype=torch.bfloat16).__enter__()


@dataclass
class PathConfig:
    """Configuration for file paths"""

    output_dir: Path = Path("outputs/detection_results")

    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ROSConfig:
    """Configuration for ROS topics"""

    color_image_topic: str = "/camera/color/image_raw"
    modified_response_topic: str = "/modifiedresponse"
    action_topic: str = "/actions"
    node_name: str = "aria_object_detection"


@dataclass
class DetectionConfig:
    """Configuration for detection parameters"""

    box_threshold: float = 0.3
    text_threshold: float = 0.3
    eye_tracking_box_size: int = 150
    dump_json: bool = True
