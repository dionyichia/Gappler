# T59 experimental FAST-LIVO2 compile recipe

## Shared-host prerequisite

Reserve an idle lab-box window with the other operators before running. The wrapper
requires typing `IDLE`, checks for competing robot/bench/build processes before
pulling and compiling, and holds `~/rcp-Gappler/log/software-build.lock` until it
exits. This lock only coordinates tools that use the same lock; it cannot prevent
another operator starting an unrelated job. If activity is reported or custody
is uncertain, stop and coordinate. Never stop another operator's processes.

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
