"""File prerequisites for SLAM Toolbox; deserialization still validates contents."""
import math
import os
from pathlib import Path


def require_initial_pose(raw: str | None = None) -> list[float]:
    """Require explicit finite x,y,theta; never silently default to origin."""
    text = os.environ.get("GAPPLER_MAP_START_POSE", "") if raw is None else raw
    try:
        values = [float(part) for part in str(text).split(",")]
    except (TypeError, ValueError) as error:
        raise ValueError(f"initial pose must be 'x,y,theta': {text!r}") from error
    if len(values) != 3 or not all(math.isfinite(value) for value in values):
        raise ValueError(f"initial pose must be three finite numbers 'x,y,theta': {text!r}")
    return values


def require_serialized_map(prefix: str | Path) -> str:
    """Require readable, nonempty graph/data files before hardware launch construction."""
    prefix = Path(prefix).expanduser()
    for suffix in (".posegraph", ".data"):
        file = Path(str(prefix) + suffix)
        try:
            if not file.is_file():
                raise ValueError(f"serialized map requires a regular file: {file}")
            with file.open("rb") as stream:
                if not stream.read(1):
                    raise ValueError(f"serialized map file is empty: {file}")
        except OSError as error:
            raise ValueError(f"serialized map file is unreadable: {file}: {error}") from error
    return str(prefix)
