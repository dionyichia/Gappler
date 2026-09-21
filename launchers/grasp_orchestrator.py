#!/usr/bin/env python3
"""
Orchestrator node.

Flow:
  1. Wait for /manipulation/start (std_msgs/Bool, true)
  2. Launch main.py
  3. Wait for /return_to_user/goal_reached (std_msgs/String, "success")
  4. Launch rm_bringup (background.launch.py)
  5. Wait for /aria/audio/prompt (std_msgs/String) containing "release"
  6. Publish open gripper command and terminate
"""

import subprocess
import sys
import time

import rclpy
from gappler_common import ROOT
from rclpy.node import Node
from rm_ros_interfaces.msg import Gripperset
from std_msgs.msg import Bool, String

# Started when the start-grasp message arrives: the camera, arm and grasp nodes.
PIPELINE_DIR = str(ROOT / "launchers")
PIPELINE_PATH = f"{PIPELINE_DIR}/start_grasp_pipeline.py"

processes: list[tuple[str, subprocess.Popen]] = []


def launch(cmd, label, delay=0.0, cwd=None, env=None) -> subprocess.Popen:
    if delay > 0:
        print(f"[orchestrator] Waiting {delay}s before launching {label}...")
        time.sleep(delay)
    print(f"[orchestrator] Launching: {label}")
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd, env=env)
    processes.append((label, p))
    return p


class Orchestrator(Node):
    def __init__(self):
        super().__init__("orchestrator")

        # Internal state
        self._started = False
        self._goal_reached = False
        self._bringup_done = False

        # Open-gripper publisher
        self._gripper_pub = self.create_publisher(
            Gripperset, "/rm_driver/set_gripper_position_cmd", 10
        )

        # Subscriptions
        self._start_sub = self.create_subscription(
            Bool, "/manipulation/start", self._on_start, 10
        )
        # self._goal_sub = self.create_subscription(
        #     String, "/return_to_user/goal_reached", self._on_goal_reached, 10
        # )
        # self._return_sub = self.create_subscription(
        #     Bool, "/manipulator/return_to_user", self._on_return_to_user, 10
        # )
        self._audio_sub = self.create_subscription(
            Bool, "/manipulator/release", self._on_audio, 10
        )

        self.get_logger().info("Launching rm_bringup...")
        launch(
            ["ros2", "launch", "rm_mtc", "background.launch.py"],
            label="rm_bringup",
            delay=0.0,
        )

        self.get_logger().info("Orchestrator ready")

    # ------------------------------------------------------------------
    def _on_start(self, msg: Bool):
        if self._started or not msg.data:
            return
        self._started = True
        self.get_logger().info("Start received — launching main.py")
        launch(["python3", PIPELINE_PATH], label="main", cwd=PIPELINE_DIR)

    # ------------------------------------------------------------------
    # def _on_return_to_user(self, msg: Bool):
    #     if not msg.data:
    #         return
    #     self.get_logger().info("Grasp confirmed — terminating main.py")
    #     for label, p in processes:
    #         if label == "main":
    #             p.terminate()
    #             try:
    #                 p.wait(timeout=5)
    #             except subprocess.TimeoutExpired:
    #                 p.kill()
    #             self.get_logger().info("main.py terminated")
    #             break

    # ------------------------------------------------------------------
    # def _on_goal_reached(self, msg: String):
    #     if self._goal_reached or msg.data.strip().lower() != "success":
    #         return
    #     self._goal_reached = True
    #     self.get_logger().info("Goal reached — launching rm_bringup")
    #     launch(
    #         ["ros2", "launch", "rm_mtc", "background.launch.py"],
    #         label="rm_bringup",
    #         delay=0.0,
    #     )
    #     self._bringup_done = True

    # ------------------------------------------------------------------
    def _on_audio(self, msg: Bool):
        if not msg.data:
            return
        # if "release" not in msg.data.lower():
        #     return

        self.get_logger().info("'release' heard — opening gripper and shutting down")
        self._open_gripper()
        time.sleep(1.5)  # allow topic to deliver before exit
        rclpy.shutdown()

    # ------------------------------------------------------------------
    def _open_gripper(self):
        cmd = Gripperset()
        cmd.position = 1000
        cmd.block = False
        self._gripper_pub.publish(cmd)
        self.get_logger().info("Open-gripper command published")


def main():
    rclpy.init()
    node = Orchestrator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        print("[orchestrator] Terminated")


if __name__ == "__main__":
    main()
