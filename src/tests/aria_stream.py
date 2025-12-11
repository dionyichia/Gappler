# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
from collections import deque
from contextlib import contextmanager
import fastplotlib as fpl
import numpy as np
import signal
import subprocess
import sys
from typing import Sequence

import aria.sdk as aria
from projectaria_tools.core.sensor_data import (
    BarometerData,
    ImageDataRecord,
    MotionData,
)

NANOSECOND = 1e-9


@contextmanager
def ctrl_c_handler(signal_handler=None):
    class ctrl_c_state:
        def __init__(self):
            self._caught_ctrl_c = False

        def __bool__(self):
            return self._caught_ctrl_c

    state = ctrl_c_state()

    def _handler(sig, frame):
        state._caught_ctrl_c = True
        if signal_handler:
            signal_handler()

    original_sigint_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, _handler)

    try:
        yield state
    finally:
        signal.signal(signal.SIGINT, original_sigint_handler)


def update_iptables() -> None:
    """
    Update firewall to permit incoming UDP connections for DDS
    """
    update_iptables_cmd = [
        "sudo",
        "iptables",
        "-A",
        "INPUT",
        "-p",
        "udp",
        "-m",
        "udp",
        "--dport",
        "7000:8000",
        "-j",
        "ACCEPT",
    ]
    print("Running the following command to update iptables:")
    print(update_iptables_cmd)
    subprocess.run(update_iptables_cmd)


class TemporalWindowPlot:
    """
    Manage an fastplotlib plot with streaming data, showing the most recent values.
    """

    def __init__(
        self,
        axes,
        title: str,
        dim: int,
        window_duration_sec: float = 4,
    ):
        self.axes = axes
        self.title = title
        self.window_duration = window_duration_sec
        self.timestamps = deque()
        self.samples = [deque() for _ in range(dim)]
        self.axes.add_animations(self.update)
        self.count = 0

    def add_samples(self, timestamp_ns: float, samples: Sequence[float]):
        # Convert timestamp to seconds
        timestamp = timestamp_ns * NANOSECOND

        # Remove old data outside of the window
        while (
            self.timestamps and (timestamp - self.timestamps[0]) > self.window_duration
        ):
            self.timestamps.popleft()
            for sample in self.samples:
                sample.popleft()

        # Add new data
        self.timestamps.append(timestamp)
        for i, sample in enumerate(samples):
            self.samples[i].append(sample)

    def update(self):
        if not self.timestamps:
            return
        self.axes.clear()
        self.line_collection = self.axes.add_line_collection(
            [np.asarray(s, dtype="float32") for s in self.samples],
            cmap="tab10",
        )
        self.axes.auto_scale()
        self.axes.set_title(self.title)
        self.axes.center_title()


class BaseStreamingClientObserver:
    """
    Streaming client observer class. Describes all available callbacks that are invoked by the
    streaming client.
    """

    def on_image_received(self, image: np.array, record: ImageDataRecord) -> None:
        pass

    def on_imu_received(self, samples: Sequence[MotionData], imu_idx: int) -> None:
        pass

    def on_magneto_received(self, sample: MotionData) -> None:
        pass

    def on_baro_received(self, sample: BarometerData) -> None:
        pass

    def on_streaming_client_failure(self, reason: aria.ErrorCode, message: str) -> None:
        pass


class AriaVisualizer:
    """
    Example Aria visualiser class
    """

    def __init__(self):
        # Create a fastplotlib grid layout
        self.plots = fpl.GridPlot(shape=(3, 4), size=(1600, 1000))

        # Create the image axes
        image_axes = self.plots[0, :]
        (rgb_axes, slam1_axes, slam2_axes, et_axes) = image_axes

        self.image_plot = {
            aria.CameraId.Rgb: rgb_axes.add_image(
                np.zeros((1408, 1408, 3), dtype="uint8"),
                vmin=0,
                vmax=255,
            ),
            aria.CameraId.Slam1: slam1_axes.add_image(
                np.zeros((640, 480), dtype="uint8"),
                vmin=0,
                vmax=255,
                cmap="gray",
            ),
            aria.CameraId.Slam2: slam2_axes.add_image(
                np.zeros((640, 480), dtype="uint8"),
                vmin=0,
                vmax=255,
                cmap="gray",
            ),
            aria.CameraId.EyeTrack: et_axes.add_image(
                np.zeros((240, 640), dtype="uint8"),
                vmin=0,
                vmax=255,
                cmap="gray",
            ),
        }

        titles = ["Front RGB", "Left SLAM", "Right SLAM", "Eye Track"]
        for axes, title in zip(image_axes, titles):
            axes.set_title(title)

        # Create the sensor plots
        self.sensor_plot = {
            "accel": [
                TemporalWindowPlot(axes, f"IMU{idx} accel", 3)
                for idx, axes in enumerate(self.plots[1, 0:2])
            ],
            "gyro": [
                TemporalWindowPlot(axes, f"IMU{idx} gyro", 3)
                for idx, axes in enumerate(self.plots[1, 2:4])
            ],
            "magneto": TemporalWindowPlot(self.plots[2, 0], "Magnetometer", 3),
            "baro": TemporalWindowPlot(self.plots[2, 1], "Barometer", 1),
        }

    def render_loop(self):

        # Show the plots
        self.plots.show()

        with ctrl_c_handler(self.stop):
            # Run event loop until stopped
            fpl.run()

    def stop(self):
        self.plots.close()


class AriaVisualizerStreamingClientObserver(BaseStreamingClientObserver):
    """
    Example implementation of the streaming client observer class.
    Set an instance of this class as the observer of the streaming client using
    set_streaming_client_observer().
    """

    def __init__(self, visualizer: AriaVisualizer):
        self.visualizer = visualizer

    def on_image_received(self, image: np.array, record: ImageDataRecord) -> None:
        # Rotate images to match the orientation of the camera
        if record.camera_id != aria.CameraId.EyeTrack:
            image = np.rot90(image)
        else:
            image = np.rot90(image, 2)

        # Update the image
        self.visualizer.image_plot[record.camera_id].data = image

    def on_imu_received(self, samples: Sequence[MotionData], imu_idx: int) -> None:
        # Only plot the first IMU sample per batch
        sample = samples[0]
        self.visualizer.sensor_plot["accel"][imu_idx].add_samples(
            sample.capture_timestamp_ns, sample.accel_msec2
        )
        self.visualizer.sensor_plot["gyro"][imu_idx].add_samples(
            sample.capture_timestamp_ns, sample.gyro_radsec
        )

    def on_magneto_received(self, sample: MotionData) -> None:
        self.visualizer.sensor_plot["magneto"].add_samples(
            sample.capture_timestamp_ns, sample.mag_tesla
        )

    def on_baro_received(self, sample: BarometerData) -> None:
        self.visualizer.sensor_plot["baro"].add_samples(
            sample.capture_timestamp_ns, [sample.pressure]
        )

    def on_streaming_client_failure(self, reason: aria.ErrorCode, message: str) -> None:
        print(f"Streaming Client Failure: {reason}: {message}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--interface",
        dest="streaming_interface",
        type=str,
        required=True,
        help="Type of interface to use for streaming. Options are usb or wifi.",
        choices=["usb", "wifi"],
    )
    parser.add_argument(
        "--update_iptables",
        default=False,
        action="store_true",
        help="Update iptables to enable receiving the data stream, only for Linux.",
    )
    parser.add_argument(
        "--profile",
        dest="profile_name",
        type=str,
        default="profile18",
        required=False,
        help="Profile to be used for streaming.",
    )
    parser.add_argument(
        "--device-ip", help="IP address to connect to the device over wifi"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if args.update_iptables and sys.platform.startswith("linux"):
        update_iptables()

    #  Optional: Set SDK's log level to Trace or Debug for more verbose logs. Defaults to Info
    aria.set_log_level(aria.Level.Info)

    # 1. Create DeviceClient instance, setting the IP address if specified
    device_client = aria.DeviceClient()

    client_config = aria.DeviceClientConfig()
    if args.device_ip:
        client_config.ip_v4_address = args.device_ip
    device_client.set_client_config(client_config)

    # 2. Connect to the device
    device = device_client.connect()

    # 3. Retrieve the streaming_manager and streaming_client
    streaming_manager = device.streaming_manager
    streaming_client = streaming_manager.streaming_client

    # 4. Set custom config for streaming
    streaming_config = aria.StreamingConfig()
    streaming_config.profile_name = args.profile_name

    #    Note: by default streaming uses Wifi
    if args.streaming_interface == "usb":
        streaming_config.streaming_interface = aria.StreamingInterface.Usb

    #    Use ephemeral streaming certificates
    streaming_config.security_options.use_ephemeral_certs = True
    streaming_manager.streaming_config = streaming_config

    # 5. Start streaming
    streaming_manager.start_streaming()

    # 6. Get streaming state
    streaming_state = streaming_manager.streaming_state
    print(f"Streaming state: {streaming_state}")

    # 7. Create the visualizer observer and attach the streaming client
    aria_visualizer = AriaVisualizer()
    aria_visualizer_streaming_client_observer = AriaVisualizerStreamingClientObserver(
        aria_visualizer
    )
    streaming_client.set_streaming_client_observer(
        aria_visualizer_streaming_client_observer
    )
    streaming_client.subscribe()

    # 8. Visualize the streaming data until we close the window
    aria_visualizer.render_loop()

    # 9. Stop streaming and disconnect the device
    print("Stop listening to image data")
    streaming_client.unsubscribe()
    streaming_manager.stop_streaming()
    device_client.disconnect(device)


if __name__ == "__main__":
    main()
