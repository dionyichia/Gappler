"""T3.5e A1b: registration-free check. Raw LiDAR range per azimuth in the first 1 s of each bag (sensor frame, +x = camera forward, +y = left).
If the query started dx forward and dy left of the map's start, ranges along +x / +y shrink by about dx / dy when the walls are parallel.
usage: reloc_range_check.py BAG [BAG ...]"""
import sys
import numpy as np
import reloc_offline_prototype as P

for bag in sys.argv[1:]:
    _, scans = P.read(bag, t_max=1.0, scan_stride=1, pt_stride=1)
    pts = np.vstack([s[1] for s in scans]); pts = pts[np.linalg.norm(pts, axis=1) > 0.5]
    h = pts[(pts[:, 2] > -0.2) & (pts[:, 2] < 1.2)]
    az = np.degrees(np.arctan2(h[:, 1], h[:, 0])); rg = np.hypot(h[:, 0], h[:, 1])
    print(bag.split('/')[-2] if 'bag_0' in bag or bag.endswith('/bag') else bag.split('/')[-1], '| %d pts in 1 s, %d at body height' % (len(pts), len(h)))
    line = []
    for a in range(-180, 180, 30):
        m = np.abs((az - a + 180) % 360 - 180) < 7.5
        line.append('%4d:%5.2f' % (a, np.percentile(rg[m], 10)) if m.sum() > 50 else '%4d:  -- ' % a)
    print('  10th-pct range (m) by azimuth deg (0=forward/+x, 90=left/+y):', ' '.join(line))
