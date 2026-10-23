"""T3.5f replay A/B: top-down LiDAR density + mean reflectivity in the odom frame, with the recorded pose track.
usage: topdown.py OUT_PREFIX LABEL=BAG_DIR [...]   (ROS Humble + nav overlay sourced; T35_CONVERTER = livox_custom_to_cloud.py)
Points are placed with the bag's own /aft_mapped_to_init (IMU body in the init frame) and the staged LiDAR->IMU extrinsic; one pose per scan
(no intra-scan deskew), so this is a picture for locating surfaces, not a measurement. Slice: z within [-0.3, 1.2] m of the sensor."""
import glob, importlib.util, os, sqlite3, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

spec = importlib.util.spec_from_file_location("c", os.environ["T35_CONVERTER"])
conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
T_IL = np.array([-0.011, -0.02329, 0.04412])  # extrin_calib.extrinsic_T, R = identity
RES = 0.05


def quat_to_R(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def load(bag):
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = {n: i for i, n in db.execute("select id, name from topics")}
    pose = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/aft_mapped_to_init"],)):
        m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        pose.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    pose = np.array(pose)
    scans = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/livox/lidar"],)):
        m = conv.decode_custom_msg_numpy(bytes(d)); scans.append((m["sec"] + m["nanosec"] * 1e-9, m["array"]))
    return pose, scans


def accumulate(pose, scans, shape, org):
    cnt = np.zeros(shape); refl = np.zeros(shape)
    for st, a in scans:
        i = int(np.searchsorted(pose[:, 0], st)); i = min(max(i, 0), len(pose) - 1)
        R = quat_to_R(pose[i, 4:8]); t = pose[i, 1:4]
        ok = (a["x"] != 0) | (a["y"] != 0)
        p = np.stack([a["x"], a["y"], a["z"]], 1)[ok].astype(float); r = a["refl"][ok]
        keep = (p[:, 2] > -0.3) & (p[:, 2] < 1.2); p, r = p[keep], r[keep]
        w = (R @ (p + T_IL).T).T + t
        ix = ((w[:, 0] - org[0]) / RES).astype(int); iy = ((w[:, 1] - org[1]) / RES).astype(int)
        g = (ix >= 0) & (iy >= 0) & (ix < shape[0]) & (iy < shape[1])
        np.add.at(cnt, (ix[g], iy[g]), 1); np.add.at(refl, (ix[g], iy[g]), r[g])
    return cnt, refl


out = sys.argv[1]; runs = [a.split("=", 1) for a in sys.argv[2:]]
data = {l: load(b) for l, b in runs}
allxy = np.concatenate([d[0][:, 1:3] for d in data.values()]); lo = allxy.min(0) - 8; hi = allxy.max(0) + 8
shape = tuple(((hi - lo) / RES).astype(int)); org = lo
fig, axs = plt.subplots(2, len(runs), figsize=(7 * len(runs), 12), squeeze=False)
for k, (l, _) in enumerate(runs):
    pose, scans = data[l]; cnt, refl = accumulate(pose, scans, shape, org)
    ext = [org[0], org[0] + shape[0] * RES, org[1], org[1] + shape[1] * RES]
    np.savez_compressed("%s_%s.npz" % (out, l), cnt=cnt, refl=refl, org=org, res=RES, pose=pose)
    for r, (title, img, cmap) in enumerate([("log density", np.log1p(cnt).T, "gray_r"),
                                            ("mean reflectivity (cells >=3 pts)", np.where(cnt >= 3, refl / np.maximum(cnt, 1), np.nan).T, "viridis")]):
        ax = axs[r][k]; ax.imshow(img, origin="lower", extent=ext, cmap=cmap)
        ax.plot(pose[:, 1], pose[:, 2], "r-", lw=1); ax.plot(*pose[0, 1:3], "go", ms=8); ax.plot(*pose[-1, 1:3], "bs", ms=8)
        ax.set_title("%s: %s (green start, blue end)" % (l, title)); ax.set_aspect("equal"); ax.grid(alpha=.3)
        ax.set_xlim(pose[:, 1].min() - 6, pose[:, 1].max() + 6); ax.set_ylim(pose[:, 2].min() - 6, pose[:, 2].max() + 6)
fig.tight_layout(); fig.savefig(out + ".png", dpi=90)
print("wrote", out + ".png")
