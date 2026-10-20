#!/usr/bin/env python3
"""Reload without SLAM Toolbox's matcher: register the spin-corrected 2D scans onto a saved map image with a likelihood-field fit.
Isolates the map from the reload matcher. Box (needs the bag), numpy, scipy, PIL. Map frame = the odom frame of the mapping run's start.
The query: first N seconds of /livox/lidar, points with z_odom in [0.1, 0.7] (the SLAM scan's height band around the LiDAR at 0.2 m), through the
bridge's odom -> robot_base_link, expressed in the spin start's odom frame; the fit finds that odom frame's pose in the map.
usage: reload_on_map.py MAP_DIR [MAP_DIR ...] [--seconds 3] [--bag PATH] [--bridge PATH]"""
import argparse, importlib.util, math, re
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, map_coordinates
from scipy.optimize import minimize
import rosbag2_py
from rclpy.serialization import deserialize_message
from rosidl_runtime_py.utilities import get_message
from nav_msgs.msg import Odometry

ap = argparse.ArgumentParser(); ap.add_argument("maps", nargs="+"); ap.add_argument("--seconds", type=float, default=3.0)
ap.add_argument("--bag", default=str(Path.home() / "rcp-Gappler/log/t59-fastlivo/log/t35d-attended-20261020.raLTgE/spin-corrected/bag"))
ap.add_argument("--bridge", default=str(Path.home() / "rcp-Gappler/log/t35e-reloc/mirror2/nav/robot_slam/scripts/fastlivo_odom_bridge.py"))
args = ap.parse_args()
spec = importlib.util.spec_from_file_location("b", args.bridge); b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)
TAPE = (2.00, 1.16); GUESS = (2.0, 1.2, 0.0)
OFFSET = np.array([0.18, 0.0, 0.2])  # robot_base_link -> livox_frame (geometry.lidar_mount)

# --- query points in the spin start's odom frame
r = rosbag2_py.SequentialReader()
r.open(rosbag2_py.StorageOptions(uri=args.bag, storage_id="sqlite3"), rosbag2_py.ConverterOptions("", ""))
types = {t.name: t.type for t in r.get_all_topics_and_types()}
r.set_filter(rosbag2_py.StorageFilter(topics=["/aft_mapped_to_init", "/livox/lidar"]))
core = b.OdomFromMapper((0.191, 0.02329, 0.15588)); poses, scans = [], []
while r.has_next():
    t, d, rec = r.read_next(); rec *= 1e-9
    if t == "/aft_mapped_to_init":
        o = deserialize_message(d, Odometry); p, q = o.pose.pose.position, o.pose.pose.orientation
        pos, quat = core.update((p.x, p.y, p.z), (q.x, q.y, q.z, q.w)); poses.append((rec, np.array(pos), np.array(b.quat_to_mat(quat))))
    else:
        m = deserialize_message(d, get_message(types[t])); scans.append((rec, np.array([(q.x, q.y, q.z) for q in m.points], np.float64)))
t0 = scans[0][0]; pts = []
for rec, p_l in scans:
    if rec - t0 > args.seconds:
        break
    i = min(range(len(poses)), key=lambda k: abs(poses[k][0] - (rec + 0.1)))  # the pose closest to the scan end
    _, tb, Rb = poses[i]
    p_b = p_l + OFFSET; p_o = p_b @ Rb.T + tb
    keep = (p_o[:, 2] >= 0.1) & (p_o[:, 2] <= 0.7) & (np.hypot(p_l[:, 0], p_l[:, 1]) >= 0.5) & (np.hypot(p_l[:, 0], p_l[:, 1]) <= 20)
    pts.append(p_o[keep][:, :2])
Q = np.vstack(pts); print("query: %d points from %d scans in the first %.1f s, odom frame" % (len(Q), int(sum(1 for s in scans if s[0] - t0 <= args.seconds)), args.seconds))

for mdir in map(Path, args.maps):
    yaml = (mdir / "map/map.yaml").read_text(); res = float(re.search(r"resolution:\s*([\d.]+)", yaml).group(1))
    ox, oy = map(float, re.search(r"origin:\s*\[([-\d.e]+),\s*([-\d.e]+)", yaml).groups())
    img = np.array(Image.open(mdir / "map/map.pgm")); H, W = img.shape
    dt = distance_transform_edt(img != 0) * res   # metres to the nearest occupied cell

    def cost(v, trunc=0.3):
        x, y, yaw = v; c, s = math.cos(yaw), math.sin(yaw)
        mx = Q[:, 0] * c - Q[:, 1] * s + x; my = Q[:, 0] * s + Q[:, 1] * c + y
        col = (mx - ox) / res - 0.5; row = (H - 1) - ((my - oy) / res - 0.5)
        d = map_coordinates(dt, [row, col], order=1, mode="nearest")
        return float(np.mean(np.minimum(d, trunc) ** 2))
    best = None
    for dx in np.arange(-0.6, 0.61, 0.1):
        for dy in np.arange(-0.6, 0.61, 0.1):
            for dyaw in np.radians(np.arange(-10, 10.1, 2.5)):
                v = (GUESS[0] + dx, GUESS[1] + dy, dyaw); c0 = cost(v)
                if best is None or c0 < best[0]: best = (c0, v)
    sol = minimize(cost, best[1], method="Powell", options={"xtol": 1e-4, "ftol": 1e-9})
    x, y, yaw = sol.x; err = math.hypot(x - TAPE[0], y - TAPE[1])
    c, s = math.cos(yaw), math.sin(yaw)
    mx = Q[:, 0] * c - Q[:, 1] * s + x; my = Q[:, 0] * s + Q[:, 1] * c + y
    d = map_coordinates(dt, [(H - 1) - ((my - oy) / res - 0.5), (mx - ox) / res - 0.5], order=1, mode="nearest")
    print("%-16s fit x %.3f y %.3f yaw %+.2f deg | error vs tape %.3f m (dx %+.3f dy %+.3f) | residual rms %.3f m, points within 0.10 m %.2f | guess cost %.4f -> %.4f" % (
        mdir.name, x, y, math.degrees(yaw), err, x - TAPE[0], y - TAPE[1], math.sqrt(np.mean(np.minimum(d, 0.3) ** 2)), float((d < 0.1).mean()), cost(GUESS), sol.fun))
