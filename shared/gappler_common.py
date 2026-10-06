"""The one place that knows where the repo is and reads shared/global_config.yaml.

Import this instead of working out paths from __file__, so moving a file never
breaks a path (NEXT_STEPS 2.15). shared/base_envs/ros_humble_and_helper.sh, sourced by every
<subsystem>_env.sh and so by global_env.sh, puts shared/ on PYTHONPATH.

    from gappler_common import ROOT, config, path
    config()["topics"]["imu"]      -> "/aria/imu"
    path("openvins_ws")            -> the OpenVINS folder, ~ expanded
"""

import os
import math
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


def camera_serial(name: str) -> str:
    """A camera serial from global_config.yaml, e.g. camera_serial("wrist_camera").
    <NAME>_SERIAL in the environment wins, matching grasp/tools/record_wrist_camera.sh.
    Every RealSense launch passes one: with two cameras plugged in, a launch without a
    serial opens whichever the driver finds first (T1.13)."""
    serial = os.environ.get(f"{name.upper()}_SERIAL") or config()[name]["serial"]
    if not serial:
        raise ValueError(
            f"no serial for {name}: set it in shared/global_config.yaml or "
            f"pass {name.upper()}_SERIAL in the environment"
        )
    return str(serial)


def static_transform_args(name: str) -> list[str]:
    """Fixed mount as TF publisher xyz/yaw/pitch/roll/parent/child arguments."""
    mount = config()["geometry"][name]
    xyz = [float(value) for value in mount["xyz_m"]]
    rpy = [float(value) for value in mount["rpy_rad"]]
    if len(xyz) != 3 or len(rpy) != 3 or not all(math.isfinite(v) for v in xyz + rpy):
        raise ValueError(f"invalid finite xyz/rpy triple for mount {name}")
    parent, child = mount["parent"], mount["child"]
    if not isinstance(parent, str) or not isinstance(child, str) or not parent or not child or parent == child:
        raise ValueError(f"invalid parent/child frames for mount {name}")
    return [str(value) for value in xyz + list(reversed(rpy))] + [parent, child]


if __name__ == "__main__":  # self-check: python3 shared/gappler_common.py
    assert (ROOT / "global_env.sh").exists(), ROOT
    assert config()["topics"]["imu"] == "/aria/imu"
    assert camera_serial("wrist_camera") == "243222074878"
    os.environ["WRIST_CAMERA_SERIAL"] = "999"
    assert camera_serial("wrist_camera") == "999"
    del os.environ["WRIST_CAMERA_SERIAL"]
    assert camera_serial("mobile_base_camera") == "146222253541"
    assert path("openvins_ws") == Path(config()["paths"]["openvins_ws"]).expanduser()
    os.environ["GAPPLER_OPENVINS_WS"] = str(Path.home())
    assert path("openvins_ws") == Path.home()
    os.environ["GAPPLER_OPENVINS_WS"] = "rel/ov"
    assert path("openvins_ws") == ROOT / "rel/ov"
    print("gappler_common: PASS")
