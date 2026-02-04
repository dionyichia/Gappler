import csv
import os
import pickle
import time
from typing import Optional

import aria.sdk as aria
import numpy as np
import zmq
from projectaria_tools.core import calibration
from projectaria_tools.core.calibration import (
    get_linear_camera_calibration,
)

import config
from aria_device.base_streaming_client_observer import BaseStreamingClientObserver
from config import ZMQTopics
from services.eye_tracking import EyeTrackingPipeline


class ImageObserver(BaseStreamingClientObserver):
    def __init__(
        self,
        source_calibration: calibration.CameraCalibration,
        device_calibration: calibration.DeviceCalibration,
        save_path: str,
    ):
        self.source_calibration = source_calibration
        self.dest_calibration = get_linear_camera_calibration(
            config.AriaConfig.DEST_CALIBRATION_WIDTH_PX,
            config.AriaConfig.DEST_CALIBRATION_HEIGHT_PX,
            config.AriaConfig.DEST_CALIBRATION_FOCAL_LENGTH,
            "camera-rgb",
        )
        self.device_calibration = device_calibration
        self.save_path = save_path

        context = zmq.Context()
        self.socket = context.socket(zmq.PUB)
        self.socket.bind(config.ZMQConfig.VISUAL_FEED_ADDRESS)
        self.eye_tracking = EyeTrackingPipeline()

        self.images: dict[str, np.ndarray] = {}
        self.timestamp_ms: int = 0
        self.save_flag = config.Settings.SAVE_IMAGE_FLAG
        self.camera_id_map = config.ImageStreamProcessorConfig().CAMERA_ID_MAP

        self._setup_directories()

    def _setup_directories(self):
        """Create necessary directories for saving"""
        directories = [
            self.save_path,
            os.path.join(self.save_path, "images"),
            os.path.join(self.save_path, "undistorted_imgs"),
        ]
        for cam_id in self.camera_id_map.values():
            directories.append(os.path.join(self.save_path, cam_id))

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def on_image_received(self, image: np.ndarray, record) -> None:
        """Called when image is received from Aria stream."""
        if image is None:
            return

        if record.camera_id == aria.CameraId.Rgb:
            image = np.rot90(image, -1)

        self.images[record.camera_id] = image
        self.timestamp_ms = int(time.time_ns() / 1e6)
        timestamp_ms = self.timestamp_ms

        if record.camera_id == aria.CameraId.Rgb:
            self._publish_image(image, ZMQTopics.RGB_CAMERA_RAW)
            undistorted_image = self._undistort_image(image)
            self._publish_image(undistorted_image, ZMQTopics.RGB_CAMERA_UNDISTORTED)
            eye_tracking_image = self._eye_tracking_overlay(image)
            self._publish_image(
                eye_tracking_image, ZMQTopics.RGB_CAMERA_WITH_GAZE_DETECTION
            )

        if self.save_flag:
            self._save_image(image, timestamp_ms, record.camera_id)

    def _publish_image(self, image: np.ndarray, topic: str) -> None:
        """Publish image via ZMQ."""
        if image is None:
            return
        metadata = {"shape": image.shape, "dtype": str(image.dtype)}
        message = pickle.dumps({"topic": topic, "metadata": metadata, "image": image})
        self.socket.send(message)

    def _undistort_image(self, image: np.ndarray) -> None:
        """Undistort RGB image and store it."""
        if aria.CameraId.Rgb in self.images:
            undistort_image = calibration.distort_by_calibration(
                image,
                self.dest_calibration,
                self.source_calibration,
            )
            return undistort_image

    def _eye_tracking_overlay(self, image: np.ndarray) -> None:
        """Overlay eye-tracking data on RGB image."""
        value_mapping, eye_gaze_inference_result = self.eye_tracking.process_frame(
            self.images,
            aria.CameraId.EyeTrack,
            self.timestamp_ms,
        )

        gaze_point, image_with_gaze = self.eye_tracking.visualize_gaze(
            device_calibration=self.device_calibration,
            rgb_camera_calibration=self.source_calibration,
            images_observer=self.images,
            gaze_dict=value_mapping,
        )
        return image_with_gaze

    def _save_image(
        self, image: np.ndarray, timestamp_ms: int, camera_id: aria.CameraId
    ) -> None:
        """Save image and metadata to disk."""
        camera_name = self.camera_id_map[camera_id]
        save_folder = os.path.join(self.save_path, camera_name)

        # Ensure folder exists
        if not os.path.exists(save_folder):
            print(f"ERROR: Folder {save_folder} does not exist, create folder")
            os.makedirs(save_folder)

        # Setup CSV for timestamp tracking
        csv_path = os.path.join(save_folder, "data.csv")
        csv_header = ["#timestamp [ns]", "filename"]

        if not os.path.exists(csv_path):
            with open(csv_path, mode="w", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(csv_header)

        # Append timestamp entry
        with open(csv_path, mode="a", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([timestamp_ms, f"{timestamp_ms}.npy"])

        # Save image
        image_path = os.path.join(save_folder, f"{timestamp_ms}.npy")
        np.save(image_path, image)

        # Handle RGB camera undistortion
        if camera_id == aria.CameraId.Rgb:
            self._save_undistorted_rgb(image, timestamp_ms)

    def _save_undistorted_rgb(self, image: np.ndarray, timestamp_ms: int) -> None:
        """Undistort and save RGB image."""
        # Undistort image
        undistort_image = calibration.distort_by_calibration(
            image,
            self.dest_calibration,
            self.source_calibration,
        )

        # Save undistorted image
        undistort_path = os.path.join(self.save_path, "undistorted_imgs")
        np.save(os.path.join(undistort_path, f"{timestamp_ms}.npy"), undistort_image)

        # Update CSV
        csv_path = os.path.join(undistort_path, "data.csv")
        csv_header = ["#timestamp [ns]", "filename"]

        if not os.path.exists(csv_path):
            with open(csv_path, mode="w", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(csv_header)

        with open(csv_path, mode="a", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([timestamp_ms, f"{timestamp_ms}.npy"])

    def get_undistorted_rgb_image(self) -> Optional[np.ndarray]:
        """Get current undistorted RGB image."""
        if aria.CameraId.Rgb in self.images:
            undistort_image = calibration.distort_by_calibration(
                self.images[aria.CameraId.Rgb],
                self.dest_calibration,
                self.source_calibration,
            )
            return undistort_image
        else:
            return None

    def get_image(self, camera_id: aria.CameraId) -> Optional[np.ndarray]:
        """Get current image for specific camera."""
        return self.images.get(camera_id)

    def get_latest_timestamp(self) -> int:
        """Get latest timestamp."""
        return self.timestamp_ms
