"""Model checkpoint paths and locations."""

from pathlib import Path

from gappler_common import path

from .base import Settings


class ModelPaths:
    """Paths to model checkpoints and configurations."""

    SAM3_PATH: Path = path("sam3_weights")
    EYETRACKING_MODEL_BASE_PATH: Path = (
        Settings.PROJECT_ROOT / "aria/aria_app/models/projectaria_eyetracking/"
    )
