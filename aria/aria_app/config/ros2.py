from enum import Enum

from gappler_common import config as global_config
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy

config = global_config()

# Topics enum — built dynamically from yaml
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
