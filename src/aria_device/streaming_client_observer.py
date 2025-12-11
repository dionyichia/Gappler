import aria.sdk as aria
import csv
import numpy as np
import os
from projectaria_tools.core import calibration
from projectaria_tools.core.sensor_data import (
    BarometerData,
    ImageDataRecord,
    MotionData,
    AudioDataRecord,
    AudioData,
)
from scipy.signal import resample
from typing import Callable, Dict, List, Optional, Sequence
import wave
from pathlib import Path
from datetime import datetime
import time

import config


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


class ImageObserver(BaseStreamingClientObserver):
    """Subscription-based image observer with callback support."""

    def __init__(
        self,
        rgb_camera_calibration: calibration.CameraCalibration,
        rgb_linear_camera_calibration: calibration.CameraCalibration,
        save_path: str,
    ):
        self.rgb_camera_calibration = rgb_camera_calibration
        self.rgb_linear_camera_calibration = rgb_linear_camera_calibration
        self.save_path = save_path

        self.images: dict[str, np.ndarray] = {}
        self.timestamp_ms: int = 0
        self.save_flag = config.Settings.SAVE_IMAGE_FLAG
        self.camera_id_map = config.ImageStreamProcessorConfig().CAMERA_ID_MAP

        self._subscribers: Dict[str, List[Callable]] = {}
        self._global_subscribers: List[Callable] = []

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

    def subscribe(
        self,
        callback: Callable[[np.ndarray, int, str], None],
        camera_id: Optional[aria.CameraId] = None,
    ) -> None:
        """
        Subscribe to image updates.

        Args:
            callback: Function called with (image, timestamp_ms, camera_name)
            camera_id: Specific camera to subscribe to, or None for all cameras

        Example:
            def my_callback(image, timestamp, camera_name):
                print(f"Received {camera_name} frame at {timestamp}")

            observer.subscribe(my_callback, aria.CameraId.Rgb)
        """
        print("Subscriber added")
        if camera_id is None:
            # Subscribe to all cameras
            self._global_subscribers.append(callback)
        else:
            # Subscribe to specific camera
            camera_key = str(camera_id)
            if camera_key not in self._subscribers:
                self._subscribers[camera_key] = []
            self._subscribers[camera_key].append(callback)

    def unsubscribe(
        self,
        callback: Callable[[np.ndarray, int, str], None],
        camera_id: Optional[aria.CameraId] = None,
    ) -> None:
        """
        Unsubscribe from image updates.

        Args:
            callback: The callback function to remove
            camera_id: Specific camera to unsubscribe from, or None for global
        """
        if camera_id is None:
            if callback in self._global_subscribers:
                self._global_subscribers.remove(callback)
        else:
            camera_key = str(camera_id)
            if (
                camera_key in self._subscribers
                and callback in self._subscribers[camera_key]
            ):
                self._subscribers[camera_key].remove(callback)

    def _notify_subscribers(
        self, image: np.ndarray, timestamp_ms: int, camera_id: aria.CameraId
    ) -> None:
        """Notify all subscribers of new image."""
        camera_name = self.camera_id_map.get(camera_id, str(camera_id))
        camera_key = str(camera_id)

        # Notify camera-specific subscribers
        if camera_key in self._subscribers:
            for callback in self._subscribers[camera_key]:
                try:
                    callback(image.copy(), timestamp_ms, camera_name)
                except Exception as e:
                    print(f"Error in subscriber callback: {e}")

        # Notify global subscribers
        for callback in self._global_subscribers:
            try:
                callback(image.copy(), timestamp_ms, camera_name)
            except Exception as e:
                print(f"Error in global subscriber callback: {e}")

    def on_image_received(self, image: np.ndarray, record) -> None:
        """Called when image is received from Aria stream."""
        print("Image received")
        self.images[record.camera_id] = image
        self.timestamp_ms = int(time.time_ns() / 1e6)
        timestamp_ms = self.timestamp_ms

        # Notify subscribers first
        self._notify_subscribers(image, timestamp_ms, record.camera_id)

        # Save image if flag is enabled
        if self.save_flag:
            self._save_image(image, timestamp_ms, record.camera_id)

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
            self.rgb_linear_camera_calibration,
            self.rgb_camera_calibration,
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
                self.rgb_linear_camera_calibration,
                self.rgb_camera_calibration,
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


class AudioObserver(BaseStreamingClientObserver):
    def __init__(self, save_dir="v1/aria_pkg/output/audio_recordings"):
        self.whisper_rate = 16000  # sample rate faster-whisper = 16000
        self.aria_rate = 48000  # sample rate Aria = 48000
        self.audio = []
        self.audios = [[] for c in range(7)]
        self.sampled_audios = np.zeros(self.aria_rate * 1, dtype=np.int8)
        self.timestamp = []
        self.timestamps = []
        self.received = False
        self.last_len = 0
        self.last_save_time = time.time()
        self.save_interval = 10  # seconds

        # Setup save directory
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)

    # source sample rate to 16k
    def resample_audio(self):
        starttime_ns = np.copy(self.timestamps[0])
        audios = np.copy(np.array(self.audios))
        num_samples = int(len(audios[0]) * self.whisper_rate / self.aria_rate)
        sampled_audios = resample(np.mean(np.array(audios), axis=0), num_samples)
        sampled_audios = sampled_audios / 1e8  # normalize sound intensity
        sampled_audios = sampled_audios.astype(np.float32)
        return sampled_audios, starttime_ns

    # source sample rate to 16k for saving audios as wav
    def resample_audio_wav(self):
        audios = np.copy(np.array(self.audios))
        current_len = len(audios[1])
        if current_len <= self.last_len:
            return None, None
        # only save new part
        new_audios = [ch[self.last_len :] for ch in audios]
        self.last_len = current_len
        mixed = np.mean(np.array(new_audios), axis=0)
        # Resample von 48k -> 16k
        num_samples = int(len(new_audios[0]) * self.whisper_rate / self.aria_rate)
        sampled_audios = resample(mixed, num_samples)
        # normalize to [-1,1]
        max_val = np.max(np.abs(sampled_audios))
        if max_val > 0:
            sampled_audios = sampled_audios / max_val
        return sampled_audios.astype(np.float32), None

    def save_audio_chunk(self, audio_data, sample_rate=16000):
        """Save audio chunk to WAV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = self.save_dir / f"audio_chunk_{timestamp}.wav"

        # Convert to int16 for WAV format
        audio_int16 = (audio_data * 32767).astype(np.int16)

        with wave.open(str(filename), "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes for int16
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return filename

    def on_audio_received(self, audio_data: AudioData, record: AudioDataRecord):
        self.audio, self.timestamp = audio_data.data, record.capture_timestamps_ns
        self.timestamps += record.capture_timestamps_ns

        # Record Limitation: 100s;10 samples per second
        rec_limit = self.aria_rate * 10 * 100
        if len(self.timestamps) >= rec_limit:
            del self.timestamps[-rec_limit]

        # save data to audios
        for c in range(7):
            self.audios[c] += self.audio[c::7]
            if len(self.audios[c]) >= rec_limit:
                del self.audios[c][-rec_limit:]

        self.received = True

        # Check if 10 seconds have passed since last save
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            # Save audio chunk to file every 10 seconds
            resampled_audio, _ = self.resample_audio_wav()
            if resampled_audio is not None:
                try:
                    saved_file = self.save_audio_chunk(
                        resampled_audio, self.whisper_rate
                    )
                    print(f"Audio saved: {saved_file}")
                    self.last_save_time = current_time  # Update last save time
                except Exception as e:
                    print(f"Error saving audio: {e}")
