#!/usr/bin/env python3
"""
SAM3 ROS2 mask publisher node.
Runs inside the uv venv rooted at /home/iot22/GitHub/Renaissance-Capstone-Project.
Working directory: .../src/services/object_recognition/

Subscribes to RGB image topic.
Runs SAM3 inference with a fixed text prompt.
Publishes the highest-scoring boolean mask as mono8 Image on the SAM mask topic.
"""

import os
import sys

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

from message_filters import ApproximateTimeSynchronizer, Subscriber
from geometry_msgs.msg import PointStamped

from services.object_recognition.sam3_model import SAM3Model
from services.visualizer.renderers.object_mask_visualizer import ObjectMaskVisualizer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOPIC_RGB = "/camera/camera/color/image_raw"
TOPIC_DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
TOPIC_MASK = "/camera/sam/mask"

FX, FY = 910.7627, 910.3762
CX, CY = 657.9279, 375.1953
DEPTH_SCALE = 0.001

SAM3_CHECKPOINT = (
    "/home/iot22/GitHub/Renaissance-Capstone-Project/src/models/sam3/sam3.pt"
)
TEXT_PROMPT = "box"
CONFIDENCE = 0.5


class Sam3RosNode(Node):
    def __init__(self):
        super().__init__("sam3_ros_node")

        # Initialise model
        self.get_logger().info("Loading SAM3 model...")
        self.model = SAM3Model(
            checkpoint_path=SAM3_CHECKPOINT,
            confidence_threshold=CONFIDENCE,
        )
        self.get_logger().info("SAM3 model loaded")

        # Publisher
        self.mask_pub = self.create_publisher(Image, TOPIC_MASK, 10)

        # Subscriber
        self.centroid_pub = self.create_publisher(PointStamped, "/object_centroid", 10)

        self.rgb_sub = Subscriber(self, Image, TOPIC_RGB)
        self.depth_sub = Subscriber(self, Image, TOPIC_DEPTH)
        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=10, slop=0.05
        )
        self.sync.registerCallback(self.rgb_depth_callback)

        self.get_logger().info(
            f"SAM3 node ready — subscribing to {TOPIC_RGB}, publishing to {TOPIC_MASK}"
        )

    # -----------------------------------------------------------------------
    # Callback
    # -----------------------------------------------------------------------
    def rgb_depth_callback(self, rgb_msg: Image, depth_msg: Image):
        # Convert ROS Image (rgb8) to numpy array (H, W, 3) uint8
        img = np.frombuffer(rgb_msg.data, dtype=np.uint8).reshape(rgb_msg.height, rgb_msg.width, -1)

        # Run inference
        try:
            inference_state = self.model.process_text_prompt(img, TEXT_PROMPT)
        except Exception as e:
            self.get_logger().warn(f"SAM3 inference failed: {e}")
            return

        # Extract best mask
        results = (
            inference_state  # process_text_prompt returns the inference state dict
        )
        best_mask, best_score, centroid = ObjectMaskVisualizer.get_best_mask(inference_state)

        if best_mask is None:
            self.get_logger().info("No detection above threshold")
            return

        # Publish as mono8
        mask_msg = Image()
        mask_msg.header = msg.header  # match timestamp for ApproximateTimeSynchronizer
        mask_msg.height = msg.height
        mask_msg.width = msg.width
        mask_msg.encoding = "mono8"
        mask_msg.step = msg.width
        mask_msg.data = bytes(best_mask.astype(np.uint8).flatten())
        self.mask_pub.publish(mask_msg)
        self.get_logger().debug(f"Mask published with score: {best_score}")

        # Publish centroid
        if centroid is None:
            self.get_logger().info("No centroid detected")
            return
        cx, cy = centroid
        depth = np.frombuffer(depth_msg.data, dtype=np.uint16).reshape(depth_msg.height, depth_msg.width)
        z = depth[cy, cx] * DEPTH_SCALE
        if z <= 0:
            return
        pt = PointStamped()
        pt.header = rgb_msg.header
        pt.header.frame_id = "camera_color_optical_frame"
        pt.point.x = (cx - CX) * z / FX
        pt.point.y = (cy - CY) * z / FY
        pt.point.z = z
        self.centroid_pub.publish(pt)
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    rclpy.init()
    node = Sam3RosNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
