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
from typing import Sequence
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
    def __init__(
        self,
        rgb_camera_calibration,
        rgb_linear_camera_calibration,
        save_path,
        camera_id_map,
    ):
        self.images: dict[str, np.ndarray] = {}
        self.timestamp: int = 0
        self.save_flag = config.Settings.SAVE_IMAGE_FLAG
        self.rgb_camera_calibration = rgb_camera_calibration
        self.rgb_linear_camera_calibration = rgb_linear_camera_calibration
        self.save_path = save_path
        self.camera_id_map = camera_id_map

    def on_image_received(self, image: np.ndarray, record: ImageDataRecord) -> None:
        self.images[record.camera_id] = image
        self.timestamp = record.capture_timestamp_ns
        timestamp_ns = self.timestamp
        save_folder = os.path.join(self.save_path, self.camera_id_map[record.camera_id])

        # save image if save_flag is True
        if self.save_flag:
            if not os.path.exists(save_folder):
                print(f"ERROR: Folder {save_folder} does not exist, create folder")
                os.makedirs(save_folder)
            csv_path = os.path.join(save_folder, "data.csv")
            csv_header = ["#timestamp [ns]", "filename"]

            # save csv file with timestamp and corresponding img for all cam_ids
            if not os.path.exists(csv_path):
                with open(csv_path, mode="w", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow(csv_header)
            with open(csv_path, mode="a", newline="") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow([timestamp_ns, f"{timestamp_ns}.npy"])

            # save all images
            image_path = os.path.join(self.save_path, "images")
            np.save(os.path.join(image_path, f"{timestamp_ns}.npy"), image)

            # undistort RGB image
            if record.camera_id == aria.CameraId.Rgb:
                # undistort img
                undistort_image = calibration.distort_by_calibration(
                    image,
                    self.rgb_linear_camera_calibration,
                    self.rgb_camera_calibration,
                )
                # save undistorted image
                undistort_path = os.path.join(self.save_path, "undistorted_imgs")
                np.save(
                    os.path.join(undistort_path, f"{timestamp_ns}.npy"), undistort_image
                )

    def get_undistorted_rgb_image(self) -> np.ndarray:
        if aria.CameraId.Rgb in self.images:
            undistort_image = calibration.distort_by_calibration(
                self.images[aria.CameraId.Rgb],
                self.rgb_linear_camera_calibration,
                self.rgb_camera_calibration,
            )
            return undistort_image
        else:
            return None


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
