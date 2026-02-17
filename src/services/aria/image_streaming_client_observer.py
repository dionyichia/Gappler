import pickle
from typing import Optional, Tuple

import aria.sdk as aria
import numpy as np
import zmq
from projectaria_tools.core import calibration
from projectaria_tools.core.calibration import (
    get_linear_camera_calibration,
)

from config import AriaConfig, ZMQConfig, ZMQTopics
from services.aria.base_streaming_client_observer import BaseStreamingClientObserver
from services.aria.eye_tracking import EyeTrackingPipeline


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

        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(ZMQConfig.VISUAL_FEED_ADDRESS)

        self.eye_tracking = EyeTrackingPipeline(
            self.device_calibration, self.source_calibration
        )

    def on_image_received(self, image: np.ndarray, record) -> None:
        """Called when image is received from Aria stream."""
        if image is None:
            return

        if record.camera_id == aria.CameraId.Rgb:
            image = np.rot90(image, -1)
            self._publish_image(image, ZMQTopics.RGB_CAMERA_RAW)
            undistorted_image = self._undistort_image(image.copy())
            self._publish_image(undistorted_image, ZMQTopics.RGB_CAMERA_UNDISTORTED)

        elif record.camera_id == aria.CameraId.EyeTrack:
            eye_gaze_position = self._track_eye_gaze_position(image.copy())
            message = pickle.dumps(
                {"topic": "eye_gaze_position", "position": eye_gaze_position}
            )
            self.socket.send(message)

    def _publish_image(self, image: np.ndarray, topic: str) -> None:
        """Publish image via ZMQ."""
        if len(image) == 0:
            return
        metadata = {"shape": image.shape, "dtype": str(image.dtype)}
        message = pickle.dumps({"topic": topic, "metadata": metadata, "image": image})
        self.socket.send(message)

    def _undistort_image(self, image: np.ndarray) -> np.ndarray:
        """Undistort RGB image."""
        undistort_image = calibration.distort_by_calibration(
            image,
            self.dest_calibration,
            self.source_calibration,
        )
        return undistort_image

    def _track_eye_gaze_position(
        self, image: np.ndarray
    ) -> Optional[Tuple[float, float]]:
        """Generates a gaze position based on an eye image."""
        gaze_estimate = self.eye_tracking.predict_eye_gaze(image)

        gaze_position = self.eye_tracking.project_gaze(gaze_estimate=gaze_estimate)

        return gaze_position
