"""The memory graph (M6): objects and the anchor photos that saw them.

A Python library, not a ROS node. A node will use it later (T7.2). The stages
follow HiCo-Nav's construction pipeline, S0 to S13, in
docs/hico-nav/hico-nav-github-docs/cmg_construction_pipeline.md:

    stage_types.py         the data passed between stages (S0-S9)
    config.py              every tuning constant, one place
    detection_filter.py    S2  drop detections that should never become objects
    anchor_gate.py         S3  is this photo worth keeping
    masks.py               S4 erosion, S5 mask cleanup
    image_feature.py       S6  crop, encode, normalise (the encoder is plugged in)
    clip_encoder.py        S6  the real encoder, open_clip ViT-B-32, images and text (needs torch)
    geometry.py            S7 back-projection, S8 cloud cleanup and 3D box, S9 range
    association.py         S10 overlap score and the match decision
    anchor_object_graph.py the graph: anchors, objects, the edges between them

Only anchor_object_graph.py is stdlib-only. The stage modules need numpy and
scipy, so this file imports nothing, and the graph stays usable without them.

Provisional name and home (2026-10-05). "memory_graph" is a temporary name. It
will be renamed when this code is integrated into the navigation module. Where
it lives is open decision D-MG4 in docs/MEMORY_GRAPH_DESIGN.md. Moving or
renaming the folder later means updating the `memory_graph.` imports and the
L0 line in bench/run.sh.
"""
