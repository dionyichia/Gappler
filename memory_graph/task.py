"""The task inside the graph (T6.7a): its text feature, its class sets, the score.

A task is one instruction, "find a chair". Three things about it are held here:

    feature   the instruction as a vector, in the same space as the image
              features (OpenClipEncoder.encode_text), L2-normalised
    targets   the classes the instruction asks for
    related   classes likely to be near a target, from the reasoning layer (T6.7b)

and one number is computed from it: how similar an object or a photo is to the
task, the cosine between its feature and the task's.

Upstream holds these in TargetManager (map/map_elements.py:217). It scores a
photo, the sum over the photo's crops (map_elements.py:322), but it never sets
the score of an object, so that field stays 0 there. Here ObjectStore sets it
on insert and on merge.

Not here: choosing the classes from the instruction (T6.7b), and the blacklist
and the ranked target list (T6.8a).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Iterable, Optional, Protocol, Sequence

import numpy as np


class TextEncoder(Protocol):
    def encode_text(self, texts: Sequence[str]) -> np.ndarray:
        """Sentences -> (N, D) float array, in the image features' space."""
        ...


def _unit(vector: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64).reshape(-1)
    norm = np.linalg.norm(vector)
    return vector / norm if norm > 0 else vector


@dataclass(frozen=True)
class TaskContext:
    """One task. Frozen: a new instruction or a new class set is a new
    TaskContext, handed to ObjectStore.set_task, so every score is redone."""

    instruction: str
    feature: np.ndarray                               # (D,), L2-normalised
    targets: FrozenSet[str] = field(default_factory=frozenset)
    related: FrozenSet[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        feature = _unit(self.feature)
        if feature.size == 0 or not np.isfinite(feature).all() or not feature.any():
            raise ValueError("the task feature must be a finite, non-zero vector")
        object.__setattr__(self, "feature", feature)
        object.__setattr__(self, "targets", frozenset(self.targets))
        # A class is a target or related, never both. Target wins.
        object.__setattr__(self, "related", frozenset(self.related) - self.targets)

    @classmethod
    def from_text(
        cls,
        instruction: str,
        encoder: TextEncoder,
        targets: Iterable[str] = (),
        related: Iterable[str] = (),
    ) -> "TaskContext":
        """Embed the instruction with the encoder that made the image features."""
        return cls(instruction, np.asarray(encoder.encode_text([instruction]))[0],
                   frozenset(targets), frozenset(related))

    @property
    def classes(self) -> FrozenSet[str]:
        """Targets and related together. This is the `targets` argument of the
        anchor gate (S3): a photo showing any of them is kept."""
        return self.targets | self.related

    def with_classes(self, targets: Iterable[str], related: Iterable[str] = ()) -> "TaskContext":
        """The same instruction with new class sets, without embedding it again."""
        return TaskContext(self.instruction, self.feature, frozenset(targets), frozenset(related))

    def score(self, feature: Optional[np.ndarray]) -> float:
        """cos(feature, task feature), in [-1, 1]. 0 for no feature or an
        all-zero one."""
        if feature is None:
            return 0.0
        feature = np.asarray(feature, dtype=np.float64).reshape(-1)
        if feature.shape != self.feature.shape:
            raise ValueError(
                f"feature has {feature.size} numbers, the task feature has {self.feature.size}. "
                "Both must come from the same encoder"
            )
        norm = np.linalg.norm(feature)
        return float(feature @ self.feature / norm) if norm > 0 else 0.0

    def photo_score(self, features: Optional[np.ndarray]) -> float:
        """The score of one photo, for its anchor: the sum of `score` over the
        photo's object features, (N, D). A sum, as upstream, so a photo with
        more objects scores higher."""
        if features is None or len(features) == 0:
            return 0.0
        return float(sum(self.score(row) for row in np.asarray(features)))
