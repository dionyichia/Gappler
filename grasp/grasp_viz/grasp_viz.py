"""
Grasp candidate visualizer.
Subscribes to /grasp_candidates and publishes a MarkerArray to RViz.

Each candidate is visualized as a gripper geometry in base_link frame:
  - Palm cylinder (approach axis)
  - Left finger bar
  - Right finger bar

Poses are transformed from camera_color_optical_frame → base_link.

Run in any ROS2 env (does not need conda).
"""

import numpy as np
import rclpy
from geometry_msgs.msg import Point, PointStamped
from rclpy.node import Node
from grasp_interfaces.msg import GraspCandidateArray
from sensor_msgs.msg import Image
from std_msgs.msg import String
from tf2_geometry_msgs import do_transform_pose
from tf2_ros import Buffer, TransformListener
from visualization_msgs.msg import Marker, MarkerArray

# Gripper geometry constants (metres)
PALM_LENGTH = 0.04  # cylinder along approach axis
PALM_RADIUS = 0.006
FINGER_LENGTH = 0.04  # finger bar length along approach axis
FINGER_RADIUS = 0.005
FINGER_OFFSET = 0.01  # finger offset along approach axis from palm centre


class GraspVisualizer(Node):
    def __init__(self):
        super().__init__("grasp_visualizer")

        # TF
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Grasp candidates
        self.sub = self.create_subscription(
            GraspCandidateArray, "/grasp_candidates", self.grasp_callback, 10
        )
        self.pub = self.create_publisher(MarkerArray, "/grasp_candidate_markers", 10)

        # SAM mask — republish as rgb8 for RViz Image display
        self.mask_sub = self.create_subscription(
            Image, "/camera/sam/mask", self.mask_callback, 10
        )
        self.mask_pub = self.create_publisher(Image, "/debug/sam_mask", 10)

        # Centroid sphere marker
        self.centroid_sub = self.create_subscription(
            PointStamped, "/object_centroid", self.centroid_callback, 10
        )
        self.centroid_pub = self.create_publisher(Marker, "/debug/centroid_marker", 10)

        # Pipeline state text marker
        self.state_sub = self.create_subscription(
            String, "/pipeline_state", self.state_callback, 10
        )
        self.state_marker_pub = self.create_publisher(Marker, "/debug/state_marker", 10)
        self.current_state = "IDLE"

        self.get_logger().info("Grasp visualizer ready")

    # ------------------------------------------------------------------
    # SAM mask callback
    # ------------------------------------------------------------------
    def mask_callback(self, msg: Image):
        mono = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width)
        rgb = np.stack([mono * 255, mono * 255, mono * 255], axis=-1).astype(np.uint8)
        out = Image()
        out.header = msg.header
        out.height = msg.height
        out.width = msg.width
        out.encoding = "rgb8"
        out.step = msg.width * 3
        out.data = rgb.tobytes()
        self.mask_pub.publish(out)

    # ------------------------------------------------------------------
    # Centroid callback
    # ------------------------------------------------------------------
    def centroid_callback(self, msg: PointStamped):
        m = Marker()
        m.header = msg.header
        m.ns = "centroid"
        m.id = 0
        m.type = Marker.SPHERE
        m.action = Marker.ADD
        m.pose.position = msg.point
        m.pose.orientation.w = 1.0
        m.scale.x = m.scale.y = m.scale.z = 0.03
        m.color.r = 1.0
        m.color.g = 0.0
        m.color.b = 0.0
        m.color.a = 1.0
        m.lifetime.sec = 1
        self.centroid_pub.publish(m)

    # ------------------------------------------------------------------
    # State callback
    # ------------------------------------------------------------------
    def state_callback(self, msg: String):
        self.current_state = msg.data
        m = Marker()
        m.header.frame_id = "base_link"
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns = "state"
        m.id = 0
        m.type = Marker.TEXT_VIEW_FACING
        m.action = Marker.ADD
        m.pose.position.x = 0.0
        m.pose.position.y = 0.0
        m.pose.position.z = 0.8
        m.pose.orientation.w = 1.0
        m.scale.z = 0.1
        m.color.r = m.color.g = m.color.b = m.color.a = 1.0
        m.text = f"State: {msg.data}"
        m.lifetime.sec = 3
        self.state_marker_pub.publish(m)

    # ------------------------------------------------------------------
    # Grasp candidates callback
    # ------------------------------------------------------------------
    def grasp_callback(self, msg: GraspCandidateArray):
        marker_array = MarkerArray()

        clear = Marker()
        clear.action = Marker.DELETEALL
        marker_array.markers.append(clear)

        if not msg.grasps:
            self.pub.publish(marker_array)
            return

        # Lookup transform once for this batch
        try:
            transform = self.tf_buffer.lookup_transform(
                "base_link",
                msg.header.frame_id,
                rclpy.time.Time(),
                timeout=rclpy.duration.Duration(seconds=0.1),
            )
        except Exception as e:
            self.get_logger().warn(f"TF lookup failed: {e}")
            return

        scores = [g.score for g in msg.grasps]
        min_s = min(scores)
        max_s = max(scores) if max(scores) != min_s else min_s + 1e-6

        marker_id = 0
        for i, grasp in enumerate(msg.grasps[:1]):
            # Transform pose to base_link
            pose_base = do_transform_pose(grasp.pose, transform)

            t = (grasp.score - min_s) / (max_s - min_s)
            color = (0.0, float(t), 1.0, 0.9)  # RGBA: blue→cyan by score

            # ---- Palm cylinder (along approach / +Z of grasp frame) ----
            palm = Marker()
            palm.header.frame_id = "base_link"
            palm.header.stamp = self.get_clock().now().to_msg()
            palm.ns = "palm"
            palm.id = marker_id
            marker_id += 1
            palm.type = Marker.CYLINDER
            palm.action = Marker.ADD
            palm.pose = pose_base
            palm.scale.x = PALM_RADIUS * 2
            palm.scale.y = PALM_RADIUS * 2
            palm.scale.z = PALM_LENGTH
            palm.color.r, palm.color.g, palm.color.b, palm.color.a = color
            palm.lifetime.sec = 1
            marker_array.markers.append(palm)

            # ---- Derive rotation matrix from quaternion ----
            q = pose_base.orientation
            qx, qy, qz, qw = q.x, q.y, q.z, q.w

            # X axis of grasp frame (finger width direction)
            gx = np.array(
                [
                    1 - 2 * (qy**2 + qz**2),
                    2 * (qx * qy + qw * qz),
                    2 * (qx * qz - qw * qy),
                ]
            )
            # Z axis of grasp frame (approach direction)
            gz = np.array(
                [
                    2 * (qx * qz + qw * qy),
                    2 * (qy * qz - qw * qx),
                    1 - 2 * (qx**2 + qy**2),
                ]
            )

            cx = pose_base.position.x
            cy = pose_base.position.y
            cz = pose_base.position.z
            half_w = float(grasp.width) / 2.0

            # Finger tips are offset along approach axis from palm centre
            for side, sign in [("left", -1.0), ("right", 1.0)]:
                finger_centre = np.array(
                    [
                        cx + sign * half_w * gx[0] + FINGER_OFFSET * gz[0],
                        cy + sign * half_w * gx[1] + FINGER_OFFSET * gz[1],
                        cz + sign * half_w * gx[2] + FINGER_OFFSET * gz[2],
                    ]
                )

                finger = Marker()
                finger.header.frame_id = "base_link"
                finger.header.stamp = self.get_clock().now().to_msg()
                finger.ns = f"finger_{side}"
                finger.id = marker_id
                marker_id += 1
                finger.type = Marker.CYLINDER
                finger.action = Marker.ADD
                finger.pose.position.x = finger_centre[0]
                finger.pose.position.y = finger_centre[1]
                finger.pose.position.z = finger_centre[2]
                finger.pose.orientation = (
                    pose_base.orientation
                )  # same orientation as palm
                finger.scale.x = FINGER_RADIUS * 2
                finger.scale.y = FINGER_RADIUS * 2
                finger.scale.z = FINGER_LENGTH
                finger.color.r = 0.0
                finger.color.g = 1.0
                finger.color.b = 0.0
                finger.color.a = 0.9
                finger.lifetime.sec = 1
                marker_array.markers.append(finger)

            # ---- Score text ----
            text = Marker()
            text.header.frame_id = "base_link"
            text.header.stamp = self.get_clock().now().to_msg()
            text.ns = "scores"
            text.id = marker_id
            marker_id += 1
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose = pose_base
            text.pose.position.z += 0.04
            text.scale.z = 0.02
            text.color.r = text.color.g = text.color.b = text.color.a = 1.0
            text.text = f"s:{grasp.score:.2f} w:{grasp.width:.3f} d:{grasp.depth:.3f}"
            text.lifetime.sec = 1
            marker_array.markers.append(text)

            # ---- Approach arrow (red, points along +Z of grasp frame) ----
            arrow = Marker()
            arrow.header.frame_id = "base_link"
            arrow.header.stamp = self.get_clock().now().to_msg()
            arrow.ns = "approach"
            arrow.id = marker_id
            marker_id += 1
            arrow.type = Marker.ARROW
            arrow.action = Marker.ADD
            # Arrow defined by two points: tail at palm centre, head along gz
            ARROW_LENGTH = 0.08
            tail = Point(x=cx, y=cy, z=cz)
            head = Point(
                x=cx + ARROW_LENGTH * gz[0],
                y=cy + ARROW_LENGTH * gz[1],
                z=cz + ARROW_LENGTH * gz[2],
            )
            arrow.points = [tail, head]
            arrow.scale.x = 0.008  # shaft diameter
            arrow.scale.y = 0.014  # head diameter
            arrow.scale.z = 0.02  # head length
            arrow.color.r = 1.0
            arrow.color.g = 0.0
            arrow.color.b = 0.0
            arrow.color.a = 1.0
            arrow.lifetime.sec = 1
            marker_array.markers.append(arrow)

        self.pub.publish(marker_array)
        self.get_logger().debug(
            f"Published markers for {len(msg.grasps)} grasps in base_link"
        )


def main():
    rclpy.init()
    node = GraspVisualizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
