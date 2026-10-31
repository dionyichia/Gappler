# MobileSAM (vendored)

A small, fast Segment Anything model. GraRe uses it to cut out the object each grasp touches. Used through
`grasp/anygrasp_node/grare_rerank.py` (T1.61).

- Source: https://github.com/ChaoningZhang/MobileSAM, commit `f706ad9`. Apache 2.0 licence, see `LICENSE`.
- Copied unchanged: the `mobile_sam` package only. Not installed: `grare_rerank.py` puts this folder on
  `sys.path`. Needs `timm`, already in the AnyGrasp venv.
- Weights are not here: `assets/models/mobile_sam/mobile_sam.pt` (`docs/ASSETS.md`).
