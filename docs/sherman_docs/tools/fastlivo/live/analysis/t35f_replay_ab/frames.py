"""T3.5f replay A/B: contact sheet of camera frames along a bag, each labelled with the recorded pose (x, y, yaw deg) at that time.
usage: frames.py OUT.png BAG_DIR N   (ROS Humble sourced)"""
import glob, math, sqlite3, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image

out, bag, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
tid = {nm: i for i, nm in db.execute("select id, name from topics")}
pose = []
for ts, d in db.execute("select timestamp, data from messages where topic_id=? order by timestamp", (tid["/aft_mapped_to_init"],)):
    m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
    pose.append((ts * 1e-9, p.x, p.y, math.degrees(math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z)))))
pose = np.array(pose)
ts_all = [r[0] for r in db.execute("select timestamp from messages where topic_id=? order by timestamp", (tid["/camera/camera/color/image_raw"],))]
want = np.linspace(ts_all[0], ts_all[-1], n + 2)[1:-1]
cols = 4; rows = (n + cols - 1) // cols
fig, axs = plt.subplots(rows, cols, figsize=(5 * cols, 3.9 * rows), squeeze=False)
for ax in axs.flat: ax.axis("off")
for k, w in enumerate(want):
    t = ts_all[int(np.argmin(np.abs(np.array(ts_all) - w)))]
    d = db.execute("select data from messages where topic_id=? and timestamp=?", (tid["/camera/camera/color/image_raw"], t)).fetchone()[0]
    m = deserialize_message(bytes(d), Image)
    a = np.frombuffer(m.data, np.uint8).reshape(m.height, m.width, -1)[:, :, :3]
    if m.encoding == "bgr8": a = a[:, :, ::-1]
    i = int(np.argmin(np.abs(pose[:, 0] - t * 1e-9)))
    ax = axs.flat[k]; ax.imshow(a); ax.set_title("t=%.0fs x%.1f y%.1f yaw%.0f" % ((t - ts_all[0]) * 1e-9, pose[i, 1], pose[i, 2], pose[i, 3]), fontsize=10)
fig.tight_layout(); fig.savefig(out, dpi=70); print("wrote", out)
