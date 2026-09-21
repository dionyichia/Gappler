#!/usr/bin/env python3
"""
AnyGrasp Detection ROS2 node.
Runs inside the AnyGrasp conda environment.
Subscribes to RGB, depth, and SAM mask topics.
Runs per-frame detection (stateless) when pipeline state is EXECUTING.
Publishes top 5 grasp candidates to /grasp_candidates as GraspCandidateArray.
"""

import argparse

import numpy as np
import rclpy
import tf2_ros
from gsnet import AnyGrasp  # Compiled binary, must be in conda env
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from rm_ros_interfaces.msg import GraspCandidate, GraspCandidateArray
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint_path", required=True)
parser.add_argument("--max_gripper_width", type=float, default=0.1)
parser.add_argument("--gripper_height", type=float, default=0.03)
parser.add_argument("--top_down_grasp", action="store_true")
parser.add_argument("--debug", action="store_true")
cfgs, _ = parser.parse_known_args()
cfgs.max_gripper_width = 0.07
cfgs.gripper_height = 0.04
cfgs.top_down_grasp = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOPIC_RGB = "/camera/camera/color/image_raw"
TOPIC_DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
TOPIC_MASK = "/camera/sam/mask"
TOPIC_CAMERA_INFO = "/camera/camera/color/camera_info"

DEPTH_SCALE = 0.001  # metres per depth unit
NUM_CANDIDATES = 5

# Wide lims — SAM mask handles spatial filtering
LIMS = [-1.0, 1.0, -1.0, 1.0, 0.0, 1.5]


class AnyGraspDetectionNode(Node):
    def __init__(self):
        super().__init__("anygrasp_detection_node")

        # Intrinsics — gated until received
        self.fx = self.fy = self.cx = self.cy = None
        self.intrinsics_received = False
        self.camera_info_sub = self.create_subscription(
            CameraInfo, TOPIC_CAMERA_INFO, self.camera_info_callback, 1
        )

        # Pipeline state gate
        self.pipeline_state = "IDLE"
        self.state_sub = self.create_subscription(
            String, "/pipeline_state", self.state_callback, 10
        )

        # AnyGrasp detector (stateless)
        self.detector = AnyGrasp(cfgs)
        self.detector.load_net()
        self.get_logger().info("AnyGrasp detection model loaded")

        # Latest mask cache — decoupled from RGB/depth sync
        self.latest_mask = None
        self.mask_sub = self.create_subscription(
            Image, TOPIC_MASK, self.mask_callback, 10
        )

        # Publisher
        self.grasp_pub = self.create_publisher(
            GraspCandidateArray, "/grasp_candidates", 10
        )

        # Synchronized RGB + depth
        self.rgb_sub = Subscriber(self, Image, TOPIC_RGB)
        self.depth_sub = Subscriber(self, Image, TOPIC_DEPTH)
        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub], queue_size=10, slop=0.05
        )
        self.sync.registerCallback(self.synced_callback)

        self.get_logger().info("AnyGrasp detection node ready")

    # -----------------------------------------------------------------------
    # CameraInfo — one-time latch
    # -----------------------------------------------------------------------
    def camera_info_callback(self, msg: CameraInfo):
        if self.intrinsics_received:
            return
        self.fx = msg.k[0]
        self.fy = msg.k[4]
        self.cx = msg.k[2]
        self.cy = msg.k[5]
        self.intrinsics_received = True
        self.get_logger().info(
            f"Intrinsics: fx={self.fx:.2f} fy={self.fy:.2f} "
            f"cx={self.cx:.2f} cy={self.cy:.2f}"
        )
        self.destroy_subscription(self.camera_info_sub)

    # -----------------------------------------------------------------------
    # Pipeline state
    # -----------------------------------------------------------------------
    def state_callback(self, msg: String):
        prev = self.pipeline_state
        self.pipeline_state = msg.data
        if msg.data == "IDLE" and prev != "IDLE":
            self.latest_mask = None
            self.get_logger().info("Pipeline IDLE: detection node reset")

    # -----------------------------------------------------------------------
    # Mask cache
    # -----------------------------------------------------------------------
    def mask_callback(self, msg: Image):
        self.latest_mask = msg

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def image_to_numpy(self, msg: Image, normalize: bool = False) -> np.ndarray:
        dtype = np.uint8 if msg.encoding in ("rgb8", "mono8") else np.uint16
        img = np.frombuffer(msg.data, dtype=dtype).reshape(msg.height, msg.width, -1)
        img = img.squeeze()
        if normalize:
            return img.astype(np.float32) / 255.0
        return img

    def build_point_cloud(self, depth: np.ndarray):
        h, w = depth.shape
        xmap, ymap = np.meshgrid(np.arange(w), np.arange(h))
        points_z = depth * DEPTH_SCALE
        points_x = (xmap - self.cx) * points_z / self.fx
        points_y = (ymap - self.cy) * points_z / self.fy
        return np.stack([points_x, points_y, points_z], axis=-1)

    def rotation_to_quaternion(self, rot_matrix: np.ndarray):
        return Rotation.from_matrix(rot_matrix).as_quat()

    def build_grasp_msg(self, gg) -> GraspCandidateArray:
        msg = GraspCandidateArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "camera_color_optical_frame"

        for i in range(min(NUM_CANDIDATES, len(gg))):
            g = GraspCandidate()
            g.score = float(gg[i].score)
            g.width = float(gg[i].width)
            g.depth = float(gg[i].depth)

            t = gg[i].translation
            g.pose.position.x = float(t[0])
            g.pose.position.y = float(t[1])
            g.pose.position.z = float(t[2])

            q = self.rotation_to_quaternion(gg[i].rotation_matrix)
            g.pose.orientation.x = float(q[0])
            g.pose.orientation.y = float(q[1])
            g.pose.orientation.z = float(q[2])
            g.pose.orientation.w = float(q[3])

            msg.grasps.append(g)

        return msg

    # -----------------------------------------------------------------------
    # Synchronized callback — runs detection per frame when EXECUTING
    # -----------------------------------------------------------------------
    def synced_callback(self, rgb_msg: Image, depth_msg: Image):
        if not self.intrinsics_received:
            return
        if self.pipeline_state != "IDLE":
            return
        if self.latest_mask is None:
            self.get_logger().warn("No SAM mask received yet, skipping frame")
            return

        colors = self.image_to_numpy(rgb_msg, normalize=True)
        depth = self.image_to_numpy(depth_msg)

        points_full = self.build_point_cloud(depth)

        # Combined SAM mask + depth validity
        depth_mask = (points_full[:, :, 2] > 0) & (points_full[:, :, 2] < 1.5)
        sam_mask = self.image_to_numpy(self.latest_mask).astype(bool)
        combined_mask = depth_mask & sam_mask

        if combined_mask.sum() == 0:
            self.get_logger().warn("Combined mask empty, skipping frame")
            return

        points = points_full[combined_mask].astype(np.float32)
        colors_masked = colors[combined_mask].astype(np.float32)

        # Per-frame stateless detection
        try:
            gg, _ = self.detector.get_grasp(
                points,
                colors_masked,
                lims=LIMS,
                apply_object_mask=True,
                dense_grasp=False,
                collision_detection=True,
            )
        except Exception as e:
            self.get_logger().warn(f"Detection failed: {e}")
            return

        if gg is None or len(gg) == 0:
            self.get_logger().warn("No grasps detected")
            return

        gg = gg.nms().sort_by_score()

        msg = self.build_grasp_msg(gg)
        self.grasp_pub.publish(msg)
        self.get_logger().debug(f"Published {len(msg.grasps)} detection candidates")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    rclpy.init()
    node = AnyGraspDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
