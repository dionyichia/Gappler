# services/image_service.py
import cv2
import numpy as np
from PIL import Image
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ImageService:
    """Service for image loading and processing"""

    @staticmethod
    def load_image(image_path: str) -> np.ndarray:
        """Load image from file path"""
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Failed to load image from {image_path}")
        return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    @staticmethod
    def load_pil_image(image_path: str) -> Image.Image:
        """Load image as PIL Image"""
        return Image.open(image_path)

    @staticmethod
    def save_image(image: np.ndarray, output_path: str):
        """Save numpy array as image"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if len(image.shape) == 3 and image.shape[2] == 3:
            # Convert RGB to BGR for OpenCV
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        cv2.imwrite(str(output_path), image)
        logger.info(f"Saved image to {output_path}")
