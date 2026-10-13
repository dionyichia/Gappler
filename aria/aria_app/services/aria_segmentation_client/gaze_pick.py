"""Which mask the user looks at. No ROS, so the recording replay tool and tests use it too (T2.9)."""

import numpy as np


def mean_gaze(samples, now: float, window_s: float):
    """Mean (x, y) of the (time, x, y) samples in the last window_s before now. None if none."""
    recent = [(x, y) for t, x, y in samples if now - window_s < t <= now]
    return tuple(np.mean(recent, axis=0)) if recent else None


def pick_mask(masks, x: float, y: float, radius: float):
    """(index, distance px) of the mask under (x, y), else of the nearest within radius.
    (None, nearest distance) if none is in range. Ties go to the earlier mask, the higher score."""
    dists = [np.hypot(*(np.nonzero(m)[::-1] - np.array([[x], [y]]))).min() if m.any() else np.inf
             for m in masks]
    if not dists:
        return None, np.inf
    i = int(np.argmin(dists))
    return (i if dists[i] <= radius else None), float(dists[i])
