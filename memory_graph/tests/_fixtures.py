"""Synthetic scenes for the stage tests. No recorded data needed."""

import numpy as np

from memory_graph.stage_types import Detections, Observation

W, H = 160, 120
K = np.array([[100.0, 0, W / 2], [0, 100.0, H / 2], [0, 0, 1]])


def pose(R=None, t=(0.0, 0.0, 0.0)):
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    T[:3, 3] = t
    return T


def rot_z(deg):
    a = np.radians(deg)
    return np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])


def rot_y(deg):
    a = np.radians(deg)
    return np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])


def dets(boxes, confs, labels, masks=None, class_ids=None):
    n = len(labels)
    return Detections(
        xyxy=np.asarray(boxes, dtype=float).reshape(-1, 4),
        conf=np.asarray(confs, dtype=float),
        class_id=np.arange(n) if class_ids is None else class_ids,
        label=labels,
        masks=None if masks is None else np.asarray(masks, dtype=bool),
    )


def patch_scene(patches, wall_depth=3.0, T_world_cam=None, noise=0.01, seed=0):
    """A wall at wall_depth with flat square patches in front of it.

    patches: list of (u0, v0, u1, v1, depth) in pixels and metres. Each patch gets
    +-noise of depth jitter so its 3D box has some thickness, as real objects do.
    Returns the Observation and one bool mask per patch.
    """
    rng = np.random.default_rng(seed)
    depth = np.full((H, W), wall_depth, dtype=np.float32)
    masks = []
    for u0, v0, u1, v1, d in patches:
        m = np.zeros((H, W), dtype=bool)
        m[v0:v1, u0:u1] = True
        depth[m] = d + rng.uniform(-noise, noise, size=m.sum())
        masks.append(m)
    rgb = np.full((H, W, 3), 128, dtype=np.uint8)
    obs = Observation(rgb=rgb, depth=depth, K=K.copy(),
                      T_world_cam=pose() if T_world_cam is None else T_world_cam, frame_id=0)
    return obs, np.array(masks, dtype=bool)


def patch_centre_cam(u0, v0, u1, v1, d):
    """Camera-frame centre of a patch's back-projected pixels."""
    us = np.arange(u0, u1, dtype=float)
    vs = np.arange(v0, v1, dtype=float)
    return np.array([(us.mean() - K[0, 2]) * d / K[0, 0], (vs.mean() - K[1, 2]) * d / K[1, 1], d])
