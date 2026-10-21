"""One recorded photo through every stage, S0 to S11, and a 3D view of the result (T6.3).

    S0       replay_loader.FastLivoBag, or a photo saved by save_photo
    S1, S4   SAM 3, every vocabulary phrase in one batched call (sam3_batched.py)
    S2, S5   detection_filter.py, masks.py (inside sam3_adapter.segment_photo)
    S6       open_clip crops (image_feature.py, clip_encoder.py)
    S7-S9    geometry.build_candidates
    S10-S11  object_store.ObjectStore.integrate

On the lab box, from the repo root (needs the GPU, SAM 3 and the CLIP weights):

    .venv/bin/python -m memory_graph.run_photo --bag <handdriven1_0.db3> --frames 700 \\
        --rrd out.rrd --save-fixture out_fixture/

Open the view on any machine with the same rerun version: `rerun out.rrd`.

The stages after S1 do not need a model, so a photo can be saved with SAM 3's raw
output and the CLIP vectors (save_photo, save_fixture) and replayed later without
a GPU. memory_graph/tests/test_run_photo.py does that on a stored lab photo.
"""

from __future__ import annotations

import argparse
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import AbstractSet, Dict, List, Optional, Sequence, Union

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.detection_filter import filter_detections
from memory_graph.geometry import build_candidates
from memory_graph.image_feature import image_features
from memory_graph.masks import clean_masks
from memory_graph.object_store import ObjectStore
from memory_graph.sam3_adapter import detect
from memory_graph.stage_types import Candidate, Detections, Observation

# SAM 3's own confidence cut. S2 keeps a target class down to this score, so SAM 3
# must not drop it first (T6.3c item 3). Same value as the 2026-10-20 timing run.
SAM3_THRESHOLD = 0.15


@dataclass
class PhotoResult:
    """Everything one photo produced, kept so it can be shown and saved."""

    obs: Observation
    raw: Detections              # S1 and S4: SAM 3's output, before S2
    dets: Detections             # after S2 and S5, sorted by confidence
    features: np.ndarray         # (len(dets), D), S6
    candidates: List[Candidate]  # S7 to S9


def stages_after_detection(
    obs: Observation,
    raw: Detections,
    features_for,
    targets: AbstractSet[str],
    cfg: MemoryGraphConfig,
) -> PhotoResult:
    """S2, S5, S6 and S7 to S9 on SAM 3's output. `features_for(dets)` returns
    one S6 vector per detection: the encoder, or vectors saved earlier."""
    dets = filter_detections(raw, obs.rgb.shape[:2], targets, cfg)
    dets, _ = clean_masks(dets, cfg)
    features = np.asarray(features_for(dets))
    if len(dets) and len(features) != len(dets):
        raise ValueError(f"{len(features)} features for {len(dets)} detections")
    candidates = build_candidates(obs, dets, cfg, features if len(dets) else None)
    return PhotoResult(obs, raw, dets, features, candidates)


def run_photo(
    obs: Observation,
    segmenter,
    encoder,
    vocabulary: Sequence[str],
    targets: AbstractSet[str],
    cfg: MemoryGraphConfig,
) -> PhotoResult:
    """S1 to S9 for one photo. Same steps as sam3_adapter.segment_photo, with
    SAM 3's raw output kept so the photo can be saved as a fixture."""
    raw = detect(segmenter, obs.rgb, vocabulary)
    return stages_after_detection(
        obs, raw, lambda d: image_features(obs.rgb, d.xyxy, encoder, cfg), targets, cfg
    )


def summary(result: PhotoResult, ids: Sequence[int] = ()) -> List[str]:
    """One line per candidate: label, score, points, centre, box size, distance,
    and the object it went to if `ids` (from ObjectStore.integrate) is given."""
    cam = result.obs.camera_position
    lines = [f"frame {result.obs.frame_id}: {len(result.raw)} raw detections, "
             f"{len(result.dets)} after S2 and S5, {len(result.candidates)} objects"]
    for k, c in enumerate(result.candidates):
        obj = f" -> object {ids[k]}" if k < len(ids) else ""
        lines.append(
            f"  {c.label:<14} conf {c.conf:.2f}  {len(c.points):5d} pts  "
            f"centre {np.round(c.box.center, 2).tolist()}  size {np.round(c.box.extent, 2).tolist()}  "
            f"{np.linalg.norm(c.box.center - cam):.2f} m away{obj}"
        )
    return lines


# ---------------------------------------------------------------- saving a photo

def save_photo(path: Union[str, Path], result: PhotoResult) -> None:
    """The photo, SAM 3's raw output and the S6 vectors, as one .npz.

    Colour is stored as JPEG (it only colours the points, S6 is stored), depth as
    uint16 millimetres, masks bit-packed. A lab photo comes to well under 1 MB.
    """
    from PIL import Image

    obs, raw = result.obs, result.raw
    jpeg = io.BytesIO()
    Image.fromarray(obs.rgb).save(jpeg, format="JPEG", quality=90)
    masks = raw.masks if raw.masks is not None else np.zeros((0, *obs.depth.shape), dtype=bool)
    np.savez_compressed(
        path,
        rgb_jpeg=np.frombuffer(jpeg.getvalue(), dtype=np.uint8),
        depth_mm=np.round(obs.depth * 1000.0).astype(np.uint16),
        K=obs.K, T_world_cam=obs.T_world_cam,
        frame_id=obs.frame_id, timestamp=obs.timestamp,
        xyxy=raw.xyxy, conf=raw.conf, class_id=raw.class_id,
        label=np.array(raw.label, dtype=str),
        masks=np.packbits(masks, axis=-1), mask_width=masks.shape[-1],
        features=result.features.astype(np.float32),
    )


def load_photo(path: Union[str, Path]):
    """(Observation, raw Detections, S6 vectors) from a save_photo file."""
    from PIL import Image

    z = np.load(path)
    rgb = np.asarray(Image.open(io.BytesIO(z["rgb_jpeg"].tobytes())).convert("RGB"))
    depth = z["depth_mm"].astype(np.float32) / 1000.0
    obs = Observation(rgb=rgb, depth=depth, K=z["K"], T_world_cam=z["T_world_cam"],
                      frame_id=int(z["frame_id"]), timestamp=float(z["timestamp"]))
    masks = np.unpackbits(z["masks"], axis=-1, count=int(z["mask_width"])).astype(bool)
    raw = Detections(xyxy=z["xyxy"], conf=z["conf"], class_id=z["class_id"],
                     label=[str(s) for s in z["label"]], masks=masks)
    return obs, raw, z["features"].astype(np.float64)


# ---------------------------------------------------------------- the 3D view

def _palette(n: int) -> np.ndarray:
    """n distinct uint8 colours."""
    hues = (np.arange(n) * 0.61803) % 1.0
    import colorsys

    return np.array([[int(255 * v) for v in colorsys.hsv_to_rgb(h, 0.8, 0.95)] for h in hues], dtype=np.uint8)


def log_rerun(
    path: Union[str, Path],
    results: Sequence[PhotoResult],
    store: Optional[ObjectStore] = None,
    room: Optional[np.ndarray] = None,
) -> None:
    """Write a Rerun .rrd: the room cloud in grey, each photo's camera, image and
    masks, each candidate's cleaned cloud and box, and the fused objects."""
    import rerun as rr
    from scipy.spatial.transform import Rotation

    rr.init("gappler_memory_graph_t6_3", spawn=False)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    rr.save(str(path))
    rr.log("world", rr.ViewCoordinates.RIGHT_HAND_Z_UP, static=True)
    if room is not None and len(room):
        rr.log("world/room", rr.Points3D(room, colors=[150, 150, 150], radii=0.01), static=True)

    def boxes(entity, items, colors, labels):
        if not items:
            return
        rr.log(entity, rr.Boxes3D(
            centers=[b.center for b in items], half_sizes=[b.extent / 2 for b in items],
            quaternions=[rr.Quaternion(xyzw=Rotation.from_matrix(_proper(b.R)).as_quat()) for b in items],
            colors=colors, labels=labels,
        ))

    for res in results:
        obs, f = res.obs, f"world/frame_{res.obs.frame_id}"
        h, w = obs.depth.shape
        rr.log(f"{f}/camera", rr.Transform3D(translation=obs.T_world_cam[:3, 3], mat3x3=obs.T_world_cam[:3, :3]))
        rr.log(f"{f}/camera/image", rr.Pinhole(image_from_camera=obs.K, resolution=[w, h], image_plane_distance=0.3))
        rr.log(f"{f}/camera/image/rgb", rr.Image(obs.rgb))
        rr.log(f"{f}/camera/image/depth", rr.DepthImage(obs.depth, meter=1.0))
        seg = np.zeros((h, w), dtype=np.uint16)
        for i in range(len(res.dets)):
            seg[res.dets.masks[i]] = i + 1
        rr.log(f"{f}/camera/image/masks", rr.SegmentationImage(seg))
        rr.log(f"{f}/camera/image/masks", rr.AnnotationContext(
            [(i + 1, f"{lbl} {c:.2f}") for i, (lbl, c) in enumerate(zip(res.dets.label, res.dets.conf))]
        ), static=True)
        colors = _palette(len(res.candidates))
        for k, c in enumerate(res.candidates):
            rr.log(f"{f}/candidates/{k}_{c.label.replace(' ', '_')}",
                   rr.Points3D(c.points, colors=colors[k], radii=0.012))
        boxes(f"{f}/boxes", [c.box for c in res.candidates], colors,
              [f"{c.label} {c.conf:.2f}" for c in res.candidates])

    if store is not None and len(store):
        entries = store.entries()
        boxes("world/objects", [e.box for e in entries], _palette(len(entries)),
              [f"#{e.id} {e.label} x{e.sightings}" for e in entries])


def _proper(R: np.ndarray) -> np.ndarray:
    """A PCA box's axes can form a reflection. Flip one axis so it is a rotation."""
    R = np.array(R, dtype=float)
    if np.linalg.det(R) < 0:
        R[:, 2] = -R[:, 2]
    return R


# ---------------------------------------------------------------- models

def build_sam3(checkpoint: Union[str, Path], threshold: float = SAM3_THRESHOLD, max_prompts_per_pass: int = 16):
    """SAM 3 set up as the segmentation service does: bfloat16 autocast and tf32."""
    import torch
    import sam3
    from sam3 import build_sam3_image_model
    from sam3.model.sam3_image_processor import Sam3Processor

    from memory_graph.sam3_batched import BatchedSam3

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
    bpe = Path(sam3.__file__).parent / "assets" / "bpe_simple_vocab_16e6.txt.gz"
    model = build_sam3_image_model(bpe_path=str(bpe), checkpoint_path=str(checkpoint), load_from_HF=False)
    return BatchedSam3(Sam3Processor(model, confidence_threshold=threshold), max_prompts_per_pass)


def main(argv: Optional[Sequence[str]] = None) -> int:
    repo = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--bag", help="FAST-LIVO rosbag2 .db3")
    src.add_argument("--photo", nargs="+", help="photos saved by --save-fixture: no model needed")
    ap.add_argument("--frames", type=int, nargs="+", default=[], help="frame indices in the bag")
    ap.add_argument("--cloud-window", type=float, default=1.0,
                    help="seconds of LiDAR either side of each image (1.0 s fills about 13 percent)")
    ap.add_argument("--sam3", default=str(repo / "assets/models/sam3/sam3.pt"))
    ap.add_argument("--targets", nargs="*", default=[])
    ap.add_argument("--rrd", help="write the 3D view here")
    ap.add_argument("--room", help=".npy world points to draw behind the objects")
    ap.add_argument("--save-fixture", help="folder: one .npz per photo, plus expected.json")
    args = ap.parse_args(argv)

    cfg = MemoryGraphConfig()
    targets = frozenset(args.targets)
    results: List[PhotoResult] = []
    if args.bag:
        from memory_graph.clip_encoder import OpenClipEncoder
        from memory_graph.replay_loader import FastLivoBag
        from memory_graph.vocabulary import Vocabulary

        bag = FastLivoBag(args.bag, cloud_window_s=args.cloud_window)
        segmenter, encoder = build_sam3(args.sam3), OpenClipEncoder.from_config(cfg)
        vocabulary = Vocabulary.from_config(cfg)
        for i in args.frames:
            results.append(run_photo(bag.observation(i), segmenter, encoder, vocabulary, targets, cfg))
    else:
        for p in args.photo:
            obs, raw, feats = load_photo(p)
            results.append(stages_after_detection(obs, raw, lambda d, f=feats: f, targets, cfg))

    store = ObjectStore(cfg)
    expected: Dict[str, list] = {}
    for res in results:
        ids = store.integrate(res.candidates, anchor=res.obs.frame_id)
        print("\n".join(summary(res, ids)))
        expected[str(res.obs.frame_id)] = [
            {"label": c.label, "points": len(c.points), "centre": np.round(c.box.center, 4).tolist()}
            for c in res.candidates
        ]
    print(f"object store: {len(store)} objects from {len(results)} photos")
    for e in store.entries():
        print(f"  #{e.id} {e.label:<14} seen {e.sightings}x  centre {np.round(e.box.center, 2).tolist()}")

    if args.rrd:
        room = np.load(args.room) if args.room else None
        log_rerun(args.rrd, results, store, room)
        print(f"wrote {args.rrd}")
    if args.save_fixture:
        out = Path(args.save_fixture)
        out.mkdir(parents=True, exist_ok=True)
        for res in results:
            save_photo(out / f"photo_{res.obs.frame_id:04d}.npz", res)
        (out / "expected.json").write_text(json.dumps(expected, indent=1) + "\n")
        print(f"saved {len(results)} photos to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
