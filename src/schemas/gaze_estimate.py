from dataclasses import dataclass
from typing import Dict, List


@dataclass
class GazeEstimate:
    """Container for gaze estimation results with uncertainty bounds."""

    yaw: float
    pitch: float
    yaw_lower: float
    pitch_lower: float
    yaw_upper: float
    pitch_upper: float
    timestamp_ms: int
    depth_m: str = ""

    def to_csv_row(self) -> List:
        """Convert to CSV row format compatible with MPS eye gaze format."""
        return [
            self.timestamp_ms,
            self.yaw,
            self.pitch,
            self.depth_m,
            self.yaw_lower,
            self.pitch_lower,
            self.yaw_upper,
            self.pitch_upper,
        ]

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for easy access."""
        return {
            "yaw": self.yaw,
            "pitch": self.pitch,
            "yaw_lower": self.yaw_lower,
            "pitch_lower": self.pitch_lower,
            "yaw_upper": self.yaw_upper,
            "pitch_upper": self.pitch_upper,
        }
