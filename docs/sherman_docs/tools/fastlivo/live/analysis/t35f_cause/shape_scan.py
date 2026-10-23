"""T3.5f cause hunt: loop shape from /aft_mapped_to_init only (sqlite, no image reads). usage: shape_scan.py LABEL=BAG_DIR ..."""
import glob, math, sqlite3, sys
import numpy as np
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

for arg in sys.argv[1:]:
    label, bag = arg.split("=", 1)
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = db.execute("select id from topics where name='/aft_mapped_to_init'").fetchone()[0]
    rows = []
    for ts, data in db.execute("select timestamp, data from messages where topic_id=? order by timestamp", (tid,)):
        m = deserialize_message(bytes(data), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        roll = math.atan2(2 * (q.w * q.x + q.y * q.z), 1 - 2 * (q.x * q.x + q.y * q.y))
        pitch = math.asin(max(-1, min(1, 2 * (q.w * q.y - q.z * q.x))))
        rows.append((ts * 1e-9, p.x, p.y, p.z, yaw, roll, pitch))
    a = np.array(rows); t = a[:, 0] - a[0, 0]; x, y = a[:, 1] - a[0, 1], a[:, 2] - a[0, 2]
    yaw = np.unwrap(a[:, 4]); dy = yaw - yaw[0]
    area = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
    print("=" * 10, label, "poses", len(a))
    print(" path bbox x[%.2f,%.2f] y[%.2f,%.2f]; signed area %.2f m2 (+ = counter-clockwise); unwrapped yaw: final %+.1f deg, min %+.1f, max %+.1f" % (
        x.min(), x.max(), y.min(), y.max(), area, math.degrees(dy[-1]), math.degrees(dy.min()), math.degrees(dy.max())))
    print(" total turning (sum |dyaw|) %.0f deg; roll/pitch deg at start %.2f/%.2f, end %.2f/%.2f, max |roll| %.2f max |pitch| %.2f" % (
        math.degrees(np.abs(np.diff(yaw)).sum()), math.degrees(a[0, 5]), math.degrees(a[0, 6]), math.degrees(a[-1, 5]), math.degrees(a[-1, 6]),
        math.degrees(np.abs(a[:, 5]).max()), math.degrees(np.abs(a[:, 6]).max())))
    for f in np.linspace(0, 1, 11):
        i = min(int(f * (len(a) - 1)), len(a) - 1)
        print("  t=%5.1f s  x %+6.2f y %+6.2f z %+6.3f  yaw %+7.1f deg  roll %+5.2f pitch %+5.2f" % (t[i], x[i], y[i], a[i, 3] - a[0, 3], math.degrees(dy[i]), math.degrees(a[i, 5]), math.degrees(a[i, 6])))
