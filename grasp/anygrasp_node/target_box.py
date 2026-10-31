"""Measure the grasp target as a box standing on the table, for MoveIt's planning scene (T1.48).

MoveIt avoids only what its planning scene holds, and the target was never in it, so the path to a
grasp pushed the box away (CODE_AUDIT A4). The wrist camera looks down at about 45 deg, so it sees
the top face and the front face but never the bottom. The box is therefore:
  footprint  the smallest turned rectangle around the points seen from above, its edges trimmed by
             target_box_edge_percentile so a few stray points beside the box can't widen it
  height     from just above the table top up to the highest points. The table height is known.
  pad        added on every side, so depth noise never makes the box smaller than the object
  gap        the box starts target_box_table_gap_m above the table. Touching counts as a collision in MoveIt, so
             a box sitting on the table slab would make every move after attaching it start in
             collision. The gripper always grasps well above the bottom 5 mm.

Points come in base_link (x, y on the table, z up), in metres.

Every threshold is in grasp/grasp_config.yaml (target_box_*), passed in by the node.

Run this file to check the fit, with those thresholds: python3 target_box.py
"""

import numpy as np


def target_box(points, table_top_z, pad, top_percentile, edge_percentile, table_gap_m, angle_step_deg):
    """Return (centre xyz, yaw in radians, size xyz) of the box, or None if no point is above the table.

    top_percentile ignores the highest few points: flying pixels at the edges can sit far above.
    edge_percentile does the same for the footprint's sides (the same idea as fit_percentile).
    ponytail: the footprint's turn is searched in angle_step_deg steps, not an exact minimum-area
    rectangle. The pad is far larger than the error."""
    above = points[points[:, 2] > table_top_z]
    if len(above) == 0:
        return None
    xy = above[:, :2]
    best = None
    for a in np.radians(np.arange(0.0, 90.0, angle_step_deg)):
        c, s = np.cos(a), np.sin(a)
        # The points in a frame turned by a: its axes are the rectangle's sides
        u = xy @ np.array([[c, -s], [s, c]])
        lo, hi = np.percentile(u, [edge_percentile, 100 - edge_percentile], axis=0)
        area = np.prod(hi - lo)
        if best is None or area < best[0]:
            best = (area, a, lo, hi)
    _, yaw, lo, hi = best
    mid = (lo + hi) / 2
    c, s = np.cos(yaw), np.sin(yaw)
    centre_xy = np.array([[c, -s], [s, c]]) @ mid
    bottom = table_top_z + table_gap_m
    top = np.percentile(above[:, 2], top_percentile) + pad
    if top <= bottom:
        return None
    centre = np.array([centre_xy[0], centre_xy[1], (bottom + top) / 2])
    size = np.array([hi[0] - lo[0] + 2 * pad, hi[1] - lo[1] + 2 * pad, top - bottom])
    return centre, float(yaw), size


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
    from gappler_common import config
    cfg = config("grasp", "anygrasp_detection_node")
    BOX = dict(top_percentile=cfg["target_box_top_percentile"], edge_percentile=cfg["target_box_edge_percentile"],
               table_gap_m=cfg["target_box_table_gap_m"], angle_step_deg=cfg["target_box_angle_step_deg"])
    TABLE_GAP = BOX["table_gap_m"]
    rng = np.random.default_rng(0)
    table = 0.12
    # The test box from 2026-10-26: 6 x 7.5 x 14 cm, turned 30 deg, standing at (-0.5, 0.1).
    # Points on its top face and one side face only, as the wrist camera sees it.
    yaw_true, l, w, h = np.radians(30), 0.06, 0.075, 0.14
    top = np.column_stack([rng.uniform(-l / 2, l / 2, 500), rng.uniform(-w / 2, w / 2, 500),
                           np.full(500, h)])
    side = np.column_stack([np.full(500, l / 2), rng.uniform(-w / 2, w / 2, 500),
                            rng.uniform(0, h, 500)])
    local = np.vstack([top, side])
    c, s = np.cos(yaw_true), np.sin(yaw_true)
    world = local @ np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]]) + [-0.5, 0.1, table]

    centre, yaw, size = target_box(world, table, 0.0, **BOX)
    # The edge trim also drops real edge points, so a clean box comes out a few mm small. The pad
    # (1 cm on each side) covers that.
    assert np.allclose(sorted(size[:2]), [l, w], atol=0.005), ("footprint must be 6 x 7.5 cm", size)
    assert abs(size[2] - (h - TABLE_GAP)) < 0.003, ("height from the gap above the table", size)
    assert np.allclose(centre, [-0.5, 0.1, table + (TABLE_GAP + h) / 2], atol=0.003), ("centre", centre)
    # A box's footprint repeats every 90 deg, so compare the turn modulo 90
    assert abs((np.degrees(yaw) - 30) % 90) < 1.0 or abs((np.degrees(yaw) - 30) % 90) > 89.0, yaw

    _, _, padded = target_box(world, table, 0.01, **BOX)
    assert np.allclose(padded - size, [0.02, 0.02, 0.01]), ("pad on every side, top only", padded)

    # Flying pixels far above the box must not raise it
    stray = np.vstack([world, [[-0.5, 0.1, table + 0.5]] * 5])
    assert abs(target_box(stray, table, 0.0, **BOX)[2][2] - (h - TABLE_GAP)) < 0.005, "stray points raised the box"

    # Stray points beside the box (a mask that leaks onto the table, depth noise at the edges) must
    # not widen it. The trim drops edge_percentile of the points at each side, so that many strays.
    n = int(len(world) * BOX["edge_percentile"] / 100)
    beside = np.column_stack([rng.uniform(-0.60, -0.40, n), rng.uniform(0.0, 0.2, n),
                              np.full(n, table + 0.01)])
    _, _, wide = target_box(np.vstack([world, beside]), table, 0.0, **BOX)
    assert np.all(wide[:2] < size[:2] + 0.005), ("stray points beside the box widened it", wide, size)

    assert target_box(world[world[:, 2] < table], table, 0.01, **BOX) is None, "nothing above the table"
    print("target_box: all checks pass")
