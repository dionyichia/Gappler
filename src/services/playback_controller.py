import time
from collections import deque
from typing import Optional, Tuple

import numpy as np
from projectaria_tools.core import calibration
from projectaria_tools.core.calibration import get_linear_camera_calibration
from projectaria_tools.core.data_provider import (
    VrsDataProvider,
    create_vrs_data_provider,
)
from projectaria_tools.core.sensor_data import SensorDataType, TimeDomain
from projectaria_tools.core.stream_id import StreamId
from tqdm import tqdm

from config import AriaConfig, PlaybackControllerConfig, ROS2Config, ROS2Topics
from services.aria_device.eye_tracking import EyeTrackingPipeline


class PlaybackController:
    def __init__(
        self,
        vrs_filepath: str,
    ):
        self.vrs_filepath = vrs_filepath
        self.playback_speed = PlaybackControllerConfig.PLAYBACK_SPEED
        self.vrs_data_provider: VrsDataProvider = create_vrs_data_provider(vrs_filepath)

        self.eye_stream_id = StreamId(AriaConfig.EYE_STREAM_ID)
        self.rgb_stream_id = StreamId(AriaConfig.RGB_STREAM_ID)

        self.eye_stream_label = self.vrs_data_provider.get_label_from_stream_id(
            self.eye_stream_id
        )

        self.rgb_stream_label = self.vrs_data_provider.get_label_from_stream_id(
            self.rgb_stream_id
        )

        self.device_calibration = self.vrs_data_provider.get_device_calibration()
        self.rgb_camera_calibration = self.device_calibration.get_camera_calib(
            self.rgb_stream_label
        )
        self.dest_calibration = get_linear_camera_calibration(
            AriaConfig.DEST_CALIBRATION_WIDTH_PX,
            AriaConfig.DEST_CALIBRATION_HEIGHT_PX,
            AriaConfig.DEST_CALIBRATION_FOCAL_LENGTH,
            "camera-rgb",
        )

        self.eye_tracking = EyeTrackingPipeline(
            self.device_calibration, self.rgb_camera_calibration
        )

        # Frame counts
        self.eye_frame_count = self.vrs_data_provider.get_num_data(self.eye_stream_id)
        self.rgb_frame_count = self.vrs_data_provider.get_num_data(self.rgb_stream_id)

        # Buffer for frames that are ready to be displayed
        self.frame_buffer: deque = deque()

        # Timing variables for synchronized playback
        self.first_timestamp_ns: Optional[int] = None
        self.playback_start_time: Optional[float] = None

    def _publish_image(self, image: np.ndarray, topic: str) -> None:
        """Publish image."""
        if len(image) == 0:
            return

    def _undistort_image(self, image: np.ndarray) -> np.ndarray:
        """Undistort RGB image."""
        undistort_image = calibration.distort_by_calibration(
            image,
            self.dest_calibration,
            self.rgb_camera_calibration,
        )
        return undistort_image

    def _track_eye_gaze_position(
        self, image: np.ndarray
    ) -> Optional[Tuple[float, float]]:
        """Generates a gaze position based on an eye image."""
        gaze_estimate = self.eye_tracking.predict_eye_gaze(image)

        gaze_position = self.eye_tracking.project_gaze(gaze_estimate=gaze_estimate)

        return gaze_position

    def _process_frame(self, image: np.ndarray, stream_id: StreamId) -> None:
        """Process and publish a frame."""
        if len(image) == 0:
            return

        if stream_id == self.rgb_stream_id:
            image = np.rot90(image, -1)
            self._publish_image(image, ROS2Topics.RGB_CAMERA_RAW)
            undistorted_image = self._undistort_image(image.copy())
            self._publish_image(undistorted_image, ROS2Topics.RGB_CAMERA_UNDISTORTED)

        elif stream_id == self.eye_stream_id:
            eye_gaze_position = self._track_eye_gaze_position(image.copy())
            self._publish_image(image, ROS2Topics.EYE_TRACKING_RAW)

    def _get_playback_time_sec(self) -> float:
        """Get the current playback time in seconds since start."""
        if self.playback_start_time is None:
            return 0.0
        return time.time() - self.playback_start_time

    def _should_display_frame(self, data_timestamp_ns: int) -> bool:
        """
        Check if a frame should be displayed based on current playback time.

        Args:
            data_timestamp_ns: The timestamp of the data from the VRS file (in nanoseconds)

        Returns:
            True if the frame should be displayed now, False if it's in the future
        """
        if self.first_timestamp_ns is None:
            return True  # Display first frame immediately

        # Calculate when this frame should be displayed
        recording_elapsed_ns = data_timestamp_ns - self.first_timestamp_ns
        recording_elapsed_sec = recording_elapsed_ns / 1e9
        target_playback_time_sec = recording_elapsed_sec / self.playback_speed

        # Check if we've reached the display time
        current_playback_time = self._get_playback_time_sec()

        return current_playback_time >= target_playback_time_sec

    def play(self) -> None:
        """
        Play back the VRS file with synchronized timing across all streams.
        Uses a non-blocking approach where frames are buffered and displayed
        when their timestamp is reached.
        """
        # Configure delivery options - activate all streams you want to play
        deliver_option = self.vrs_data_provider.get_default_deliver_queued_options()
        deliver_option.deactivate_stream_all()
        deliver_option.activate_stream(self.rgb_stream_id)
        deliver_option.activate_stream(self.eye_stream_id)

        # Calculate total frames
        total_frames = self.eye_frame_count + self.rgb_frame_count

        # Create progress bar
        progress_bar = tqdm(total=total_frames, desc="Playing VRS file")

        # Create an iterator for the data
        data_iterator = iter(
            self.vrs_data_provider.deliver_queued_sensor_data(deliver_option)
        )

        playback_active = True

        while playback_active:
            # Try to buffer more frames (fill buffer with upcoming frames)
            try:
                # Buffer multiple frames ahead to ensure smooth playback
                while len(self.frame_buffer) < 10:  # Keep 10 frames buffered
                    data = next(data_iterator)

                    if data.sensor_data_type() == SensorDataType.IMAGE:
                        data_timestamp_ns = data.get_time_ns(TimeDomain.HOST_TIME)
                        image_data, record = data.image_data_and_record()
                        image = image_data.to_numpy_array()
                        stream_id = data.stream_id()

                        # Add to buffer with timestamp
                        self.frame_buffer.append(
                            {
                                "timestamp_ns": data_timestamp_ns,
                                "image": image,
                                "stream_id": stream_id,
                            }
                        )

                        # Initialize timing on first frame
                        if self.first_timestamp_ns is None:
                            self.first_timestamp_ns = data_timestamp_ns
                            self.playback_start_time = time.time()

                    progress_bar.update(1)

            except StopIteration:
                # No more data to buffer
                if len(self.frame_buffer) == 0:
                    playback_active = False
                    break

            # Process frames from buffer that are ready to display
            frames_displayed = 0
            while self.frame_buffer and self._should_display_frame(
                self.frame_buffer[0]["timestamp_ns"]
            ):
                frame_data = self.frame_buffer.popleft()
                self._process_frame(frame_data["image"], frame_data["stream_id"])
                frames_displayed += 1

            # Small sleep to prevent busy-waiting if no frames are ready
            if frames_displayed == 0 and self.frame_buffer:
                time.sleep(0.001)  # 1ms sleep to reduce CPU usage

        progress_bar.close()


def playback(vrs_filepath: str):
    """
    Main playback function with synchronized multi-stream playback.

    Args:
        vrs_filepath: Path to the VRS file
    """
    observer = PlaybackController(vrs_filepath)
    observer.play()


# Delete if unused
# Configure the loop for data replay
# stream_config = vrs_data_provider.get_configuration(rgb_stream_id)
# fps = stream_config.get_nominal_rate_hz()  # or similar method name
