"""Configuration package for Aria streaming application.

Usage:
    from config import Settings, AriaConfig, ZMQConfig

    settings = Settings()
    aria_config = AriaConfig()
"""

import warnings

warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")


from .aria import AriaConfig
from .base import Settings
from .eye_tracking import EyeTrackingConfig
from .models import ModelPaths
from .playback_controller_config import PlaybackControllerConfig
from .visualization import VisualizationConfig
from .zmq import ZMQConfig, ZMQTopics

__all__ = [
    # Base configuration
    "Settings",
    # Device configuration
    "AriaConfig",
    # Processing configuration
    "VisualizationConfig",
    # Communication configuration
    "ZMQConfig",
    "ZMQTopics",
    # Eye tracking
    "EyeTrackingConfig",
    # Models
    "ModelPaths",
    "PlaybackControllerConfig",
]
