"""A whole photo scored against the task text (T6.7d).

Upstream scores each frontier by the photo taken there: the photo is encoded
once with CLIP, the vector is kept on the frame, and the score is its cosine
with the task's text feature (habitat/policy.py:178). This is that score, for
any list of photos, so it does not depend on frontiers.

It differs from TaskContext.photo_score, which is the score of an anchor: the
sum over the photo's object features. Here the whole photo is one feature, so
a photo with no detections still has a score.

Gappler plans no frontier exploration in M6. This is here for M9, or for
picking which stored photos to search when no object answers the task.
"""

from __future__ import annotations

from typing import Dict, Hashable, List, Protocol, Sequence, Tuple

import numpy as np

from memory_graph.image_feature import l2_normalise
from memory_graph.task import TaskContext


class ImageEncoder(Protocol):
    def encode(self, crops: Sequence[np.ndarray]) -> np.ndarray:
        """RGB uint8 images -> (N, D) float array, in the text features' space."""
        ...


Photo = Tuple[Hashable, np.ndarray]   # (key, RGB uint8 image), the key names the photo


class PhotoScorer:
    """Scores photos against a task. Each photo is encoded once, the first time
    its key is seen, as upstream keeps the vector on the frame. A key is assumed
    to always name the same image: call `forget` if it does not."""

    def __init__(self, encoder: ImageEncoder) -> None:
        self._encoder = encoder
        self._features: Dict[Hashable, np.ndarray] = {}

    def __len__(self) -> int:
        """Photos with a stored feature."""
        return len(self._features)

    def features(self, photos: Sequence[Photo]) -> np.ndarray:
        """(N, D) L2-normalised, one row per photo, in the order given. The
        photos not seen before are encoded in one call."""
        new: Dict[Hashable, np.ndarray] = {}
        for key, image in photos:
            if key not in self._features and key not in new:
                new[key] = image
        if new:
            encoded = l2_normalise(self._encoder.encode(list(new.values())))
            if len(encoded) != len(new):
                raise ValueError(f"the encoder returned {len(encoded)} features for {len(new)} photos")
            self._features.update(zip(new.keys(), encoded))
        if not photos:
            return np.zeros((0, 0))
        return np.stack([self._features[key] for key, _ in photos])

    def scores(self, task: TaskContext, photos: Sequence[Photo]) -> np.ndarray:
        """(N,) cos(photo feature, task feature), in [-1, 1], in the order given."""
        if not photos:
            return np.zeros(0)
        features = self.features(photos)
        if features.shape[1] != task.feature.size:
            raise ValueError(
                f"photo features have {features.shape[1]} numbers, the task feature has "
                f"{task.feature.size}. Both must come from the same encoder"
            )
        return features @ task.feature

    def ranked(self, task: TaskContext, photos: Sequence[Photo]) -> List[Tuple[Hashable, float]]:
        """(key, score) pairs, the highest score first. Equal scores keep the
        order given."""
        scores = self.scores(task, photos)
        order = sorted(range(len(photos)), key=lambda i: -scores[i])
        return [(photos[i][0], float(scores[i])) for i in order]

    def forget(self, key: Hashable) -> None:
        """Drop a photo's stored feature, so it is encoded again next time."""
        self._features.pop(key, None)
