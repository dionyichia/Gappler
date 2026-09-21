import logging
from typing import Callable

import aria.sdk as aria
import numpy as np

from services.aria_device.stream.base_streaming_client_observer import (
    BaseStreamingClientObserver,
)

logger = logging.getLogger(__name__)

ImageCallback = Callable[[np.ndarray, object], None]


class ImageObserver(BaseStreamingClientObserver):
    """Routes incoming camera frames to a registered callback per camera ID.

    Callbacks are invoked on the SDK callback thread. Implementations should
    be non-blocking — hand off to a queue if any real work is needed.
    """

    def __init__(self) -> None:
        self._callbacks: dict[aria.CameraId, ImageCallback] = {}

    def register_on_image_callback(
        self, camera_id: aria.CameraId, callback: ImageCallback
    ) -> None:
        """Register a callback for a specific camera ID. One callback per ID."""
        self._callbacks[camera_id] = callback

    def on_image_received(self, image: np.ndarray, record) -> None:
        if image is None:
            return
        cb = self._callbacks.get(record.camera_id)
        if cb is not None:
            cb(image, record)
