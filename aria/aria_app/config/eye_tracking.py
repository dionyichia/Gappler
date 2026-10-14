"""Configuration constants for Aria streaming application."""

from gappler_common import config

_cfg = config("aria", "eye_tracking")  # aria/aria_config.yaml, section eye_tracking


class EyeTrackingConfig:
    DEFAULT_DEPTH_M = _cfg["default_depth_m"]
