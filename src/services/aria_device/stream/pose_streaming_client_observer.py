import logging
import time
from typing import Callable, Sequence

import aria.sdk as aria
import numpy as np
from projectaria_tools.core.sensor_data import ImageDataRecord, MotionData

from services.aria_device.stream.base_streaming_client_observer import (
    BaseStreamingClientObserver,
)

logger = logging.getLogger(__name__)

ImageCallback = Callable[[np.ndarray, object], None]
ImuCallback = Callable[[Sequence[MotionData], int], None]


class AriaVIOObserver(BaseStreamingClientObserver):
    def __init__(self) -> None:
        # --- MONITORING LOGIC ---
        # self._last_callback_time = time.time()
        # self._total_samples_received = 0
        # ------------------------

        self._image_callbacks = dict[aria.CameraId, ImageCallback]()
        self._imu_callbacks = dict[int, ImuCallback]()

    def register_on_image_callback(
        self, camera_id: aria.CameraId, callback: ImageCallback
    ) -> None:
        """Register a callback for a specific camera ID. One callback per ID."""
        self._image_callbacks[camera_id] = callback

    def register_on_imu_callback(self, imu_id: int, callback: ImuCallback) -> None:
        """Register a callback for a specific IMU ID. One callback per ID."""
        self._imu_callbacks[imu_id] = callback

    def on_image_received(self, image: np.ndarray, record: ImageDataRecord) -> None:
        if image is None:
            return
        cb = self._image_callbacks.get(record.camera_id)
        if cb is not None:
            cb(image, record)

    def on_imu_received(self, samples: Sequence[MotionData], imu_idx: int) -> None:
        if len(samples) == 0:
            return

        # --- MONITORING LOGIC ---
        # self._total_samples_received += len(samples)
        # now = time.time()
        # if now - self._last_callback_time >= 1.0:
        #     # This is the RAW rate from the hardware
        #     print(f"[Hardware Rate] {self._total_samples_received} samples/sec")
        #     self._total_samples_received = 0
        #     self._last_callback_time = now
        # ------------------------

        cb = self._imu_callbacks.get(imu_idx)
        if cb is not None:
            cb(samples, imu_idx)
