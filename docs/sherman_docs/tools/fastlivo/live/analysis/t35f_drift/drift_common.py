"""T3.5f drift-location analyses: shared bag paths and frame helpers. Builds on route_common (frozen T3.5e prototype, LEVEL=1 GRAV4=1 FLAT_MAX=0.5).
Run from a directory that holds route_common.py and a reloc/ directory with reloc_offline_prototype.py, ROS Humble sourced, T35_CONVERTER set."""
import json, os, glob, sqlite3
import numpy as np
import route_common as R
P = R.P
L = os.path.expanduser("~/rcp-Gappler/log/t59-fastlivo/log")
BAGS = {
    "run1": L + "/t35f-live-20261021/bag",
    "run2": L + "/t35f-live-20261021/run2/bag",
    "hd1": L + "/t35d-attended-20261020.raLTgE/run/bag/handdriven1",   # original bag: has /aft_mapped_to_init and /cloud_registered (the replay copy has neither)
}
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)
COL = {"run1": "#d62728", "run2": "#1f77b4", "hd1": "#2ca02c"}


def tf_inv(T):
    Ti = np.eye(4); Ti[:3, :3] = T[:3, :3].T; Ti[:3, 3] = -T[:3, :3].T @ T[:3, 3]
    return Ti


def load_frames():
    """dict label -> 4x4 transform taking that run's levelled session frame into the run 1 levelled session frame (step 0 output)."""
    d = json.load(open(os.path.join(OUT, "step0_frames.json")))
    return {k: np.array(v) for k, v in d.items()}


def apply(T, xyz):
    return xyz @ T[:3, :3].T + T[:3, 3]


def read_registered(bag, level_Rt, band=None, vox=0.05, stride=1):
    """/cloud_registered of a bag as one voxelised cloud in the run's levelled session frame (row-vector p @ Rt). Empty heartbeat messages are skipped."""
    from rclpy.serialization import deserialize_message
    from sensor_msgs.msg import PointCloud2
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = {n: i for i, n in db.execute("select id, name from topics")}[ "/cloud_registered"]
    acc, buf, n = [], [], 0
    for k, (d,) in enumerate(db.execute("select data from messages where topic_id=? order by timestamp", (tid,))):
        if k % stride:
            continue
        m = deserialize_message(bytes(d), PointCloud2)
        if m.width * m.height == 0:
            continue
        a = np.frombuffer(bytes(m.data), np.uint8).reshape(-1, m.point_step)
        xyz = np.stack([a[:, o:o + 4].copy().view(np.float32)[:, 0] for o in (0, 4, 8)], 1).astype(np.float64)
        buf.append(xyz @ level_Rt); n += 1
        if n % 150 == 0:
            acc = [P.voxel(np.vstack(acc + buf), vox)]; buf = []
    return P.voxel(np.vstack(acc + buf), vox), n
