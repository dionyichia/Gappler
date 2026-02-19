"""Configuration package for Aria streaming application.

Usage:
    from config import Settings, AriaConfig, ROS2Config

    settings = Settings()
    aria_config = AriaConfig()
"""

import warnings

warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")


from .aria import AriaConfig
from .audio_streaming_pipeline_config import AudioStreamingPipelineConfig
from .base import Settings
from .eye_tracking import EyeTrackingConfig
from .models import ModelPaths
from .playback_controller_config import PlaybackControllerConfig
from .ros2 import ROS2Config, ROS2Topics
from .visualizer_config import VisualizerConfig

__all__ = [
    "AriaConfig",
    "AudioStreamingPipelineConfig",
    "Settings",
    "EyeTrackingConfig",
    "ModelPaths",
    "PlaybackControllerConfig",
    "ROS2Config",
    "ROS2Topics",
    "VisualizerConfig",
]
