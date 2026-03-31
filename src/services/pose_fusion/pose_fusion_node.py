"""
Pose fusion node — Option 3 external graph/fusion layer.

Architecture
------------
Does NOT touch OpenVINS internals.  Runs alongside it as a separate ROS 2
node that subscribes to three topics and publishes one corrected pose:

  /aria/vio_pose    (PoseStamped) ← OpenVINS output, arbitrary VIO world frame
  /aria/aruco_pose  (PoseStamped) ← T_camera_marker published by image pipeline
  /aria/imu         (Imu)         ← raw IMU

  /aria/fused_pose  (PoseStamped) → corrected pose expressed in SLAM map frame

Frame conventions
-----------------
  map      — SLAM map origin (robot LiDAR-SLAM frame)
  glasses  — Aria glasses IMU / OpenVINS reference frame
  camera   — Aria RGB camera optical frame
  marker   — ArUco marker body frame

Correction update (fires on every ArUco detection)
---------------------------------------------------
  T_map_marker     : known from SLAM map, set via ROS params
  T_camera_marker  : from ArUco detection (= /aria/aruco_pose message)
  T_map_camera     = T_map_marker @ inv(T_camera_marker)
  T_map_glasses    ≈ T_map_camera   (barebones: camera ≈ glasses IMU origin)

  T_correction     = T_map_glasses_aruco @ inv(T_vio_at_detection_time)
  Fused pose       = T_correction @ T_vio_current


ROS parameters
--------------
  marker_pos_{x,y,z}           — ArUco marker translation in SLAM map (m)
  marker_quat_{x,y,z,w}        — ArUco marker orientation in SLAM map

Usage
-----
  ros2 run <your_package> pose_fusion_node \
      --ros-args \
      -p marker_pos_x:=1.5 -p marker_pos_y:=0.0 -p marker_pos_z:=0.9 \
      -p marker_quat_w:=1.0
"""

import logging
from typing import Optional

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, TransformStamped
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from scipy.spatial.transform import Rotation
from std_msgs.msg import Header
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster

logger = logging.getLogger(__name__)

VIDEO_QOS = QoSProfile(
    reliability=ReliabilityPolicy.BEST_EFFORT,
    history=HistoryPolicy.KEEP_LAST,
    depth=1,
)

# ── helpers ──────────────────────────────────────────────────────────────────


def _pose_to_T(msg: PoseStamped) -> np.ndarray:
    """Convert a PoseStamped to a 4×4 homogeneous transform (float64)."""
    p = msg.pose.position
    q = msg.pose.orientation
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
    T[:3, 3] = [p.x, p.y, p.z]
    return T


def _pwcs_to_T(msg: PoseWithCovarianceStamped) -> np.ndarray:
    p = msg.pose.pose.position
    q = msg.pose.pose.orientation
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = Rotation.from_quat([q.x, q.y, q.z, q.w]).as_matrix()
    T[:3, 3] = [p.x, p.y, p.z]
    return T


def _T_to_pose_stamped(
    T: np.ndarray,
    frame_id: str,
    stamp,
) -> PoseStamped:
    """Convert a 4x4 homogeneous transform to a PoseStamped."""
    msg = PoseStamped()
    msg.header = Header()
    msg.header.stamp = stamp
    msg.header.frame_id = frame_id

    msg.pose.position.x = float(T[0, 3])
    msg.pose.position.y = float(T[1, 3])
    msg.pose.position.z = float(T[2, 3])

    q = Rotation.from_matrix(T[:3, :3]).as_quat()  # [x, y, z, w]
    msg.pose.orientation.x = float(q[0])
    msg.pose.orientation.y = float(q[1])
    msg.pose.orientation.z = float(q[2])
    msg.pose.orientation.w = float(q[3])

    return msg


# ── node ─────────────────────────────────────────────────────────────────────


class PoseFusionNode(Node):
    """Fuses OpenVINS VIO with periodic ArUco pose corrections."""

    def __init__(self) -> None:
        super().__init__("aria_pose_fusion")

        self._static_broadcaster = StaticTransformBroadcaster(self)
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = "global"
        t.child_frame_id = "map"
        t.transform.rotation.w = 1.0  # identity — adjust once you know the real offset
        self._static_broadcaster.sendTransform(t)

        # ── parameters ────────────────────────────────────────────────────────
        # Marker pose in SLAM map frame.  Set these to match the known ArUco
        # position in your map before running.  Defaults = map origin.
        self.declare_parameter("marker_pos_x", 0.0)
        self.declare_parameter("marker_pos_y", 0.0)
        self.declare_parameter("marker_pos_z", 0.0)
        self.declare_parameter("marker_quat_x", 0.0)
        self.declare_parameter("marker_quat_y", 0.0)
        self.declare_parameter("marker_quat_z", 0.0)
        self.declare_parameter("marker_quat_w", 1.0)

        # ── subscribers ───────────────────────────────────────────────────────
        self.create_subscription(
            PoseWithCovarianceStamped,
            "/ov_msckf/poseimu",
            self._on_vio_pose,
            VIDEO_QOS,
        )
        self.create_subscription(
            PoseStamped,
            "/aria/aruco_pose",
            self._on_aruco_pose,
            VIDEO_QOS,
        )
        self.create_subscription(
            PoseStamped,
            "/robot_pose",
            self._on_robot_pose,
            10,
        )

        self._pub = self.create_publisher(PoseStamped, "/aria/fused_pose", 10)
        self._tf_broadcaster = TransformBroadcaster(self)

        # T_map_glasses at the moment of the last ArUco fix.
        # Defaults to identity so VIO broadcasts immediately; ArUco corrects position later.
        self._T_anchor: np.ndarray = np.eye(4)
        # T_vio at the moment of the last ArUco fix
        self._T_vio_at_anchor: Optional[np.ndarray] = None
        # Latest raw VIO pose
        self._T_vio_current: Optional[np.ndarray] = None
        # Latest robot pose in map frame — None if robot is not running
        self._T_robot: Optional[np.ndarray] = None
        # Guard: only publish /aria/fused_pose after at least one real ArUco fix
        self._aruco_seen: bool = False

        print("PoseFusionNode started.")

    # ── parameter helpers ─────────────────────────────────────────────────────

    def _T_map_marker(self) -> np.ndarray:
        """Build T_map_marker from current ROS parameters."""
        px = self.get_parameter("marker_pos_x").value
        py = self.get_parameter("marker_pos_y").value
        pz = self.get_parameter("marker_pos_z").value
        qx = self.get_parameter("marker_quat_x").value
        qy = self.get_parameter("marker_quat_y").value
        qz = self.get_parameter("marker_quat_z").value
        qw = self.get_parameter("marker_quat_w").value

        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = Rotation.from_quat([qx, qy, qz, qw]).as_matrix()
        T[:3, 3] = [px, py, pz]
        return T

    def _on_robot_pose(self, msg: PoseStamped) -> None:
        self._T_robot = _pose_to_T(msg)

    def _on_aruco_pose(self, msg: PoseStamped) -> None:
        T_camera_marker = _pose_to_T(msg)

        if self._T_robot is not None:
            # Robot is running — use its live map pose as the marker position
            T_map_marker = self._T_robot
        else:
            # Robot not running — fall back to static params (QR code = origin)
            T_map_marker = self._T_map_marker()

        T_map_glasses = T_map_marker @ np.linalg.inv(T_camera_marker)

        self._T_anchor = T_map_glasses
        self._T_vio_at_anchor = (
            self._T_vio_current.copy() if self._T_vio_current is not None else None
        )
        self._aruco_seen = True

        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = "map"
        t.child_frame_id = "aria_glasses"
        t.transform.translation.x = float(T_map_glasses[0, 3])
        t.transform.translation.y = float(T_map_glasses[1, 3])
        t.transform.translation.z = float(T_map_glasses[2, 3])
        q = Rotation.from_matrix(T_map_glasses[:3, :3]).as_quat()
        t.transform.rotation.x = float(q[0])
        t.transform.rotation.y = float(q[1])
        t.transform.rotation.z = float(q[2])
        t.transform.rotation.w = float(q[3])
        self._tf_broadcaster.sendTransform(t)

        print(
            f"ArUco anchor reset. "
            f"pos=[{T_map_glasses[0, 3]:.3f}, {T_map_glasses[1, 3]:.3f}, {T_map_glasses[2, 3]:.3f}]"
        )

    def _on_vio_pose(self, msg: PoseStamped) -> None:
        self._T_vio_current = _pwcs_to_T(msg)

        if self._T_vio_at_anchor is None:
            self._T_vio_at_anchor = self._T_vio_current.copy()
            return

        T_delta = np.linalg.inv(self._T_vio_at_anchor) @ self._T_vio_current

        delta_dist = np.linalg.norm(T_delta[:3, 3])
        if delta_dist > 2.0:
            self.get_logger().warning(
                f"VIO drift {delta_dist:.2f}m from anchor — consider scanning ArUco marker"
            )

        T_fused = self._T_anchor @ T_delta

        if self._aruco_seen:
            fused_msg = _T_to_pose_stamped(T_fused, "map", msg.header.stamp)
            self._pub.publish(fused_msg)

        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = "map"
        t.child_frame_id = "glasses"
        t.transform.translation.x = float(T_fused[0, 3])
        t.transform.translation.y = float(T_fused[1, 3])
        t.transform.translation.z = float(T_fused[2, 3])
        q = Rotation.from_matrix(T_fused[:3, :3]).as_quat()
        t.transform.rotation.x = float(q[0])
        t.transform.rotation.y = float(q[1])
        t.transform.rotation.z = float(q[2])
        t.transform.rotation.w = float(q[3])
        self._tf_broadcaster.sendTransform(t)
        print("VIO Published")


# ── entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    rclpy.init()
    node = PoseFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
