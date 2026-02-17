"""ZMQ communication protocol configuration."""

from dataclasses import dataclass
from enum import Enum


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
