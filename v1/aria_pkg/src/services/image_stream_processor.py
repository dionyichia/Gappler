from pathlib import Path
from enum import Enum

import aria.sdk as aria
import cv2
import numpy as np
import os
import threading
import time
import zmq

from aria_device import AriaStreamClient, ImageObserver
from utils import DirectoryManager, quit_keypress, CSVWriter
from config import ImageStreamProcessorConfig, ZMQConfig
import services.eye_tracking

ZMQ_PORT = "tcp://localhost:5556"
ZMQ_TOPIC = "command"
STATUS_PRINT_INTERVAL = 2  # seconds


class SavingState(Enum):
    WAIT = 0
    START = 1
    END = 2


class CommandListener:
    """Listens for control commands via ZMQ."""

    def __init__(self):
        self.saving_state = SavingState.WAIT
        self._last_print_time = 0
        self._running = False

    def start_listening(self) -> None:
        """Start listening thread for control commands."""
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()

    def _listen_loop(self) -> None:
        """Main listening loop for ZMQ commands."""
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(ZMQ_PORT)
        socket.setsockopt_string(zmq.SUBSCRIBE, ZMQ_TOPIC)
        print(f"ZMQ socket connected to {ZMQ_PORT} for commands")

        self._running = True
        try:
            while self._running:
                _, command = socket.recv_string().split(" ", 1)
                self._handle_command(command)

                if self.saving_state == SavingState.END:
                    break
        finally:
            socket.close()

    def _handle_command(self, command: str) -> None:
        """Process received command."""
        current_time = time.time()

        if command == "WAIT":
            self.saving_state = SavingState.WAIT
            if current_time - self._last_print_time >= STATUS_PRINT_INTERVAL:
                print("Subscriber running, waiting for start command")
                self._last_print_time = current_time

        elif command == "START" and self.saving_state == SavingState.WAIT:
            self.saving_state = SavingState.START
            print("Start detected, saving data now")

        elif command == "END" and self.saving_state == SavingState.START:
            self.saving_state = SavingState.END
            print("Finish detected, stopping data saving")

        else:
            print(f"Error: Invalid command '{command}' received")


def stream_image(project_root: Path) -> None:
    # Setup directories and CSV writer
    save_path = os.path.join(project_root, "data")

    directories = [
        os.path.join(save_path, "rgbcam"),
        os.path.join(save_path, "eyetrack"),
        os.path.join(save_path, "images"),
        os.path.join(save_path, "undistorted_imgs"),
        os.path.join(save_path, "eyetracking"),
    ]

    for directory in directories:
        DirectoryManager.create_or_reset(directory)

    csv_writer = CSVWriter(
        os.path.join(save_path, "eyetracking", "general_eye_gaze.csv"),
        ImageStreamProcessorConfig.EYE_GAZE_CSV_HEADERS,
    )

    # 1. Initialize eye-tracking inference model
    system = services.eye_tracking.initialize_eye_tracking("cuda")

    # 2. Setup Aria data streaming
    with AriaStreamClient() as aria_stream_client:
        data_channels = [aria.StreamingDataType.Rgb, aria.StreamingDataType.EyeTrack]
        message_size = 1  # 1 is usually sufficient for real-time applications
        observer = aria_stream_client.subscribe(
            data_channels,
            ImageObserver(
                system.rgb_camera_calibration,
                system.rgb_linear_camera_calibration,
                save_path,
                ImageStreamProcessorConfig.CAMERA_ID_MAP,
            ),
            message_size,
        )

        # 3. Listening thread for ZMQ control msg
        command_listener = CommandListener()
        command_listener.start_listening()

        # 4. Setup OpenCV window
        aria_window = "Meta Aria image"
        cv2.namedWindow(aria_window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(aria_window, 1024, 1024)
        cv2.setWindowProperty(aria_window, cv2.WND_PROP_TOPMOST, 1)
        cv2.moveWindow(aria_window, 50, 50)

        # 5. Visualize data stream
        while not quit_keypress():
            value_mapping, eye_gaze_inference_result = (
                services.eye_tracking.real_time_eyetracking(
                    system.inference_model,
                    observer.images,
                    aria.CameraId.EyeTrack,
                    observer.timestamp,
                )
            )
            gaze_point, image_with_gaze = (
                services.eye_tracking.eye_tracking_visualization(
                    system.device_calibration,
                    system.rgb_camera_calibration,
                    system.rgb_stream_label,
                    aria.CameraId.Rgb,
                    observer.images,
                    value_mapping,
                )
            )  # , T_device_CPF)

            # visualize streaming and save when START command is detected
            if command_listener.saving_state == SavingState.START:
                observer.save_flag = True
                if image_with_gaze is not None:
                    image_with_gaze = np.array(image_with_gaze)
                    rotated_image = np.rot90(image_with_gaze, -1)
                    color_img = cv2.cvtColor(rotated_image, cv2.COLOR_RGB2BGR)
                    cv2.imshow(aria_window, color_img)
                    gaze_point_rotated = np.array(
                        [image_with_gaze.shape[0] - gaze_point[1] - 1, gaze_point[0]]
                    )
                    eye_gaze_inference_result.extend(
                        gaze_point_rotated.tolist()
                    )  # extend with coordinates of ET
                    csv_writer.write_row(
                        eye_gaze_inference_result,
                    )
            elif command_listener.saving_state == SavingState.END:
                print("Stop listening to image data")
                break

        # 6. free resources
        cv2.destroyAllWindows()
        print("Streaming terminated, resources cleaned up")
