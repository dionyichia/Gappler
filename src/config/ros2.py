from enum import Enum
from pathlib import Path

import yaml
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

config_path = Path(__file__).parent.parent.parent / "shared" / "config.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)

# Topics enum — built dynamically from yaml
ROS2Topics = Enum(
    "ROS2Topics", {k.upper(): v for k, v in config["ros2"]["topics"].items()}
)

# QoS profile — reconstructed from yaml
_qos_cfg = config["ros2"]["qos"]["video"]
VIDEO_QOS = QoSProfile(
    reliability=ReliabilityPolicy[_qos_cfg["reliability"]],
    history=HistoryPolicy[_qos_cfg["history"]],
    depth=_qos_cfg["depth"],
)
