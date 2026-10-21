"""A whole recorded drive through S3 and S1 to S6 once, on the GPU, saved for T6.4.

T6.4 tunes the merge test (S10) and the stages after it. Those need no model, so
the drive is run through SAM 3 and CLIP once here, every kept photo is saved, and
the tuning replays the saved photos on any CPU (step 2 of T6.4, not in this file).

Which photos are kept. The gate's pose half runs first, as T6.5b decided (D-MG12):
SAM 3 only sees a photo if the camera moved or turned enough since the last kept
photo. Then the gate's other half: a photo with no detections left after S2 is not
kept. Photos are saved at a finer gate than the real one (`--fine-m`, `--fine-deg`)
so a replay can try other gate settings. Each photo also records whether the real
gate (cfg.gate_translation_m, cfg.gate_rotation_rad) keeps it, judged among the
saved photos only. That is a close stand-in for the real gate, not the same set:
the real gate run over every frame can pick a photo the fine gate skipped. On
handdriven1 it keeps 26 of the saved photos where the exact rule keeps 29
(memory_graph/gate_sweep.py, T6.5).

Each saved photo is save_photo's .npz plus one CLIP vector for every raw detection
(`raw_features.npy` alongside). Vectors per raw detection, not per cleaned one, mean
a replay with other S2 or S5 settings still finds the right vector for each object.

On the lab box, from the repo root:

    .venv/bin/python -m memory_graph.run_drive --bag <handdriven1_0.db3> --out <dir>
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import time
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from memory_graph.anchor_gate import pose_moved
from memory_graph.config import MemoryGraphConfig
from memory_graph.image_feature import image_features
from memory_graph.run_photo import SAM3_THRESHOLD, build_sam3, save_photo, stages_after_detection
from memory_graph.sam3_adapter import detect
from memory_graph.stage_types import Detections


def raw_index(raw: Detections) -> Dict[Tuple, int]:
    """Key each raw detection by what S2 and S5 copy unchanged (label, score, box),
    so a cleaned detection can find its raw row, and with it its CLIP vector."""
    return {(lbl, round(float(c), 6), tuple(np.round(b, 3))): i
            for i, (lbl, c, b) in enumerate(zip(raw.label, raw.conf, raw.xyxy))}


def features_from_raw(raw: Detections, raw_features: np.ndarray):
    """A features_for (see run_photo.stages_after_detection) that looks up each
    cleaned detection's vector among the raw ones. Fails loudly on a miss."""
    index = raw_index(raw)

    def lookup(dets: Detections) -> np.ndarray:
        rows = []
        for lbl, c, b in zip(dets.label, dets.conf, dets.xyxy):
            key = (lbl, round(float(c), 6), tuple(np.round(b, 3)))
            if key not in index:
                raise KeyError(f"no raw detection for {key}")
            rows.append(index[key])
        return raw_features[rows] if rows else np.zeros((0, raw_features.shape[1] if raw_features.ndim == 2 else 0))
    return lookup


def main(argv: Optional[Sequence[str]] = None) -> int:
    repo = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bag", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cloud-window", type=float, default=1.0)
    ap.add_argument("--fine-m", type=float, default=0.25, help="save gate: metres moved")
    ap.add_argument("--fine-deg", type=float, default=15.0, help="save gate: degrees turned")
    ap.add_argument("--sam3", default=str(repo / "assets/models/sam3/sam3.pt"))
    ap.add_argument("--limit", type=int, default=0, help="stop after this many saved photos (0: all)")
    args = ap.parse_args(argv)

    from memory_graph.clip_encoder import OpenClipEncoder
    from memory_graph.replay_loader import FastLivoBag
    from memory_graph.vocabulary import Vocabulary

    cfg = MemoryGraphConfig()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bag = FastLivoBag(args.bag, cloud_window_s=args.cloud_window)
    segmenter, encoder = build_sam3(args.sam3), OpenClipEncoder.from_config(cfg)
    vocabulary = Vocabulary.from_config(cfg)
    fine = dataclasses.replace(cfg, gate_translation_m=args.fine_m, gate_rotation_rad=float(np.radians(args.fine_deg)))

    last_fine = last_real = None
    photos, seconds = [], []
    for i, frame in enumerate(bag.frames):
        T = frame.T_world_cam
        if not pose_moved(T, last_fine, fine):
            continue
        t0 = time.time()
        obs = bag.observation(i)
        raw = detect(segmenter, obs.rgb, vocabulary)
        raw_feats = image_features(obs.rgb, raw.xyxy, encoder, cfg) if len(raw) else np.zeros((0, 0))
        res = stages_after_detection(obs, raw, features_from_raw(raw, raw_feats), frozenset(), cfg)
        seconds.append(time.time() - t0)
        if not len(res.dets):             # the gate's other half: nothing left after S2
            continue
        last_fine = T
        real = pose_moved(T, last_real, cfg)
        if real:
            last_real = T
        name = f"photo_{obs.frame_id:04d}"
        save_photo(out / f"{name}.npz", res)
        np.save(out / f"{name}_raw_features.npy", raw_feats.astype(np.float16))
        photos.append({"frame": obs.frame_id, "t": round(obs.timestamp - bag.frames[0].timestamp, 3),
                       "real_gate": bool(real), "raw": len(raw), "cleaned": len(res.dets),
                       "candidates": len(res.candidates), "seconds": round(seconds[-1], 2)})
        print(f"{name} t {photos[-1]['t']:6.1f} s  raw {len(raw):3d}  cleaned {len(res.dets):3d}  "
              f"objects {len(res.candidates):3d}  real gate {real}  {seconds[-1]:.2f} s", flush=True)
        if args.limit and len(photos) >= args.limit:
            break

    index = {
        "bag": str(args.bag), "frames_in_bag": len(bag.frames), "cloud_window_s": args.cloud_window,
        "fine_gate": {"metres": args.fine_m, "degrees": args.fine_deg},
        "real_gate": {"metres": cfg.gate_translation_m, "degrees": round(float(np.degrees(cfg.gate_rotation_rad)), 2)},
        "sam3_threshold": SAM3_THRESHOLD, "vocabulary": list(vocabulary),
        "occlusion": {"window": bag.occlusion_window, "margin": bag.occlusion_margin},
        "photos": photos,
    }
    (out / "index.json").write_text(json.dumps(index, indent=1) + "\n")
    real_n = sum(p["real_gate"] for p in photos)
    print(f"saved {len(photos)} photos ({real_n} kept by the real gate), "
          f"{len(seconds)} photos through SAM 3, median {np.median(seconds):.2f} s each")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
