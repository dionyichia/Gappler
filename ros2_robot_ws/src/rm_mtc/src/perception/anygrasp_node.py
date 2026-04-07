#!/usr/bin/env python3
"""
AnyGrasp ROS2 publisher node.
Runs inside the AnyGrasp conda environment.
Subscribes to RGB, depth, and SAM mask topics.
Publishes top 5 grasp candidates to /grasp_candidates.
"""

import argparse

import numpy as np
import rclpy
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from rm_ros_interfaces.msg import GraspCandidate, GraspCandidateArray
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tracker import AnyGraspTracker  # Compiled binary, must be in conda env

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint_path", required=True)
parser.add_argument("--filter", type=str, default="oneeuro")
parser.add_argument("--debug", action="store_true")
cfgs, _ = parser.parse_known_args()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOPIC_RGB = "/camera/camera/color/image_raw"
TOPIC_DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
TOPIC_MASK = "/camera/sam/mask"
TOPIC_CAMERA_INFO = "/camera/camera/color/camera_info"

DEPTH_SCALE = 0.001  # metres per depth unit (1mm for D435i z16)
NUM_CANDIDATES = 5


class AnyGraspNode(Node):
    def __init__(self):
        super().__init__("anygrasp_node")

        # Intrinsics — gated until received
        self.fx = self.fy = self.cx = self.cy = None
        self.intrinsics_received = False
        self.camera_info_sub = self.create_subscription(
            CameraInfo, TOPIC_CAMERA_INFO, self.camera_info_callback, 1
        )

        # Pipeline state
        self.pipeline_state = "IDLE"
        self.state_sub = self.create_subscription(
            String, "/pipeline_state", self.state_callback, 10
        )

        # AnyGrasp tracker
        self.tracker = AnyGraspTracker(cfgs)
        self.tracker.load_net()
        self.get_logger().info("AnyGrasp model loaded")

        # State
        self.frame_idx = 0
        self.grasp_ids = [0]
        self.tracking_stable = False
        self.latest_mask = None

        # Publisher
        self.grasp_pub = self.create_publisher(
            GraspCandidateArray, "/grasp_candidates", 10
        )

        # Standalone mask subscriber — decoupled from RGB/depth sync
        self.mask_sub = self.create_subscription(
            Image, TOPIC_MASK, self.mask_callback, 10
        )

        # Synchronized subscribers: RGB + depth ONLY
        self.rgb_sub = Subscriber(self, Image, TOPIC_RGB)
        self.depth_sub = Subscriber(self, Image, TOPIC_DEPTH)
        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub],
            queue_size=10,
            slop=0.05,
        )
        self.sync.registerCallback(self.synced_callback)
        self.get_logger().info(
            "AnyGrasp node ready, waiting for intrinsics and synchronized frames..."
        )

    # -----------------------------------------------------------------------
    # CameraInfo callback — one-time latch
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
            f"Intrinsics received: fx={self.fx:.2f} fy={self.fy:.2f} "
            f"cx={self.cx:.2f} cy={self.cy:.2f}"
        )
        self.destroy_subscription(self.camera_info_sub)

    # -----------------------------------------------------------------------
    # Mask callback — cache latest mask
    # -----------------------------------------------------------------------
    def mask_callback(self, msg: Image):
        self.latest_mask = msg

    # -----------------------------------------------------------------------
    # Pipeline state callback
    # -----------------------------------------------------------------------
    def state_callback(self, msg: String):
        prev = self.pipeline_state
        self.pipeline_state = msg.data
        if msg.data == "IDLE" and prev != "IDLE":
            self.frame_idx = 0
            self.grasp_ids = [0]
            self.tracking_stable = False
            self.latest_mask = None
            self.get_logger().info("Pipeline IDLE: AnyGrasp reset")

    # -----------------------------------------------------------------------
    # Convert raw ROS Image message to numpy array
    # -----------------------------------------------------------------------
    def image_to_numpy(self, msg: Image, normalize: bool = False) -> np.ndarray:
        dtype = np.uint8 if msg.encoding in ("rgb8", "mono8") else np.uint16
        img = np.frombuffer(msg.data, dtype=dtype).reshape(msg.height, msg.width, -1)
        img = img.squeeze()
        if normalize:
            return img.astype(np.float32) / 255.0
        return img

    # -----------------------------------------------------------------------
    # Build point cloud from depth + intrinsics
    # -----------------------------------------------------------------------
    def build_point_cloud(self, depth: np.ndarray):
        h, w = depth.shape
        xmap, ymap = np.meshgrid(np.arange(w), np.arange(h))
        points_z = depth * DEPTH_SCALE
        points_x = (xmap - self.cx) * points_z / self.fx
        points_y = (ymap - self.cy) * points_z / self.fy
        return np.stack([points_x, points_y, points_z], axis=-1)

    # -----------------------------------------------------------------------
    # Convert 3x3 rotation matrix to quaternion (x, y, z, w)
    # -----------------------------------------------------------------------
    def rotation_to_quaternion(self, rot_matrix: np.ndarray):
        r = Rotation.from_matrix(rot_matrix)
        return r.as_quat()

    # -----------------------------------------------------------------------
    # Build GraspCandidateArray from a GraspGroup
    # -----------------------------------------------------------------------
    def build_grasp_msg(self, grasp_group) -> GraspCandidateArray:
        msg = GraspCandidateArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "camera_color_optical_frame"

        # Sort by score descending, take top N
        scores = grasp_group.scores
        sorted_idx = np.argsort(scores)[::-1][:NUM_CANDIDATES]

        for i in sorted_idx:
            g = GraspCandidate()
            g.score = float(grasp_group.scores[i])
            g.width = float(grasp_group.widths[i])
            g.depth = float(grasp_group.depths[i])

            # Translation
            t = grasp_group.translations[i]
            g.pose.position.x = float(t[0])
            g.pose.position.y = float(t[1])
            g.pose.position.z = float(t[2])

            # Rotation matrix → quaternion
            q = self.rotation_to_quaternion(grasp_group.rotation_matrices[i])
            g.pose.orientation.x = float(q[0])
            g.pose.orientation.y = float(q[1])
            g.pose.orientation.z = float(q[2])
            g.pose.orientation.w = float(q[3])

            msg.grasps.append(g)

        return msg

    # -----------------------------------------------------------------------
    # Synchronized callback
    # -----------------------------------------------------------------------
    def synced_callback(self, rgb_msg: Image, depth_msg: Image):
        if not self.intrinsics_received:
            return
        # if self.pipeline_state == "IDLE":
        #     return
        if self.latest_mask is None:
            self.get_logger().warn("No SAM mask received yet, skipping frame")
            return

        colors = self.image_to_numpy(rgb_msg, normalize=True)
        depth = self.image_to_numpy(depth_msg)

        points_full = self.build_point_cloud(depth)

        # Depth validity mask (0 < z < 1.5m)
        depth_mask = (points_full[:, :, 2] > 0) & (points_full[:, :, 2] < 1.5)

        # SAM mask applied on every frame
        sam_mask = self.image_to_numpy(self.latest_mask).astype(bool)
        combined_mask = depth_mask & sam_mask

        if combined_mask.sum() == 0:
            self.get_logger().warn("Combined mask is empty, skipping frame")
            return

        points = points_full[combined_mask]
        colors_masked = colors[combined_mask]

        if self.frame_idx == 0:
            target_gg, curr_gg, target_grasp_ids, _ = self.tracker.update(
                points, colors_masked, self.grasp_ids
            )

            if curr_gg is None or len(curr_gg) == 0:
                self.get_logger().warn("Frame 0: no grasps detected in masked region")
                return

            n = min(30, len(curr_gg))
            self.grasp_ids = np.arange(n)[:30:6]
            target_gg = curr_gg[self.grasp_ids]
            self.tracking_stable = True
            self.get_logger().info(
                f"Frame 0: selected {len(self.grasp_ids)} seed grasps"
            )

        else:
            target_gg, curr_gg, target_grasp_ids, _ = self.tracker.update(
                points, colors_masked, self.grasp_ids
            )

            if target_grasp_ids is None or len(target_grasp_ids) == 0:
                self.get_logger().warn("Tracking lost, resetting to frame 0")
                self.frame_idx = 0
                self.grasp_ids = [0]
                self.tracking_stable = False
                return

            self.grasp_ids = target_grasp_ids

        if self.tracking_stable and target_gg is not None and len(target_gg) > 0:
            msg = self.build_grasp_msg(target_gg)
            self.grasp_pub.publish(msg)
            self.get_logger().debug(f"Published {len(msg.grasps)} grasp candidates")

        self.frame_idx += 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    rclpy.init()
    node = AnyGraspNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
