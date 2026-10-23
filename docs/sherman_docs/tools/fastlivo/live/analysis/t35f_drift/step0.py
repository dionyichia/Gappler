"""T3.5f drift step 0: common frame. All transforms act between LEVELLED session frames (each run's first-pose roll/pitch removed), 4-DOF, frozen T3.5e prototype.
0a: run 2 first 3 s onto run 1 first 3 s.  0b: run 1 first 20 s into the handdriven1 map (global sweep, no seed), accept at inliers >= 0.9, then invert.
Writes out/step0_frames.json {label: 4x4 into the run 1 frame}.  usage: step0.py"""
import json, math, sys
import numpy as np
from scipy.spatial import cKDTree
import drift_common as D
R, P = D.R, D.P
GATE = 0.9


def show(tag, T, inl, rms, rp):
    print("%s: dx %+.3f dy %+.3f dz %+.3f m, dyaw %+.2f deg | inliers %.3f rms_p2p %.3f rms_plane %.3f" % (tag, T[0, 3], T[1, 3], T[2, 3], P.yaw_of(T), inl, rms, rp), flush=True)


def early(label, sec, scan_stride=1):
    odom, scans = R.read_fast(D.BAGS[label], t_max=sec, scan_stride=scan_stride)
    return odom, scans


# ---- 0a
o1, s1 = early("run1", 3.0); o2, s2 = early("run2", 3.0)
M1, tree1, n1, ok1 = R.build_map(o1, s1)
Q2 = P.voxel(P.to_session_frame(o2, s2))
S = P.voxel(P.to_session_frame(o1, s1))
Ts, i, r, p = P.icp_plane(S, tree1, M1, n1, P.Tz(0.3, -0.2, 10), ok=ok1)
show("0a self-test run1[0:3] onto itself from (0.3,-0.2,10deg), identity expected", Ts, i, r, p)
T0, inl, rms, rp = P.icp_plane(Q2, tree1, M1, n1, np.eye(4), ok=ok1)
show("0a run2[0:3 s] -> run1[0:3 s]", T0, inl, rms, rp)
alts = []
for dx, dy, dyaw in [(0.3, 0, 0), (0, 0.3, 0), (-0.3, -0.3, 0), (0, 0, 10), (0, 0, -10), (0, 0, 30)]:
    Ti, i2, _, _ = P.icp_plane(Q2, tree1, M1, n1, P.Tz(dx, dy, dyaw), ok=ok1)
    alts.append((np.linalg.norm(Ti[:3, 3] - T0[:3, 3]), abs((P.yaw_of(Ti) - P.yaw_of(T0) + 180) % 360 - 180)))
print("0a basin: 6 other starts agree within %.3f m / %.2f deg at worst" % (max(a for a, _ in alts), max(b for _, b in alts)))
print("0a first-pose gap: run1 odom0 %s ; run2 odom0 %s" % (np.round(o1[0, 1:4], 3), np.round(o2[0, 1:4], 3)))
frames = {"run1": np.eye(4), "run2": T0}

# ---- 0b: run 1 early (20 s) as query into the handdriven1 map (which has the larger extent); invert afterwards
oh, sh = R.read_fast(D.BAGS["hd1"], scan_stride=2)
Mh, treeh, nh, okh = R.build_map(oh, sh)
print("0b hd1 map: %d voxels (%d planar)" % (len(Mh), okh.sum()))
oe, se = early("run1", 20.0)
Qe = P.voxel(P.to_session_frame(oe, se)); Qc = P.voxel(Qe, 0.2)
print("0b query: run1 first 20 s, %d scans, %d voxels (%d at 0.2 m for the sweep)" % (len(se), len(Qe), len(Qc)), flush=True)
cands = []
for yaw in range(0, 360, 15):
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            T, inl, rms, rp = P.icp_plane(Qc, treeh, Mh, nh, P.Tz(dx, dy, yaw), iters=40, ok=okh)
            cands.append((inl, T))
cands.sort(key=lambda c: -c[0]); top = []
for inl, T in cands:   # coarse candidates: distinct = more than 0.3 m or 10 deg from every kept one; the 30 best are refined, then de-duplicated again
    if all(np.linalg.norm(T[:2, 3] - t[:2, 3]) > 0.3 or abs((P.yaw_of(T) - P.yaw_of(t) + 180) % 360 - 180) > 10 for _, t in top):
        top.append((inl, T))
    if len(top) == 30:
        break
print("0b global sweep: %d starts (24 yaws x 49 offsets, 40 iterations, 0.2 m voxels); 30 distinct coarse candidates refined at full resolution, then merged when they converge to the same pose:" % len(cands))
ref = []
for inl0, T in top:
    T2, inl, rms, rp = P.icp_plane(Qe, treeh, Mh, nh, T, iters=80, ok=okh)
    if all(np.linalg.norm(T2[:2, 3] - t[:2, 3]) > 0.1 or abs((P.yaw_of(T2) - P.yaw_of(t) + 180) % 360 - 180) > 3 for _, t, _, _ in ref):
        ref.append((inl, T2, rms, rp))
ref.sort(key=lambda c: -c[0])
for k, (inl, T, rms, rp) in enumerate(ref[:3]):
    show("  #%d run1->hd1" % (k + 1), T, inl, rms, rp)
best = ref[0]
clear = best[0] >= GATE and (len(ref) < 2 or ref[1][0] < best[0] - 0.15)
print("0b decision: best inliers %.3f, second %.3f -> %s" % (best[0], ref[1][0], "ACCEPT" if clear else "REJECT (gate %.1f and a 0.15 margin)" % GATE))
if clear:
    Th = D.tf_inv(best[1])        # hd1 frame -> run1 frame
    frames["hd1"] = Th
    # reverse check: hd1 voxels near the run1-early map, registered onto it from the inverse transform
    Me, treee, ne, oke = R.build_map(oe, se)
    d, _ = treee.query(Mh); sub = Mh[d < 1.0]
    Tr, inl_r, rms_r, rp_r = P.icp_plane(sub, treee, Me, ne, Th, ok=oke)
    show("0b reverse check, %d hd1 voxels within 1 m of the run1 early map, hd1->run1" % len(sub), Tr, inl_r, rms_r, rp_r)
    print("0b reverse minus inverse(forward): %.3f m, %.2f deg" % (np.linalg.norm(Tr[:2, 3] - Th[:2, 3]), (P.yaw_of(Tr) - P.yaw_of(Th) + 180) % 360 - 180))
    show("0b hd1 -> run1 frame (used downstream)", Th, best[0], best[2], best[3])
json.dump({k: v.tolist() for k, v in frames.items()}, open(D.OUT + "/step0_frames.json", "w"))
print("frames written:", sorted(frames))
