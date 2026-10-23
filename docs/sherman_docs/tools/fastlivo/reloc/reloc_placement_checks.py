"""T3.5e A: is the ~1.3 m placement difference real?  Run with LEVEL=1 GRAV4=1 (levelled, yaw+xyz solve).
usage: reloc_placement_checks.py MAP_BAG QUERY_BAG QUERY_SECONDS TAG OUTDIR
Prints (1) a global sweep with distinct solutions, (2) A^T A degeneracy at the best one,
(3) a y-profile: for each fixed y of the query centroid in the map frame, the best x and yaw (CSV + PNG)."""
import csv, math, os, sys
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
import reloc_offline_prototype as P

map_bag, q_bag, qsec, tag, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4], sys.argv[5]
os.makedirs(out, exist_ok=True)
odom, scans = P.read(map_bag, scan_stride=2)
M = P.voxel(P.to_session_frame(odom, scans)); tree = cKDTree(M)
nrm, flat = P.normals(M, tree); ok = flat <= P.FLAT_MAX
qo, qs = P.read(q_bag, t_max=qsec)
Q = P.voxel(P.to_session_frame(qo, qs))
print('%s: map %d voxels (%d planar); query %d scans in %.0f s -> %d voxels; LEVEL %d GRAV4 %s' % (tag, len(M), ok.sum(), len(qs), qsec, len(Q), P.LEVEL, P.GRAV4))

# (1) global sweep, keep every solution, then cluster
sols = []
for yaw in range(0, 360, 30):
    for dx, dy in [(0, 0), (0.5, 0), (-0.5, 0), (0, 0.5), (0, -0.5), (0, 1.0), (0, 1.5)]:
        T, inl, r2, rp = P.icp_plane(Q, tree, M, nrm, P.Tz(dx, dy, yaw), iters=60, ok=ok)
        sols.append((inl, T, rp))
sols.sort(key=lambda s: -s[0])
distinct = []
for inl, T, rp in sols:
    if all(np.linalg.norm(T[:3, 3] - D[1][:3, 3]) > 0.3 or abs((P.yaw_of(T) - P.yaw_of(D[1]) + 180) % 360 - 180) > 10 for D in distinct):
        distinct.append((inl, T, rp))
print('GLOBAL sweep: %d starts, %d distinct solutions; top 5 (inliers, plane rms):' % (len(sols), len(distinct)))
for inl, T, rp in distinct[:5]:
    print('  inl %.3f rms_pl %.3f | %s' % (inl, rp, P.pose_str(T)))
best = distinct[0][1]

# (2) degeneracy at the best solution: H = A^T A / N, A = [ (p-c) x n , n ] over planar inliers
p = Q @ best[:3, :3].T + best[:3, 3]
dist, idx = tree.query(p); m = (dist < 0.15) & ok[idx]
n = nrm[idx[m]]; c = p[m].mean(0)
A = np.hstack([np.cross(p[m] - c, n), n])
names = ['rotX', 'rotY', 'rotZ(yaw)', 'tx', 'ty', 'tz']
for label, cols in (('6-DOF', list(range(6))), ('4-DOF yaw+xyz', [2, 3, 4, 5])):
    H = A[:, cols].T @ A[:, cols] / len(A)
    w, v = np.linalg.eigh(H)
    print('A^T A %s at best (N=%d planar inliers): eigenvalues %s  condition %.1f' % (label, len(A), np.array2string(w, precision=4), w[-1] / max(w[0], 1e-12)))
    vv = v[:, 0]
    print('  weakest direction: ' + ', '.join('%s %+.2f' % (names[cols[i]], vv[i]) for i in np.argsort(-abs(vv))[:3]))
print('normal axes among planar inliers: |nx|>0.7 %.0f%%  |ny|>0.7 %.0f%%  |nz|>0.7 %.0f%%' % tuple(100 * (abs(n[:, k]) > 0.7).mean() for k in range(3)))

# (3) y profile. Variables: x, yaw free; y of the query centroid fixed; z and level fixed at the best.
Mp, Np = M[ok], nrm[ok]; tp = cKDTree(Mp)
c0 = Q.mean(0); X = Q - c0
sub = X[np.random.RandomState(0).choice(len(X), min(4000, len(X)), replace=False)]
cb = best[:3, :3] @ c0 + best[:3, 3]; yaw_b = P.yaw_of(best); z_b = cb[2]


def place(Xs, x, y, yaw):
    a = math.radians(yaw); R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    return Xs @ R.T + np.array([x, y, z_b])


def cost(v, y):
    d, i = tp.query(place(sub, v[0], y, v[1]), distance_upper_bound=0.5)
    r = np.where(np.isfinite(d), np.abs(np.einsum('ij,ij->i', Np[np.minimum(i, len(Np) - 1)], place(sub, v[0], y, v[1]) - Mp[np.minimum(i, len(Np) - 1)])), 0.15)
    return float(np.mean(np.minimum(r, 0.15) ** 2))


rows = []
for y in np.arange(-3.0, 3.01, 0.1):
    bestc = None
    starts = [(x0, y0) for x0 in cb[0] + np.array([-1, 0, 1]) for y0 in yaw_b + np.array([-10, 0, 10])]
    starts += [((T[:3, :3] @ c0 + T[:3, 3])[0], P.yaw_of(T)) for _, T, _ in distinct[:5]]  # the sweep's own top solutions, so the profile cannot do worse than ICP
    for x0, y0 in starts:
        r = minimize(cost, [x0, y0], args=(y,), method='Nelder-Mead', options=dict(xatol=1e-3, fatol=1e-9, maxiter=80))
        if bestc is None or r.fun < bestc.fun: bestc = r
    pf = place(X, bestc.x[0], y, bestc.x[1])
    d, i = tree.query(pf); mi = d < 0.15
    rp = float(np.sqrt(np.mean(np.einsum('ij,ij->i', nrm[i[mi]], pf[mi] - M[i[mi]]) ** 2))) if mi.any() else float('nan')
    rows.append((round(float(y), 2), bestc.x[0], bestc.x[1], bestc.fun, mi.mean(), rp))
    print('  y %.2f: x %.3f yaw %.2f cost %.5f inliers %.3f rms_pl %.3f' % rows[-1], flush=True)
with open('%s/yprofile_%s.csv' % (out, tag), 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['y_m', 'x_m', 'yaw_deg', 'trunc_cost', 'inliers', 'rms_plane_m']); w.writerows(rows)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
R_ = np.array(rows)
fig, ax = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
ax[0].plot(R_[:, 0], R_[:, 4], 'o-'); ax[0].set_ylabel('inlier fraction (<0.15 m)')
ax[1].plot(R_[:, 0], R_[:, 3], 'o-'); ax[1].set_ylabel('truncated plane cost'); ax[1].set_xlabel('y of query centroid in map frame (m)')
ax[0].set_title('y fit profile, %s (x and yaw re-optimised per y)' % tag)
fig.tight_layout(); fig.savefig('%s/yprofile_%s.png' % (out, tag), dpi=110)
loc = [R_[k, 0] for k in range(1, len(R_) - 1) if R_[k, 3] < R_[k - 1, 3] and R_[k, 3] < R_[k + 1, 3]]
print('local minima of cost at y =', loc, '| global min y %.2f inliers %.3f; best inliers anywhere %.3f at y %.2f' % (R_[R_[:, 3].argmin(), 0], R_[R_[:, 3].argmin(), 4], R_[:, 4].max(), R_[R_[:, 4].argmax(), 0]))
