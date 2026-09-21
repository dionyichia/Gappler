# ASSETS — the files the code needs that git does not hold

> **Paths moved 2026-09-21 (reorg).** Many cites below use the old layout (`src/`, `ros2_robot_ws/`,
> `Navigation_Module/`). Look up the new path in [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.15,
> "Where things moved". Line numbers inside moved files did not change with the move.


**Why this exists:** four things the stack needs at runtime are deliberately not in git. A fresh
clone has none of them, and until 2026-09-11 nothing recorded where they came from. This is that
record. Tags as elsewhere: `[code]` read from source · `[observed]` measured on the lab box ·
`[inferred]` reasoning.

## The files

| File (repo-relative) | Size | SHA-256 | What it is | Why not in git |
|---|---|---|---|---|
| `src/models/sam3/sam3.pt` | 3,450,062,241 B | `9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e` | SAM 3 segmentation weights | Over GitHub's 100 MB limit; Meta's weights are licence-gated `[inferred]`. Ignored by root `.gitignore:16` |
| `ros2_robot_ws/src/rm_mtc/src/perception/log/checkpoint_detection.tar` | 296,408,957 B | `a05c3690b95c8b65e78b1bb8a28f1d5ca96613391946e450afacae840bbcf7b2` | AnyGrasp detection network — what `main` launches (`ros2_robot_ws/src/main.py:30`) | Over 100 MB, and ignored **by accident**: `ros2_robot_ws/.gitignore:3` ignores every folder named `log` (meant for colcon logs) |
| `ros2_robot_ws/src/rm_mtc/src/perception/log/checkpoint_tracking.tar` | 23,723,468 B | `98271b6125c2cc05e118ac0537fefb335c06dbd7d55fdd36fee25f55fd6eccd6` | AnyGrasp tracking network — the one verified on 2026-08-25 | Same accidental `log` rule |
| `.venv/` | several GB | — | Installed Python packages (SAM 3, Aria SDK, torch, whisper) | Generated and machine-specific. **Never copy it — rebuild it:** `uv sync` from `pyproject.toml` + `uv.lock`, which are in git |

Checksums `[observed]` 2026-09-11: identical in `~/rcp-github`, `~/rcp-desktop` and `~/rcp-Gappler`
on the lab box, so every copy there is the same file.

**In git, for comparison:** the AnyGrasp licence (`perception/license/Puneet.*`, machine-locked to
the lab box) and its compiled binaries (`perception/*.so`, CPython 3.10). `lib_cxx.so` links
`libcrypto.so.1.1`, which the box has system-wide (`/lib/x86_64-linux-gnu/`) `[observed]`.

**Ignore rules (2026-09-11):** the root `.gitignore` now ignores model weights by extension
(`*.pt`, `*.pth`, `*.ckpt`, `*.onnx`, `*.safetensors`, `*.engine`, `*.h5`), `assets/models/`, the
AnyGrasp checkpoints **by name** (no longer relying on the accidental `log` rule), recordings
(`*.vrs`, bags, `*.avi`/`*.mp4`, `frame_*.png`, `src/output/`) and archives. One exception is kept
tracked: `src/models/projectaria_eyetracking/weights.pth` (11 MB, the Aria eye-gaze model, in git
since before the rule). Large files **already in history** (OpenVINS `ov_data/` datasets, the gripper
serial-debugger `.exe`, AnyGrasp `lib_cxx` builds for four Pythons) stay tracked — untracking them
would not shrink the clone, and a `git pull` would delete them from every working tree.

## Also outside git, on the lab box

Not model files, but the same problem: **`~/rcp-old-ros-wkspace`** (4.5 GB) is a copy, made
2026-09-11, of `~iot22/Ros2Workspaces` — the base's navigation workspace, a git repo with no commits
and no remote. `robot_navigation` and `xpkg_demo` came from it into this repo on 2026-09-21 (T0.4),
under `Navigation_Module/src/`. What else in it is needed: [`NEXT_STEPS.md`](NEXT_STEPS.md) §2.9.

**The saved lab map stays outside git on purpose.** The launch files read it from `$GAPPLER_MAP_DIR`
(default `~/maps`), because a map belongs to one room, not to the code (T0.3). The one that exists is
in `~iot22/maps/`, saved 2026-04-10 `[observed]`:

| File | Size | Read by |
|---|---|---|
| `completed_map.posegraph`, `completed_map.data` | 25 MB, 2.5 MB | `slam_localization.launch.py:149`, SLAM Toolbox's saved pose graph |
| `current_map.pgm`, `current_map.yaml` | 213 KB, 129 B | an image map, 0.05 m per pixel. Pass it to `robot_navigation` with `map:=` |

To use it as `rcp2026`: `mkdir -p ~/maps && cp ~iot22/maps/* ~/maps/`. It is five months old, so the
lab may have changed since. Re-mapping is T3.5.

## Where they come from

- **SAM 3 weights** — Meta's SAM 3 release (Hugging Face, licence acceptance required)
  `[inferred]`. The repo installs SAM 3's *code* from the fork `Axemortal/rcp-sam3` (pinned in
  `uv.lock` to `a9d9a34`) but has **no download step for the weights**. Whoever re-downloads should
  compare the checksum above and note the exact source here.
- **AnyGrasp checkpoints** — supplied by the AnyGrasp SDK vendor together with the licence
  `[inferred]`. Keep the originals; the licence is tied to this machine.
- **Lab box, today:** copies live in `~/rcp-Gappler` (copied 2026-09-11 from `~/rcp-github`).

## Where they are read from `[code]`

`src/models/sam3/sam3.pt` — `ros2_robot_ws/src/rm_mtc/src/perception/sam3_ros_node.py:38` and
`src/services/object_recognition/sam3_model.py:91`, both as absolute `/home/iot22/...` paths
(NEXT_STEPS §2.5). The AnyGrasp checkpoints — passed as `--checkpoint_path log/checkpoint_*.tar`
relative to the perception folder (`ros2_robot_ws/src/main.py`, startup guide).

## Proposed layout (Dion, 2026-09-11 — not done yet)

One obvious home for every model file instead of three nested ones:

```
assets/models/
├── sam3/sam3.pt
└── anygrasp/{checkpoint_detection.tar, checkpoint_tracking.tar}
```

gitignored as `assets/models/**` with a `README` listing the checksums above, and the code reading
one configurable path instead of hardcoded ones. Tracked as NEXT_STEPS §2.8. When it moves, update
`bench/preflight.py`'s `assets` group and the table above.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-09-11 | Claude (Opus 5) + Dion | Created. Checksums, sizes, sources, why each is ignored; the accidental `log` rule; proposed `assets/models/`. |
| 2026-09-11 | Claude (Opus 5) + Dion | Moved to `docs/`. Root `.gitignore` now covers weights, recordings and archives explicitly; recorded why already-tracked big files stay. |
| 2026-09-11 | Claude (Opus 5) + Dion | Added the `~/rcp-old-ros-wkspace` pointer (NEXT_STEPS §2.9). |
| 2026-09-21 | Claude (Opus 5) + Dion | `robot_navigation` and `xpkg_demo` are now in the repo (T0.4). Recorded the saved lab map: where it is, its files, and why it stays out of git. |
| 2026-09-21 | Claude (Opus 5) + Dion | Pointer at the top to the old-to-new path table in `NEXT_STEPS` §2.15, after the reorg moved our code. |
