"""T3.5f replay A/B: return-to-start error of a pose track. First-to-last difference of the mapper's own odometry (frame = mapper origin).
usage: closure.py NAME=SOURCE [...]     SOURCE is a replay's evidence/odom_poses.csv, or bag:BAG_DIR for the recorded /aft_mapped_to_init (needs ROS Humble sourced)
Prints, per source: poses, path length, horizontal / vertical closure, yaw change first to last, closure as a share of path."""
import csv, math, sys


def yaw(q):
    x, y, z, w = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def rows_csv(path):
    with open(path) as f:
        return [tuple(float(v) for v in r.values()) for r in csv.DictReader(f)]


def rows_bag(bag):
    import glob, sqlite3
    from rclpy.serialization import deserialize_message
    from nav_msgs.msg import Odometry
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = db.execute("select id from topics where name='/aft_mapped_to_init'").fetchone()[0]
    out = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid,)):
        m = deserialize_message(bytes(d), Odometry); p, q = m.pose.pose.position, m.pose.pose.orientation
        out.append((m.header.stamp.sec + m.header.stamp.nanosec * 1e-9, p.x, p.y, p.z, q.x, q.y, q.z, q.w))
    return out


def closure(rows):
    a, b = rows[0], rows[-1]
    path = sum(math.hypot(r[1] - p[1], r[2] - p[2]) for p, r in zip(rows, rows[1:]))
    h = math.hypot(b[1] - a[1], b[2] - a[2]); dyaw = math.degrees((yaw(b[4:8]) - yaw(a[4:8]) + math.pi) % (2 * math.pi) - math.pi)
    return {"poses": len(rows), "path_m": path, "horizontal_m": h, "vertical_m": b[3] - a[3], "yaw_deg": dyaw, "pct_of_path": 100 * h / path if path else float("nan")}


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        name, src = arg.split("=", 1)
        c = closure(rows_bag(src[4:]) if src.startswith("bag:") else rows_csv(src))
        print("%-28s poses %5d  path %6.2f m  closure %.3f m horizontal, %+.3f m vertical, yaw %+.1f deg  (%.2f %% of path)" % (
            name, c["poses"], c["path_m"], c["horizontal_m"], c["vertical_m"], c["yaw_deg"], c["pct_of_path"]))
