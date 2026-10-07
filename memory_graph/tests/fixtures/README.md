# Test photos for the image feature (T6.3f)

`test_clip_encoder.py` looks here for three photos:

| File | What it shows |
|---|---|
| `chair_view_a.jpg` | a chair |
| `chair_view_b.jpg` | the same chair from a nearby viewpoint |
| `sink.jpg` | a sink |

Each photo should be cropped roughly to the object, as a detection box would be.
Keep them small (about 640 px on the long side).

Until all three exist, the chair-against-sink test reports SKIPPED, and T6.3f is
not done. When you add them, note below where each came from and its licence.
