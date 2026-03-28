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
from sensor_msgs.msg import Image
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
# Constants — replace placeholders with actual topic names
# ---------------------------------------------------------------------------
TOPIC_RGB = "/camera/camera/color/image_raw"
TOPIC_DEPTH = "/camera/camera/aligned_depth_to_color/image_raw"
TOPIC_MASK = "/PLACEHOLDER/sam/mask"

# Camera intrinsics — read in from camera_info for D435i
FX, FY = 910.7627, 910.3762
CX, CY = 657.9279, 375.1953
DEPTH_SCALE = 0.001  # metres per depth unit (1mm for D435i z16)

NUM_CANDIDATES = 5


class AnyGraspNode(Node):
    def __init__(self):
        super().__init__("anygrasp_node")

        # AnyGrasp tracker
        self.tracker = AnyGraspTracker(cfgs)
        self.tracker.load_net()
        self.get_logger().info("AnyGrasp model loaded")

        # State
        self.frame_idx = 0
        self.grasp_ids = [0]
        self.tracking_stable = False

        # Publisher
        self.grasp_pub = self.create_publisher(
            GraspCandidateArray, "/grasp_candidates", 10
        )

        # Synchronized subscribers: RGB + depth + SAM mask
        self.rgb_sub = Subscriber(self, Image, TOPIC_RGB)
        self.depth_sub = Subscriber(self, Image, TOPIC_DEPTH)
        self.mask_sub = Subscriber(self, Image, TOPIC_MASK)

        self.sync = ApproximateTimeSynchronizer(
            [self.rgb_sub, self.depth_sub, self.mask_sub],
            queue_size=10,
            slop=0.05,  # 50ms tolerance for time diff between frames
        )
        self.sync.registerCallback(self.synced_callback)
        self.get_logger().info(
            "AnyGrasp node ready, waiting for synchronized frames..."
        )

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
        points_x = (xmap - CX) * points_z / FX
        points_y = (ymap - CY) * points_z / FY
        return np.stack([points_x, points_y, points_z], axis=-1)

    # -----------------------------------------------------------------------
    # Convert 3x3 rotation matrix to quaternion (x, y, z, w)
    # -----------------------------------------------------------------------
    def rotation_to_quaternion(self, rot_matrix: np.ndarray):
        r = Rotation.from_matrix(rot_matrix)
        return r.as_quat()  # returns [x, y, z, w]

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
    def synced_callback(self, rgb_msg: Image, depth_msg: Image, mask_msg: Image):
        # Convert messages to numpy
        colors = self.image_to_numpy(rgb_msg, normalize=True)
        depth = self.image_to_numpy(depth_msg)
        mask = self.image_to_numpy(mask_msg).astype(bool)

        # Build full point cloud
        points_full = self.build_point_cloud(depth)

        # Depth validity mask (0 < z < 1.5m)
        depth_mask = (points_full[:, :, 2] > 0) & (points_full[:, :, 2] < 0.5)

        if self.frame_idx == 0:
            # Frame 0: use SAM mask to select initial grasps
            combined_mask = depth_mask & mask
            points = points_full[combined_mask]
            colors_masked = colors[combined_mask]

            target_gg, curr_gg, target_grasp_ids, _ = self.tracker.update(
                points, colors_masked, self.grasp_ids
            )

            if curr_gg is None or len(curr_gg) == 0:
                self.get_logger().warn("Frame 0: no grasps detected in SAM mask region")
                return

            # Select top NUM_CANDIDATES from detected grasps spread across object
            n = min(30, len(curr_gg))
            self.grasp_ids = np.arange(n)[:30:6]
            target_gg = curr_gg[self.grasp_ids]
            self.tracking_stable = True
            self.get_logger().info(
                f"Frame 0: selected {len(self.grasp_ids)} seed grasps"
            )

        else:
            # Subsequent frames: use full point cloud for tracking
            points = points_full[depth_mask]
            colors_masked = colors[depth_mask]

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

        # Only publish when tracking is stable
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
