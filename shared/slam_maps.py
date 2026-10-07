"""File prerequisites for SLAM Toolbox; deserialization still validates contents."""
import hashlib
import json
import math
import os
from pathlib import Path

SNAPSHOT_FILES = ("completed_map.posegraph", "completed_map.data", "current_map.yaml", "current_map.pgm")


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


def require_snapshot_manifest(folder: str | Path) -> dict:
    """Require the owned-saver manifest and verify its file checksums/geometry."""
    folder = Path(folder).expanduser()
    manifest_file = folder / "manifest.json"
    try:
        manifest = json.loads(manifest_file.read_text())
    except OSError as error:
        raise ValueError(f"snapshot manifest unreadable: {manifest_file}: {error}") from error
    except ValueError as error:
        raise ValueError(f"snapshot manifest is not valid JSON: {manifest_file}") from error
    if not isinstance(manifest, dict):
        raise ValueError(f"snapshot manifest must be an object: {manifest_file}")
    frame = manifest.get("frame")
    width, height, resolution = manifest.get("width"), manifest.get("height"), manifest.get("resolution")
    if not isinstance(frame, str) or not frame:
        raise ValueError(f"snapshot manifest has invalid frame: {manifest_file}")
    if (not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0
            or not isinstance(resolution, (int, float)) or not math.isfinite(resolution) or resolution <= 0):
        raise ValueError(f"snapshot manifest has invalid width/height/resolution: {manifest_file}")
    checksums = manifest.get("sha256")
    if not isinstance(checksums, dict):
        raise ValueError(f"snapshot manifest lacks sha256 checksums: {manifest_file}")
    for name in SNAPSHOT_FILES:
        expected = checksums.get(name)
        if not isinstance(expected, str) or not expected:
            raise ValueError(f"snapshot manifest lacks checksum for {name}")
        try:
            digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        except OSError as error:
            raise ValueError(f"snapshot file unreadable: {name}: {error}") from error
        if digest != expected:
            raise ValueError(f"snapshot file checksum mismatch: {name}")
    return manifest
