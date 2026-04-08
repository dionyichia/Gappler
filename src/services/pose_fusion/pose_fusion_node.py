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
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from scipy.spatial.transform import Rotation
from std_msgs.msg import Empty, Header
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster
from visualization_msgs.msg import Marker

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

        # self._static_broadcaster = StaticTransformBroadcaster(self)
        # t = TransformStamped()
        # t.header.stamp = self.get_clock().now().to_msg()
        # t.header.frame_id = "global"
        # t.child_frame_id = "map"
        # t.transform.rotation.w = 1.0  # identity — adjust once you know the real offset
        # self._static_broadcaster.sendTransform(t)

        # ── parameters ────────────────────────────────────────────────────────
        # Marker pose in SLAM map frame.  Set these to match the known ArUco
        # position in your map before running.  Defaults = map origin.
        self.declare_parameter("marker_pos_x", 0.0)
        self.declare_parameter("marker_pos_y", 0.0)
        self.declare_parameter("marker_pos_z", 0.0)
        self.declare_parameter("marker_quat_x", 0.0)
        self.declare_parameter("marker_quat_y", 0.0)
        self.declare_parameter("marker_quat_z", 0.0)

        # Fixed offset from robot SLAM origin to ArUco marker (robot frame).
        # Marker is at back-right corner of base, 1.2 m above ground:
        #   x = -0.30 (back), y = -0.31 (right), z = 1.2 (height)
        self.declare_parameter("marker_offset_x", -0.20)
        self.declare_parameter("marker_offset_y", -0.25)
        self.declare_parameter("marker_offset_z", 1.20)
        self.declare_parameter("marker_offset_quat_x", 0.0)
        self.declare_parameter("marker_offset_quat_y", 0.0)
        self.declare_parameter("marker_offset_quat_z", 0.0)
        self.declare_parameter("marker_offset_quat_w", 1.0)

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
        self._pose_initialized_pub = self.create_publisher(
            Empty, "/aria/pose_initialized", 10
        )
        self._glasses_marker_pub = self.create_publisher(
            Marker, "/aria/glasses_marker", 10
        )
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
        """Build T_map_marker from current ROS parameters (static / no-robot fallback)."""
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

    def _T_robot_marker(self) -> np.ndarray:
        """Fixed transform from robot SLAM origin to ArUco marker (robot frame)."""
        ox = self.get_parameter("marker_offset_x").value
        oy = self.get_parameter("marker_offset_y").value
        oz = self.get_parameter("marker_offset_z").value
        qx = self.get_parameter("marker_offset_quat_x").value
        qy = self.get_parameter("marker_offset_quat_y").value
        qz = self.get_parameter("marker_offset_quat_z").value
        qw = self.get_parameter("marker_offset_quat_w").value

        T = np.eye(4, dtype=np.float64)
        T[:3, :3] = Rotation.from_quat([qx, qy, qz, qw]).as_matrix()
        T[:3, 3] = [ox, oy, oz]
        return T

    def _on_robot_pose(self, msg: PoseStamped) -> None:
        self._T_robot = _pose_to_T(msg)

    def _on_aruco_pose(self, msg: PoseStamped) -> None:
        T_camera_marker = _pose_to_T(msg)

        if self._T_robot is not None:
            # Robot is running — chain robot map pose with fixed robot→marker offset
            T_map_marker = self._T_robot @ self._T_robot_marker()
        else:
            # Robot not running — fall back to static params
            T_map_marker = self._T_map_marker()

        T_map_glasses = T_map_marker @ np.linalg.inv(T_camera_marker)

        self._T_anchor = T_map_glasses
        self._T_vio_at_anchor = (
            self._T_vio_current.copy() if self._T_vio_current is not None else None
        )
        first_fix = not self._aruco_seen
        self._aruco_seen = True

        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = "base_link"
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

        # Publish fused pose directly from ArUco — works even without VIO running
        aruco_fused_msg = _T_to_pose_stamped(
            T_map_glasses, "base_link", msg.header.stamp
        )
        self._pub.publish(aruco_fused_msg)
        self._publish_glasses_marker(T_map_glasses, msg.header.stamp)

        # Notify downstream nodes the first time a valid fix is received
        if first_fix:
            self._pose_initialized_pub.publish(Empty())

        print(
            f"ArUco anchor updated. "
            f"pos=[{T_map_glasses[0, 3]:.3f}, {T_map_glasses[1, 3]:.3f}, {T_map_glasses[2, 3]:.3f}]"
        )

    def _on_vio_pose(self, msg: PoseWithCovarianceStamped) -> None:
        T_new = _pwcs_to_T(msg)

        # Sanity check: reject frames where VIO teleports (> 0.5 m from last pose)
        if self._T_vio_current is not None:
            step = np.linalg.norm(T_new[:3, 3] - self._T_vio_current[:3, 3])
            if step > 0.5:
                self.get_logger().warning(
                    f"VIO jump of {step:.2f} m rejected — likely tracking loss"
                )
                return

        self._T_vio_current = T_new

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
            fused_msg = _T_to_pose_stamped(T_fused, "base_link", msg.header.stamp)
            self._pub.publish(fused_msg)
            self._publish_glasses_marker(T_fused, msg.header.stamp)

        t = TransformStamped()
        t.header.stamp = msg.header.stamp
        t.header.frame_id = "base_link"
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

    def _publish_glasses_marker(self, T_fused: np.ndarray, stamp) -> None:
        """Publish 'Aria Glasses' text label above the existing TF frame in RViz."""
        x, y, z = float(T_fused[0, 3]), float(T_fused[1, 3]), float(T_fused[2, 3])

        label = Marker()
        label.header.frame_id = "base_link"
        label.header.stamp = stamp
        label.ns = "aria_glasses"
        label.id = 0
        label.type = Marker.TEXT_VIEW_FACING
        label.action = Marker.ADD
        label.lifetime = Duration(seconds=3).to_msg()  # auto-expires if VIO stops
        label.pose.position.x = x
        label.pose.position.y = y
        label.pose.position.z = z + 0.25  # float above the TF axes
        label.pose.orientation.w = 1.0
        label.scale.z = 0.15  # text height in metres
        label.color.r = 1.0
        label.color.g = 1.0
        label.color.b = 1.0
        label.color.a = 1.0
        label.text = "Aria Glasses"
        self._glasses_marker_pub.publish(label)


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
