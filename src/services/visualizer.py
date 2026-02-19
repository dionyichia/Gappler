import threading
import time
from enum import Enum

import cv2
import numpy as np
import zmq

from config import ZMQConfig

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


aria_window = "Meta Aria image"

# 3. Listening thread for ZMQ control msg
command_listener = CommandListener()
command_listener.start_listening()

cv2.namedWindow(aria_window, cv2.WINDOW_NORMAL)
cv2.resizeWindow(aria_window, 1024, 1024)
cv2.setWindowProperty(aria_window, cv2.WND_PROP_TOPMOST, 1)
cv2.moveWindow(aria_window, 50, 50)
# if image_with_gaze is not None:
#     image_with_gaze = np.array(image_with_gaze)
#     rotated_image = np.rot90(image_with_gaze, -1)
#     color_img = cv2.cvtColor(rotated_image, cv2.COLOR_RGB2BGR)
#     cv2.imshow(aria_window, color_img)

#     gaze_point_rotated = np.array(
#         [
#             image_with_gaze.shape[0] - gaze_point[1] - 1,
#             gaze_point[0],
#         ]
#     )
#     eye_gaze_inference_result.extend(gaze_point_rotated.tolist())
#     csv_writer.write_row(eye_gaze_inference_result)

#     print("Cleaning up resources...")

#     try:
#         cv2.destroyAllWindows()
#     except Exception as e:
#         print(f"Error closing OpenCV windows: {e}")
