"""Model checkpoint paths and locations."""

from pathlib import Path

from .base import Settings


class ModelPaths:
    """Paths to model checkpoints and configurations."""

    SAM3_PATH: Path = Settings.PROJECT_ROOT / "aria/aria_app/models/sam3/sam3.pt"
    EYETRACKING_MODEL_BASE_PATH: Path = (
        Settings.PROJECT_ROOT / "aria/aria_app/models/projectaria_eyetracking/"
    )
