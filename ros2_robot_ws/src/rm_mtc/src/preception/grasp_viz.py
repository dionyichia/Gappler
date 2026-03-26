"""
Grasp candidate visualizer.
Subscribes to /grasp_candidates and publishes a MarkerArray to RViz.
Each candidate is shown as an arrow (direction = grasp approach vector)
with color scaled by score (green = high, red = low).
Run in any ROS2 env (does not need conda).
"""

import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray
from rm_ros_interfaces.msg import GraspCandidateArray


class GraspVisualizer(Node):
    def __init__(self):
        super().__init__("grasp_visualizer")

        self.sub = self.create_subscription(
            GraspCandidateArray, "/grasp_candidates", self.callback, 10
        )

        self.pub = self.create_publisher(MarkerArray, "/grasp_candidate_markers", 10)

        self.get_logger().info("Grasp visualizer ready")

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
            # ---- Arrow marker: shows grasp position and approach direction ----
            arrow = Marker()
            arrow.header = msg.header
            arrow.ns = "grasp_candidates"
            arrow.id = i
            arrow.type = Marker.ARROW
            arrow.action = Marker.ADD
            arrow.pose = grasp.pose
            arrow.scale.x = 0.05  # arrow length
            arrow.scale.y = 0.008  # arrow shaft diameter
            arrow.scale.z = 0.012  # arrow head diameter
            arrow.lifetime.sec = 1  # auto-expire after 1s

            # Color: green (high score) → red (low score)
            t = (grasp.score - min_s) / (max_s - min_s)
            arrow.color.r = float(1.0 - t)
            arrow.color.g = float(t)
            arrow.color.b = 0.0
            arrow.color.a = 0.9

            marker_array.markers.append(arrow)

            # ---- Text marker: shows score value above arrow ----
            text = Marker()
            text.header = msg.header
            text.ns = "grasp_scores"
            text.id = i + 100
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose = grasp.pose
            text.pose.position.z += 0.04  # offset above arrow
            text.scale.z = 0.02
            text.color.r = 1.0
            text.color.g = 1.0
            text.color.b = 1.0
            text.color.a = 0.9
            text.text = f"{grasp.score:.3f}"
            text.lifetime.sec = 1

            marker_array.markers.append(text)

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
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
