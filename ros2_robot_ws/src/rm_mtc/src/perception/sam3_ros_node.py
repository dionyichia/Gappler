#!/usr/bin/env python3
"""
SAM3 ROS2 mask publisher node.
Runs inside the project's uv venv, with src/ on PYTHONPATH.
Working directory: .../src/services/object_recognition/

Subscribes to RGB + depth image topics.
Runs SAM3 inference with a fixed text prompt.
Publishes:
  - Highest-scoring boolean mask as mono8 Image on /camera/sam/mask
  - 2D centroid + depth as PointStamped on /object_centroid_2d
      x = pixel column, y = pixel row, z = depth in metres at centroid pixel
"""

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from sensor_msgs.msg import CameraInfo, Image

from config import ModelPaths
from services.object_recognition.sam3_model import SAM3Model
from services.visualizer.renderers.object_mask_visualizer import ObjectMaskVisualizer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOPIC_RGB = "/camera/camera/color/image_raw"
TOPIC_DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
TOPIC_MASK = "/camera/sam/mask"
TOPIC_CENTROID_VIZ = "/object_centroid"
TOPIC_CENTROID_2D = "/object_centroid_2d"
TOPIC_CAMERA_INFO = "/camera/camera/color/camera_info"

DEPTH_SCALE = 0.001  # metres per depth unit

# One definition of this path lives in src/config/models.py. Do not add a second.
SAM3_CHECKPOINT = str(ModelPaths.SAM3_PATH)
TEXT_PROMPT = "box"
CONFIDENCE = 0.5


class Sam3RosNode(Node):
    def __init__(self):
        super().__init__("sam3_ros_node")

        # Intrinsics — gated until received
        self.image_cx = self.image_cy = None
        self.fx = self.fy = None
        self.intrinsics_received = False
        self.camera_info_sub = self.create_subscription(
            CameraInfo, TOPIC_CAMERA_INFO, self.camera_info_callback, 1
        )

        # Initialise model
        self.get_logger().info("Loading SAM3 model...")
        self.model = SAM3Model(
            checkpoint_path=SAM3_CHECKPOINT,
            confidence_threshold=CONFIDENCE,
        )
        self.get_logger().info("SAM3 model loaded")

        # Publishers
        self.mask_pub = self.create_publisher(Image, TOPIC_MASK, 10)
        self.centroid_pub = self.create_publisher(PointStamped, TOPIC_CENTROID_2D, 10)
        self.centroid_viz_pub = self.create_publisher(
            PointStamped, TOPIC_CENTROID_VIZ, 10
        )

        # Synchronized RGB + depth subscribers
        self.rgb_sub = Subscriber(self, Image, TOPIC_RGB)
        self.depth_sub = Subscriber(self, Image, TOPIC_DEPTH)
        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=10, slop=0.05
        )
        self.sync.registerCallback(self.rgb_depth_callback)

        self.get_logger().info(
            f"SAM3 node ready — subscribing to {TOPIC_RGB}, publishing to {TOPIC_MASK} and {TOPIC_CENTROID_2D}"
        )

    # -----------------------------------------------------------------------
    # CameraInfo callback — one-time latch for image center
    # -----------------------------------------------------------------------
    def camera_info_callback(self, msg: CameraInfo):
        if self.intrinsics_received:
            return
        self.fx = msg.k[0]
        self.fy = msg.k[4]
        self.image_cx = msg.k[2]
        self.image_cy = msg.k[5]
        self.intrinsics_received = True
        self.get_logger().info(
            f"Intrinsics received: fx={self.fx:.2f} fy={self.fy:.2f} "
            f"image_cx={self.image_cx:.2f} image_cy={self.image_cy:.2f}"
        )
        self.destroy_subscription(self.camera_info_sub)

    # -----------------------------------------------------------------------
    # Synchronized callback
    # -----------------------------------------------------------------------
    def rgb_depth_callback(self, rgb_msg: Image, depth_msg: Image):
        if not self.intrinsics_received:
            return

        # Convert RGB to numpy
        img = np.frombuffer(rgb_msg.data, dtype=np.uint8).reshape(
            rgb_msg.height, rgb_msg.width, -1
        )

        # Run inference
        try:
            inference_state = self.model.process_text_prompt(img, TEXT_PROMPT)
        except Exception as e:
            self.get_logger().warn(f"SAM3 inference failed: {e}")
            return

        # Extract best mask and 2D centroid
        best_mask, best_score, centroid_px = ObjectMaskVisualizer.get_best_mask(
            inference_state
        )

        if best_mask is None:
            self.get_logger().info("No detection above threshold")
            return

        # Publish mask as mono8
        mask_msg = Image()
        mask_msg.header = rgb_msg.header
        mask_msg.height = rgb_msg.height
        mask_msg.width = rgb_msg.width
        mask_msg.encoding = "mono8"
        mask_msg.step = rgb_msg.width
        mask_msg.data = bytes(best_mask.astype(np.uint8).flatten())
        self.mask_pub.publish(mask_msg)
        self.get_logger().debug(f"Mask published with score: {best_score:.3f}")

        # Publish 2D centroid + depth
        if centroid_px is None:
            self.get_logger().info("No centroid detected")
            return

        cx_px, cy_px = centroid_px

        # Read depth at centroid pixel
        depth = np.frombuffer(depth_msg.data, dtype=np.uint16).reshape(
            depth_msg.height, depth_msg.width
        )
        depth_vals = depth[best_mask]
        depth_vals = depth_vals[depth_vals > 0]
        if len(depth_vals) == 0:
            self.get_logger().warn("No valid depth in mask region, skipping")
            return
        z = float(np.median(depth_vals)) * DEPTH_SCALE

        # Publish 2D centroid for arm calibration
        pt = PointStamped()
        pt.header = rgb_msg.header
        pt.header.frame_id = "camera_color_optical_frame"
        pt.point.x = float(cx_px)  # pixel column
        pt.point.y = float(cy_px)  # pixel row
        pt.point.z = z  # depth in metres
        self.centroid_pub.publish(pt)

        # Publish 3D centroid for viz
        viz_pt = PointStamped()
        viz_pt.header = rgb_msg.header
        viz_pt.header.frame_id = "camera_color_optical_frame"
        # Back-project pixel coords to 3D metres using live intrinsics
        viz_pt.point.x = (float(cx_px) - self.image_cx) * z / self.fx
        viz_pt.point.y = (float(cy_px) - self.image_cy) * z / self.fy
        viz_pt.point.z = z
        self.centroid_viz_pub.publish(viz_pt)

        self.get_logger().debug(
            f"Centroid published: px=({cx_px}, {cy_px}) depth={z:.3f}m"
        )


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
