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
