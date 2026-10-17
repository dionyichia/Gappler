"""Which mask the user looks at. No ROS, so the recording replay tool and tests use it too (T2.9)."""

from collections import Counter

import numpy as np


def vote(masks, points, radius: float, min_share: float):
    """Which mask most gaze points fall on (T2.20). Each (x, y) point votes for the mask
    pick_mask gives it, or for none. (index, share, mean distance px of its votes) for the mask
    with the most votes, if its share of all points is at least min_share, else with None in
    place of the index. With no votes at all: (None, 0.0, nearest distance px). Ties go to the
    earlier mask, the higher score.
    Unlike a mean, two fixations on two objects do not average to a point between them."""
    picks = [pick_mask(masks, x, y, radius) for x, y in points]
    votes = Counter(i for i, _ in picks if i is not None)
    if not votes:
        return None, 0.0, min((d for _, d in picks), default=np.inf)
    i = min(votes, key=lambda j: (-votes[j], j))
    share = votes[i] / len(points)
    dist = float(np.mean([d for j, d in picks if j == i]))
    return (i if share >= min_share else None), share, dist


def pick_mask(masks, x: float, y: float, radius: float):
    """(index, distance px) of the mask under (x, y), else of the nearest within radius.
    (None, nearest distance) if none is in range. Ties go to the earlier mask, the higher score."""
    dists = [np.hypot(*(np.nonzero(m)[::-1] - np.array([[x], [y]]))).min() if m.any() else np.inf
             for m in masks]
    if not dists:
        return None, np.inf
    i = int(np.argmin(dists))
    return (i if dists[i] <= radius else None), float(dists[i])
