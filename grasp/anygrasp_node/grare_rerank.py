"""Re-rank AnyGrasp's raw grasps with GraRe (arXiv 2608.00946, T1.61).

GraRe is a learned grasp scorer. For each grasp it looks at the points around the gripper (the local
cloud) and at the object the grasp touches (a MobileSAM mask prompted at the grasp), and scores how
likely the grasp is to hold. Its score replaces AnyGrasp's before NMS, so NMS keeps GraRe's best grasp
in each patch. Offline on 60 real frames its first pick held in 60 of 60, AnyGrasp's in 0 of 40
(docs/dion_docs/local/experiments/T1.47_ideal_cloud/FINDINGS.md).

GraRe's own code took 18 s a frame. Three speedups bring it to about 1.2 s, each with its own switch:
  skip_duplicates     about half of AnyGrasp's raw grasps are exact copies. Score the first copy of each,
                      in the original order: GraRe's SAM prompts are grouped greedily in list order
                      (vendor scene_labeling.py:1060), so sorting the grasps changes the scores.
  crop_cloud          only points that can be near some grasp go into GraRe's KD tree. Exact.
  gpu_neighbourhoods  the per-grasp neighbourhood, shell split and farthest point sampling on the GPU,
                      instead of a Python loop per grasp.

GraRe and MobileSAM are vendored unchanged in grasp/vendor/ (see their README.md).
Run this file on the box to check it (GPU, anygrasp venv, weights): python3 grare_rerank.py
"""

import contextlib
import functools
import sys
from types import SimpleNamespace

import numpy as np
import torch
import yaml

from gappler_common import ROOT, config, path

VENDOR = ROOT / "grasp" / "vendor"
sys.path[:0] = [str(VENDOR / "grare"), str(VENDOR / "MobileSAM")]
from grare.cli.demo import _make_online_extractor, _score_candidates  # noqa: E402
from grare.rescoring import load_model_checkpoint  # noqa: E402
from grare.rescoring.inference import _build_export_scores  # noqa: E402


def dedup(rows):
    """First copy of each exact duplicate row, original order kept. Returns the kept rows' indices and,
    for every row, the slot of its kept copy."""
    _, first, inv = np.unique(rows, axis=0, return_index=True, return_inverse=True)
    keep = np.sort(first)
    slot = np.empty(len(rows), np.int64)
    slot[keep] = np.arange(len(keep))
    return keep, slot[first[inv.ravel()]]


def crop(points, t, radius):
    """Points inside the grasp centres' bounding box plus radius, in their original order. Every point within
    radius of a grasp centre is inside, so GraRe's KD tree finds the same neighbours in the same order."""
    lo, hi = t.min(0) - radius - 1e-6, t.max(0) + radius + 1e-6
    return points[np.all((points >= lo) & (points <= hi), axis=1)]


def fps_padded(cloud, sizes, budget):
    """GraRe's _fps_indices (seed at the point farthest from the origin, then the farthest from those picked)
    on a padded (n, m, 3) CUDA tensor whose rows hold sizes[i] valid points. The points come out of the GPU
    rotation, which rounds differently from numpy's in the last bit (up to 6e-10 m). Those differences change
    which point is farthest, so the sample and the score differ from GraRe's own (up to 0.07 on real frames,
    same first pick in 60 of 60). Exact would need the rotation on the CPU, about 0.8 s more a frame."""
    valid = torch.arange(cloud.shape[1], device=cloud.device)[None] < sizes[:, None]
    rows = torch.arange(len(cloud), device=cloud.device)
    sel = torch.empty((len(cloud), budget), dtype=torch.long, device=cloud.device)
    sel[:, 0] = torch.linalg.vector_norm(cloud, dim=2).masked_fill(~valid, float("-inf")).argmax(1)
    dist = torch.full(cloud.shape[:2], float("inf"), device=cloud.device).masked_fill(~valid, float("-inf"))
    for s in range(1, budget):
        diff = cloud - cloud[rows, sel[:, s - 1]][:, None]
        torch.minimum(dist, diff[..., 0] ** 2 + diff[..., 1] ** 2 + diff[..., 2] ** 2, out=dist)
        sel[:, s] = dist.argmax(1)
    return sel


def precision(name):
    """float32 runs as is. float16 or bfloat16 runs the CUDA ops inside under torch.autocast."""
    if name == "float32":
        return contextlib.nullcontext()
    return torch.autocast("cuda", dtype={"float16": torch.float16, "bfloat16": torch.bfloat16}[name])


def local_cloud_gpu(self, grasp_group_array, *, observed_points, local_cloud_tree, chunk):
    """GraRe's _extract_local_cloud (stratified_fps, vendor scene_labeling.py:945), every step on the GPU.
    Same neighbours (distance <= radius in float64, like cKDTree), same index order, same shells, same
    sampling recurrence. Bound to GraRe's extractor in place of its own method."""
    cfg = self.config
    edges, budgets = cfg.shell_edges_m, cfg.shell_budgets
    n, P, S = len(grasp_group_array), int(sum(budgets)), len(budgets)
    if n == 0 or len(observed_points) == 0:
        return np.zeros((n, P, 3), np.float32), np.zeros((n, P), bool)
    with torch.inference_mode():
        cloud = torch.from_numpy(observed_points).cuda()
        cloud64 = cloud.double()
        t = torch.from_numpy(np.ascontiguousarray(grasp_group_array[:, 13:16])).cuda()
        R = torch.from_numpy(np.ascontiguousarray(grasp_group_array[:, 4:13])).cuda().reshape(-1, 3, 3)
        g_ids, pts_all = [], []
        for a in range(0, n, chunk):  # neighbours, sorted by grasp then by cloud index, like query_ball_point
            d2 = ((cloud64[None] - t[a:a + chunk, None].double()) ** 2).sum(-1)
            g, k = torch.nonzero(d2 <= cfg.local_cloud_radius ** 2, as_tuple=True)
            g = g + a
            p = cloud[k] - t[g]
            # (p @ R) one column at a time, the same summation order as numpy's float32 matmul [inferred]
            pts_all.append(torch.stack([p[:, 0] * R[g, 0, c] + p[:, 1] * R[g, 1, c] + p[:, 2] * R[g, 2, c]
                                        for c in range(3)], 1))
            g_ids.append(g)
        g, pts = torch.cat(g_ids), torch.cat(pts_all)
        r = torch.linalg.vector_norm(pts, dim=1).double()
        shell = torch.full_like(g, -1)
        for s in range(S):
            last = s == S - 1
            inside = (r >= edges[s]) & ((r <= edges[s + 1] + 1e-9) if last else (r < edges[s + 1]))
            shell[inside] = s
        ok = shell >= 0
        g, pts, shell = g[ok], pts[ok], shell[ok]
        key = g * S + shell  # already grouped by grasp. A stable sort groups by shell inside each, order kept
        key, order = torch.sort(key, stable=True)
        pts = pts[order]
        counts = torch.bincount(key, minlength=n * S)
        start = torch.cumsum(counts, 0) - counts
        pos = torch.arange(len(key), device="cuda") - start[key]  # position inside its (grasp, shell)
        offsets = torch.as_tensor(np.r_[0, np.cumsum(budgets)[:-1]], device="cuda")
        budget_of = torch.as_tensor(budgets, device="cuda")
        local = torch.zeros((n, P, 3), dtype=torch.float32, device="cuda")
        mask = torch.zeros((n, P), dtype=torch.bool, device="cuda")
        kg, ks = key // S, key % S
        small = counts[key] <= budget_of[ks]  # shells that fit keep every point, in order
        local[kg[small], offsets[ks[small]] + pos[small]] = pts[small]
        mask[kg[small], offsets[ks[small]] + pos[small]] = True
        for s, b in enumerate(budgets):
            big = torch.nonzero(counts.view(n, S)[:, s] > b).ravel()  # grasps whose shell s needs sampling
            if not len(big):
                continue
            sizes = counts.view(n, S)[big, s]
            padded = torch.zeros((len(big), int(sizes.max()), 3), dtype=torch.float32, device="cuda")
            row = torch.full((n,), -1, dtype=torch.long, device="cuda")
            row[big] = torch.arange(len(big), device="cuda")
            here = ~small & (ks == s)
            padded[row[kg[here]], pos[here]] = pts[here]
            sel = fps_padded(padded, sizes, b)
            local[big[:, None], offsets[s] + torch.arange(b, device="cuda")[None]] = \
                padded[torch.arange(len(big), device="cuda")[:, None], sel]
            mask[big, offsets[s]:offsets[s] + b] = True
        return local.cpu().numpy(), mask.cpu().numpy()


class GraspReranker:
    """GraRe and MobileSAM, loaded once. cfg is the grare: block of grasp_config.yaml."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.model = load_model_checkpoint(str(path("grare_weights")), device="cuda")
        with open(VENDOR / "grare" / "configs" / "_base.yaml") as f:
            grare_cfg = yaml.safe_load(f)  # GraRe's SAM prompt settings, from its repo unchanged
        self.extractor = _make_online_extractor(self.model, device="cuda", resolved=SimpleNamespace(
            detector="graspnet_baseline", camera="realsense", config=grare_cfg,
            sam_checkpoint=str(path("mobile_sam_weights"))))
        if cfg["gpu_neighbourhoods"]:
            self.extractor._extract_local_cloud = functools.partial(local_cloud_gpu, self.extractor,
                                                                    chunk=cfg["neighbourhood_chunk"])
        object_cloud = self.extractor._extract_object_cloud  # MobileSAM runs in here

        def object_cloud_at_precision(*a, **k):
            with precision(cfg["mobile_sam_precision"]):
                return object_cloud(*a, **k)
        self.extractor._extract_object_cloud = object_cloud_at_precision

    def score(self, rows, rgb, points_full, depth_mask, K):
        """GraRe's score for each grasp, fused with AnyGrasp's by score_weight (z-scores, as GraRe does).
        rows: GraspNet's (n, 17) grasp array in the camera frame. rgb: (h, w, 3) uint8. points_full: (h, w, 3)
        camera-frame points. depth_mask: (h, w) the points to use. K: 3 x 3 intrinsics."""
        keep, slot = dedup(rows) if self.cfg["skip_duplicates"] else (np.arange(len(rows)),) * 2
        grasps = rows[keep]
        observed = points_full[depth_mask].astype(np.float32)
        if self.cfg["crop_cloud"]:
            observed = crop(observed, grasps[:, 13:16], self.extractor.config.local_cloud_radius)
        feats = self.extractor.extract(grasps, observed_points=observed, points_grid=points_full,
                                       valid_grid=depth_mask, intrinsics=K, rgb_image=rgb)
        with precision(self.cfg["model_precision"]):
            q = _score_candidates(self.model, grasps, feats, device="cuda", batch_size=self.cfg["batch_size"])
        # Copies get their kept copy's score, then fuse over every row, as GraRe would without the skip
        fused, _ = _build_export_scores(base_scores=rows[:, 0], rescoring_scores=q[slot],
                                        rescoring_score_weight=float(self.cfg["score_weight"]))
        return fused


def demo_scene(n=200, seed=0):
    """A 6 x 7.4 x 14 cm box 0.45 m in front of a 640 x 480 camera, on a table, and n grasps on it with
    half of them exact copies. Returns (rows, rgb, points_full, depth_mask, K)."""
    rng = np.random.default_rng(seed)
    K = np.array([[607.0, 0, 320.0], [0, 607.0, 240.0], [0, 0, 1.0]], np.float32)
    u, v = np.meshgrid(np.arange(640), np.arange(480))
    box = (np.abs(u - 320) < 50) & (np.abs(v - 240) < 95)
    z = np.where(box, 0.45, 0.6) + rng.normal(0, 0.001, u.shape)
    points_full = np.stack([(u - 320) * z / 607.0, (v - 240) * z / 607.0, z], -1).astype(np.float32)
    rgb = np.where(box[..., None], [200, 60, 40], [90, 90, 90]).astype(np.uint8)
    half = n // 2
    rows = np.zeros((half, 17), np.float32)
    rows[:, 0] = rng.uniform(0.1, 0.9, half)
    rows[:, 1:4] = 0.06, 0.02, 0.02
    approach = np.array([0.0, 0.0, 1.0])  # GraspNet's x axis is the approach: into the image
    for k in range(half):
        a = rng.uniform(0, np.pi)
        y = np.array([np.cos(a), np.sin(a), 0.0])
        rows[k, 4:13] = np.stack([approach, y, np.cross(approach, y)], 1).ravel()
    rows[:, 13:16] = np.c_[rng.uniform(-0.03, 0.03, (half, 2)), np.full(half, 0.43)]
    rows[:, 16] = -1
    rows = np.concatenate([rows, rows[rng.integers(0, half, n - half)]])  # exact copies, after the originals
    return rows, rgb, points_full, (z > 0) & (z < 1.5), K


if __name__ == "__main__":
    # Each speedup against GraRe's own code (all off): same first pick, scores close. The other
    # settings come from grasp_config.yaml
    scene = demo_scene()
    off = {**config("grasp", "anygrasp_detection_node")["grare"],
           "skip_duplicates": False, "crop_cloud": False, "gpu_neighbourhoods": False, "score_weight": 1.0}
    ref = GraspReranker(off).score(*scene)
    rows = scene[0]
    for name in ("skip_duplicates", "crop_cloud", "gpu_neighbourhoods"):
        q = GraspReranker({**off, name: True}).score(*scene)
        assert np.array_equal(rows[np.argmax(q)], rows[np.argmax(ref)]), (name, "first pick moved")
        print(f"{name}: same first pick, max score change {np.abs(q - ref).max():.1e}")
    assert np.allclose(GraspReranker({**off, "skip_duplicates": True}).score(*scene), ref, atol=1e-4)
    print("grare_rerank: all checks pass")
