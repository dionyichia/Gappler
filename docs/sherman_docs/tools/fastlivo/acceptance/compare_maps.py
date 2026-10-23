#!/usr/bin/env python3
"""Compare the saved 2D maps (sharpness) and the localization results (error against the tape measurement). numpy and PIL.
usage: compare_maps.py RUN_DIR   (RUN_DIR holds A_recorded, B_scanend, C_scanonly, each with map/ and loc/)"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image

TAPE = (2.00, 1.16)
RUN = Path(sys.argv[1])


def metrics(pgm):
    a = np.array(Image.open(pgm))
    occ, free = a == 0, a == 254
    pad = np.pad(occ, 1)
    nb = pad[:-2, 1:-1].astype(int) + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
    boundary = occ & (nb < 4)
    # an isolated-speckle count: occupied cells with no occupied 4-neighbour
    return {"size": list(a.shape), "occupied": int(occ.sum()), "free": int(free.sum()), "boundary_cells": int(boundary.sum()),
            "thickness_proxy": round(float(occ.sum()) / max(int(boundary.sum()), 1), 3), "speckles": int((occ & (nb == 0)).sum())}


print("== map sharpness (occupied cells: fewer and a lower thickness proxy mean thinner, crisper walls)")
for name in ("A_recorded", "B_scanend", "C_scanonly"):
    pgm = RUN / name / "map/map.pgm"
    if pgm.is_file():
        print("%-12s %s" % (name, json.dumps(metrics(pgm))))
print()
print("== reload of spin-corrected, initial guess (2.0, 1.2, 0 deg), against the tape (%.2f, %.2f). error = map->odom minus tape" % TAPE)
for name in ("A_recorded", "B_scanend"):
    f = RUN / name / "loc/result.json"
    if not f.is_file():
        print(name, "no loc result"); continue
    r = json.loads(f.read_text()); s = r["map_to_odom_samples"]
    print("%s (stamp %s): %d samples over %.0f s" % (name, r.get("stamp"), len(s), s[-1][0] - s[0][0] if s else 0))
    for lo, hi, label in ((0, 6, "first 6 s"), (6, 15, "6 to 15 s"), (15, 1e9, "after 15 s")):
        sel = [x for x in s if lo <= x[0] - s[0][0] < hi]
        if sel:
            xs, ys, yaws = (np.array([v[i] for v in sel]) for i in (1, 2, 3))
            ex, ey = xs.mean() - TAPE[0], ys.mean() - TAPE[1]
            print("   %-11s x %.3f y %.3f yaw %+.2f deg | error dx %+.3f dy %+.3f plan %.3f m | spread x %.3f y %.3f yaw %.2f" % (
                label, xs.mean(), ys.mean(), yaws.mean(), ex, ey, math.hypot(ex, ey), np.ptp(xs), np.ptp(ys), np.ptp(yaws)))
    last = s[-1] if s else None
    if last:
        print("   final sample x %.3f y %.3f yaw %+.2f -> error plan %.3f m" % (last[1], last[2], last[3], math.hypot(last[1] - TAPE[0], last[2] - TAPE[1])))
# side-by-side picture of the three maps
imgs = []
for name in ("A_recorded", "B_scanend", "C_scanonly"):
    p = RUN / name / "map/map.pgm"
    if p.is_file():
        imgs.append(Image.open(p).convert("L"))
if imgs:
    h = max(i.height for i in imgs); w = sum(i.width for i in imgs) + 10 * (len(imgs) - 1)
    canvas = Image.new("L", (w, h), 255); x = 0
    for i in imgs:
        canvas.paste(i, (x, 0)); x += i.width + 10
    canvas.save(RUN / "maps_side_by_side.png"); print("\nwrote", RUN / "maps_side_by_side.png", "(left to right: recorded stamps, scan-end stamps, scan matching only)")
