"""T3.5f cause hunt: how hard was the base pushed (IMU), and how full are the coloured clouds. usage: motion_scan.py LABEL=BAG_DIR ..."""
import glob, sqlite3, sys
import numpy as np
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import Imu, PointCloud2

for arg in sys.argv[1:]:
    label, bag = arg.split("=", 1)
    db = sqlite3.connect("file:%s?mode=ro" % glob.glob(bag + "/*.db3")[0], uri=True)
    tid = {n: i for i, n in db.execute("select id, name from topics")}
    imu = np.array([(lambda m: (m.angular_velocity.x, m.angular_velocity.y, m.angular_velocity.z, m.linear_acceleration.x, m.linear_acceleration.y, m.linear_acceleration.z))(deserialize_message(bytes(d), Imu))
                    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/livox/imu"],))])
    g = imu[:, :3]; a = imu[:, 3:]
    still = np.arange(len(imu)) < 1000  # first 5 s at 200 Hz
    gb = g[still].mean(0)
    wz = g[:, 2] - gb[2]
    acc_dev = np.linalg.norm(a, axis=1) - np.linalg.norm(a[still], axis=1).mean()
    # jerk of the horizontal acceleration at 200 Hz, smoothed over 5 samples
    sm = np.apply_along_axis(lambda c: np.convolve(c, np.ones(5) / 5, "same"), 0, a[:, :2])
    jerk = np.linalg.norm(np.diff(sm, axis=0), axis=1) * 200
    moving = np.abs(wz) > 0.02
    print("=" * 8, label, "IMU", len(imu))
    print(" gyro bias from first 5 s (rad/s): %s ; |wz| p50 %.1f p95 %.1f max %.1f deg/s (moving samples only: p50 %.1f)" % (
        np.round(gb, 4), *np.degrees(np.percentile(np.abs(wz), [50, 95])), np.degrees(np.abs(wz).max()), np.degrees(np.median(np.abs(wz[moving]))) if moving.any() else 0))
    print(" |gyro xy| (roll/pitch rates) p95 %.1f max %.1f deg/s; accel norm minus rest: p95 %.3f g max %.3f g; horiz jerk p95 %.2f max %.2f g/s" % (
        *np.degrees(np.percentile(np.linalg.norm(g[:, :2] - gb[:2], axis=1), [95])), np.degrees(np.linalg.norm(g[:, :2] - gb[:2], axis=1).max()),
        np.percentile(np.abs(acc_dev), 95), np.abs(acc_dev).max(), np.percentile(jerk, 95), jerk.max()))
    n_c = 0; n_zero = 0; pts = []
    for (d,) in db.execute("select data from messages where topic_id=? order by timestamp", (tid["/cloud_registered"],)):
        m = deserialize_message(bytes(d), PointCloud2); n = m.width * m.height; n_c += 1
        if n == 0: n_zero += 1
        else: pts.append(n)
    pts = np.array(pts)
    print(" /cloud_registered: %d msgs, %d empty (%.0f%%), non-empty median %d points, p5 %d" % (n_c, n_zero, 100 * n_zero / n_c, np.median(pts), np.percentile(pts, 5)))
