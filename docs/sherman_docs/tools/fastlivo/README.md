# T3.5 FAST-LIVO2 tooling (lab scratch, preserved)

Byte-identical copies of the lab-box scratch tooling behind the T3.5a/b
evidence. The [2026-10-17 audit](../../T3.5_VERIFICATION_20261017.md) found this
tooling untracked (finding 5); this directory preserves it in Git. Every file
was copied from the lab box and verified with SHA-256 against the originals —
26/26 identical at preservation time. `MANIFEST.sha256` carries the hashes so
the box copies can be re-verified:

```bash
cd docs/sherman_docs/tools/fastlivo
sha256sum -c MANIFEST.sha256
```

`replay/` is the exception to the frozen-copy reading: it is live reviewed
tooling that evolves (the T3.5c parameterisation changed five of its files and
`playback_qos.yaml`). Its manifest rows are regenerated with each change, and a
fresh bundle is staged to the box before a run, so a re-verification against an
older box bundle will differ exactly where the bundle predates the change.
Everything outside `replay/` is still the frozen preservation set.

Nothing here is shared runtime code: no robot-stack module imports it and
nothing commands arm or base hardware. It runs on the lab Docker host / lab
box as `rcp2026`, coordinated with the other operators. Read each bundle's own
README before running anything.

## Contents

| Path | What it is |
|---|---|
| `recipe/` | FAST-LIVO2 experimental compile recipe: pinned `U-AMC/FAST-LIVO2-ROS2` build with the `-march=native` CMake patch, the VIO sampling guard, and a bounded Docker wrapper. 10 offline unit tests. |
| `replay/` | Isolated offline replay harness for the public `Bright_Screen_Wall_raw` bag (raw bgr8 images, no republisher), with progress and container-verification scripts, configs and 45 unit tests. `AUDIT_20261016.md` / `HARNESS_PLAN.md` are the harness trail. |
| `analyze_bag.py` | Strict one-pass audit of T3.5 capture-profile bags. Exit code is the verdict: `ANALYSIS_OK` (0) or invariant `FAIL` lines (1). |
| `test_analyze_bag.py` | Synthetic mini-bag tests for the analyser's pass and fail paths. |
| `EVIDENCE_t35b-capture.sha256` | Frozen SHA-256 of the two captured bags. Verify on the box: `cd <capture dir> && sha256sum -c <repo>/docs/sherman_docs/tools/fastlivo/EVIDENCE_t35b-capture.sha256`. |
| `EVIDENCE_t59-replay-20261016T175305Z-433728.sha256` | Frozen SHA-256 of all 24 files of the accepted T3.5a replay run (same verification method). |

## Running the analyser (lab box)

The analyser needs the nav overlay for `livox_ros_driver2` messages:

```bash
source /opt/ros/humble/setup.bash
source ~/rcp-Gappler/install_nav/setup.bash

python3 analyze_bag.py ~/rcp-Gappler/log/t59-fastlivo/log/t35b-capture.R0fVks/t35b_proof3
python3 -m unittest -v test_analyze_bag
```

It streams the bag (no full-bag memory) and asserts: every topic present;
strictly increasing header stamps per topic; `point_num` == decoded points;
`timebase` == header (≤ 1 ms); finite LiDAR XYZ; `offset_time` within the scan
budget; finite IMU gyro/accel; single image geometry/encoding/frame variant;
image payload == `step × height`; single CameraInfo calibration variant;
`plumb_bob` with |D| == 5; identical image/CameraInfo stamp multisets.
Zero-range returns, per-scan point ordering, receipt-minus-header lags and IMU
means are reported, not asserted — they are characteristics, and the lags are
host-side bag timestamps, not sensor synchronisation.

Verified on `t35b_proof3` (2026-10-17): `ANALYSIS_OK`, exit 0, every audit
number reproduced; all six mini-bag tests pass (five corrupted bags fail with
the expected diagnostic, the valid bag passes).

`analyze_bag.py` supersedes the box scratch `analyze_proof3_ros.py`, which
mislabeled units (ns as µs), mislabeled a mean as a median, checked only
sampled points and printed `ANALYSIS_OK` unconditionally.

## Provenance

- Preserved 2026-10-17 from `~/rcp-Gappler/log/t59-fastlivo/log/recipe/` and
  `~/rcp-Gappler/log/t59-fastlivo/log/replay-candidate.RpximV/` (still present
  on the box as scratch, untracked). This directory is the tracked record.
- The recipe produced the replay image; the harness produced the accepted
  T3.5a PASS (`t59-replay-20261016T175305Z-433728/evidence/result.json`) — see
  [T3.5_FASTLIVO_REPLAY.md](../../T3.5_FASTLIVO_REPLAY.md) and
  [T3.5_SENSOR_CAPTURE.md](../../T3.5_SENSOR_CAPTURE.md).
- No recordings, build trees, credentials or connection details belong here.
