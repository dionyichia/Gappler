from typing import Optional, Tuple

import aria.sdk as aria
import numpy as np
from geometry_msgs.msg import Point
from projectaria_tools.core import calibration
from projectaria_tools.core.calibration import (
    get_linear_camera_calibration,
)
from sensor_msgs.msg import CompressedImage

from config import AriaConfig, ROS2Topics
from services.aria_device.base_streaming_client_observer import (
    BaseStreamingClientObserver,
)
from services.aria_device.eye_tracking import EyeTrackingPipeline
from services.ros.ros_publisher import ROSPublisher


class ImageObserver(BaseStreamingClientObserver):
    def __init__(
        self,
        source_calibration: calibration.CameraCalibration,
        device_calibration: calibration.DeviceCalibration,
    ):
        self.source_calibration = source_calibration
        self.dest_calibration = get_linear_camera_calibration(
            AriaConfig.DEST_CALIBRATION_WIDTH_PX,
            AriaConfig.DEST_CALIBRATION_HEIGHT_PX,
            AriaConfig.DEST_CALIBRATION_FOCAL_LENGTH,
            "camera-rgb",
        )
        self.device_calibration = device_calibration

        self._rgb_publisher = ROSPublisher(
            "Aria_RGB_camera_publisher",
            CompressedImage,
            ROS2Topics.RGB_CAMERA_RAW.value,
        )
        self._undistorted_rgb_publisher = ROSPublisher(
            "Aria_RGB_camera_undistorted_publisher",
            CompressedImage,
            ROS2Topics.RGB_CAMERA_UNDISTORTED.value,
        )
        self._gaze_estimate_publisher = ROSPublisher(
            "gaze_estimate_publisher",
            Point,
            ROS2Topics.EYE_TRACKING_GAZE_ESTIMATE.value,
        )

        self.eye_tracking = EyeTrackingPipeline(
            self.device_calibration, self.source_calibration
        )

    def on_image_received(self, image: np.ndarray, record) -> None:
        """Called when image is received from Aria stream."""
        if image is None:
            return

        handlers = {
            aria.CameraId.Rgb: self._handle_rgb_frame,
            aria.CameraId.EyeTrack: self._handle_eye_track_frame,
        }

        handler = handlers.get(record.camera_id)
        if handler:
            handler(image)

    def _handle_rgb_frame(self, image: np.ndarray) -> None:
        image = np.rot90(image, -1)
        self._rgb_publisher.publish_image(image)
        undistorted_image = self._undistort_image(image.copy())
        self._undistorted_rgb_publisher.publish_image(undistorted_image)

    def _handle_eye_track_frame(self, image: np.ndarray) -> None:
        gaze_estimate = self._compute_gaze_estimate(image)
        if gaze_estimate is None:
            return

        msg = Point(x=gaze_estimate[0], y=gaze_estimate[1], z=0.0)
        self._gaze_estimate_publisher.publish(msg)

    def _undistort_image(self, image: np.ndarray) -> np.ndarray:
        """Undistort RGB image."""
        undistort_image = calibration.distort_by_calibration(
            image,
            self.dest_calibration,
            self.source_calibration,
        )
        return undistort_image

    def _compute_gaze_estimate(
        self, image: np.ndarray
    ) -> Optional[Tuple[float, float]]:
        """Generates a gaze estimate based on an eye image."""
        gaze_estimate = self.eye_tracking.predict_eye_gaze(image)
        gaze_estimate = self.eye_tracking.project_gaze(gaze_estimate=gaze_estimate)
        return gaze_estimate
