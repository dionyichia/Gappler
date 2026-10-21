# Test photos for the image feature (T6.3f)

`test_clip_encoder.py` uses these for the T6.3f done-when: two views of the same
chair must score above 0.8, and the chair against each other object clearly lower.

| File | What it shows | Cut from |
|---|---|---|
| `chair_view_a.jpg` | an office chair, front view | photo 2 |
| `chair_view_b.jpg` | the same chair, front-quarter view | photo 3 |
| `sofa.jpg` | a dark sofa | photo 1 |
| `shelf.jpg` | a wooden display shelf | photo 1 |
| `bench.jpg` | a wooden bench with a grey seat | photo 3 |

Source: three phone photos taken by Zongzhe in the lab on 2026-10-07. The
originals are not in the repo. Each file is one object cropped by hand with the
pipeline's own padding (`crop_pad_ratio` 0.1), as a detection box would be, then
shrunk to at most 640 px on the long side.

The done-when first named a sink as the different object. No sink photo was
available, so on 2026-10-07 Zongzhe changed it to the other objects in these photos.

If a file is missing, the test reports SKIPPED, not passed.

# Two recorded frames for the replay loader (T6.3b)

`test_replay_loader.py` uses `tum_fr1_xyz/` for the T6.3b done-when: back-projecting
the depth image from two poses puts the same surfaces in the same place.

| File | What it is |
|---|---|
| `tum_fr1_xyz/depth/*.png` | two depth images, 640 x 480, 16-bit, 5000 units per metre. Copied unchanged |
| `tum_fr1_xyz/rgb/*.jpg` | the two colour images. Re-encoded from PNG to JPEG (quality 85) to keep the repo small |
| `tum_fr1_xyz/rgb.txt`, `depth.txt` | the lines of the original lists for these two frames, with `.jpg` names in `rgb.txt` |
| `tum_fr1_xyz/groundtruth.txt` | the two pose rows nearest in time to the two colour images |

Source: frames 0 and 124 of `rgbd_dataset_freiburg1_xyz` from the TUM RGB-D benchmark,
a handheld Kinect moved over a desk, with poses from a motion-capture system. The camera
moved 0.40 m and turned 9 degrees between the two frames.

- Download (448 MB): https://cvg.cit.tum.de/rgbd/dataset/freiburg1/rgbd_dataset_freiburg1_xyz.tgz
- Licence: Creative Commons Attribution 4.0 (CC BY 4.0).
- Credit: J. Sturm, N. Engelhard, F. Endres, W. Burgard, D. Cremers, "A Benchmark for the
  Evaluation of RGB-D SLAM Systems", IROS 2012.

The full recording is not in the repo. To run the loader on all of it, unpack the
download anywhere (`assets/recordings/` is gitignored) and pass the folder to
`TumSequence` in `memory_graph/replay_loader.py`.

# Three lab photos for the whole pipeline (T6.3)

`test_run_photo.py` replays every stage after SAM 3 (S2 to S11) on these, with no GPU
and no model.

| File | What it is |
|---|---|
| `fastlivo_photo/photo_0700.npz` | a chair, a bookcase and a sofa, about 2 m away |
| `fastlivo_photo/photo_1500.npz` | a desk with a cup and a monitor, about 1 m away |
| `fastlivo_photo/photo_2200.npz` | the bookcase of 0700 again, seen from 1.17 m away, with a TV, bench and sofa |
| `fastlivo_photo/expected.json` | per photo, the objects the GPU run gave: label, point count, box centre |

Each `.npz` holds the colour image (JPEG bytes), the depth (uint16 millimetres), `K`,
`T_world_cam`, SAM 3's raw output for the 30-phrase base vocabulary (boxes, scores,
labels, bit-packed masks) and one CLIP vector per detection after S5. Read and written
by `load_photo` and `save_photo` in `memory_graph/run_photo.py`.

Source: frames 700, 1500 and 2200 of the FAST-LIVO hand-driven bag
`t35d-attended-20261020.raLTgE/run/bag/handdriven1/handdriven1_0.db3` on the lab box,
recorded by the team in the lab on 2026-10-20. Depth is LiDAR projected into the colour
camera (1 s either side, occlusion filter 7 px, 10 percent) by `FastLivoBag`. Made on
the lab box GPU on 2026-10-21 with:

    python -m memory_graph.run_photo --bag <bag> --frames 700 1400 1500 2200 --save-fixture <dir>

(frame 1400 left out to keep the folder under 1 MB). SAM 3 in bfloat16 at threshold
0.15, CLIP in float16. If SAM 3, the vocabulary or the loader changes, make them again
the same way: the saved detections are SAM 3's, so `expected.json` only checks the
stages after it.

If `expected.json` is missing, the test reports SKIPPED, not passed.
