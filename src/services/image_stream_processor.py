import logging
import os
from pathlib import Path
from time import sleep

import aria.sdk as aria

from aria_device import AriaDeviceController, AriaStreamClient, ImageObserver
from config import ImageStreamProcessorConfig
from utils import CSVWriter, DirectoryManager, quit_keypress

logger = logging.getLogger(__name__)


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
) -> None:
    # Setup directories and CSV writer
    save_path = os.path.join(project_root, "output")
    setup_directories(save_path)

    aria_stream_client = None

    try:
        csv_writer = CSVWriter(
            os.path.join(save_path, "eyetracking", "general_eye_gaze.csv"),
            ImageStreamProcessorConfig.EYE_GAZE_CSV_HEADERS,
        )

        aria_stream_client = AriaStreamClient()
        aria_stream_client.__enter__()

        aria_controller = AriaDeviceController.get_instance()
        aria_rgb_calibration = aria_controller.get_rgb_camera_calibration()
        aria_device_calibration = aria_controller.get_device_calibration()
        if not aria_rgb_calibration:
            logger.error("Error: Failed to retrieve RGB camera calibration data")
            return

        data_channels = [aria.StreamingDataType.Rgb, aria.StreamingDataType.EyeTrack]
        message_size = 1  # 1 is usually sufficient for real-time applications
        observer = ImageObserver(
            source_calibration=aria_rgb_calibration,
            device_calibration=aria_device_calibration,
            save_path=save_path,
        )

        observer: ImageObserver = aria_stream_client.subscribe(
            data_channels,
            observer,
            message_size,
        )

        while not quit_keypress():
            sleep(1000000)

    except KeyboardInterrupt:
        print("\nStreaming interrupted by user")
    except Exception as e:
        print(f"Error during streaming: {e}")
        raise
    finally:
        if aria_stream_client is not None:
            try:
                aria_stream_client.__exit__(None, None, None)
            except Exception as e:
                print(f"Error closing Aria stream: {e}")

        print("Streaming terminated, resources cleaned up")
