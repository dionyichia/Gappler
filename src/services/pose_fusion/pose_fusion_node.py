"""
Pose fusion node — Option 3 external graph/fusion layer.

Architecture
------------
Does NOT touch OpenVINS internals.  Runs alongside it as a separate ROS 2
node that subscribes to three topics and publishes one corrected pose:

  /aria/vio_pose    (PoseStamped) ← OpenVINS output, arbitrary VIO world frame
  /aria/aruco_pose  (PoseStamped) ← T_camera_marker published by image pipeline
  /aria/imu         (Imu)         ← raw IMU, used for ZUPT detection

  /aria/fused_pose  (PoseStamped) → corrected pose expressed in SLAM map frame
  /aria/is_stationary (Bool)      → ZUPT flag (high when device is still)

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

ZUPT (zero-velocity) handling
------------------------------
OpenVINS accumulates velocity and gyro-bias drift when the glasses stop
moving, because the filter still integrates noisy IMU samples.  This node
detects stillness via a sliding IMU window and freezes the published pose
until motion resumes, preventing the fused output from drifting while
stationary.  The /aria/is_stationary flag can also be used externally to
trigger a VIO reinitialisation if desired.

ROS parameters
--------------
  marker_pos_{x,y,z}           — ArUco marker translation in SLAM map (m)
  marker_quat_{x,y,z,w}        — ArUco marker orientation in SLAM map
  zupt_gyro_threshold  (rad/s) — max gyro magnitude to count as still
  zupt_accel_threshold (m/s²)  — max deviation from |g| to count as still
  zupt_window_s        (s)     — duration of stillness before ZUPT triggers

Usage
-----
  ros2 run <your_package> pose_fusion_node \
      --ros-args \
      -p marker_pos_x:=1.5 -p marker_pos_y:=0.0 -p marker_pos_z:=0.9 \
      -p marker_quat_w:=1.0
"""

import collections
import logging
from typing import Optional

import numpy as np
import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from scipy.spatial.transform import Rotation
from sensor_msgs.msg import Imu
from std_msgs.msg import Bool, Header

logger = logging.getLogger(__name__)

GRAVITY = 9.81  # m/s²
_ZUPT_MIN_SAMPLES = 5  # discard windows with too few IMU samples


# ── helpers ──────────────────────────────────────────────────────────────────


def _pose_stamped_to_T(msg: PoseStamped) -> np.ndarray:
    """Convert a PoseStamped to a 4×4 homogeneous transform (float64)."""
    p = msg.pose.position
    q = msg.pose.orientation
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

        # ZUPT thresholds — tune to your environment
        self.declare_parameter("zupt_gyro_threshold", 0.05)  # rad/s
        self.declare_parameter("zupt_accel_threshold", 0.15)  # m/s²
        self.declare_parameter("zupt_window_s", 0.5)  # seconds

        # ── subscribers ───────────────────────────────────────────────────────
        self.create_subscription(
            PoseStamped,
            "/aria/vio_pose",
            self._on_vio_pose,
            10,
        )
        self.create_subscription(
            PoseStamped,
            "/aria/aruco_pose",
            self._on_aruco_pose,
            10,
        )
        self.create_subscription(
            Imu,
            "/aria/imu",
            self._on_imu,
            qos_profile_sensor_data,
        )

        # ── publishers ────────────────────────────────────────────────────────
        self._fused_pub = self.create_publisher(PoseStamped, "/aria/fused_pose", 10)
        self._stationary_pub = self.create_publisher(Bool, "/aria/is_stationary", 10)

        # ── state ─────────────────────────────────────────────────────────────
        # T_correction transforms VIO world → SLAM map:
        #   T_map_glasses = T_correction @ T_vio_glasses
        # None until the first ArUco fix arrives (VIO passes through raw).
        self._T_correction: Optional[np.ndarray] = None

        # Latest fused 4×4 — used as the frozen output while stationary.
        self._last_fused_T: Optional[np.ndarray] = None

        # Latest raw VIO 4×4 — needed to compute T_correction on ArUco update.
        self._last_vio_T: Optional[np.ndarray] = None

        self._is_stationary: bool = False

        # ZUPT window: deque of (timestamp_s, accel_deviation, gyro_magnitude)
        self._imu_window: collections.deque = collections.deque()

        self.get_logger().info(
            "PoseFusionNode started.  Waiting for /aria/vio_pose and /aria/aruco_pose."
        )

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

    # ── ZUPT detection ────────────────────────────────────────────────────────

    def _update_zupt(
        self, timestamp_s: float, accel_dev: float, gyro_mag: float
    ) -> bool:
        """
        Add a sample to the sliding window and return True if the device has
        been stationary for the full zupt_window_s duration.
        """
        window_s = self.get_parameter("zupt_window_s").value
        gyro_thresh = self.get_parameter("zupt_gyro_threshold").value
        accel_thresh = self.get_parameter("zupt_accel_threshold").value

        self._imu_window.append((timestamp_s, accel_dev, gyro_mag))

        # Evict samples older than the window
        while self._imu_window and (timestamp_s - self._imu_window[0][0]) > window_s:
            self._imu_window.popleft()

        if len(self._imu_window) < _ZUPT_MIN_SAMPLES:
            return False

        return all(a < accel_thresh and g < gyro_thresh for _, a, g in self._imu_window)

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _on_imu(self, msg: Imu) -> None:
        """
        Detect zero-velocity transitions.

        When the device transitions from moving → stationary the fused pose
        is frozen to prevent VIO drift from accumulating in the output.
        On stationary → moving the last fused pose is used as the starting
        point; the next ArUco sighting will re-anchor if needed.
        """
        ts = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        ax = msg.linear_acceleration.x
        ay = msg.linear_acceleration.y
        az = msg.linear_acceleration.z
        gx = msg.angular_velocity.x
        gy = msg.angular_velocity.y
        gz = msg.angular_velocity.z

        accel_mag = np.sqrt(ax**2 + ay**2 + az**2)
        gyro_mag = np.sqrt(gx**2 + gy**2 + gz**2)
        accel_dev = abs(accel_mag - GRAVITY)

        was_stationary = self._is_stationary
        self._is_stationary = self._update_zupt(ts, accel_dev, gyro_mag)

        if self._is_stationary != was_stationary:
            state_str = (
                "STATIONARY — pose frozen"
                if self._is_stationary
                else "MOVING — resuming VIO"
            )
            self.get_logger().info(f"Motion state changed: {state_str}")
            self._stationary_pub.publish(Bool(data=self._is_stationary))

    def _on_aruco_pose(self, msg: PoseStamped) -> None:
        """
        ArUco detection fires: recompute T_correction.

        The message holds T_camera_marker (marker in camera frame).
        We invert that to get T_marker_camera, then chain with T_map_marker
        to place the camera (= glasses, approximately) in the SLAM map.

        T_map_glasses_aruco = T_map_marker @ T_marker_camera
        T_correction        = T_map_glasses_aruco @ inv(T_vio_glasses_current)
        """
        T_camera_marker = _pose_stamped_to_T(msg)
        T_map_marker = self._T_map_marker()

        # camera expressed in map frame
        T_map_camera = T_map_marker @ np.linalg.inv(T_camera_marker)

        # Barebones assumption: glasses IMU ≈ RGB camera centre.
        # For a more accurate result add T_camera_glasses extrinsics here:
        #   T_map_glasses = T_map_camera @ T_camera_glasses
        T_map_glasses_aruco = T_map_camera

        if self._last_vio_T is not None:
            # Re-anchor: align the VIO frame so the current VIO pose maps
            # onto the ArUco-derived pose in the SLAM map frame.
            self._T_correction = T_map_glasses_aruco @ np.linalg.inv(self._last_vio_T)
            offset = self._T_correction[:3, 3]
            self.get_logger().info(
                f"ArUco correction updated. "
                f"Translation offset [x={offset[0]:.3f} y={offset[1]:.3f} z={offset[2]:.3f}] m"
            )
        else:
            # No VIO data yet — store ArUco fix directly as the correction.
            # VIO is treated as starting from identity, so T_correction = T_map_glasses.
            self._T_correction = T_map_glasses_aruco
            self.get_logger().info(
                "ArUco: first fix received before any VIO — stored directly."
            )

        # Freeze at the corrected ArUco pose (highest accuracy anchor)
        self._last_fused_T = T_map_glasses_aruco

    def _on_vio_pose(self, msg: PoseStamped) -> None:
        """
        Apply accumulated correction and publish the fused pose.

        Behaviour:
          - Stationary  → publish the frozen pose (ZUPT, no drift)
          - Moving, correction known  → T_fused = T_correction @ T_vio
          - Moving, no correction yet → pass VIO through unchanged
        """
        T_vio = _pose_stamped_to_T(msg)
        self._last_vio_T = T_vio  # always track, needed by _on_aruco_pose

        if self._is_stationary and self._last_fused_T is not None:
            # Hold position — do not let drifting VIO move the output
            T_fused = self._last_fused_T
        elif self._T_correction is not None:
            T_fused = self._T_correction @ T_vio
            self._last_fused_T = T_fused
        else:
            # No ArUco fix yet — publish raw VIO (in VIO world frame)
            T_fused = T_vio
            self._last_fused_T = T_vio

        fused_msg = _T_to_pose_stamped(T_fused, "map", msg.header.stamp)
        self._fused_pub.publish(fused_msg)


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
