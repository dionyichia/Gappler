#!/usr/bin/env python3
"""Run the glasses object-pick chain on a recording, one stage at a time (T2.9).

Stage 1, frames: the RGB frames, rotated and undistorted. Each output image shows three panels:
  raw       rotated 90 degrees clockwise, as the app publishes it
  live      rotated, then undistorted with the unrotated calibration (image_streaming_pipeline.py:132-135)
  fixed     undistorted, then rotated
If live and fixed differ, the live order is wrong.

Stage 2, gaze: the eye model on every eye camera frame, cut at the fixed gaze depth
(eye_tracking.py) and moved through the same undistort and rotate as the image, as et_worker
publishes it. For each RGB frame the gaze is averaged over the last gaze_window_s, as the aria
segmentation client does (gaze_pick.mean_gaze). Draws the averaged gaze (big ring) and the newest eye frame's
gaze (small ring). Writes gaze.csv, one row per RGB frame, and the frames without rings in
clean/, for SAM 3 on the box (segment_frames_with_sam3.py, stage 3).

Stage 4, pick: the mask under the averaged gaze, else the nearest within pick_radius_px
(gaze_pick.pick_mask, aria_config.yaml).
Reads gaze.csv and the box's masks, copied into <id>.pick/3_masks/. Writes pick.csv and, per
frame, every mask with its score, the picked one boxed thick.

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
from gaze_pick import mean_gaze, pick_mask  # noqa: E402
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


def draw_detections(image, masks, scores, picked, x, y):
    """Every mask tinted and tagged #n, the gaze ring, and a legend of scores on the right."""
    colors = [tuple(int(c) for c in np.random.default_rng(j).integers(60, 255, 3)) for j in range(len(masks))]
    for j, m in enumerate(masks):
        image[m] = 0.45 * image[m] + 0.55 * np.array(colors[j])
    for j, m in enumerate(masks):
        ys, xs = np.nonzero(m)
        cv2.rectangle(image, (xs.min(), ys.min()), (xs.max(), ys.max()), colors[j], 5 if j == picked else 2)
        cv2.putText(image, f"#{j + 1}", (int(xs.min()), max(int(ys.min()) - 8, 25)), 0, 0.9, colors[j], 2)
    cv2.circle(image, (int(x), int(y)), int(PICK["pick_radius_px"]), (255, 0, 0), 3)
    cv2.circle(image, (int(x), int(y)), 8, (255, 0, 0), -1)
    legend = np.full((image.shape[0], 380, 3), 30, np.uint8)
    lines = [(f"{len(masks)} found", (255, 255, 255))] + [
        (f"#{j + 1}  {s:.2f}" + ("  PICKED" if j == picked else ""), colors[j]) for j, s in enumerate(scores)]
    lines.append(("nothing picked" if picked is None else "", (80, 80, 255)))
    for k, (text, color) in enumerate(lines):
        cv2.putText(legend, text, (15, 45 + 45 * k), 0, 0.9, color, 2)
    return np.hstack([image, legend])


def pick_stage(pick_dir: Path) -> None:
    out = pick_dir / "4_pick"
    out.mkdir(exist_ok=True)
    with open(pick_dir / "2_gaze" / "gaze.csv") as f:
        gaze = list(csv.DictReader(f))
    rows = []
    for g in gaze:
        mask_file = pick_dir / "3_masks" / f"{g['frame']}.npz"
        if not mask_file.exists() or not g["x_px"]:
            continue
        found = np.load(mask_file)
        masks, scores = found["masks"], found["scores"]
        x, y = float(g["x_px"]), float(g["y_px"])
        i, dist = pick_mask(masks, x, y, PICK["pick_radius_px"])
        rows.append([g["frame"], g["stop"], len(masks), "" if i is None else i,
                     "" if i is None else round(float(scores[i]), 3), round(dist, 1)])

        image = cv2.imread(str(pick_dir / "2_gaze" / "clean" / f"{g['frame']}.jpg"))
        cv2.imwrite(str(out / f"{g['frame']}.jpg"), draw_detections(image, masks, scores, i, x, y))

    with open(out / "pick.csv", "w", newline="") as f:
        csv.writer(f).writerows([["frame", "stop", "masks", "picked", "score", "dist_px"], *rows])
    print(f"{sum(r[3] != '' for r in rows)} of {len(rows)} frames picked a mask -> {out}")


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
            raw = np.rot90(image, -1)
            live = calibration.distort_by_calibration(np.ascontiguousarray(raw), dest, src)
            panels = [cv2.resize(np.ascontiguousarray(p), (PANEL_PX, PANEL_PX)) for p in (raw, live, fixed)]
            for p, label in zip(panels, ("raw", "live", "fixed")):
                cv2.putText(p, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
            cv2.imwrite(str(out / f"{name}.jpg"), cv2.cvtColor(np.hstack(panels), cv2.COLOR_RGB2BGR))
            continue

        px = mean_gaze(samples, t_ns / 1e9, PICK["gaze_window_s"])
        px_now = mean_gaze(samples, t_ns / 1e9, 0.1)   # the newest eye frame alone, at 10 fps
        rows.append([name, stop, *(px or ("", "")), *(px_now or ("", ""))])
        cv2.imwrite(str(out / "clean" / f"{name}.jpg"), cv2.cvtColor(fixed, cv2.COLOR_RGB2BGR))
        if px is not None:
            cv2.circle(fixed, (int(px[0]), int(px[1])), 25, (255, 0, 0), 6)
        if px_now is not None:
            cv2.circle(fixed, (int(px_now[0]), int(px_now[1])), 10, (255, 255, 0), 3)
        cv2.imwrite(str(out / f"{name}.jpg"),
                    cv2.cvtColor(cv2.resize(fixed, (PANEL_PX * 2, PANEL_PX * 2)), cv2.COLOR_RGB2BGR))

    if args.stage == 2:
        with open(out / "gaze.csv", "w", newline="") as f:
            csv.writer(f).writerows(
                [["frame", "stop", "x_px", "y_px", "x_now_px", "y_now_px"], *rows])
    print(f"{n} frames -> {out}")


if __name__ == "__main__":
    # Self-check: with no lens distortion, to_published_pixel is just the 90 degree rotation
    flat = calibration.get_linear_camera_calibration(4, 4, 2, "camera-rgb")
    a = np.zeros((4, 4))
    a[1, 3] = 1  # x=3, y=1
    x, y = (round(v) for v in to_published_pixel((3, 1), flat, flat))
    assert np.rot90(a, -1)[y, x] == 1
    main()
