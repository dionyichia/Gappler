import math
import numpy as np
import reloc_offline_prototype as P
A = "/home/rcp2026/rcp-Gappler/log/t59-fastlivo/log/t35d-attended-20261020.raLTgE"


def fit(fl):
    for _ in range(6):  # trim to 2 sigma
        c = fl.mean(0); u, s, vt = np.linalg.svd(fl - c, full_matrices=False); n = vt[2] if vt[2][2] > 0 else -vt[2]
        d = (fl - c) @ n; keep = np.abs(d) < max(2 * d.std(), 0.006); fl = fl[keep]
    return n, d.std(), len(fl)


for name, bag in (("handdriven1", A + "/run/bag/handdriven1"), ("spin-corrected", A + "/spin-corrected/bag")):
    for tmax, rad in ((3.0, 3.0), (3.0, 5.0), (10.0, 3.0), (10.0, 5.0)):
        odom, scans = P.read(bag, t_max=tmax, scan_stride=1, pt_stride=1)
        pts = P.to_session_frame(odom, scans)
        near = pts[(np.hypot(pts[:, 0], pts[:, 1]) < rad) & (pts[:, 2] < -0.05)]
        h, e = np.histogram(near[:, 2], bins=np.arange(-1.2, -0.05, 0.02)); z0 = e[h.argmax()] + 0.01
        n, sd, k = fit(near[np.abs(near[:, 2] - z0) < 0.08])
        print("%-15s first %4.1f s, radius %.0f m: floor z %.3f, %5d pts, sd %.1f mm | normal tilt about-x %+.2f deg, about-y %+.2f deg" % (name, tmax, rad, z0, k, sd * 1e3, math.degrees(-n[1] / n[2]), math.degrees(n[0] / n[2])))
