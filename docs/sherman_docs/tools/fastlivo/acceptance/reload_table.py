#!/usr/bin/env python3
"""Reload error against the tape for every localization result under a run directory. map -> odom is the pose of the spin start in the map.
Times are seconds from the first TF sample. error = (map->odom) minus tape, plan distance in metres. numpy only.
usage: reload_table.py RUN_DIR [RUN_DIR ...]"""
import json, math, sys
from pathlib import Path
import numpy as np

TAPE = (2.00, 1.16)
rows = []
for run in map(Path, sys.argv[1:]):
    for f in sorted(run.rglob("result.json")):
        r = json.loads(f.read_text())
        if r.get("mode") != "localize" or not r.get("map_to_odom_samples"):
            continue
        s = np.array(r["map_to_odom_samples"]); t = s[:, 0] - s[0, 0]
        def at(T):
            i = int(np.argmin(abs(t - T))); return s[i, 1:4]
        def err(v): return math.hypot(v[0] - TAPE[0], v[1] - TAPE[1])
        label = str(f.parent.relative_to(run)).replace("/loc", "") if f.parent != run else run.name
        graph = next((p.split("=", 1)[1] for p in r.get("slam_params", []) if False), "")
        mt0 = any("minimum_travel_distance=0.0" in p for p in r.get("slam_params", []))
        rows.append((str(run.name) + "/" + label, "all scans" if mt0 else "gate 0.1/0.1", at(3), at(6), at(15), s[-1, 1:4], err(at(3)), err(at(6)), err(at(15)), err(s[-1, 1:4])))
print("%-28s %-12s | %-24s | %-24s | %-24s | %-24s" % ("session", "min travel", "t=3 s  x,y,yaw (err m)", "t=6 s", "t=15 s", "final"))
for lab, mt, a, b, c, d, ea, eb, ec, ed in rows:
    f = lambda v, e: "%.3f,%.3f,%+5.1f (%.3f)" % (v[0], v[1], v[2], e)
    print("%-28s %-12s | %-24s | %-24s | %-24s | %-24s" % (lab, mt, f(a, ea), f(b, eb), f(c, ec), f(d, ed)))
print("tape (%.2f, %.2f); operator guess (2.0, 1.2, 0) is %.3f m from the tape" % (TAPE[0], TAPE[1], math.hypot(2.0 - TAPE[0], 1.2 - TAPE[1])))
