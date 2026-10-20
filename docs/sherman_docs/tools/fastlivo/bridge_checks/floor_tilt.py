import math, sys
import numpy as np
import reloc_offline_prototype as P
A = "/home/rcp2026/rcp-Gappler/log/t59-fastlivo/log/t35d-attended-20261020.raLTgE"
for name, bag in (("handdriven1", A + "/run/bag/handdriven1"), ("spin-corrected", A + "/spin-corrected/bag")):
    odom, scans = P.read(bag, t_max=3.0, scan_stride=1, pt_stride=1)
    pts = P.to_session_frame(odom, scans)
    near = pts[(np.hypot(pts[:, 0], pts[:, 1]) < 5.0) & (pts[:, 2] < -0.1)]
    h, e = np.histogram(near[:, 2], bins=np.arange(-1.2, -0.1, 0.05)); z0 = e[h.argmax()] + 0.025
    fl = near[np.abs(near[:, 2] - z0) < 0.06]
    c = fl.mean(0); u, s, vt = np.linalg.svd(fl - c, full_matrices=False); n = vt[2] if vt[2][2] > 0 else -vt[2]
    R0 = P.rot(odom[0, 4:8]); roll0 = math.degrees(math.atan2(R0[2, 1], R0[2, 2])); pitch0 = math.degrees(-math.asin(R0[2, 0]))
    print("%-15s floor z %.2f m, %d pts | floor normal tilt: about-x(roll-like) %+.2f deg, about-y(pitch-like) %+.2f deg | first-pose roll %+.2f pitch %+.2f deg | plane rms %.1f mm" % (
        name, z0, len(fl), math.degrees(-n[1] / n[2]), math.degrees(n[0] / n[2]), roll0, pitch0, 1e3 * s[2] / math.sqrt(len(fl))))
