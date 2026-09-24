from dataclasses import dataclass


@dataclass
class GazeEstimate:
    """Container for gaze estimation results with uncertainty bounds."""

    yaw: float
    pitch: float
    yaw_lower: float
    pitch_lower: float
    yaw_upper: float
    pitch_upper: float
