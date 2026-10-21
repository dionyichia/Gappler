"""T3.5f cause hunt: when do the mapper's sync warnings happen, relative to the bag window. usage: sync_scan.py LABEL=STDERR_LOG:BAG_START_EPOCH:BAG_SECONDS"""
import re, sys
import numpy as np
ansi = re.compile(r'\x1b\[[0-9;]*m')
warn = re.compile(r'\[(\d+\.\d+)\] \[laserMapping\]: IMU and LiDAR not synced! delta time: (-?[\d.]+)')
hard = re.compile(r'\[(\d+\.\d+)\] \[laserMapping\]: Self sync IMU and LiDAR, HARD time lag is (-?[\d.]+)')
for arg in sys.argv[1:]:
    label, spec = arg.split('=', 1); path, b0, dur = spec.split(':'); b0 = float(b0); dur = float(dur)
    w, h, first, last = [], [], None, None
    for line in open(path, errors='replace'):
        line = ansi.sub('', line)
        m = warn.search(line)
        if m: w.append((float(m.group(1)), float(m.group(2)))); continue
        m = hard.search(line)
        if m: h.append((float(m.group(1)), float(m.group(2))))
    w = np.array(w).reshape(-1, 2); h = np.array(h).reshape(-1, 2)
    print("=" * 8, label, "log lines of sync warnings: %d, HARD lag lines: %d; bag window %.1f to %.1f" % (len(w), len(h), b0, b0 + dur))
    for name, a in (("not-synced", w), ("HARD lag", h)):
        if not len(a): continue
        inb = a[(a[:, 0] >= b0) & (a[:, 0] <= b0 + dur)]
        print(" %s: log time %.1f to %.1f; in drive window: %d; before window: %d; after: %d" % (name, a[0, 0], a[-1, 0], len(inb), (a[:, 0] < b0).sum(), (a[:, 0] > b0 + dur).sum()))
        print("   value stats: min %.4f median %.4f max %.4f; first 3 %s; last 3 %s" % (a[:, 1].min(), np.median(a[:, 1]), a[:, 1].max(), np.round(a[:3, 1], 4), np.round(a[-3:, 1], 4)))
        if len(inb): print("   in-window values: min %.4f median %.4f max %.4f" % (inb[:, 1].min(), np.median(inb[:, 1]), inb[:, 1].max()))
        t = np.floor(a[:, 0] - a[0, 0]).astype(int); u, c = np.unique(t // 60, return_counts=True)
        print("   per minute from first warning:", dict(zip(u.tolist(), c.tolist())))
