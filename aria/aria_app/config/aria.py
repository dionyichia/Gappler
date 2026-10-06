"""Aria device and streaming configuration."""

import ipaddress
from dataclasses import dataclass
from typing import Optional

import aria.sdk as aria
from gappler_common import config

_cfg = config("aria", "aria_device")  # aria/aria_config.yaml, section aria_device


@dataclass(frozen=True)
class AriaConfig:
    ARIA_LOG_LEVEL: aria.Level = aria.Level.Info
    ARIA_STREAMING_PROFILE_NAME: str = _cfg["streaming_profile_name"]
    USE_EPHEMERAL_CERTS: bool = _cfg["use_ephemeral_certs"]

    EYE_STREAM_ID: str = "211-1"
    RGB_STREAM_ID: str = "214-1"
    RGB_STREAM_LABEL: str = "camera-rgb"
    SLAM_LEFT_STREAM_LABEL: str = "camera-slam-left"
    SLAM_RIGHT_STREAM_LABEL: str = "camera-slam-right"

    DEST_CALIBRATION_HEIGHT_PX: int = _cfg["undistorted_image_size_px"]
    DEST_CALIBRATION_WIDTH_PX: int = _cfg["undistorted_image_size_px"]
    DEST_CALIBRATION_FOCAL_LENGTH: int = _cfg["undistorted_focal_length_px"]

    NUM_AUDIO_CHANNELS: int = 7
    AUDIO_SAMPLE_RATE: int = 48_000

    # Empty in the config means USB
    ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = (
        ipaddress.IPv4Address(_cfg["device_ip_address"]) if _cfg["device_ip_address"] else None
    )
