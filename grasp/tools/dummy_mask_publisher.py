"""Stand-in for SAM 3, so the arm can be exercised with no perception model loaded (T1.16).

Subscribes to depth only. Publishes, for every depth frame:
  - an all-True mask on /camera/sam/mask, for the AnyGrasp nodes
  - a centroid on /object_centroid_2d, for the grasp state machine

Both are needed. The state machine grasps from the centroid while USE_SIMPLE_EXECUTE is true
(grasp_state_machine.cpp:41, CHANNEL_CONTRACT B-1) and never reads the mask, so a mask alone
cannot drive a grasp. The mask is what the AnyGrasp path uses, once T1.17 turns it on.

The mask is every pixel, so the centroid is the image centre and the depth is the median of the
frame, which is what SAM 3 would produce from the same all-True mask
(sam3_ros_node.py:139-164). Field meanings match it exactly: x is the pixel column, y is the
pixel row, z is metres.

WARNING: it claims every pixel is the object, so the arm reaches for the middle of whatever is
in front of the camera. Put one object in view, on a clear table.

    python3 grasp/tools/dummy_mask_publisher.py

Still open in T2.1: whether this file survives the one segmentation service.
"""

import numpy as np
import rclpy
from geometry_msgs.msg import PointStamped
from rclpy.node import Node
from sensor_msgs.msg import Image

# The real channels, published by sam3_ros_node.py:31-33 when perception is running.
TOPIC_DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
TOPIC_MASK = "/camera/sam/mask"
TOPIC_CENTROID_2D = "/object_centroid_2d"
DEPTH_SCALE = 0.001  # metres per depth unit, same as sam3_ros_node.py:36
CENTROID_FRAME = "camera_color_optical_frame"


class DummyMaskPublisher(Node):
    def __init__(self):
        super().__init__("dummy_mask_publisher")

        self.mask_pub = self.create_publisher(Image, TOPIC_MASK, 10)
        self.centroid_pub = self.create_publisher(PointStamped, TOPIC_CENTROID_2D, 10)

        self.depth_sub = self.create_subscription(
            Image, TOPIC_DEPTH, self.depth_callback, 10
        )

        self.get_logger().info(
            f"stand-in ready: all-True mask on {TOPIC_MASK}, "
            f"image-centre centroid on {TOPIC_CENTROID_2D}"
        )

    def depth_callback(self, depth_msg: Image):
        mask_msg = Image()
        # Match header exactly so ApproximateTimeSynchronizer aligns them
        mask_msg.header = depth_msg.header
        mask_msg.height = depth_msg.height
        mask_msg.width = depth_msg.width

        mask_msg.encoding = "mono8"
        mask_msg.step = depth_msg.width
        # All-True mask: every pixel is part of the "object"
        mask_msg.data = bytes(
            np.ones(depth_msg.height * depth_msg.width, dtype=np.uint8)
        )
        self.mask_pub.publish(mask_msg)

        z = median_depth_m(depth_msg.data)
        if z is None:
            self.get_logger().warn("no valid depth in the frame, no centroid published")
            return

        pt = PointStamped()
        pt.header = depth_msg.header
        pt.header.frame_id = CENTROID_FRAME
        pt.point.x = float(depth_msg.width // 2)   # pixel column
        pt.point.y = float(depth_msg.height // 2)  # pixel row
        pt.point.z = z                             # depth in metres
        self.centroid_pub.publish(pt)


def median_depth_m(data: bytes) -> float | None:
    """Median of the non-zero depth readings, in metres. None if the frame has none.
    Zero means no reading in a RealSense depth image, so it cannot be averaged in."""
    depth = np.frombuffer(data, dtype=np.uint16)
    valid = depth[depth > 0]
    if valid.size == 0:
        return None
    return float(np.median(valid)) * DEPTH_SCALE


def main():
    rclpy.init()
    node = DummyMaskPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
