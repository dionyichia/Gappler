from enum import Enum

from gappler_common import config as gappler_config
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

# shared/global_config.yaml + aria/aria_config.yaml
config = gappler_config("aria")

# Topics enum, built from yaml at import time. Holds aria's own topics and the global ones.
ROS2Topics = Enum(
    "ROS2Topics", {k.upper(): v for k, v in config["topics"].items()}
)

# QoS profile — reconstructed from yaml
_qos_cfg = config["qos"]["video"]
VIDEO_QOS = QoSProfile(
    reliability=ReliabilityPolicy[_qos_cfg["reliability"]],
    history=HistoryPolicy[_qos_cfg["history"]],
    depth=_qos_cfg["depth"],
)
