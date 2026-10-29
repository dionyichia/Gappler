"""Remove table and stray pixels from the object mask before AnyGrasp and the MoveIt box see it (T1.60).

SAM's mask can spill past the object's edge onto the table behind it. Those table points then
count as object: on capture A they stretched the MoveIt box from about 8.6 to 22 cm, because the
camera reads the table 1.5 to 2.5 cm high and the fixed table_top_z cut let them through.

This works in the camera frame, so a calibration error cannot move a cutoff:
  1. table   find the flat surface around the mask (the mask itself left out) that faces up.
             "Up" comes from TF and only has to be right within denoise_max_tilt_deg. RANSAC: try many
             random sets of 3 points, keep the plane most points lie on, then refine it.
  2. remove  drop mask pixels on the table (within a noise-scaled band) or below it.
  3. split   neighbouring pixels with nearly the same depth are one surface. A depth jump starts
             a new one. A leaked table strip sits well behind the object, so it ends up separate.
             Keep the biggest surface, plus any other within denoise_merge_gap_m of it (an object cut in two
             by something thin in front of it).
  4. reject  return None when the table or the object cannot be trusted. The node skips the
             frame and waits for the next one.

Known limit: a mask that spills onto another object touching this one, at the same depth, is not
caught (no depth jump to split on). Evidence: docs/dion_docs/local/experiments/T1.51_denoise_point_cloud.

Run this file to check it, with the thresholds from grasp_config.yaml: python3 denoise_point_cloud.py
"""

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

# Every threshold lives in grasp/grasp_config.yaml (anygrasp_detection_node, keys denoise_*). The node
# passes them in as cfg, without the denoise_ prefix.


def _sigma(z, cfg):
    """Depth noise (m) at depth z: grows with depth squared."""
    return cfg["depth_noise_at_half_metre_m"] * (z / 0.5) ** 2


def _band(z, cfg):
    """How far (m) from the plane a point may lie and still count as table."""
    return np.clip(cfg["table_band_sigmas"] * _sigma(z, cfg), cfg["table_band_min_m"], cfg["table_band_max_m"])


def _fit_plane(P, up, rng, cfg):
    """Plane n.p + d = 0 with n within max_tilt_deg of up. Returns (n, d, inliers, rms) or None."""
    S = P[rng.choice(len(P), min(len(P), cfg["ransac_sample_points"]), replace=False)]
    band = _band(S[:, 2], cfg)
    cos_tilt = np.cos(np.radians(cfg["max_tilt_deg"]))
    best, best_k = None, 0
    for _ in range(cfg["ransac_iterations"]):
        a, b, c = S[rng.choice(len(S), 3, replace=False)]
        n = np.cross(b - a, c - a)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            continue
        n = n / norm if n @ up > 0 else -n / norm
        if n @ up < cos_tilt:
            continue
        k = np.sum(np.abs(S @ n - n @ a) < band)
        if k > best_k:
            best, best_k = (n, -n @ a), k
    if best is None:
        return None
    n, d = best
    for _ in range(cfg["refine_passes"]):  # least squares on the inliers of the whole region
        inl = np.abs(P @ n + d) < _band(P[:, 2], cfg)
        c = P[inl].mean(axis=0)
        n = np.linalg.svd(P[inl] - c, full_matrices=False)[2][2]
        n = n if n @ up > 0 else -n
        d = -n @ c
    return n, d, inl, float(np.sqrt(np.mean((P[inl] @ n + d) ** 2)))


def _surfaces(valid, z, step_rel):
    """Label 4-connected pixels of `valid` whose neighbour depth step is under step_rel * z."""
    idx = -np.ones(valid.shape, int)
    idx[valid] = np.arange(valid.sum())
    rows, cols = [], []
    for dy, dx in ((0, 1), (1, 0)):
        h, w = valid.shape[0] - dy, valid.shape[1] - dx
        za, zb = z[:h, :w], z[dy:, dx:]
        ok = valid[:h, :w] & valid[dy:, dx:] & (np.abs(za - zb) < step_rel * np.minimum(za, zb))
        rows.append(idx[:h, :w][ok])
        cols.append(idx[dy:, dx:][ok])
    r, c = np.concatenate(rows), np.concatenate(cols)
    n = int(valid.sum())
    return connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)[1]


def drop_table_and_stray_pixels(points, mask, up, cfg, rng=None):
    """Keep only the object's pixels of a SAM mask, using the depth behind it.

    points  HxWx3 camera-frame points in metres (z = 0 where depth is missing)
    mask    HxW bool, SAM's mask
    up      unit vector, base_link's up in the camera frame (from TF)
    cfg     the denoise_* values of grasp_config.yaml, without the prefix
    Returns (object HxW bool mask or None, reason string)."""
    rng = rng or np.random.default_rng(0)
    z = points[..., 2]
    valid = z > 0
    mvalid = mask & valid
    if mvalid.sum() < cfg["min_object_points"]:
        return None, "mask has too few depth points"
    # 1. Table: a window around the mask's bounding box, the mask itself (grown) left out
    ys, xs = np.nonzero(mask)
    hy = ys.max() - ys.min() + cfg["region_margin_px"]
    hx = xs.max() - xs.min() + cfg["region_margin_px"]
    win = np.zeros_like(mask)
    win[max(0, ys.min() - hy): ys.max() + hy, max(0, xs.min() - hx): xs.max() + hx] = True
    near = np.abs(z - np.median(z[mvalid])) < cfg["region_depth_m"]
    region = win & valid & near & ~ndimage.binary_dilation(mask, iterations=cfg["mask_grow_px"])
    fit = _fit_plane(points[region], up, rng, cfg) if region.sum() >= cfg["min_table_points"] else None
    if fit is None:
        return None, "no table near the expected up"
    n, d, inl, rms = fit
    tilt = np.degrees(np.arccos(np.clip(n @ up, -1.0, 1.0)))
    if tilt > cfg["max_tilt_deg"]:  # the refinement can drift to a plane the samples would not accept
        return None, f"table {tilt:.0f} deg off TF up"
    if inl.sum() < cfg["min_table_points"] or rms > cfg["max_table_rms_m"]:
        return None, f"table not trustworthy ({inl.sum()} points, rms {rms * 1000:.1f} mm)"
    # 2. Remove what lies on or below the table
    k = cfg["remove_band_sigmas"]
    above = mvalid & (points @ n + d > np.maximum(k * _sigma(z, cfg), max(k * rms, cfg["table_band_min_m"])))
    if above.sum() < cfg["min_object_points"]:
        return None, "nothing above the table in the mask"
    # 3. Split by depth jumps, keep the biggest surface and any close to it
    lab = _surfaces(above, z, cfg["depth_step_rel"])
    counts = np.bincount(lab)
    main = int(np.argmax(counts))
    P = points[above]
    tree = cKDTree(P[lab == main])
    gap = cfg["merge_gap_m"]
    kept = [main] + [int(k) for k in np.argsort(-counts)[1:] if counts[k] >= cfg["min_surface_pixels"]
                     and tree.query(P[lab == k], distance_upper_bound=gap)[0].min() < gap]
    keep = np.isin(lab, kept)
    out = np.zeros_like(mask)
    out[above] = keep
    # 4. Can the result be trusted
    if out.sum() < cfg["min_object_points"]:
        return None, "too few object pixels left"
    if out.sum() < cfg["min_kept_frac"] * mvalid.sum():
        return None, f"mask is mostly not the object (kept {out.sum() / mvalid.sum():.0%})"
    if keep.sum() < cfg["min_main_frac"] * len(keep):
        return None, f"object splits into several surfaces (kept {keep.sum() / len(keep):.0%})"
    return out, f"ok: dropped {mvalid.sum() - out.sum()} of {mvalid.sum()} mask pixels, table tilt {tilt:.1f} deg"


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
    from gappler_common import config
    cfg = {k.removeprefix("denoise_"): v for k, v in config("grasp", "anygrasp_detection_node").items()
           if k.startswith("denoise_")}

    # Camera 0.5 m above a table, looking down at 45 deg. A 6 x 7.4 x 14 cm box at the image centre.
    # Ray-cast, so the mask's spill above the box's top edge sees the table about 20 cm behind it.
    K = np.array([[607.0, 0, 320.0], [0, 607.0, 240.0], [0, 0, 1.0]])
    u, v = np.meshgrid(np.arange(640), np.arange(480))
    rays = np.stack([(u - 320.0) / 607.0, (v - 240.0) / 607.0, np.ones(u.shape)], -1).reshape(-1, 3)
    a = np.radians(45)
    # Camera-to-world: optical z forward and 45 deg down, x right, y down in the image
    R = np.array([[1, 0, 0], [0, -np.sin(a), np.cos(a)], [0, -np.cos(a), -np.sin(a)]], float)
    box_c, half = np.array([0.0, 0.0, 0.07]), np.array([0.03, 0.037, 0.07])
    eye = box_c - 0.5 * R[:, 2]
    d = rays @ R.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t_table = np.where(d[:, 2] < 0, -eye[2] / d[:, 2], np.inf)
        t1, t2 = (box_c - half - eye) / d, (box_c + half - eye) / d
    tn, tf = np.minimum(t1, t2).max(1), np.maximum(t1, t2).min(1)
    t_box = np.where((tf >= tn) & (tn > 0), tn, np.inf)
    is_box = (t_box < t_table).reshape(480, 640)
    rng = np.random.default_rng(1)
    zc = np.minimum(t_box, t_table).reshape(480, 640)  # optical z equals t (ray z is 1)
    zc = zc + rng.normal(0, 1, zc.shape) * _sigma(zc, cfg)
    pts = np.stack([(u - 320.0) * zc / 607.0, (v - 240.0) * zc / 607.0, zc], -1)
    up_cam = R.T @ [0, 0, 1.0]

    # Spill: 15 px of table above the box's top edge, about 10% of the mask
    rows = np.nonzero(is_box.any(1))[0]
    spill = ndimage.binary_dilation(is_box, iterations=15) & ~is_box & (v < rows.min() + 15)
    assert spill.sum() > 0.05 * is_box.sum(), ("spill too small to test", spill.sum(), is_box.sum())
    out, why = drop_table_and_stray_pixels(pts, is_box | spill, up_cam, cfg)
    assert out is not None, why
    assert not (out & spill).any(), ("table spill kept", (out & spill).sum())
    assert (out & is_box).sum() > 0.95 * is_box.sum(), ("box pixels lost", (out & is_box).sum(), is_box.sum())

    # A mask on the table only has nothing above the table
    assert drop_table_and_stray_pixels(pts, spill | (ndimage.binary_dilation(spill, iterations=20) & ~is_box), up_cam, cfg)[0] is None

    # TF 30 deg wrong: no table where TF says up is, so the frame is refused
    c, s = np.cos(np.radians(30)), np.sin(np.radians(30))
    bad_up = np.array([[1, 0, 0], [0, c, -s], [0, s, c]]) @ up_cam
    assert drop_table_and_stray_pixels(pts, is_box | spill, bad_up, cfg)[0] is None, "a 30 deg TF error was accepted"

    # A mask with no depth behind it
    assert drop_table_and_stray_pixels(np.zeros_like(pts), is_box, up_cam, cfg)[0] is None
    print("denoise_point_cloud: all checks pass")
