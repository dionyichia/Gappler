"""File prerequisites for SLAM Toolbox; deserialization still validates contents."""
from pathlib import Path


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
