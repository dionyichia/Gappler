import logging
from dataclasses import dataclass
import torch
from gappler_common import ROOT, config

_cfg = config("aria", "app")  # aria/aria_config.yaml, section app


@dataclass(frozen=True)
class Settings:
    """General application settings."""

    APP_NAME: str = "Renaissance Capstone Project"
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    REALSENSE_INIT_DELAY = _cfg["realsense_init_delay_s"]  # seconds to wait for RealSense node to initialize

    LOG_DIR: str = "logs"
    LOG_LEVEL: str = logging.INFO

    PROJECT_ROOT = ROOT
