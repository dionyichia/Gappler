import logging
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImageHelper:
    @staticmethod
    def compress_image(image: np.ndarray) -> tuple[bool, bytes]:
        success, compressed = cv2.imencode(
            ".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80]
        )
        return success, compressed.tobytes()

    @staticmethod
    def uncompress_image(image_bytes: bytes) -> Optional[np.ndarray]:
        try:
            np_arr = np.frombuffer(image_bytes, dtype=np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if frame is None or frame.size == 0 or np.all(frame == 0):
                logger.warning("Received empty or all-black frame, skipping")
                return None

            return frame
        except Exception as e:
            logger.error(f"Failed to decode image: {e}")
            return None
