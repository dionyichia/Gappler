import logging
from dataclasses import dataclass
import torch
from gappler_common import ROOT


@dataclass(frozen=True)
class Settings:
    """General application settings."""

    APP_NAME: str = "Renaissance Capstone Project"
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    REALSENSE_INIT_DELAY = 3  # seconds to wait for RealSense node to initialize

    LOG_DIR: str = "logs"
    LOG_LEVEL: str = logging.INFO

    PROJECT_ROOT = ROOT
