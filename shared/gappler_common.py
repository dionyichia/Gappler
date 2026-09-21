"""The one place that knows where the repo is and reads shared/global_config.yaml.

Import this instead of working out paths from __file__, so moving a file never
breaks a path (NEXT_STEPS 2.15). env.sh puts shared/ on PYTHONPATH.

    from gappler_common import ROOT, config, path
    config()["topics"]["imu"]      -> "/aria/imu"
    path("openvins_ws")            -> the OpenVINS folder, ~ expanded
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml

# This file is shared/gappler_common.py and stays there, so the repo is one folder up.
ROOT = Path(__file__).resolve().parent.parent
GLOBAL_YAML = ROOT / "shared" / "global_config.yaml"


@lru_cache(maxsize=None)
def config() -> dict:
    """The values in global_config.yaml, without the ROS parameter-file wrapper."""
    with open(GLOBAL_YAML) as f:
        return yaml.safe_load(f)["/**"]["ros__parameters"]


def path(name: str) -> Path:
    """A path from global_config.yaml `paths:`. GAPPLER_<NAME> in the environment wins.
    A relative path is taken from the repo root."""
    raw = os.environ.get(f"GAPPLER_{name.upper()}") or config()["paths"][name]
    p = Path(raw).expanduser()
    return p if p.is_absolute() else ROOT / p


if __name__ == "__main__":  # self-check: python3 shared/gappler_common.py
    assert (ROOT / "env.sh").exists(), ROOT
    assert config()["topics"]["imu"] == "/aria/imu"
    assert path("openvins_ws") == Path(config()["paths"]["openvins_ws"]).expanduser()
    os.environ["GAPPLER_OPENVINS_WS"] = str(Path.home())
    assert path("openvins_ws") == Path.home()
    os.environ["GAPPLER_OPENVINS_WS"] = "rel/ov"
    assert path("openvins_ws") == ROOT / "rel/ov"
    print("gappler_common: PASS")
