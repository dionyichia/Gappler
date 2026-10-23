#!/usr/bin/env python3
"""Overlay a saved 2D SLAM map on the 2D projection of the saved 3D PCD, in the same frame, and measure any warp. Box or Mac with numpy, scipy, PIL.
PCD frame camera_init -> odom (the base at startup, sidecar camera_init_to_odom) -> map (map_to_odom at save, sidecar). Height band: the SLAM scan
saw z in [-0.1, 0.5] m around the LiDAR, which sits 0.2 m above robot_base_link, so z_odom in [0.1, 0.7].
usage: overlay_pcd.py SESSION_DIR [OUT_PNG]   (SESSION_DIR has result.json and map/map.pgm, map/map.yaml, map/cloud_registered.pcd)"""
import json, math, re, sys
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, shift as nd_shift

d = Path(sys.argv[1]); outpng = Path(sys.argv[2]) if len(sys.argv) > 2 else d / "overlay.png"
res_json = json.loads((d / "result.json").read_text())
yaml = (d / "map/map.yaml").read_text()
res = float(re.search(r"resolution:\s*([\d.]+)", yaml).group(1)); ox, oy = map(float, re.search(r"origin:\s*\[([-\d.e]+),\s*([-\d.e]+)", yaml).groups())
img = np.array(Image.open(d / "map/map.pgm")); H, W = img.shape; slam = img == 0


def rot(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


raw = (d / "map/cloud_registered.pcd").read_bytes(); k = raw.index(b"DATA binary\n") + len(b"DATA binary\n")
pts = np.frombuffer(raw[k:], "<f4").reshape(-1, 3).astype(np.float64)
ci = res_json["camera_init_to_odom"]; R_ci = rot(ci["quat_xyzw"]); t_ci = np.array(ci["xyz"])
p_odom = (pts - t_ci) @ R_ci                      # R^T (p - t)
mo = res_json["map_to_odom_at_save"]; p_map = p_odom @ rot(mo["quat_xyzw"]).T + np.array([mo["x"], mo["y"], mo["z"]])
band = (p_odom[:, 2] >= 0.1) & (p_odom[:, 2] <= 0.7)
q = p_map[band]
ix = np.floor((q[:, 0] - ox) / res).astype(int); iy = (H - 1) - np.floor((q[:, 1] - oy) / res).astype(int)
ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
cnt = np.zeros((H, W), int); np.add.at(cnt, (iy[ok], ix[ok]), 1)
pcd = cnt >= 2
print("%s: map %dx%d at %.2f m, origin (%.2f, %.2f). PCD %d points, %d in the height band, %d inside the map; PCD occupied cells %d, SLAM occupied cells %d" % (
    d.name, W, H, res, ox, oy, len(pts), int(band.sum()), int(ok.sum()), int(pcd.sum()), int(slam.sum())))


def prf(a, b, tol):
    bd = binary_dilation(b, iterations=tol) if tol else b
    ad = binary_dilation(a, iterations=tol) if tol else a
    return (a & bd).sum() / max(a.sum(), 1), (b & ad).sum() / max(b.sum(), 1)   # share of a explained by b, share of b explained by a
for tol in (0, 1, 2, 4):
    p, r_ = prf(pcd, slam, tol)
    print("  tolerance %d cell(s) = %.2f m: share of PCD cells explained by the SLAM map %.2f | share of SLAM cells explained by the PCD %.2f" % (tol, tol * res, p, r_))
# global alignment search: shift (dx, dy cells) and rotate (deg) the PCD raster to best explain it within 1 cell of the SLAM map
slam_d = binary_dilation(slam, iterations=1); best = (-1, 0, 0, 0)
ys, xs = np.nonzero(pcd); cx, cy = W / 2, H / 2
for yaw in np.arange(-6, 6.1, 1.0):
    a = math.radians(yaw); c, s_ = math.cos(a), math.sin(a)
    xr = (xs - cx) * c - (ys - cy) * s_ + cx; yr = (xs - cx) * s_ + (ys - cy) * c + cy
    for dx in range(-20, 21, 2):
        for dy in range(-20, 21, 2):
            xi = np.round(xr + dx).astype(int); yi = np.round(yr + dy).astype(int); m = (xi >= 0) & (xi < W) & (yi >= 0) & (yi < H)
            sc = slam_d[yi[m], xi[m]].sum() / len(xs)
            if sc > best[0]: best = (sc, yaw, dx, dy)
base = slam_d[ys, xs].sum() / len(xs)
print("  global rigid search: explained share %.3f with no shift, best %.3f at yaw %+.0f deg, dx %+d dy %+d cells (%.2f, %.2f m; image rows grow downward)" % (base, best[0], best[1], best[2], best[3], best[2] * res, -best[3] * res))
# local warp: best (dx, dy) per tile of the occupied area
print("  local shifts per tile (cells; one cell = %.2f m): shift that best lines the PCD up with the SLAM map" % res)
rows = []
th, tw = H // 5, W // 3
for ty in range(5):
    line = []
    for tx in range(3):
        sl = (slice(ty * th, (ty + 1) * th), slice(tx * tw, (tx + 1) * tw))
        pc, sm = pcd[sl], slam_d[sl]
        if pc.sum() < 150:
            line.append("   --   "); continue
        yy, xx = np.nonzero(pc); bestt = (-1, 0, 0)
        for dx in range(-10, 11):
            for dy in range(-10, 11):
                xi, yi = xx + dx, yy + dy; m = (xi >= 0) & (xi < tw) & (yi >= 0) & (yi < th)
                sc = sm[yi[m], xi[m]].sum() / len(xx)
                if sc > bestt[0]: bestt = (sc, dx, dy)
        line.append("%+3d,%+3d (%.2f)" % (bestt[1], bestt[2], bestt[0]))
    print("    row %d: %s" % (ty, " | ".join(line)))
rgb = np.full((H, W, 3), 255, np.uint8)
rgb[binary_dilation(pcd)] = (255, 150, 150); rgb[slam] = (30, 30, 30); rgb[slam & binary_dilation(pcd)] = (150, 0, 150)
Image.fromarray(rgb).save(outpng); print("  wrote", outpng, "(black: SLAM map, pink: PCD projection, purple: both)")
