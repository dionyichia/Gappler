#!/usr/bin/env python3
"""Run the glasses object-pick chain on a recording, one stage at a time (T2.9).

Stage 1, frames: the RGB frames, rotated and undistorted. Each output image shows three panels:
  raw       rotated 90 degrees clockwise, as the app publishes it
  old       rotated, then undistorted with the unrotated calibration, the app's order before T2.13
  fixed     undistorted, then rotated, the app's order since T2.13
The shift between old and fixed is the T2.13 error.

Stage 2, gaze: the eye model on every eye camera frame, cut at the fixed gaze depth
(eye_tracking.py) and moved through the same undistort and rotate as the image, as et_worker
publishes it. Draws, on each RGB frame, the gaze samples that vote on it (a ring each). Writes
gaze_samples.csv, one row per eye frame with its capture time, gaze.csv, one row per RGB frame
with its capture time, and the frames without rings in clean/, for SAM 3 on the box
(segment_frames_with_sam3.py, stage 3).

Stage 4, pick: the gaze samples captured within gaze_to_image_max_s of the frame vote, as the
aria segmentation client does (gaze_pick.vote, aria_config.yaml): each picks the mask under it,
else the nearest within pick_radius_px. The mask with at least vote_min_share of the votes wins.
Reads gaze.csv, gaze_samples.csv and the box's masks, copied into <id>.pick/3_masks/. Writes
pick.csv and, per frame, every mask with its score, the picked one boxed thick.

Runs on any machine, no ROS, no glasses SDK. Needs projectaria_tools, and for stage 2 torch and
projectaria-eyetracking (pyproject.toml). Dion's Mac has them in the aria-test venv:
    python aria/tools/replay_recording_gaze_pick.py <recordings>/<id>.vrs --stage 2
    python aria/tools/replay_recording_gaze_pick.py <recordings>/<id>.vrs --stage 4
Writes <id>.pick/ next to the recording, outside git.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from projectaria_tools.core import calibration
from projectaria_tools.core.data_provider import create_vrs_data_provider

from projectaria_tools.core.stream_id import StreamId

REPO = Path(__file__).resolve().parents[2]
# The live code's own helpers, imported by folder: their packages pull in ROS and the glasses SDK
for folder in ("shared", "aria/aria_app/services/aria_device/stream",
               "aria/aria_app/services/aria_segmentation_client"):
    sys.path.insert(0, str(REPO / folder))
from gappler_common import config  # noqa: E402
from gaze_pick import vote  # noqa: E402
from undistortion_helper import to_published_pixel  # noqa: E402

RGB_STREAM_ID = "214-1"  # AriaConfig.RGB_STREAM_ID
EYE_STREAM_ID = "211-1"  # AriaConfig.EYE_STREAM_ID
EYE_MODEL = REPO / "aria/aria_app/models/projectaria_eyetracking"  # ModelPaths
PANEL_PX = 512
PICK = config("aria", "aria_segmentation_client")


def stop_at(t_ns: int, stops: list) -> int:
    """Stop number the frame falls in, 0 if none."""
    for s in stops:
        if s["start_device_ns"] <= t_ns <= s["end_device_ns"]:
            return s["stop"]
    return 0


def gaze_angles(model, eye_image: np.ndarray) -> tuple:
    """Yaw and pitch in radians from one eye camera image, as eye_tracking.py predicts them."""
    import torch

    preds, _, _ = model.predict(torch.as_tensor(eye_image))
    return tuple(float(v) for v in preds[0].detach().numpy())


def gaze_pixel(yaw: float, pitch: float, device_calib, src, depth_m: float):
    """Raw RGB pixel the gaze points at, cut at depth_m. None if outside the image."""
    from projectaria_tools.core.mps.utils import get_gaze_vector_reprojection

    # The reprojection reads only .yaw and .pitch. EyeGaze has no constructor in this SDK.
    return get_gaze_vector_reprojection(
        eye_gaze=SimpleNamespace(yaw=yaw, pitch=pitch), stream_id_label="camera-rgb",
        device_calibration=device_calib, camera_calibration=src, depth_m=depth_m)


def voters(samples, t: float):
    """The (x, y) of the (time, x, y) samples captured within gaze_to_image_max_s of time t."""
    return [(x, y) for ts, x, y in samples if abs(ts - t) <= PICK["gaze_to_image_max_s"]]


def draw_detections(image, masks, scores, picked, points, share):
    """Every mask tinted and tagged #n, a dot per voting gaze sample with the pick radius around
    the first, and a legend of scores and the vote share on the right."""
    colors = [tuple(int(c) for c in np.random.default_rng(j).integers(60, 255, 3)) for j in range(len(masks))]
    for j, m in enumerate(masks):
        image[m] = 0.45 * image[m] + 0.55 * np.array(colors[j])
    for j, m in enumerate(masks):
        ys, xs = np.nonzero(m)
        cv2.rectangle(image, (xs.min(), ys.min()), (xs.max(), ys.max()), colors[j], 5 if j == picked else 2)
        cv2.putText(image, f"#{j + 1}", (int(xs.min()), max(int(ys.min()) - 8, 25)), 0, 0.9, colors[j], 2)
    if points:
        cv2.circle(image, tuple(int(v) for v in points[0]), int(PICK["pick_radius_px"]), (255, 0, 0), 3)
    for x, y in points:
        cv2.circle(image, (int(x), int(y)), 8, (255, 0, 0), -1)
    legend = np.full((image.shape[0], 380, 3), 30, np.uint8)
    lines = [(f"{len(masks)} found", (255, 255, 255))] + [
        (f"#{j + 1}  {s:.2f}" + ("  PICKED" if j == picked else ""), colors[j]) for j, s in enumerate(scores)]
    lines.append((f"vote share {share:.2f}" + ("  nothing picked" if picked is None else ""), (80, 80, 255)))
    for k, (text, color) in enumerate(lines):
        cv2.putText(legend, text, (15, 45 + 45 * k), 0, 0.9, color, 2)
    return np.hstack([image, legend])


def pick_stage(pick_dir: Path) -> None:
    out = pick_dir / "4_pick"
    out.mkdir(exist_ok=True)
    with open(pick_dir / "2_gaze" / "gaze.csv") as f:
        frames = list(csv.DictReader(f))
    with open(pick_dir / "2_gaze" / "gaze_samples.csv") as f:
        samples = [(float(r["t_s"]), float(r["x_px"]), float(r["y_px"])) for r in csv.DictReader(f)]
    rows = []
    for g in frames:
        mask_file = pick_dir / "3_masks" / f"{g['frame']}.npz"
        points = voters(samples, float(g["t_s"]))
        if not mask_file.exists() or not points:
            continue
        found = np.load(mask_file)
        masks, scores = found["masks"], found["scores"]
        i, share, dist = vote(masks, points, PICK["pick_radius_px"], PICK["vote_min_share"])
        rows.append([g["frame"], g["stop"], len(masks), len(points), "" if i is None else i,
                     "" if i is None else round(float(scores[i]), 3), round(share, 2), round(dist, 1)])

        image = cv2.imread(str(pick_dir / "2_gaze" / "clean" / f"{g['frame']}.jpg"))
        cv2.imwrite(str(out / f"{g['frame']}.jpg"), draw_detections(image, masks, scores, i, points, share))

    with open(out / "pick.csv", "w", newline="") as f:
        csv.writer(f).writerows(
            [["frame", "stop", "masks", "votes", "picked", "score", "share", "dist_px"], *rows])
    print(f"{sum(r[4] != '' for r in rows)} of {len(rows)} frames picked a mask -> {out}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("vrs", type=Path)
    parser.add_argument("--stage", type=int, choices=(1, 2, 4), default=2)
    args = parser.parse_args()
    if args.stage == 4:
        return pick_stage(args.vrs.with_suffix(".pick"))

    cfg = config("aria", "aria_device")
    size, focal = cfg["undistorted_image_size_px"], cfg["undistorted_focal_length_px"]

    provider = create_vrs_data_provider(str(args.vrs))
    rgb, eye = StreamId(RGB_STREAM_ID), StreamId(EYE_STREAM_ID)
    device_calib = provider.get_device_calibration()
    src = device_calib.get_camera_calib("camera-rgb")
    dest = calibration.get_linear_camera_calibration(size, size, focal, "camera-rgb")

    stops_file = args.vrs.with_suffix(".stops.json")
    stops = json.loads(stops_file.read_text())["stops"] if stops_file.exists() else []

    out = args.vrs.with_suffix(".pick") / ("1_frames" if args.stage == 1 else "2_gaze")
    (out / "clean").mkdir(parents=True, exist_ok=True)
    if args.stage == 2:
        from projectaria_eyetracking.inference import infer

        model = infer.EyeGazeInference(
            str(EYE_MODEL / "weights.pth"), str(EYE_MODEL / "config.yaml"), "cpu")
        depth_m = config("aria", "eye_tracking")["default_depth_m"]
        rows = []
        samples = []   # (time s, x, y) in the published image, one per eye frame, as et_worker sends
        for k in range(provider.get_num_data(eye)):
            eye_image, eye_record = provider.get_image_data_by_index(eye, k)
            raw = gaze_pixel(*gaze_angles(model, eye_image.to_numpy_array()), device_calib, src, depth_m)
            px = None if raw is None else to_published_pixel(raw, src, dest)
            if px is not None:
                samples.append((eye_record.capture_timestamp_ns / 1e9, *px))

    n = provider.get_num_data(rgb)
    t0 = provider.get_image_data_by_index(rgb, 0)[1].capture_timestamp_ns
    for i in range(n):
        image, record = provider.get_image_data_by_index(rgb, i)
        image = image.to_numpy_array()
        t_ns = record.capture_timestamp_ns
        fixed = np.ascontiguousarray(np.rot90(calibration.distort_by_calibration(image, dest, src), -1))
        stop = stop_at(t_ns, stops)
        name = f"{(t_ns - t0) / 1e9:06.1f}s" + (f"_stop{stop}" if stop else "")

        if args.stage == 1:
            raw = np.ascontiguousarray(np.rot90(image, -1))
            old = calibration.distort_by_calibration(raw, dest, src)
            panels = [cv2.resize(p, (PANEL_PX, PANEL_PX)) for p in (raw, old, fixed)]
            for p, label in zip(panels, ("raw", "old", "fixed")):
                cv2.putText(p, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            cv2.imwrite(str(out / f"{name}.jpg"), cv2.cvtColor(np.hstack(panels), cv2.COLOR_RGB2BGR))
            continue

        rows.append([name, stop, t_ns / 1e9])
        cv2.imwrite(str(out / "clean" / f"{name}.jpg"), cv2.cvtColor(fixed, cv2.COLOR_RGB2BGR))
        for x, y in voters(samples, t_ns / 1e9):
            cv2.circle(fixed, (int(x), int(y)), 10, (255, 0, 0), 3)
        cv2.imwrite(str(out / f"{name}.jpg"),
                    cv2.cvtColor(cv2.resize(fixed, (PANEL_PX * 2, PANEL_PX * 2)), cv2.COLOR_RGB2BGR))

    if args.stage == 2:
        # Times on the glasses clock, as the live topics are stamped (T2.19)
        with open(out / "gaze.csv", "w", newline="") as f:
            csv.writer(f).writerows([["frame", "stop", "t_s"], *rows])
        with open(out / "gaze_samples.csv", "w", newline="") as f:
            csv.writer(f).writerows([["t_s", "x_px", "y_px"], *samples])
    print(f"{n} frames -> {out}")


if __name__ == "__main__":
    # Self-check: with no lens distortion, to_published_pixel is just the 90 degree rotation
    flat = calibration.get_linear_camera_calibration(4, 4, 2, "camera-rgb")
    a = np.zeros((4, 4))
    a[1, 3] = 1  # x=3, y=1
    x, y = (round(v) for v in to_published_pixel((3, 1), flat, flat))
    assert np.rot90(a, -1)[y, x] == 1
    main()
