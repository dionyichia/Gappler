#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from tf2_ros import Buffer, TransformListener

class PosePublisher(Node):
    def __init__(self):
        super().__init__('pose_publisher')
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.publisher = self.create_publisher(PoseStamped, '/robot_pose', 10)
        self.timer = self.create_timer(0.1, self.publish_pose)

    def publish_pose(self):
        try:
            transform = self.tf_buffer.lookup_transform(
                'map', 'robot_base_link', rclpy.time.Time())
            pose = PoseStamped()
            pose.header.stamp = self.get_clock().now().to_msg()
            pose.header.frame_id = 'map'
            pose.pose.position.x = transform.transform.translation.x
            pose.pose.position.y = transform.transform.translation.y
            pose.pose.orientation = transform.transform.rotation
            self.publisher.publish(pose)
        except Exception as e:
            self.get_logger().warn(f'TF lookup failed (map→robot_base_link): {e}', throttle_duration_sec=5.0)

def main():
    rclpy.init()
    rclpy.spin(PosePublisher())

if __name__ == '__main__':
    main()

