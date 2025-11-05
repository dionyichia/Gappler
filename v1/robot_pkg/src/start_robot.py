import argparse
import os
from real_sense_reader import RealSenseReader
import shutil
import time
from ultralytics import YOLO
import zmq

from robot_functions import Robot
from tool_service import ToolService
from common import TerminalRawMode, exit_keypress
from camera_calibration.calibration import run_calibration
from intel_publisher import zmq_publish_image, show_webcams


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--calibrate",
        default=False,
        action="store_true",
        help="Run the calibration for the camera and robot. Do once a month",
    )
    parser.add_argument(
        "--stream",
        default=False,
        action="store_true",
        help="Streams the Output of the camera in order to adjust the robot starting pose",
    )
    return parser.parse_args()


def main():
    srcpath = os.path.dirname(os.path.abspath(__file__))
    filepath = srcpath[:-4]  # Adjust path to project root

    args = parse_args()
    if args.calibrate:
        print("Robot started in calibration mode: Starting calibration now!")
        run_calibration()

        # delete old T_cam2gripper file, move new file into foundation_pose folder
        old_path = os.path.join(srcpath, 'T_cam2gripper.npy')
        new_path = os.path.join(srcpath, 'foundation_pose/T_cam2gripper.npy')
        if os.path.exists(new_path):
            os.remove(new_path)
        if os.path.exists(old_path):
            shutil.move(old_path, new_path)
        exit()

    webcam = RealSenseReader()
    print("real sense reader done")
    maskModel = YOLO(os.path.join(srcpath, 'best.pt'))
    print("mask model loaded")

    if args.stream:        
        print("Robot started in streaming mode: Starting streaming now!")
        show_webcams(webcam, maskModel)
        exit()

    robot = Robot(webcam, maskModel)
    tool_service = ToolService(robot)
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind("tcp://*:5559")
    n = 0


    while not exit_keypress():
        zmq_publish_image(context, webcam, maskModel)
        print("listening for tools to use...")

        # Wait for request from Aria PC
        tool_call = socket.recv_json()
        print(f"Received tool call: {tool_call}")

        if tool_call is not None:
            success = tool_service.parse_and_execute_response(tool_call)
            print(f"Grab success: {success}")
            socket.send_json(success)
        else:
            print("Incorrect coordinates received")
        n += 1
    
    print("All tasks done, closing ZMQ socket and context")
    socket.close()
    context.term()
    time.wait(10)

              

if __name__ == "__main__":
    with TerminalRawMode():
        main()
