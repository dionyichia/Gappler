"""The one place that knows where the repo is and reads the config files.

Import this instead of working out paths from __file__, so moving a file never
breaks a path (NEXT_STEPS 2.15). shared/base_envs/ros_humble_and_helper.sh, sourced by every
<subsystem>_env.sh and so by global_env.sh, puts shared/ on PYTHONPATH.

Config has two levels: shared/global_config.yaml, and one <subsystem>/<subsystem>_config.yaml
per subsystem with a section per node. config() merges them, global first.

    from gappler_common import ROOT, config, path
    config()["topics"]["object_centroid_2d"]           -> "/object_centroid_2d" (global only)
    config("grasp", "sam3_ros_node")["confidence"]     -> global + grasp + that node's section
    path("openvins_ws")                                -> the OpenVINS folder, ~ expanded
"""

import os
import math
from functools import lru_cache
from pathlib import Path

import yaml

# This file is shared/gappler_common.py and stays there, so the repo is one folder up.
ROOT = Path(__file__).resolve().parent.parent
GLOBAL_YAML = ROOT / "shared" / "global_config.yaml"


def _section(yaml_path: Path, section: str = "/**") -> dict:
    """One section of a ROS parameter file, without the ros__parameters wrapper."""
    with open(yaml_path) as f:
        return ((yaml.safe_load(f) or {}).get(section) or {}).get("ros__parameters") or {}


def _merge(into: dict, new: dict, where: str) -> None:
    """Add new's keys to into. A key set in two places is refused: each value lives in one file."""
    for key, value in new.items():
        if isinstance(value, dict) and isinstance(into.get(key), dict):
            _merge(into[key], value, where)
        elif key in into:
            raise ValueError(f"config key {key!r} is set twice, again in {where}. "
                             "Each value lives in one file (NEXT_STEPS 2.15)")
        else:
            into[key] = value


@lru_cache(maxsize=None)
def config(subsystem: str | None = None, node: str | None = None) -> dict:
    """Global values, plus one subsystem's shared values and one node's section when named.
    The same merge a launch file does when it loads global, then the subsystem file.
    Treat the result as read-only: it is cached."""
    merged = _section(GLOBAL_YAML)
    if subsystem:
        sub_yaml = ROOT / subsystem / f"{subsystem}_config.yaml"
        _merge(merged, _section(sub_yaml), str(sub_yaml.relative_to(ROOT)))
        if node:
            _merge(merged, _section(sub_yaml, node), f"{sub_yaml.relative_to(ROOT)} {node}:")
    return merged


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


def camera_reference_frame() -> str:
    """Navigation's D455 depth origin, named consistently with its mount/driver."""
    child = config()["geometry"]["d455_bottom_screw"]["child"]
    suffix = "_bottom_screw_frame"
    if not isinstance(child, str) or not child.endswith(suffix) or child == suffix:
        raise ValueError("D455 screw frame requires a nonempty camera prefix")
    return child[:-len(suffix)] + "_depth_optical_frame"


if __name__ == "__main__":  # self-check: python3 shared/gappler_common.py
    assert (ROOT / "global_env.sh").exists(), ROOT
    assert config()["topics"]["object_centroid_2d"] == "/object_centroid_2d"
    assert "imu" not in config()["topics"]  # aria-only, so not in global
    assert config("aria")["topics"]["imu"] == "/aria/imu"
    assert config("grasp", "sam3_ros_node")["confidence"] == 0.5
    assert "confidence" not in config("grasp")  # node sections only when the node is named
    for sub in ("aria", "arm", "grasp", "nav"):  # every file loads, no key set twice
        config(sub)
    try:
        _merge({"a": {"b": 1}}, {"a": {"b": 2}}, "test")
        raise AssertionError("a duplicate key was accepted")
    except ValueError:
        pass
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
