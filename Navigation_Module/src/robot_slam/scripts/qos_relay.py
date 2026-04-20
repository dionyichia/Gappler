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
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import PointCloud2

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
        self._pub = self.create_publisher(PointCloud2, "/cloud_relay", BEST_EFFORT_QOS)
        self.create_subscription(
            PointCloud2, "/livox/lidar", self._relay, RELIABLE_QOS
        )
        self.get_logger().info(
            "QoS relay: /livox/lidar (RELIABLE) → /cloud_relay (BEST_EFFORT)"
        )

    def _relay(self, msg: PointCloud2) -> None:
        self._pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = QoSRelay()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
