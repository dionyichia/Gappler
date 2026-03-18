import logging
from ipaddress import IPv4Address
from multiprocessing import Queue
from multiprocessing.synchronize import Event
from typing import Optional

from services.aria_device import AriaDeviceController

logger = logging.getLogger(__name__)


class AriaStreamingPipeline:
    def __init__(
        self,
        aria_streaming_started: Event,
        quit_event: Event,
        device_ip: Optional[IPv4Address],
        profile_name: str,
        config_queue: Queue,
    ):
        self._streaming_started = aria_streaming_started
        self._quit_event = quit_event
        self._device_ip = device_ip
        self._profile_name = profile_name
        self._config_queue = config_queue

    def run(self) -> None:
        try:
            with AriaDeviceController.get_instance() as aria_controller:
                aria_controller.connect(device_ip=self._device_ip)
                interface = None if self._device_ip else "usb"
                logger.info(
                    f"Connected to Aria device using {interface if interface else 'wifi'}"
                )

                aria_controller.start_streaming(
                    profile=self._profile_name, interface=interface
                )
                logger.info(f"Streaming started with profile: {self._profile_name}")
                self._streaming_started.set()

                sensors_calib_json_str = (
                    aria_controller.get_sensors_calibration_json_str()
                )

                self._config_queue.put(sensors_calib_json_str)

                self._quit_event.wait()
        except Exception as e:
            logger.error(f"✗ Error stopping streaming: {e}")
            self._quit_event.set()


def start_aria_stream(
    aria_streaming_started: Event,
    quit_event: Event,
    device_ip: Optional[IPv4Address],
    profile_name: str,
    config_queue: Queue,
) -> None:
    AriaStreamingPipeline(
        aria_streaming_started, quit_event, device_ip, profile_name, config_queue
    ).run()
