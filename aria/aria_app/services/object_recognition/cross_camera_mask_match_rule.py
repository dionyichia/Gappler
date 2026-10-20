"""T8.7: which glasses mask and which wrist mask are the same object, from CLIP cosine scores.

Rule agreed with Dion, 2026-10-20 (docs/bench-runs/2026-10-20-labbox-t8.7-mask-embedding-offline.txt):
  a. scores[g, w] is the cosine of glasses mask g vs wrist mask w;
  b. drop pairs below TAU;
  c. keep pairs within DELTA of the best one left;
  d. gaze picks the glasses mask among those (the caller's pick_glasses). Gaze too far from all of
     them (pick_glasses gives None): no match, so looking away does not match another object;
  e. one wrist mask left for it: that is the match. More than one (identical wrist objects): None.

No ROS or torch here, so the check below runs anywhere:
    python aria/aria_app/services/object_recognition/cross_camera_mask_match_rule.py
"""

import logging
from typing import Callable, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# From the T8.7 offline tests: box pairs scored 0.60 to 0.64, background 0.45 to 0.52. Tune on the box.
TAU = 0.56
DELTA = 0.01


def pick_mask_pair(
    scores: np.ndarray, pick_glasses: Callable[[List[int]], Optional[int]]
) -> Optional[Tuple[int, int]]:
    """(glasses index, wrist index), or None: nothing at or above TAU, no candidate near the gaze
    (pick_glasses gave None), or a wrist tie."""
    keep = scores >= TAU
    if not keep.any():
        logger.info(f"No glasses/wrist pair at or above {TAU}")
        return None
    keep &= scores >= scores[keep].max() - DELTA
    g = pick_glasses(np.flatnonzero(keep.any(axis=1)).tolist())
    if g is None:
        return None  # pick_glasses logs why
    wrist = np.nonzero(keep[g])[0]
    if len(wrist) > 1:
        # ponytail: identical wrist objects give up; geometric tie-break is later (NEXT_STEPS 2.13).
        logger.info(f"wrist tie: glasses mask {g} matches wrist masks {wrist.tolist()}")
        return None
    return g, int(wrist[0])


if __name__ == "__main__":
    first = lambda gs: gs[0]
    last = lambda gs: gs[-1]
    # Clear winner.
    assert pick_mask_pair(np.array([[0.62, 0.50], [0.48, 0.51]]), first) == (0, 0)
    # Nothing reaches tau.
    assert pick_mask_pair(np.array([[0.55, 0.40]]), first) is None
    # Two glasses masks tie with different wrist masks: gaze decides.
    tie = np.array([[0.620, 0.40], [0.40, 0.615]])
    assert pick_mask_pair(tie, first) == (0, 0)
    assert pick_mask_pair(tie, last) == (1, 1)
    # Just outside delta: gaze is not asked to choose between them.
    assert pick_mask_pair(np.array([[0.63, 0.40], [0.40, 0.61]]), last) == (0, 0)
    # One glasses mask matches two wrist masks equally: wrist tie.
    assert pick_mask_pair(np.array([[0.60, 0.605]]), first) is None
    # Gaze far from every candidate: no match, even with a clear winner.
    assert pick_mask_pair(np.array([[0.62, 0.50]]), lambda gs: None) is None
    # Exactly tau passes.
    assert pick_mask_pair(np.array([[0.56]]), first) == (0, 0)
    print("cross_camera_mask_match_rule: all checks pass")
