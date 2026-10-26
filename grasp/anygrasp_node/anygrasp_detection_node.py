#!/usr/bin/env python3
"""
AnyGrasp Detection ROS2 node.
Runs inside the AnyGrasp conda environment.
Subscribes to RGB, depth, and SAM mask topics.
Runs per-frame detection (stateless) when pipeline state is EXECUTING.
Publishes top 5 grasp candidates to /grasp_candidates as GraspCandidateArray.
"""

import argparse
import os
import sys

import numpy as np
import rclpy
import tf2_ros
from message_filters import ApproximateTimeSynchronizer, Subscriber
from rclpy.node import Node
from grasp_interfaces.msg import GraspCandidate, GraspCandidateArray
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import CameraInfo, Image
from sensor_msgs_py import point_cloud2
from std_msgs.msg import String
from gappler_common import config
from anygrasp_to_grasp_frame import fingertip_position, fits_gripper, nearer_twin, to_grasp_frame

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
cfgs.gripper_height = 0.04
cfgs.top_down_grasp = False

# shared/global_config.yaml and grasp/grasp_config.yaml
CFG = config("grasp", "anygrasp_detection_node")

# Load the chosen SDK from its folder (T1.45). Both SDKs read ./license, so run from that folder.
SDK = CFG["anygrasp_sdk"]
SDK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), SDK)
cfgs.checkpoint_path = os.path.abspath(cfgs.checkpoint_path)
os.chdir(SDK_DIR)
sys.path.insert(0, SDK_DIR)
if SDK == "anygrasp3":
    from gsnet import create_detector  # noqa: E402  compiled binary, needs the anygrasp venv
elif SDK == "anygrasp2":
    from gsnet import AnyGrasp  # noqa: E402
else:
    raise ValueError(f"anygrasp_sdk must be anygrasp2 or anygrasp3, got {SDK!r}")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TOPICS = CFG["topics"]
TOPIC_RGB = TOPICS["wrist_camera_color"]
TOPIC_DEPTH = TOPICS["wrist_camera_aligned_depth"]
TOPIC_MASK = TOPICS["wrist_camera_object_mask"]
TOPIC_CAMERA_INFO = TOPICS["wrist_camera_info"]

DEPTH_SCALE = CFG["wrist_camera"]["depth_scale_m"]  # metres per depth unit
NUM_CANDIDATES = CFG["num_grasp_candidates"]

# Wide lims (anygrasp2 only), SAM mask handles spatial filtering
LIMS = CFG["workspace_limits_m"]
cfgs.max_gripper_width = CFG["max_gripper_width_m"]
# A grasp's approach is its rotation's x column. Kept if within max_approach_deg of the camera's z.
MAX_APPROACH_RAD = float(np.radians(CFG["max_approach_deg"]))
MIN_APPROACH_COS = float(np.cos(MAX_APPROACH_RAD))
SCENE_MARGIN = float(CFG["scene_margin_m"])  # anygrasp3: scene kept around the object's box
# Does the object fit the real gripper (T1.32, anygrasp_to_grasp_frame.py fits_gripper)
FIT = dict(max_width=CFG["max_object_width_m"], max_depth=CFG["max_grasp_depth_m"],
           finger_height=CFG["finger_height_m"], percentile=CFG["fit_percentile"])


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
            String, TOPICS["pipeline_state"], self.state_callback, 10
        )

        # AnyGrasp detector (stateless)
        if SDK == "anygrasp3":
            # Licence checked here only, not per grasp: plug in USB devices (Aria) after this (T1.45)
            self.detector = create_detector(cfgs)
            if self.detector is None:
                raise RuntimeError(f"AnyGrasp 3 licence failed, see {SDK_DIR}/license (docs/ASSETS.md)")
        else:
            self.detector = AnyGrasp(cfgs)
            self.detector.load_net()
        self.get_logger().info(f"AnyGrasp detection model loaded ({SDK})")

        # Latest mask cache — decoupled from RGB/depth sync
        self.latest_mask = None
        self.mask_sub = self.create_subscription(
            Image, TOPIC_MASK, self.mask_callback, 10
        )

        # Publisher
        self.grasp_pub = self.create_publisher(
            GraspCandidateArray, TOPICS["grasp_candidates"], 10
        )
        # The points AnyGrasp is given, for RViz (T1.34): do the fingers sit on the box faces
        self.points_pub = self.create_publisher(
            point_cloud2.PointCloud2, TOPICS["debug_anygrasp_points"], 1
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

            # grasp_frame is at the fingertips, AnyGrasp's point is depth short of them
            t = fingertip_position(gg[i].translation, gg[i].rotation_matrix, gg[i].depth)
            g.pose.position.x = float(t[0])
            g.pose.position.y = float(t[1])
            g.pose.position.z = float(t[2])

            # AnyGrasp's axes -> grasp_frame's, which moveToPose aims, then the twin that turns the
            # wrist least (anygrasp_to_grasp_frame.py)
            q = self.rotation_to_quaternion(nearer_twin(to_grasp_frame(gg[i].rotation_matrix)))
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
        # Only EXECUTING reads candidates (grasp_state_machine.cpp graspCallback). Was "IDLE",
        # so none ever reached the arm (CODE_AUDIT A1, fixed in T1.8)
        if self.pipeline_state != "EXECUTING":
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

        # The object's points: fits_gripper and RViz use them with either SDK
        points = points_full[combined_mask].astype(np.float32)
        # Stamped now, like the candidates (build_grasp_msg), so RViz can place a replayed bag's frames
        header = depth_msg.header
        header.stamp = self.get_clock().now().to_msg()
        self.points_pub.publish(point_cloud2.create_cloud_xyz32(header, points))

        # Per-frame stateless detection
        try:
            if SDK == "anygrasp3":
                # The scene near the object, so the collision check sees the table and neighbours.
                # Points further than the margin cannot touch a gripper on the object, and the whole
                # scene took 2.3 s a frame (T1.45). Grasps only on the SAM mask, approaching along
                # the camera's view.
                lo, hi = points.min(axis=0) - SCENE_MARGIN, points.max(axis=0) + SCENE_MARGIN
                near = depth_mask & np.all((points_full >= lo) & (points_full <= hi), axis=2)
                gg = self.detector.get_grasp(points_full[near].astype(np.float32), {
                    "region_steering": sam_mask[near],
                    "approach_steering": [0.0, 0.0, 1.0],
                    "approach_thresh": MAX_APPROACH_RAD,
                    "dense_grasp": False,
                    "collision_detection": True,
                })
            else:
                gg, _ = self.detector.get_grasp(
                    points,
                    colors[combined_mask].astype(np.float32),
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
        if SDK == "anygrasp2":  # anygrasp3 was steered to this cone already
            gg = gg[gg.rotation_matrices[:, 2, 0] >= MIN_APPROACH_COS]
            if len(gg) == 0:
                self.get_logger().warn("No grasp along the camera's view", throttle_duration_sec=5.0)
                return
        fit = [fits_gripper(points, t, r, d, **FIT)
               for t, r, d in zip(gg.translations, gg.rotation_matrices, gg.depths)]
        keep = np.array([f[0] for f in fit])
        if not keep.any():
            # Why, from the narrowest grasp (T1.37). nan: no object points between the pads.
            _, w, d = min(fit, key=lambda f: np.nan_to_num(f[1], nan=np.inf))
            self.get_logger().warn(
                f"No grasp fits the gripper: narrowest {w:.3f} m wide "
                f"(limit {FIT['max_width']}), tips {d:.3f} m in (limit {FIT['max_depth']}). "
                f"{len(fit)} grasps checked (T1.32)", throttle_duration_sec=5.0)
            return
        gg = gg[keep]

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
