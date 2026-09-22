#!/usr/bin/env python3
"""
object_approach_node.py
-----------------------
Bridges the SAM3 object detection output (Aria-side pipeline) to Nav2.

Subscribes to /manipulation/goal_pose (PoseStamped) — published by the
object_recognition_pipeline. The pipeline back-projects the SAM3 centroid to 3D,
transforms it to base_link frame, and publishes it here.
TF handles the transform from base_link → map frame.

On each received pose:
  1. Transforms the object position from the source frame → map frame via TF.
  2. Publishes a Marker to /object_marker so the object appears in RViz.
  3. Checks the distance from the camera (front of robot) to the object.
     Camera/LiDAR is 0.18 m forward of base_link. Arm base is 0.48 m above base_link.
  4. If distance > 0.6 m, computes an approach goal that places the camera
     within 0.6 m of the object (robot facing the object) and publishes it
     to /goal_pose for Nav2.
  5. If already within 0.6 m, publishes Bool(True) to /manipulation/start so
     the manipulation pipeline can proceed.

Topics
------
  Subscribed:
    /manipulation/goal_pose (geometry_msgs/PoseStamped)  — 3D object centroid in base_link frame
    /goal_reached         (std_msgs/String)            — resets guard on new cycle

  Published:
    /goal_pose            (geometry_msgs/PoseStamped)  — approach nav goal for Nav2
    /object_marker        (visualization_msgs/Marker)  — orange sphere on RViz map
    /object_map_pose      (geometry_msgs/PointStamped) — object coords in map frame
    /manipulation/start   (std_msgs/Bool)              — fired when robot is in position

Manual testing (bypass SAM3):
  ros2 topic pub --once /manipulation/goal_pose geometry_msgs/msg/PoseStamped \
    '{header: {frame_id: "base_link"}, pose: {position: {x: 0.5, y: 0.0, z: 0.5}, orientation: {w: 1.0}}}'
"""
import math

import rclpy
from geometry_msgs.msg import PointStamped, PoseStamped
from rclpy.node import Node
from rclpy.time import Time
from scipy.spatial.transform import Rotation
from std_msgs.msg import Bool, Empty, String
from tf2_geometry_msgs import do_transform_pose_stamped
from tf2_ros import Buffer, TransformListener
from visualization_msgs.msg import Marker

# Forward offset of the camera/LiDAR from robot_base_link — used only for
# computing the Nav2 approach goal (how far in front of the robot to stop).
CAMERA_X_OFFSET = 0.18  # metres
# Target clearance: camera must be within this distance of the object
APPROACH_DISTANCE = 0.6  # metres


class ObjectApproachNode(Node):
    def __init__(self):
        super().__init__("object_approach_node")

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._last_object_map: PointStamped | None = None
        self._approach_done: bool = False  # guard: navigate once per detection
        self._object_name: str = "object"  # updated from /aria/audio/prompt
        self._tracking_robot: bool = False  # True after grasp, marker follows robot

        # Topic  : /manipulation/goal_pose  (confirmed — object_recognition_pipeline.py)
        # Type   : PoseStamped             (confirmed — publisher uses PoseStamped)
        # frame  : base_link               (confirmed — pipeline transforms to base_link before publishing)
        # QoS    : depth=10 RELIABLE       (confirmed — matches pipeline publisher)
        self.create_subscription(
            PoseStamped, "/manipulation/goal_pose", self._on_object_pose, 10
        )
        self.create_subscription(
            String, "/goal_reached", self._on_goal_reached, 10
        )
        self.create_subscription(
            String, "/aria/audio/prompt", self._on_audio_prompt, 10
        )
        self.create_subscription(
            Empty, "/manipulation/done", self._on_manipulation_done, 10
        )
        self.create_subscription(
            Bool, "/manipulator/release", self._on_release, 10
        )

        self._goal_pub = self.create_publisher(PoseStamped, "/goal_pose", 10)
        self._marker_pub = self.create_publisher(Marker, "/object_marker", 10)
        self._map_pose_pub = self.create_publisher(
            PointStamped, "/object_map_pose", 10
        )
        # Signal to manipulation team: receiving this means "robot is in position,
        # start grasping".
        self._manipulation_start_pub = self.create_publisher(
            Bool, "/manipulation/start", 10
        )

        # Timer: republishes marker at robot position while tracking after grasp
        self.create_timer(0.2, self._tracking_timer)

        self.get_logger().info(
            "ObjectApproachNode ready. Waiting for /manipulation/goal_pose... "
            "Manual test: ros2 topic pub --once /manipulation/goal_pose "
            "geometry_msgs/msg/PoseStamped "
            "'{header: {frame_id: \"base_link\"}, pose: {position: {x: 0.5, y: 0.0, z: 0.5}, orientation: {w: 1.0}}}'"
        )

    # ── callbacks ─────────────────────────────────────────────────────────────

    def _on_audio_prompt(self, msg: String) -> None:
        """Track the current object name for use in the RViz label."""
        name = msg.data.strip()
        if name and name.lower() != "end":
            self._object_name = name

    def _on_manipulation_done(self, _: Empty) -> None:
        """Grasp complete — marker should now follow the robot back to the user."""
        self.get_logger().info("Manipulation done. Marker now tracks robot position.")
        self._tracking_robot = True

    def _on_release(self, msg: Bool) -> None:
        """Object released — delete the marker and stop tracking."""
        if not msg.data:
            return
        self.get_logger().info("Release triggered. Removing object marker.")
        self._tracking_robot = False
        self._last_object_map = None
        self._delete_marker()

    def _tracking_timer(self) -> None:
        """Republish marker at robot_base_link position in map while tracking."""
        if not self._tracking_robot:
            return
        try:
            t = self._tf_buffer.lookup_transform("map", "robot_base_link", Time())
        except Exception:
            return
        x = t.transform.translation.x
        y = t.transform.translation.y
        z = t.transform.translation.z + 0.48  # arm height above base
        self._publish_marker(x, y, z)

    def _on_goal_reached(self, msg: String) -> None:
        """After approach nav completes, fire /manipulation/start if we have the object."""
        if msg.data.strip().lower() != "success":
            return
        self._approach_done = False
        # If we already know where the object is, we're now in position — signal the arm
        if self._last_object_map is not None:
            self.get_logger().info(
                "Approach complete. Publishing /manipulation/start."
            )
            self._manipulation_start_pub.publish(Bool(data=True))
            self._approach_done = True  # prevent re-triggering until next object

    def _on_object_pose(self, msg: PoseStamped) -> None:
        if self._approach_done:
            return

        # ── Step 1: transform object from arm base_link → map frame ──────────
        # The static TF robot_base_link → base_link bridges the two trees so
        # TF can resolve base_link → map in one lookup.
        try:
            transform = self._tf_buffer.lookup_transform(
                "map", msg.header.frame_id, Time()
            )
        except Exception as e:
            self.get_logger().warn(
                f"TF lookup failed ({msg.header.frame_id} → map): {e}"
            )
            return

        pose_in_map: PoseStamped = do_transform_pose_stamped(msg, transform)
        object_in_map = PointStamped()
        object_in_map.header = pose_in_map.header
        object_in_map.point = pose_in_map.pose.position
        self._last_object_map = object_in_map
        ox, oy = pose_in_map.pose.position.x, pose_in_map.pose.position.y

        # ── Step 2: publish map-frame coords + RViz marker ────────────────────
        self._map_pose_pub.publish(object_in_map)
        self._publish_marker(ox, oy, pose_in_map.pose.position.z)
        self.get_logger().info(f"Object in map frame: x={ox:.3f} y={oy:.3f}")

        # ── Step 3: get robot position in map frame ───────────────────────────
        try:
            robot_transform = self._tf_buffer.lookup_transform(
                "map", "robot_base_link", Time()
            )
        except Exception as e:
            self.get_logger().warn(f"TF lookup failed (robot_base_link → map): {e}")
            return

        rx = robot_transform.transform.translation.x
        ry = robot_transform.transform.translation.y
        robot_yaw = Rotation.from_quat([
            robot_transform.transform.rotation.x,
            robot_transform.transform.rotation.y,
            robot_transform.transform.rotation.z,
            robot_transform.transform.rotation.w,
        ]).as_euler("xyz")[2]

        # Camera is CAMERA_X_OFFSET metres ahead of base_link along the robot yaw
        cam_x = rx + math.cos(robot_yaw) * CAMERA_X_OFFSET
        cam_y = ry + math.sin(robot_yaw) * CAMERA_X_OFFSET
        distance = math.hypot(ox - cam_x, oy - cam_y)
        self.get_logger().info(f"Camera-to-object distance: {distance:.3f} m")

        # ── Step 5: navigate if too far, else signal in-range ─────────────────
        if distance <= APPROACH_DISTANCE:
            self.get_logger().info(
                "Object within 0.6 m. Publishing /manipulation/start."
            )
            self._approach_done = True
            self._manipulation_start_pub.publish(Bool(data=True))
            return

        # Goal: put the camera APPROACH_DISTANCE in front of the object.
        # Approach from the robot's current side so it doesn't overshoot.
        angle_to_robot = math.atan2(cam_y - oy, cam_x - ox)
        goal_x = ox + math.cos(angle_to_robot) * (APPROACH_DISTANCE + CAMERA_X_OFFSET)
        goal_y = oy + math.sin(angle_to_robot) * (APPROACH_DISTANCE + CAMERA_X_OFFSET)

        # Robot faces toward the object
        facing_angle = math.atan2(oy - goal_y, ox - goal_x)
        q = Rotation.from_euler("z", facing_angle).as_quat()

        goal = PoseStamped()
        goal.header.frame_id = "map"
        goal.header.stamp = self.get_clock().now().to_msg()
        goal.pose.position.x = goal_x
        goal.pose.position.y = goal_y
        goal.pose.position.z = 0.0
        goal.pose.orientation.x = float(q[0])
        goal.pose.orientation.y = float(q[1])
        goal.pose.orientation.z = float(q[2])
        goal.pose.orientation.w = float(q[3])

        self._goal_pub.publish(goal)
        self._approach_done = True
        self.get_logger().info(
            f"Approaching object. Nav goal: x={goal_x:.3f} y={goal_y:.3f} "
            f"(was {distance:.3f} m away)"
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _publish_marker(self, x: float, y: float, z: float) -> None:
        now = self.get_clock().now().to_msg()

        # Orange sphere at object location
        sphere = Marker()
        sphere.header.frame_id = "map"
        sphere.header.stamp = now
        sphere.ns = "detected_object"
        sphere.id = 0
        sphere.type = Marker.SPHERE
        sphere.action = Marker.ADD
        sphere.pose.position.x = x
        sphere.pose.position.y = y
        sphere.pose.position.z = z
        sphere.pose.orientation.w = 1.0
        sphere.scale.x = 0.15
        sphere.scale.y = 0.15
        sphere.scale.z = 0.15
        sphere.color.r = 1.0
        sphere.color.g = 0.5
        sphere.color.b = 0.0
        sphere.color.a = 1.0
        self._marker_pub.publish(sphere)

        # Text label floating above the sphere
        label = Marker()
        label.header.frame_id = "map"
        label.header.stamp = now
        label.ns = "detected_object"
        label.id = 1
        label.type = Marker.TEXT_VIEW_FACING
        label.action = Marker.ADD
        label.pose.position.x = x
        label.pose.position.y = y
        label.pose.position.z = z + 0.25  # float above the sphere
        label.pose.orientation.w = 1.0
        label.scale.z = 0.15  # text height
        label.color.r = 1.0
        label.color.g = 1.0
        label.color.b = 1.0
        label.color.a = 1.0
        label.text = self._object_name.capitalize()
        self._marker_pub.publish(label)

    def _delete_marker(self) -> None:
        for mid in (0, 1):
            m = Marker()
            m.header.frame_id = "map"
            m.header.stamp = self.get_clock().now().to_msg()
            m.ns = "detected_object"
            m.id = mid
            m.action = Marker.DELETE
            self._marker_pub.publish(m)


def main() -> None:
    rclpy.init()
    node = ObjectApproachNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
