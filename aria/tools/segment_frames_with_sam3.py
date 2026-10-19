#!/usr/bin/env python3
"""Segment a folder of saved glasses frames with SAM 3, as the segmentation service would (T2.9 stage 3).

Uses the service's own model wrapper and result handling (segmentation_service.Sam3,
segmentation_logic.detections_from_sam3) and its settings, without ROS calls. Writes one
<frame>.npz per image: masks (N, H, W) bool, scores (N,), best first.

On the lab box, after the GPU check in CLAUDE.md:
    source shared_services/shared_services_env.sh
    PYTHONPATH=shared_services/segmentation:$PYTHONPATH python aria/tools/segment_frames_with_sam3.py <frames dir> <out dir> --prompt box
"""

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from gappler_common import path
from segmentation_logic import detections_from_sam3
from segmentation_service import CFG, Sam3


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("frames", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--min-score", type=float, default=CFG["min_score"],
                        help="default: the service's min_score")
    parser.add_argument("--max-detections", type=int, default=CFG["max_detections"],
                        help="default: the service's max_detections")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    model = Sam3(str(path("sam3_weights")), args.min_score)
    for frame in sorted(args.frames.glob("*.jpg")):
        image = cv2.cvtColor(cv2.imread(str(frame)), cv2.COLOR_BGR2RGB)
        start = time.monotonic()
        found = detections_from_sam3(
            model.process_text_prompt(image, args.prompt), args.min_score, args.max_detections)
        ms = (time.monotonic() - start) * 1000
        masks = np.array([d.mask for d in found], dtype=bool).reshape(-1, *image.shape[:2])
        np.savez_compressed(args.out / f"{frame.stem}.npz", masks=masks,
                            scores=np.array([d.score for d in found]))
        print(f"{frame.stem}: {len(found)} found, scores {[round(d.score, 2) for d in found]}, {ms:.0f} ms")


if __name__ == "__main__":
    main()
