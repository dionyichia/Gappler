"""How many photos the gate's pose half keeps on a drive, and the SAM 3 time it saves (T6.5).

With the pose half first (D-MG12), SAM 3 runs once per photo that passes it, so
the cost of the expensive stage can be counted from the poses alone: no images,
no GPU, no model. For each gate setting this reports the photos kept, the photos
kept per minute, and the SAM 3 calls and seconds compared with two other ways of
choosing photos: every frame, and a fixed rate (one photo a second by default).

Assumption: a photo that passes the pose half is accepted, so the last accepted
pose moves to it. In the full pipeline a photo with no detections after S2 is not
accepted and the pose does not move. On the lab drive every photo SAM 3 saw had
detections (T6.4's run), so the count here is the count there.

On the lab box, from the repo root:

    .venv/bin/python -m memory_graph.gate_sweep --bag <handdriven1_0.db3> \\
        --sam3-seconds 1.85 --json <out.json>
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
from typing import Dict, List, Optional, Sequence

import numpy as np

from memory_graph.anchor_gate import AnchorGate
from memory_graph.config import MemoryGraphConfig


def pose_gate_keeps(poses: Sequence[np.ndarray], cfg: MemoryGraphConfig) -> List[int]:
    """Indices of the photos the pose half keeps, in order, committing each one."""
    gate = AnchorGate(cfg)
    kept = []
    for i, T in enumerate(poses):
        if gate.check_pose(T):
            gate.commit(T)
            kept.append(i)
    return kept


def fixed_rate_keeps(timestamps: Sequence[float], rate_hz: float) -> List[int]:
    """Indices kept by taking a photo every 1 / rate_hz seconds, the first one included."""
    if rate_hz <= 0:
        raise ValueError("rate_hz must be positive")
    kept, last = [], None
    for i, t in enumerate(timestamps):
        if last is None or t - last >= 1.0 / rate_hz - 1e-9:
            kept.append(i)
            last = t
    return kept


def sweep(
    timestamps: Sequence[float],
    poses: Sequence[np.ndarray],
    metres: Sequence[float],
    degrees: Sequence[float],
    sam3_seconds: float,
    rate_hz: float = 1.0,
    cfg: Optional[MemoryGraphConfig] = None,
) -> Dict:
    """One row per (metres, degrees) setting, plus the totals for every frame and
    for the fixed rate. `sam3_seconds` is the cost of one SAM 3 call."""
    if len(timestamps) != len(poses):
        raise ValueError(f"{len(timestamps)} timestamps for {len(poses)} poses")
    if not len(poses):
        raise ValueError("no frames")
    cfg = cfg or MemoryGraphConfig()
    duration = float(timestamps[-1] - timestamps[0])
    minutes = duration / 60.0
    frames = len(poses)
    fixed = len(fixed_rate_keeps(timestamps, rate_hz))
    rows = []
    for m in metres:
        for d in degrees:
            setting = dataclasses.replace(cfg, gate_translation_m=float(m), gate_rotation_rad=math.radians(d))
            kept = len(pose_gate_keeps(poses, setting))
            rows.append({
                "metres": float(m), "degrees": float(d), "kept": kept,
                "per_minute": round(kept / minutes, 2) if minutes > 0 else None,
                "sam3_seconds": round(kept * sam3_seconds, 1),
                "saved_vs_every_frame": round(1 - kept / frames, 4),
                "saved_vs_fixed_rate": round(1 - kept / fixed, 4),
            })
    return {
        "frames": frames, "duration_s": round(duration, 2), "sam3_seconds_per_call": sam3_seconds,
        "every_frame": {"calls": frames, "sam3_seconds": round(frames * sam3_seconds, 1)},
        "fixed_rate": {"rate_hz": rate_hz, "calls": fixed, "sam3_seconds": round(fixed * sam3_seconds, 1)},
        "real_gate": {"metres": cfg.gate_translation_m, "degrees": round(math.degrees(cfg.gate_rotation_rad), 2)},
        "rows": rows,
    }


def _floats(text: str) -> List[float]:
    return [float(x) for x in text.split(",") if x.strip()]


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bag", required=True)
    ap.add_argument("--sam3-seconds", type=float, required=True, help="median seconds per SAM 3 call")
    ap.add_argument("--metres", default="0.5,1,2")
    ap.add_argument("--degrees", default="30,45,90")
    ap.add_argument("--rate-hz", type=float, default=1.0)
    ap.add_argument("--json", help="also write the result here")
    args = ap.parse_args(argv)

    from memory_graph.replay_loader import FastLivoBag

    bag = FastLivoBag(args.bag)       # reads poses up front, images and clouds only on demand
    result = sweep([f.timestamp for f in bag.frames], [f.T_world_cam for f in bag.frames],
                   _floats(args.metres), _floats(args.degrees), args.sam3_seconds, args.rate_hz)
    result["bag"] = str(args.bag)

    print(f"{result['frames']} frames over {result['duration_s']} s. SAM 3 at {args.sam3_seconds} s a call: "
          f"every frame {result['every_frame']['sam3_seconds']} s, "
          f"{args.rate_hz} Hz {result['fixed_rate']['calls']} calls {result['fixed_rate']['sam3_seconds']} s")
    print(f"{'metres':>6} {'degrees':>7} {'kept':>5} {'per min':>8} {'SAM 3 s':>8} {'saved vs all':>12} {'vs rate':>8}")
    for r in result["rows"]:
        print(f"{r['metres']:6.2f} {r['degrees']:7.1f} {r['kept']:5d} {r['per_minute']:8.2f} {r['sam3_seconds']:8.1f} "
              f"{100 * r['saved_vs_every_frame']:11.2f}% {100 * r['saved_vs_fixed_rate']:7.1f}%")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(result, f, indent=1)
            f.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
