"""
Grasp candidate visualizer.
Subscribes to /grasp_candidates and publishes a MarkerArray to RViz.
Each candidate is visualized as:
  - Approach arrow (blue, length scaled by depth)
  - Width bar (green, length = gripper width, perpendicular to approach)
  - Score text label

Run in any ROS2 env (does not need conda).
Launch with: ros2 run rm_mtc grasp_viz
RViz config loaded automatically from perception/rviz_config.rviz
"""

import os
import subprocess

import numpy as np
import psutil
import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node
from rm_ros_interfaces.msg import GraspCandidateArray
from visualization_msgs.msg import Marker, MarkerArray

RVIZ_CONFIG = os.path.join(os.path.dirname(__file__), "rviz_config.rviz")


class GraspVisualizer(Node):
    def __init__(self):
        super().__init__("grasp_visualizer")

        self.sub = self.create_subscription(
            GraspCandidateArray, "/grasp_candidates", self.callback, 10
        )

        self.pub = self.create_publisher(MarkerArray, "/grasp_candidate_markers", 10)

        rviz_running = any("rviz2" in p.name() for p in psutil.process_iter())
        if not rviz_running:
            self.rviz_proc = subprocess.Popen(["rviz2", "-d", RVIZ_CONFIG])
        else:
            self.get_logger().info("RViz already running, skipping launch")

        self.get_logger().info("Grasp visualizer ready")

    def _make_marker(
        self, msg, ns, id_, type_, pose, scale, color, text="", lifetime=1
    ):
        m = Marker()
        m.header = msg.header
        m.ns = ns
        m.id = id_
        m.type = type_
        m.action = Marker.ADD
        m.pose = pose
        m.scale.x, m.scale.y, m.scale.z = scale
        m.color.r, m.color.g, m.color.b, m.color.a = color
        m.lifetime.sec = lifetime
        if text:
            m.text = text
        return m

    def callback(self, msg: GraspCandidateArray):
        marker_array = MarkerArray()

        # Clear previous markers
        clear = Marker()
        clear.action = Marker.DELETEALL
        marker_array.markers.append(clear)

        if not msg.grasps:
            self.pub.publish(marker_array)
            return

        scores = [g.score for g in msg.grasps]
        min_s = min(scores)
        max_s = max(scores) if max(scores) != min_s else min_s + 1e-6

        for i, grasp in enumerate(msg.grasps):
            t = (grasp.score - min_s) / (max_s - min_s)

            # ---- Approach arrow: blue, length = depth ----
            approach = self._make_marker(
                msg,
                ns="approach",
                id_=i,
                type_=Marker.ARROW,
                pose=grasp.pose,
                scale=(float(grasp.depth), 0.008, 0.012),
                color=(0.0, float(t), 1.0, 0.9),
            )
            marker_array.markers.append(approach)

            # ---- Width bar: perpendicular line in grasp x-axis ----
            # Compute endpoints in the grasp frame x-axis (gripper opening direction)
            q = grasp.pose.orientation
            # Rotate [1,0,0] by quaternion to get gripper x-axis in world frame
            # Using quaternion rotation: v' = q * v * q^-1
            qx, qy, qz, qw = q.x, q.y, q.z, q.w
            # x-axis of grasp frame expressed in camera frame
            gx = np.array(
                [
                    1 - 2 * (qy**2 + qz**2),
                    2 * (qx * qy + qw * qz),
                    2 * (qx * qz - qw * qy),
                ]
            )
            half_w = float(grasp.width) / 2.0
            cx = grasp.pose.position.x
            cy = grasp.pose.position.y
            cz = grasp.pose.position.z

            p1, p2 = Point(), Point()
            p1.x = cx - half_w * gx[0]
            p1.y = cy - half_w * gx[1]
            p1.z = cz - half_w * gx[2]
            p2.x = cx + half_w * gx[0]
            p2.y = cy + half_w * gx[1]
            p2.z = cz + half_w * gx[2]

            width_bar = Marker()
            width_bar.header = msg.header
            width_bar.ns = "width"
            width_bar.id = i
            width_bar.type = Marker.LINE_STRIP
            width_bar.action = Marker.ADD
            width_bar.scale.x = 0.005  # line width
            width_bar.color.r = 0.0
            width_bar.color.g = 1.0
            width_bar.color.b = 0.0
            width_bar.color.a = 0.9
            width_bar.points = [p1, p2]
            width_bar.lifetime.sec = 1
            marker_array.markers.append(width_bar)

            # ---- Score text ----
            text_pose = grasp.pose
            text_pose.position.z += 0.04
            score_text = self._make_marker(
                msg,
                ns="scores",
                id_=i,
                type_=Marker.TEXT_VIEW_FACING,
                pose=text_pose,
                scale=(0.0, 0.0, 0.02),
                color=(1.0, 1.0, 1.0, 0.9),
                text=f"s:{grasp.score:.2f} w:{grasp.width:.3f} d:{grasp.depth:.3f}",
            )
            marker_array.markers.append(score_text)

        self.pub.publish(marker_array)
        self.get_logger().debug(f"Published {len(msg.grasps)} grasp markers")


def main():
    rclpy.init()
    node = GraspVisualizer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if hasattr(node, "rviz_proc"):
            node.rviz_proc.terminate()
        node.destroy_node()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
