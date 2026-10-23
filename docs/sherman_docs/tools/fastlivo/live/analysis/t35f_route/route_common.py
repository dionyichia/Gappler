"""T3.5f route analyses: shared reader and conventions. Import AFTER setting LEVEL=1 GRAV4=1 FLAT_MAX=0.5 in the environment, because the frozen
T3.5e prototype (reloc/reloc_offline_prototype.py, imported as P) reads them at import. Needs ROS Humble + nav overlay sourced, numpy, scipy.
Reader = the prototype's P.read with the numpy CustomMsg decoder (equal fields, 0.4 ms instead of 110 ms per scan): points[::pt_stride] as float64,
scan stamp = header stamp + 0.05 s + T35_DELTA, odometry from /aft_mapped_to_init. T35_CONVERTER = path of livox_custom_to_cloud.py."""
import glob, importlib.util, math, os, sqlite3, sys
import numpy as np

os.environ.setdefault("LEVEL", "1"); os.environ.setdefault("GRAV4", "1"); os.environ.setdefault("FLAT_MAX", "0.5")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "reloc"))
import reloc_offline_prototype as P  # noqa: E402
from rclpy.serialization import deserialize_message  # noqa: E402
from nav_msgs.msg import Odometry  # noqa: E402

spec = importlib.util.spec_from_file_location("c", os.environ["T35_CONVERTER"])
conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)

DELTA = float(os.environ.get("T35_DELTA", "0"))  # seconds added to every scan stamp before pairing it with a pose (0 = the prototype's own convention)
BOX = (-2.1, 3.7, -4.0, 3.7)           # the C glass box of replay A/B/C/D (odom frame)
ROOM = (-1.8, 3.5, -3.8, 3.4)          # approximate glass planes, from the dense wall bands of topdown.png; used only for a proximity distance


def read_fast(bag, scan_stride=1, pt_stride=4, t_max=None):
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = {n: i for i, n in db.execute("select id, name from topics")}
    odom = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/aft_mapped_to_init"],)):
        m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        odom.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    odom = np.array(odom); scans = []; t0 = None
    for n, (d,) in enumerate(db.execute("select data from messages where topic_id=? order by timestamp", (tid["/livox/lidar"],))):
        m = conv.decode_custom_msg_numpy(bytes(d)); s = m["sec"] + m["nanosec"] * 1e-9
        t0 = s if t0 is None else t0
        if t_max is not None and s - t0 > t_max:
            break
        if (n + 1) % scan_stride:
            continue
        a = m["array"][::pt_stride]
        scans.append((s + 0.05 + DELTA, np.stack([a["x"], a["y"], a["z"]], 1).astype(np.float64)))
    return odom, scans


def level_rot(odom):
    """The prototype's LEVEL=+1 rotation: row-vector map p' = p @ Rt removes the session's first-pose roll and pitch."""
    R0 = P.rot(odom[0, 4:8])
    r0 = math.atan2(R0[2, 1], R0[2, 2]); p0 = -math.asin(np.clip(R0[2, 0], -1, 1))
    Rx = np.array([[1, 0, 0], [0, math.cos(r0), -math.sin(r0)], [0, math.sin(r0), math.cos(r0)]])
    Ry = np.array([[math.cos(p0), 0, math.sin(p0)], [0, 1, 0], [-math.sin(p0), 0, math.cos(p0)]])
    return Ry @ Rx


def session_track(odom):
    """Per-pose position and yaw (deg) in the levelled session frame, same frame as P.to_session_frame output."""
    Rt = level_rot(odom)
    pos = odom[:, 1:4] @ Rt
    yaw = np.array([math.degrees(math.atan2((Rt.T @ P.rot(q))[1, 0], (Rt.T @ P.rot(q))[0, 0])) for q in odom[:, 4:8]])
    return pos, yaw


def glass_distance(xy):
    """Distance from points to the nearest approximate glass plane of ROOM (negative outside)."""
    x0, x1, y0, y1 = ROOM
    return np.minimum.reduce([xy[:, 0] - x0, x1 - xy[:, 0], xy[:, 1] - y0, y1 - xy[:, 1]])


def build_map(odom, scans):
    """Frozen-prototype map: voxel 0.10, normals k=12, planar mask flat <= FLAT_MAX."""
    from scipy.spatial import cKDTree
    M = P.voxel(P.to_session_frame(odom, scans)); tree = cKDTree(M)
    nrm, flat = P.normals(M, tree)
    return M, tree, nrm, flat <= P.FLAT_MAX
