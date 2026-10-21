"""Score the memory graph on a saved drive against the hand-marked ground truth (T6.4).

Replays the photos run_drive.py saved through S2 to S13 with a given config, on any
CPU, then compares the objects in the store with the ground truth list
(memory_graph/eval/, T6.4e):

    duplicates    one real object, more than one graph object on it
    false merges  one graph object whose points cover two real objects
    misses        a real object with no graph object on it
    extras        a graph object of a scored class that lands on no real object

Only graph objects whose label is one of the ground truth's classes are scored.
Small things (book, light, paper ...) stay in the graph but are not counted.

How a graph object is placed on a real one. Its box centre must lie inside the
real object's outline grown by `margin` (20 cm) and within its height range grown
by `z_margin` (30 cm). The height test keeps a TV on the wall from landing on the
sofa below it. If the centre lands in two outlines, the nearer real centre wins.
The class does not have to match: a "table" on a marked desk is placed on it, and
the label is scored separately (`label_ok`). So a wrong label is not mistaken for
a duplicate plus a miss.

Duplicates are counted two ways. `duplicates` counts every extra graph object on a
real object. `duplicates_same_class` only counts those whose label fits the real
object's class (desk and table fit each other, so do shelf and cabinet). A
bookcase marked as one shelf collects several graph "book" or "shelf" objects for
its cells: the second number shows how many of those look like the object itself.

From the repo root, on the saved drive:

    python -m memory_graph.score_drive <drive_dir> [--gate fine] [--set match_radius_m=0.05 ...]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from memory_graph.anchor_store import AnchorStore
from memory_graph.cleanup import PeriodicCleanup
from memory_graph.config import MemoryGraphConfig
from memory_graph.object_store import ObjectStore
from memory_graph.run_drive import features_from_raw
from memory_graph.run_photo import load_photo, stages_after_detection

REPO = Path(__file__).resolve().parent.parent
DEFAULT_GT = REPO / "memory_graph" / "eval" / "lab_ground_truth_handdriven1.json"
# Labels that name the same kind of thing for scoring.
SAME_KIND = [{"table", "desk"}, {"shelf", "cabinet"}]


@dataclass
class GtObject:
    id: int
    cls: str
    corners: np.ndarray      # (4, 2) outline on the floor, metres
    z_bottom: float          # world z, metres
    z_top: float

    @property
    def centre(self) -> np.ndarray:
        return np.array([*self.corners.mean(axis=0), (self.z_bottom + self.z_top) / 2])


def load_ground_truth(path=DEFAULT_GT):
    """(objects, classes) from a T6.4e ground truth file."""
    j = json.loads(Path(path).read_text())
    floor = float(j["floor_z"])
    objects = [GtObject(int(o["id"]), o["class"], np.array(o["corners"], dtype=float),
                        floor + o["z_bottom_above_floor"], floor + o["z_top_above_floor"]) for o in j["objects"]]
    return objects, list(j["classes"])


def same_kind(a: str, b: str) -> bool:
    return a == b or any(a in g and b in g for g in SAME_KIND)


def _inside(xy: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Point in polygon for many points, by ray casting."""
    x, y = xy[:, 0], xy[:, 1]
    inside = np.zeros(len(xy), dtype=bool)
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        cross = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xs = (x2 - x1) * (y - y1) / (y2 - y1) + x1
        inside ^= cross & (x < xs)
    return inside


def _edge_distance(xy: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Distance from each point to the polygon's outline."""
    d = np.full(len(xy), np.inf)
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        ab = b - a
        t = np.clip(((xy - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
        d = np.minimum(d, np.linalg.norm(xy - (a + t[:, None] * ab), axis=1))
    return d


def on_object(points: np.ndarray, g: GtObject, margin: float, z_margin: float) -> np.ndarray:
    """Which 3D points fall on real object g (outline grown by margin, height by z_margin)."""
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    xy = points[:, :2]
    flat = _inside(xy, g.corners) | (_edge_distance(xy, g.corners) <= margin)
    tall = (points[:, 2] >= g.z_bottom - z_margin) & (points[:, 2] <= g.z_top + z_margin)
    return flat & tall


def score(objects: Sequence, gt: Sequence[GtObject], classes: Iterable[str],
          margin: float = 0.20, z_margin: float = 0.30,
          merge_fraction: float = 0.15, merge_points: int = 20) -> Dict:
    """Compare graph objects (anything with .id, .label, .box.center, .points,
    .sightings) with the ground truth. See the module docstring for the rules.

    A graph object is a false merge if at least two real objects each hold
    `merge_fraction` of its points and at least `merge_points` points.
    """
    classes = set(classes)
    scored = [o for o in objects if o.label in classes]
    on: Dict[int, List] = {g.id: [] for g in gt}
    extras, false_merges = [], []
    label_ok = 0
    for o in scored:
        c = np.asarray(o.box.center, dtype=float)
        hits = [g for g in gt if on_object(c[None], g, margin, z_margin)[0]]
        if hits:
            g = min(hits, key=lambda h: np.linalg.norm(h.centre[:2] - c[:2]))
            on[g.id].append(o)
            label_ok += same_kind(o.label, g.cls)
        else:
            extras.append(o)
        pts = np.asarray(o.points, dtype=float)
        covered = [g.id for g in gt
                   if (n := int(on_object(pts, g, 0.0, 0.10).sum())) >= merge_points and n >= merge_fraction * len(pts)]
        if len(covered) >= 2:
            false_merges.append((o, covered))
    by_id = {g.id: g for g in gt}
    per_gt = []
    for gid, objs in on.items():
        g = by_id[gid]
        same = [o for o in objs if same_kind(o.label, g.cls)]
        per_gt.append({"gt": gid, "class": g.cls, "graph_objects": len(objs), "same_class": len(same),
                       "labels": sorted(o.label for o in objs)})
    placed = sum(len(v) for v in on.values())
    return {
        "scored_objects": len(scored), "unscored_objects": len(objects) - len(scored), "ground_truth": len(gt),
        "duplicates": sum(max(0, len(v) - 1) for v in on.values()),
        "duplicates_same_class": sum(max(0, r["same_class"] - 1) for r in per_gt),
        "false_merges": len(false_merges),
        "misses": sum(1 for v in on.values() if not v),
        "misses_same_class": sum(1 for r in per_gt if r["same_class"] == 0),
        "extras": len(extras),
        "label_ok": f"{label_ok} of {placed}",
        "per_ground_truth": per_gt,
        "extra_objects": [{"id": o.id, "label": o.label, "centre": np.round(o.box.center, 2).tolist(),
                           "sightings": o.sightings} for o in extras],
        "false_merge_objects": [{"id": o.id, "label": o.label, "covers": ids} for o, ids in false_merges],
    }


def load_drive(drive_dir, gate: str = "real"):
    """The saved photos of a drive, in order: (Observation, raw Detections, raw vectors).
    gate "real" keeps the photos the real gate kept, "fine" keeps every saved one."""
    drive_dir = Path(drive_dir)
    index = json.loads((drive_dir / "index.json").read_text())
    out = []
    for p in index["photos"]:
        if gate == "real" and not p["real_gate"]:
            continue
        name = f"photo_{p['frame']:04d}"
        obs, raw, _ = load_photo(drive_dir / f"{name}.npz")
        raw_feats = np.load(drive_dir / f"{name}_raw_features.npy").astype(np.float64)
        out.append((obs, raw, raw_feats))
    return out


def replay(photos, cfg: MemoryGraphConfig) -> ObjectStore:
    """S2 to S13 over saved photos, as the live pipeline would run them."""
    objects = ObjectStore(cfg)
    anchors = AnchorStore(cfg, objects.graph)
    cleanup = PeriodicCleanup(objects, anchors)
    for obs, raw, raw_feats in photos:
        res = stages_after_detection(obs, raw, features_from_raw(raw, raw_feats), frozenset(), cfg)
        ids = objects.integrate(res.candidates, anchor=obs.frame_id)
        if anchors.add(obs, res.dets, res.candidates, ids) is not None:
            cleanup.photo_stored()
    return objects


def with_settings(cfg: MemoryGraphConfig, settings: Sequence[str]) -> MemoryGraphConfig:
    """cfg with `name=value` overrides, each value read as the field's current type."""
    changes = {}
    for item in settings:
        name, _, text = item.partition("=")
        if not hasattr(cfg, name):
            raise ValueError(f"no config field {name!r}")
        current = getattr(cfg, name)
        if isinstance(current, bool):
            changes[name] = text.lower() in ("1", "true", "yes")
        elif isinstance(current, (int, float, str)):
            changes[name] = type(current)(text)
        else:
            raise ValueError(f"{name} is not a number, flag or word")
    return dataclasses.replace(cfg, **changes)


def summary_line(r: Dict) -> str:
    return (f"duplicates {r['duplicates']} (same class {r['duplicates_same_class']})  "
            f"false merges {r['false_merges']}  misses {r['misses']} (same class {r['misses_same_class']})  "
            f"extras {r['extras']}  label ok {r['label_ok']}  "
            f"[{r['scored_objects']} scored, {r['unscored_objects']} unscored objects]")


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("drive", help="folder written by run_drive")
    ap.add_argument("--gt", default=str(DEFAULT_GT))
    ap.add_argument("--gate", choices=("real", "fine"), default="real")
    ap.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE", help="config overrides")
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)
    cfg = with_settings(MemoryGraphConfig(), args.set)
    gt, classes = load_ground_truth(args.gt)
    store = replay(load_drive(args.drive, args.gate), cfg)
    report = score(store.entries(), gt, classes)
    report["settings"] = {"gate": args.gate, **{s.partition("=")[0]: s.partition("=")[2] for s in args.set}}
    print(summary_line(report))
    for r in report["per_ground_truth"]:
        print(f"  gt {r['gt']:3d} {r['class']:<15} {r['graph_objects']:2d} graph objects "
              f"({r['same_class']} same class)  {', '.join(r['labels'])}")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
