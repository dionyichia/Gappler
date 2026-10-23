"""T3.5f replay A/B: the glass/mirror removal box against where each run drove, plus how much of each scan falls outside it.
usage: glass_overlay.py OUT_PREFIX X0 X1 Y0 Y1 LABEL=BAG_DIR [...]    (ROS Humble + nav overlay sourced; T35_CONVERTER set; matplotlib on the box)
Writes OUT_PREFIX.png (density from the topdown npz files next to OUT_PREFIX's directory, box, tracks with start/end) and prints, per run: min distance of
the path to each box edge, share of non-zero LiDAR points outside the box overall and by the robot's heading (8 bins of 45 deg, 0 = +x)."""
import glob, importlib.util, math, os, sqlite3, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("m", os.path.join(here, "make_replay_bag.py")); mk = importlib.util.module_from_spec(spec); spec.loader.exec_module(mk)
spec = importlib.util.spec_from_file_location("c", os.environ["T35_CONVERTER"]); conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
out = sys.argv[1]; box = tuple(map(float, sys.argv[2:6])); runs = [a.split("=", 1) for a in sys.argv[6:]]
fig, axs = plt.subplots(1, len(runs), figsize=(8 * len(runs), 8), squeeze=False)
for ax, (label, bag) in zip(axs[0], runs):
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = {n: i for i, n in db.execute("select id, name from topics")}
    pose = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/aft_mapped_to_init"],)):
        m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        pose.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    pose = np.array(pose)
    yaw = np.degrees(np.arctan2(2 * (pose[:, 7] * pose[:, 6] + pose[:, 4] * pose[:, 5]), 1 - 2 * (pose[:, 5] ** 2 + pose[:, 6] ** 2)))
    tot = np.zeros(8); outside = np.zeros(8)
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/livox/lidar"],)):
        m = conv.decode_custom_msg_numpy(bytes(d)); a = m["array"]; a = a[(a["x"] != 0) | (a["y"] != 0) | (a["z"] != 0)]
        i = min(max(int(np.searchsorted(pose[:, 0], m["sec"] + m["nanosec"] * 1e-9)), 0), len(pose) - 1)
        keep = mk.keep_mask(np.stack([a["x"], a["y"], a["z"]], 1), pose[i, 1:8], box)
        b = int(((yaw[i] + 22.5) % 360) // 45); tot[b] += len(keep); outside[b] += (~keep).sum()
    x, y = pose[:, 1], pose[:, 2]
    edges = {"x0 (left)": x.min() - box[0], "x1 (right)": box[1] - x.max(), "y0 (bottom)": y.min() - box[2], "y1 (top)": box[3] - y.max()}
    print("== %s: path-to-box-edge minimum distances (m): %s" % (label, ", ".join("%s %.2f" % kv for kv in edges.items())))
    print("   non-zero points outside the box: %.1f %% overall; by heading bin (0=+x,45=+x+y,...): %s" % (
        100 * outside.sum() / tot.sum(), " ".join("%d:%.0f%%" % (k * 45, 100 * outside[k] / tot[k]) if tot[k] else "%d:-" % (k * 45) for k in range(8))))
    z = np.load("%s_%s.npz" % (out.replace("glass_overlay", "topdown"), label)); org, res, c = z["org"], float(z["res"]), z["cnt"]
    ax.imshow(np.log1p(c).T, origin="lower", extent=[org[0], org[0] + c.shape[0] * res, org[1], org[1] + c.shape[1] * res], cmap="gray_r", vmax=np.log1p(c).max() * 0.6)
    ax.plot([box[0], box[1], box[1], box[0], box[0]], [box[2], box[2], box[3], box[3], box[2]], "m--", lw=2, label="kept region (outside removed in C)")
    sc = ax.scatter(x, y, c=pose[:, 0] - pose[0, 0], s=3, cmap="plasma"); ax.plot(x[0], y[0], "go", ms=10); ax.plot(x[-1], y[-1], "bs", ms=10)
    ax.set_xlim(-4, 6); ax.set_ylim(-6, 6); ax.set_aspect("equal"); ax.grid(alpha=.3); ax.set_title("%s: path (colour = time s), green start, blue end" % label); ax.legend(loc="lower left")
fig.tight_layout(); fig.savefig(out + ".png", dpi=80); print("wrote", out + ".png")
