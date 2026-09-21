#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import can
import struct

class EchoPlusDriver(Node):
    def __init__(self):
        super().__init__('echo_plus_driver')
        
        # CAN setup
        try:
            self.bus = can.interface.Bus(channel='can0', bustype='socketcan')
            self.get_logger().info('Connected to CAN bus')
        except Exception as e:
            self.get_logger().error(f'Failed to connect to CAN: {e}')
            return
        
        # Echo Plus parameters (from manual)
        self.device_class = 0x01
        self.device_model = 0x03  # ECHO-PLUS
        self.device_number = 0x01
        
        # ROS2 subscribers
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            'cmd_vel',
            self.cmd_vel_callback,
            10
        )
        
        # ROS2 publishers
        self.status_pub = self.create_publisher(String, 'echo_status', 10)
        
        # Timer to read CAN messages
        self.create_timer(0.1, self.read_can_messages)
        
        # Enable the robot
        self.enable_robot()
        
        self.get_logger().info('Echo Plus driver started')
    
    def enable_robot(self):
        """Send enable command to switch to CAN mode"""
        # Command from manual: 01 03 01 03 with data 01 03 01 01 00 00 00 00
        can_id = (self.device_class << 24) | (self.device_model << 16) | \
                 (self.device_number << 8) | 0x03  # Function 0x03 = enable
        
        data = [0x01, 0x03, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00]
        msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=True)
        
        try:
            self.bus.send(msg)
            self.get_logger().info('Sent enable command')
        except Exception as e:
            self.get_logger().error(f'Failed to send enable: {e}')
    
    def cmd_vel_callback(self, msg):
        """Convert Twist message to CAN command"""
        # This is a placeholder - you'll need to implement the actual
        # velocity command protocol from the XSTD documentation
        # For now, let's send a basic movement command
        
        linear_x = int(msg.linear.x * 1000)  # Convert m/s to mm/s
        angular_z = int(msg.angular.z * 1000)  # Convert rad/s to mrad/s
        
        # Function 0x10 is typically for movement commands
        can_id = (self.device_class << 24) | (self.device_model << 16) | \
                 (self.device_number << 8) | 0x10
        
        # Pack data (this is simplified - check XSTD protocol for exact format)
        data = [
            (linear_x >> 8) & 0xFF,
            linear_x & 0xFF,
            (angular_z >> 8) & 0xFF,
            angular_z & 0xFF,
            0x00, 0x00, 0x00, 0x00
        ]
        
        msg = can.Message(arbitration_id=can_id, data=data, is_extended_id=True)
        
        try:
            self.bus.send(msg)
        except Exception as e:
            self.get_logger().error(f'Failed to send velocity: {e}')
    
    def read_can_messages(self):
        """Read and process CAN messages from Echo Plus"""
        msg = self.bus.recv(timeout=0.01)
        
        if msg:
            # Parse CAN ID
            device_class = (msg.arbitration_id >> 24) & 0xFF
            device_model = (msg.arbitration_id >> 16) & 0xFF
            device_number = (msg.arbitration_id >> 8) & 0xFF
            function = msg.arbitration_id & 0xFF
            
            # Check if it's from our Echo Plus
            if device_class == 0x01 and device_model == 0x03:
                self.get_logger().info(f'Received CAN: ID={hex(msg.arbitration_id)}, Data={msg.data.hex()}')
                
                # Publish status
                status_msg = String()
                status_msg.data = f'CAN ID: {hex(msg.arbitration_id)}, Function: {hex(function)}'
                self.status_pub.publish(status_msg)

def main(args=None):
    rclpy.init(args=args)
    node = EchoPlusDriver()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
