import logging
from multiprocessing.synchronize import Event

import aria.sdk as aria

from services.aria_device import AriaDeviceController, AriaStreamClient, ImageObserver

logger = logging.getLogger(__name__)


def stream_visual_feed(aria_streaming_started: Event, quit_event: Event) -> None:
    aria_stream_client = None
    aria_streaming_started.wait()

    try:
        with AriaStreamClient() as aria_stream_client:
            aria_controller = AriaDeviceController.get_instance()
            aria_rgb_calibration = aria_controller.get_rgb_camera_calibration()
            aria_device_calibration = aria_controller.get_device_calibration()
            if not aria_rgb_calibration:
                logger.error("Error: Failed to retrieve RGB camera calibration data")
                return

            data_channels = [
                aria.StreamingDataType.Rgb,
                aria.StreamingDataType.EyeTrack,
            ]
            message_size = 1  # 1 is usually sufficient for real-time applications
            observer = ImageObserver(
                source_calibration=aria_rgb_calibration,
                device_calibration=aria_device_calibration,
            )

            observer: ImageObserver = aria_stream_client.subscribe(
                data_channels,
                observer,
                message_size,
            )

            quit_event.wait()

    except KeyboardInterrupt:
        print("\nStreaming interrupted by user")
    except Exception as e:
        print(f"Error during streaming: {e}")
        raise
    finally:
        print("Streaming terminated, resources cleaned up")
