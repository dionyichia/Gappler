# data_models/schemas.py
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np


@dataclass
class ObjectDetection:
    """Single object detection result"""

    object_name: str
    lexeme: str  # noun, pronoun
    word: str
    rgb_path: str
    eye_track_path: str
    start_time_ns: int
    end_time_ns: int
    bbox: Optional[List[float]] = None
    mask: Optional[np.ndarray] = None
    position_2d: Optional[Tuple[int, int]] = None


@dataclass
class GPTRequest:
    """Parsed GPT request from ROS"""

    words: List[str]
    object_names: List[str]
    lexemes: List[str]
    start_times: List[int]
    end_times: List[int]
    rgb_paths: List[str]
    eye_track_paths: List[str]
    question: List[str] = field(default_factory=list)

    def to_detections(self) -> List[ObjectDetection]:
        """Convert to list of ObjectDetection objects"""
        detections = []
        for i in range(len(self.lexemes)):
            detection = ObjectDetection(
                object_name=self.object_names[i],
                lexeme=self.lexemes[i],
                word=self.words[i],
                rgb_path=self.rgb_paths[i],
                eye_track_path=self.eye_track_paths[i],
                start_time_ns=self.start_times[i],
                end_time_ns=self.end_times[i],
            )
            detections.append(detection)
        return detections


@dataclass
class ActionPlanRequest:
    """Request for GPT action planning"""

    object_names: List[str]
    lexemes: List[str]
    positions_2d: List[List[int]]
    question: List[str]

    def to_dict(self):
        return {
            "object_name": self.object_names,
            "lexeme": self.lexemes,
            "2d_position": self.positions_2d,
            "question": self.question,
        }
