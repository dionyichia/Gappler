#!/usr/bin/env python3
"""
qos_relay.py
------------
Re-publishes the Livox point cloud with a different QoS policy.

The Livox driver publishes /livox/lidar as RELIABLE, but
pointcloud_to_laserscan requires BEST_EFFORT. This node bridges the gap.

Topics
------
  Subscribed : /livox/lidar  (sensor_msgs/PointCloud2) — RELIABLE
  Published  : /cloud_relay  (sensor_msgs/PointCloud2) — BEST_EFFORT
"""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2
from gappler_common import config

# nav/nav_config.yaml
TOPICS = config("nav")["topics"]

RELIABLE_QOS = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)
BEST_EFFORT_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
    history=HistoryPolicy.KEEP_LAST,
    depth=10,
)


class QoSRelay(Node):
    def __init__(self) -> None:
        super().__init__("qos_relay")
        self._pub = self.create_publisher(PointCloud2, TOPICS["cloud_relay"], BEST_EFFORT_QOS)
        self.create_subscription(
            PointCloud2, TOPICS["livox_lidar"], self._relay, RELIABLE_QOS
        )
        self.get_logger().info(
            f"QoS relay: {TOPICS['livox_lidar']} (RELIABLE) → {TOPICS['cloud_relay']} (BEST_EFFORT)"
        )

    def _relay(self, msg: PointCloud2) -> None:
        self._pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = QoSRelay()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass  # Ctrl+C: exit quietly (CODE_AUDIT F4)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
