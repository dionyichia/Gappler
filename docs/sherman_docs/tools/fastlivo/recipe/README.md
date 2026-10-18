# T59 experimental FAST-LIVO2 compile recipe

## Shared-host prerequisite

Reserve an idle lab-box window with the other operators before running. Entering the
command is the confirmation; there is no typed custody prompt. The wrapper checks
for competing robot/bench/build processes before pulling and compiling, and holds
`~/rcp-Gappler/log/software-build.lock` until it exits. This lock only coordinates
tools that use the same lock; it cannot prevent another operator starting an
unrelated job. If activity is reported or custody is uncertain, stop and
coordinate. Never stop another operator's processes.

**Preparation only: not a validated build, deployment, or robot runtime.**
Transfer this folder's files to a scratch directory on the intended Linux Docker
host. Do not change Gappler. Requires Bash, Python 3 (stdlib only), Docker CLI,
interactive sudo authentication, and an existing daemon with cgroup support.

## One-command bounded build (user runs)

```bash
bash run_build.sh
```

The wrapper authenticates with `sudo -v`, runs offline checks, reports daemon
RAM/CPUs/warnings, and fails if memory/swap/CPU/PID enforcement is unavailable.
It inspects existing `buildx_buildkit` container configuration read-only, but
**never uses, creates, or changes a docker-container builder**. No buildx resource
flags are used. It refuses an existing exact `t59-fastlivo-build` container or
`t59-fast-livo2:experimental` image tag; it does not overwrite or delete them.

It pulls `ros:humble-perception-jammy`, records its repository digest, and creates
one **ordinary container** from that digest, with hard cgroup limits:
8 GiB RAM, 8 GiB RAM+swap (no additional swap), 2 CPUs, 512 PIDs. It prints these
intentions, saves/prints HostConfig, and validates actual memory, swap, CPU quota,
privilege, bridge network, mounts and devices **before start**. Unsupported or
unexpected settings stop the wrapper. Serial `-j1`/sequential compilation is
additional scheduling discipline, **not** the hard resource cap.

`docker cp` transfers the two build files; apt/git use ordinary bridge networking.
No privileged mode, host networking, mounts, devices, socket, or host source clones.
`docker start -a` output is piped through `tee` with both pipeline statuses checked.
State inspection must show stopped/exited, exit 0, no OOM kill, and no daemon
error before `docker commit` creates the experimental image. The verified source
manifest is printed and copied into the host logs. Commit does not launch anything.

Logs use a unique `build-logs.*` directory. The container, source/build trees,
logs and image are retained: **no automatic deletion, pruning, or restart**.
There is no automatic timeout. Interrupting the attached client may leave the
container running; do not assume cancellation stopped it. Inspect manually:

```bash
sudo docker inspect --format '{{json .State}}' t59-fastlivo-build
sudo docker logs --tail 100 t59-fastlivo-build
```

If you intend to stop this exact build yourself: `sudo docker stop t59-fastlivo-build`.
Do not rerun/remove containers until the lead has reviewed the retained evidence.

## AddressSanitizer rebuild (opt-in, for the mapper teardown crash)

GDB attributes the post-replay `fastlivo_mapping` SIGSEGV to `free()` inside a
`shared_ptr<PointCloudXYZINormal>` dispose during `~LIVMapper()`. The default
build carries no sanitizer flags. An instrumented rebuild is selected only
through environment overrides; unset variables reproduce the reviewed build:

```bash
T35_BUILD_NAME=t59-fastlivo-asan-build \
T35_BUILD_IMAGE=t35-fastlivo-asan:experimental \
T35_CXXFLAGS_EXTRA='-fsanitize=address -g -fno-omit-frame-pointer' \
T35_LDFLAGS_EXTRA='-fsanitize=address' \
bash run_build.sh
```

`T35_CXXFLAGS_EXTRA` is the required knob: it also triggers the toolchain-matched
`libasan` install and a fail-closed `ldd | grep libasan` check on the mapper
binary before the image commits. `-g` keeps `Release` while giving the report
usable frames. Only simple space-separated flags are supported. Run the replay with
`T35_REPLAY_IMAGE=t35-fastlivo-asan:experimental bash run_replay.sh`; the
container passes `ASAN_OPTIONS=detect_leaks=0:halt_on_error=1:abort_on_error=1`
(leak checking off to keep teardown noise out of the report). The executable
itself is ASan-linked so no `LD_PRELOAD` is needed; OpenMP threads are
instrumented like everything else. Expect roughly double memory/CPU use and a
slower build under the same 8 GiB cap; the 600-second replay budget still covers
the 67-second bag but this is not a performance benchmark.

## Compile-only check after successful image creation

```bash
bash check_compile.sh
```

Uses explicit Bash entrypoint, built unprivileged user, no network, read-only
root, dropped capabilities and no-new-privileges; writable `/tmp` is a bounded
tmpfs with HOME/ROS_HOME/ROS_LOG_DIR redirected there. Only ROS package executable
discovery and `ldd` run—no ROS nodes. Expected: `fast_livo fastlivo_mapping`, no
`not found` loader dependencies, final success message. Unique `compile-logs.*`
and stopped `t59-fastlivo-compile-check` container remain; an existing name is refused
by Docker. Do not add permissions or hardware access to compensate for failure.

## Offline checks / optional route

```bash
python3 -B test_recipe.py
for script in run_build.sh build_inside.sh check_compile.sh; do
  bash -n "$script" || exit 1
done
```

Expected: five tests, `OK`, and no Bash syntax errors. No Docker calls in tests.
`build_inside.sh` is the canonical install/fetch/patch/compile script shared by
the wrapper and minimal Dockerfile. The Dockerfile route has **no hard build
resource caps and is not recommended**. Bash uses `set -eo pipefail`, not `set -u`
before ROS setup. The tests check constraints, inspection rejection cases and
guarded replacements—not real Docker/cgroup behavior or C++ compilation.

## T3.5c counters-only diagnostic build (2026-10-18)

User-run only, from a fresh copied bundle under the box evidence/log directory:

```bash
T35_VIO_DIAGNOSTIC=1 bash run_build.sh
```

This is a separate experimental image, not a change to the accepted mapper:

- Starts from exact accepted image ID
  `sha256:d0dcfa8af10fa8d1b2f1cf42434ab1b763838d798139f266da7bcc65719de8b1`.
  No pull, apt, fetch or dependency rebuild. Network is `none`.
- Reuses this wrapper's sudo, lock, host-idle checks, 8 GiB/2 CPU/512 PID
  resource caps and inspect validators. No typed custody prompt.
- Uses container `t35-fastlivo-vio-diagnostic-build` and output image
  `t35-fastlivo-vio-diagnostic:experimental`. Existing names/tags are refused;
  all other output image names (including registry aliases) and compiler-option
  overrides are refused in this mode.
- `patch_diagnostics.py` accepts only exact safety-patched `vio.cpp` and pinned
  `LIVMapper.cpp`. It adds tagged C++ lines only. Removing tagged lines must
  recover both original files byte-for-byte (real-source test).
- `diagnostic_inside.sh` compiles only `fast_livo`, verifies both diagnostic
  log markers in the binary and retains source diff, source hashes and binary
  hash under `build-logs.*/vio-diagnostic/`. This does not prove successful
  runtime or matching; C++ compilation itself still requires this box build.

Log fields (one row per completed retrieval or VIO cloud publish):

- `[T35_DIAG_RETRIEVE]`: per-point `key_queries`, `key_hits` using the unchanged
  algorithm, and `shadow_key_hits` using insertion-consistent keys **without
  selecting them**. These are not unique-bin counts. `empty_map=1` is a separate
  startup row with no other fields.
- `null_reject`, `noobs_reject`, `behind_reject`, `projected`, `visible` count
  map-point checks on the primary voxel path; the reviewed config disables
  raycasting. `grids` counts the selected grid candidates. `depth_reject`,
  `normal_reject`, `ncc_reject`, `photo_reject`, `accepted` locate later gates.
  The reviewed config enables normals; the alternative close-view-observation
  path is not separately counted. Stages have different populations, so do
  not sum all counters into one rejection percentage.
- `[T35_DIAG_CLOUD]`: accumulated `source_points`, `coloured_points` and
  `pub_scan_num`. For the reviewed `pub_scan_num=1`, zero coloured points
  indicates no points survived the camera-view/colour-cloud filters. The log
  does not distinguish every individual cloud filter.

Do not start replay automatically after the build. Review build exit, actual
image ID, source diff/hashes and binary markers first. Then replay the unchanged
visual config/bag with `T35_REPLAY_IMAGE` set to that diagnostic image ID through
the existing custody-gated replay wrapper. Retain the original A PASS/B FAIL.
Neither zero-point-cloud rules nor the positive-visual gate is relaxed.

If the attached build terminal disconnects, that alone does not prove the
container stopped. Inspect the exact build container from another attended
terminal; if stopping is needed, use
`sudo docker stop -t 10 t35-fastlivo-vio-diagnostic-build` and verify its state.
Never delete the container, image or evidence, or close tmux without agreement.
The resource caps are not a wall-clock timeout.

Offline tests (no ROS/Docker/build):

```bash
python3 -B test_recipe.py
python3 -B test_diagnostics.py
T35_PINNED_SOURCE_DIR=<preserved-source-dir> python3 -B test_diagnostics.py
bash -n run_build.sh
bash -n diagnostic_inside.sh
```

Without `T35_PINNED_SOURCE_DIR`, the real-source test explicitly skips; it never
downloads code. That directory contains unmodified pinned `vio.cpp` and
`LIVMapper.cpp`; the test applies the existing sampling guard before diagnostics.
The pure checks are included in `bench/run.sh` L0. No runtime diagnostic result
is claimed until Sherman runs the separately reviewed build and replay.

## T3.5c visual repair candidates (2026-10-18)

`patch_visual_fixes.py` accepts the exact diagnostic VIO source only. It preserves
existing memory-safety patches, diagnostic counters, calibration and acceptance
criteria. It refuses source drift and repeated application. Two separate stages:

1. `visibility`: shared finite/positive camera-depth predicate in
   `visual_geometry.h`, checked **before projection** on both generation candidate
   sources and before final visual point insertion. This prevents behind-camera,
   zero-depth and nonfinite seeds; it does not create useful front-facing features.
2. `visibility-voxel`: the same visibility fix plus retrieval/raycast bin arithmetic
   consistent with insertion. Uses float divide, negative adjustment and integer
   truncation, retaining the pinned insertion/plane-map convention even at exact
   negative boundaries. It deliberately does not globally reindex the map to
   mathematical floor. Only the retrieval array type and two floor assignments
   change; insertion and reference-map indexing remain unchanged.

User-run only, one build and replay at a time, from a new copied bundle:

```bash
# First candidate: review its build and replay before testing the cumulative fix.
T35_VIO_DIAGNOSTIC=1 T35_VIO_REPAIR=visibility bash run_build.sh
# Later, separately approved, after the first candidate's evidence review:
T35_VIO_DIAGNOSTIC=1 T35_VIO_REPAIR=visibility-voxel bash run_build.sh
```

Output tags are fixed per stage, respectively `t35-fastlivo-visibility:experimental`
and `t35-fastlivo-visibility-voxel:experimental`; aliases/other output tags and
compiler overrides are refused. Build containers are the same names without
`:experimental`, suffixed `-build`. Defaults remain diagnostics-only without
`T35_VIO_REPAIR`; repair stages require explicit diagnostic mode. The original
accepted image is unchanged. Every build starts from its exact ID, regenerates
the reviewed counters, then applies the selected repair, mapper-only and
network-none. This is not a rebuild on top of an unknown previous candidate.

Each repair build saves `visual-fixes/` alongside `vio-diagnostic/`: stage,
source diff, patched source/header hashes. The baseline diagnostic manifest
describes the pre-repair source; `visual-fixes.sha256` describes the actual
repaired source/header. Binary hash/markers remain in `vio-diagnostic/`.

Offline regression:

```bash
python3 -B test_visual_fixes.py
T35_PINNED_SOURCE_DIR=<preserved-source-dir> python3 -B test_visual_fixes.py
```

Tests compile a standalone C++ visibility check and the **actual source-extracted**
insertion/current/raycast/reference voxel expressions. The original expressions
must reproduce a mismatch; the cumulative candidate must agree on negative,
boundary and float-rounding cases. Source tests verify guards precede projection
on all three paths and visibility-only preserves retrieval code. Missing C++
compiler or pinned source causes explicit skips, not runtime proof. Both stages
still need user-run full mapper compilation/replay; zero visual matches or
invalid clouds remain non-passing. No calibration parameters or smoke gates relax.

## F2 `blind_sqr` repair (2026-10-19)

Finding F2 (`T3.5_CONFIG_SWEEP_20261019.md`): `preprocess.blind` cannot act on the
AVIA/CustomMsg path, because the ROS 2 port dropped upstream's
`p_pre->blind_sqr = p_pre->blind * p_pre->blind`, so the range gate at
`preprocess.cpp:194` compared against a never-assigned member. `patch_blind_sqr.py`
restores that one line where upstream has it (end of the constructor's parameter
block) plus one tagged stdout line reporting the threshold in force. No other source
text changes; the accepted image is untouched.

User-run only, one build and replay at a time, from a new copied bundle:

```bash
T35_BLIND_SQR=1 bash run_build.sh
```

This is its own mode, not a visual-repair stage: it refuses to combine with
`T35_VIO_DIAGNOSTIC=1` and refuses any rebuild that also carries that mode's flags.

- Starts from exact accepted image ID
  `sha256:d0dcfa8af10fa8d1b2f1cf42434ab1b763838d798139f266da7bcc65719de8b1`.
  No pull, apt, fetch or dependency rebuild. Network is `none`.
- Container `t35-fastlivo-blind-sqr-build`, output image
  `t35-fastlivo-blind-sqr:experimental`. Existing names/tags and registry aliases
  are refused, as are compiler-option overrides.
- `patch_blind_sqr.py` accepts only the byte-identical pinned `LIVMapper.cpp`
  (`815b5f89…`) and adds tagged `/* T35_BLIND_SQR */` lines only; removing the tagged
  lines must recover the original file byte-for-byte. The output source no longer
  matches the pinned hash, so a second application is refused.
- `blind_sqr_inside.sh` compiles `fast_livo` only, verifies the patched source hash
  before building, checks the `[T35_BLIND_SQR]` marker in the binary, and retains
  `blind-sqr/` (source diff, patched source hash, binary hash, binary strings) under
  `build-logs.*/`.

The built image is a measurement and repair candidate, not an acceptance image. It
changes one behaviour: the 0.1 m blind zone now drops zero-range returns. Whether the
pinned build was keeping them is read from the preprocessed point-count line the
pinned binary already prints — procedure, prediction and falsification in
[`T3.5_F2_BLIND_SQR_PATCH.md`](../../T3.5_F2_BLIND_SQR_PATCH.md). Replay it with
`T35_REPLAY_IMAGE=t35-fastlivo-blind-sqr:experimental bash run_replay.sh` and read
`evidence/mapper.stdout.log`.

Offline tests (no ROS/Docker/build), also an L0 bench step:

```bash
python3 -B test_blind_sqr.py
T35_PINNED_SOURCE_DIR=<preserved-source-dir> python3 -B test_blind_sqr.py
bash -n run_build.sh
bash -n blind_sqr_inside.sh
```

Without `T35_PINNED_SOURCE_DIR` the real-source test explicitly skips; it never
downloads code.

## Source pins and narrowly scoped changes

| Source | Commit |
|---|---|
| U-AMC/FAST-LIVO2-ROS2 | `a09599a288c56b832114d7ad9e898248a4111d9e` |
| U-AMC/rpg_vikit_rational_polynomial | `6f213c7fe6be1aff1fc79c7bd6103e3e9bc4a02d` |
| Livox-SDK/livox_ros_driver2 | `13eb05e4e6dd7a765b934d0c5fd6236676a57b49` |
| Livox-SDK/Livox-SDK2 | `f5d9375f84efe2b15bc0a052d3e18482ed13adf4` |

Inspected raw GitHub files at these commits: FAST-LIVO2 `Dockerfile` and
`CMakeLists.txt`; Vikit common/ROS `CMakeLists.txt`, common `FindEigen.cmake`
and `math_utils.h`; driver `CMakeLists.txt` and `package_ROS2.xml`; SDK root
`CMakeLists.txt`. Raw URL pattern:
`https://raw.githubusercontent.com/OWNER/REPO/COMMIT/PATH`.

`patch_cmake.py` requires each original fragment exactly once, validating all
three files before writing. It changes only:

- Vikit common: legacy C++0x/11 flags to CMake C++17; actual unconditional test
  targets guarded by `BUILD_TESTING`; modern `Sophus::Sophus` imported target.
- Vikit ROS: imported Sophus target supplies header/dependency usage requirements.
- FAST-LIVO2: imported Sophus target for common dependencies, utils and executable.
- x86 codegen capped below AVX (no `-march=native`) in Vikit common and
  FAST-LIVO2 Release flags: Ubuntu's prebuilt PCL uses 16-byte Eigen alignment
  (plain malloc/free pair), while native-arch codegen raises ours to 32 bytes
  (handmade header pair), corrupting VoxelGrid output buffers at teardown
  (T3.5a ASan diagnosis). SSE baseline and `-O3` remain.
- FAST-LIVO2 `src/vio.cpp` + new `include/patch_sampling.h` (T3.5a sampling
  guard): `patch_vio.py` SHA-gates the pinned source, inserts a scale-aware
  sampling-footprint check, packed-grayscale validation, per-iteration
  residual/Jacobian resets, all-rejected rollback and frame-entry gain clear.
  Build refuses source drift; standalone ASan/UBSan regression lives alongside
  the patch sources.

The installed-location Vikit config shim is preserved with an explicit
`vikit_common_DIR`; apt provides modern `ros-humble-sophus`, never old Sophus
`a621ff`. The sampling guard is a bounds patch only, not an estimator-algorithm
change. No mimalloc install, dataset, or host source clone.
The SDK's own CMake explicitly chooses C++11; it remains unchanged (independent
of the C++17 Vikit/FAST-LIVO consumers).

## Limits / evidence

Prepared/revised 2026-10-15. Offline checks are not a reproduced compile failure
or successful image build: neither Docker nor ROS was run during preparation.
The CMake edits address inspected integration mismatches, not compiler-proven
failures. If compilation fails, retain its first error and make only a new
source-proven change. No runtime, dataset accuracy, timing, or hardware claim.

The wrapper records and uses the pulled digest for that run, but the initial
ROS tag, apt packages, toolchain and architecture are not fixed across runs:
**not a fully reproducible OS image**. Upstream native CPU optimizations remain,
so build on the intended machine architecture; do not assume image portability.
The dependency check covers loader resolution, not runtime plugin loading.
