import csv
import os

import cv2
import numpy as np


class FrameRecorder:
    """Handles saving frames and timestamps to disk"""

    def __init__(self, save_path: str, source_name: str):
        self.save_path = save_path
        self.source_name = source_name
        self.frame_count = 0

        # Create directories
        self.frame_dir = os.path.join(save_path, source_name, "frames")
        os.makedirs(self.frame_dir, exist_ok=True)

        # Initialize CSV
        self.csv_path = os.path.join(save_path, source_name, "timestamps.csv")
        self._init_csv()

    def _init_csv(self):
        """Initialize CSV file with header"""
        with open(self.csv_path, mode="w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["#frame_id", "filename"])

    def save_frame(self, frame: np.ndarray) -> str:
        """Save frame, return filename"""
        # Generate filename
        filename = f"{self.frame_count}.png"
        filepath = os.path.join(self.frame_dir, filename)

        # Save image
        cv2.imwrite(filepath, frame)

        # Append to CSV
        with open(self.csv_path, mode="a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([self.frame_count, filename])

        self.frame_count += 1

        if self.frame_count % 100 == 0:
            print(f"Saved {self.frame_count} {self.source_name} frames")

        return filename
