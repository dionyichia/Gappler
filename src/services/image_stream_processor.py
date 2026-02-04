import logging
import os
import threading
import time
from enum import Enum
from pathlib import Path

import aria.sdk as aria
import cv2

cv2.setNumThreads(1)
import numpy as np
import zmq

import config
import services.eye_tracking
from aria_device import AriaStreamClient, ImageObserver
from config import ImageStreamProcessorConfig, ZMQConfig
from utils import CSVWriter, DirectoryManager, quit_keypress

logger = logging.getLogger(__name__)


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

    def start_listening(self) -> None:
        """Start listening thread for control commands."""
        thread = threading.Thread(target=self._listen_loop, daemon=True)
        thread.start()

    def _listen_loop(self) -> None:
        """Main listening loop for ZMQ commands."""
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(ZMQConfig.PORT)
        socket.setsockopt_string(zmq.SUBSCRIBE, ZMQConfig.TOPIC)
        print(f"ZMQ socket connected to {ZMQConfig.PORT} for commands")

        try:
            while not self.saving_state == SavingState.END:
                _, command = socket.recv_string().split(" ", 1)
                self._handle_command(command)
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


def setup_directories(save_path: str) -> None:
    directories = [
        os.path.join(save_path, "rgbcam"),
        os.path.join(save_path, "eyetrack"),
        os.path.join(save_path, "images"),
        os.path.join(save_path, "undistorted_imgs"),
        os.path.join(save_path, "eyetracking"),
    ]

    for directory in directories:
        DirectoryManager.create_or_reset(directory)


def stream_image(
    project_root: Path,
    shared_data: dict,
) -> None:
    # Setup directories and CSV writer
    save_path = os.path.join(project_root, "output")
    setup_directories(save_path)

    aria_stream_client = None
    aria_window = "Meta Aria image"

    try:
        csv_writer = CSVWriter(
            os.path.join(save_path, "eyetracking", "general_eye_gaze.csv"),
            ImageStreamProcessorConfig.EYE_GAZE_CSV_HEADERS,
        )

        # 1. Initialize eye-tracking inference model
        inference_model = services.eye_tracking.initialize_eye_tracking_model(
            config.DEVICE
        )

        # 2. Setup Aria data streaming
        aria_stream_client = AriaStreamClient()
        aria_stream_client.__enter__()

        data_channels = [aria.StreamingDataType.Rgb, aria.StreamingDataType.EyeTrack]
        message_size = 1  # 1 is usually sufficient for real-time applications
        observer: ImageObserver = aria_stream_client.subscribe(
            data_channels,
            ImageObserver(
                source_calibration=shared_data["aria_rgb_calibration"],
                save_path=save_path,
            ),
            message_size,
        )

        # 3. Listening thread for ZMQ control msg
        command_listener = CommandListener()
        command_listener.start_listening()

        # 4. Setup OpenCV window
        cv2.namedWindow(aria_window, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(aria_window, 1024, 1024)
        cv2.setWindowProperty(aria_window, cv2.WND_PROP_TOPMOST, 1)
        cv2.moveWindow(aria_window, 50, 50)

        # 5. Visualize data stream
        while not quit_keypress():
            print("Here")
            try:
                value_mapping, eye_gaze_inference_result = (
                    services.eye_tracking.real_time_eyetracking(
                        inference_model,
                        observer.images,
                        aria.CameraId.EyeTrack,
                        observer.timestamp_ms,
                    )
                )

                gaze_point, image_with_gaze = (
                    services.eye_tracking.eye_tracking_visualization(
                        device_calibration=shared_data["aria_device_calibration"],
                        camera_calibration=shared_data["aria_rgb_calibration"],
                        images=observer.images,
                        value_mapping=value_mapping,
                    )
                )

                # visualize streaming and save when START command is detected
                if command_listener.saving_state == SavingState.START or True:
                    observer.save_flag = True
                    if image_with_gaze is not None:
                        image_with_gaze = np.array(image_with_gaze)
                        rotated_image = np.rot90(image_with_gaze, -1)
                        color_img = cv2.cvtColor(rotated_image, cv2.COLOR_RGB2BGR)
                        cv2.imshow(aria_window, color_img)

                        gaze_point_rotated = np.array(
                            [
                                image_with_gaze.shape[0] - gaze_point[1] - 1,
                                gaze_point[0],
                            ]
                        )
                        eye_gaze_inference_result.extend(gaze_point_rotated.tolist())
                        csv_writer.write_row(eye_gaze_inference_result)

                elif command_listener.saving_state == SavingState.END:
                    print("Stop listening to image data")
                    break

            except Exception as e:
                print(f"Error processing frame: {e}")
                continue

    except KeyboardInterrupt:
        print("\nStreaming interrupted by user")
    except Exception as e:
        print(f"Error during streaming: {e}")
        raise
    finally:
        print("Cleaning up resources...")

        try:
            cv2.destroyAllWindows()
        except Exception as e:
            print(f"Error closing OpenCV windows: {e}")

        if aria_stream_client is not None:
            try:
                aria_stream_client.__exit__(None, None, None)
            except Exception as e:
                print(f"Error closing Aria stream: {e}")

        print("Streaming terminated, resources cleaned up")
