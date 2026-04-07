"""Aria device and streaming configuration."""

import ipaddress
from dataclasses import dataclass
from typing import Optional

import aria.sdk as aria


@dataclass(frozen=True)
class AriaConfig:
    ARIA_LOG_LEVEL: aria.Level = aria.Level.Info
    ARIA_STREAMING_PROFILE_NAME: str = "profile15"  # for usb
    # ARIA_STREAMING_PROFILE_NAME: str = "profile28" #for wifi
    USE_EPHEMERAL_CERTS: bool = True

    EYE_STREAM_ID: str = "211-1"
    RGB_STREAM_ID: str = "214-1"
    RGB_STREAM_LABEL: str = "camera-rgb"
    SLAM_LEFT_STREAM_LABEL: str = "camera-slam-left"
    SLAM_RIGHT_STREAM_LABEL: str = "camera-slam-right"

    DEST_CALIBRATION_HEIGHT_PX: int = 1408
    DEST_CALIBRATION_WIDTH_PX: int = 1408
    DEST_CALIBRATION_FOCAL_LENGTH: int = 609

    NUM_AUDIO_CHANNELS: int = 7
    AUDIO_SAMPLE_RATE: int = 48_000

    ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = None
    # ARIA_DEVICE_IP_ADDRESS: Optional[ipaddress.IPv4Address] = ipaddress.IPv4Address(
    #     "10.42.0.70"
    # )
