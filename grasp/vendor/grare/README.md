# GraRe (vendored)

GraRe re-ranks a grasp detector's grasps with a learned score (arXiv 2608.00946). Used by
`grasp/anygrasp_node/grare_rerank.py` (T1.61).

- Source: https://github.com/Minakanmi-Yuki/grare, commit `86a2361`. MIT licence, see `LICENSE`.
- Copied unchanged: the `grare` package and `configs/_base.yaml` (its SAM prompt settings). Nothing else
  from the repo. Not installed: `grare_rerank.py` puts this folder on `sys.path`.
- Weights are not here: `assets/models/grare/gn_realsense_best.pt` (`docs/ASSETS.md`).
