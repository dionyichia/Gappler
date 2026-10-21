# T59 isolated replay bundle

## Raw-image replay (T3.5)

The republisher is removed. Raw bgr8 images come pre-decoded from the offline
raw bag (`Bright_Screen_Wall_raw`), whose report verifies every message. The
upstream republisher binary segfaults on shutdown (GDB backtrace:
`rclcpp::CallbackGroup::~CallbackGroup`), so no republish process runs.

Run `bash run_replay.sh --diagnostic` after coordinating custody to verify the
mapper subscribes directly to the staged config's own `common.img_topic`
(`/left_camera/image` for the public bag). It never resumes playback.
`DIAGNOSTIC_CAPTURED` is not localization acceptance.

Run only on the lab host, as ordinary `rcp2026`, from the copied bundle directory:

```bash
python3 -B -m unittest -v test_progress test_wrapper_runtime test_diagnostic test_replay test_replay_config
bash -n run_replay.sh
bash ./run_replay.sh
```

The config agent supplies `config/bright_screen_wall.yaml` and
`config/camera_pinhole.yaml`; this runner does not modify them.
Run its independent `test_replay_config.py` as well, using that agent's instructions.

## Running our own reviewed recording (T3.5c)

Defaults are the public raw bag and configs, so ordinary use is unchanged. The
bag and the two staged configs come from the environment:

| Variable | Meaning |
|---|---|
| `T35_REPLAY_BAG` | bag directory containing `metadata.yaml` |
| `T35_MAPPER_CONFIG` | staged mapper YAML in `config/`; plain basename, must end `.yaml` |
| `T35_CAMERA_CONFIG` | staged camera YAML in `config/`; plain basename |
| `T35_SOURCE_COMMIT` | recorded in `inputs.json` as expected provenance, not proof |

The played input topics are read from the staged mapper config itself
(`common.lid_topic`, `common.imu_topic`, and `common.img_topic` when
`common.img_en: 1`), so the config the container loads is the config that decides
the required graph edges and the callback accountant. A bag topic the mapper does
not play is recorded under `unplayed_bag_topics` in `evidence/result.json` and
never parsed; every played topic must still exist in the bag with its exact type,
be nonempty, and be CDR-serialized. The staged configs are independently checked
against the bag metadata by `check_replay_configs.py`.

`common.img_en: 0` selects the pinned fork's ONLY_LIO path (`LIVMapper.cpp:255`).
Then the camera topic is not an input, `/rgb_img` is not a required output, the
visual-retrieval gate is dropped, and a PASS can only claim LiDAR-inertial smoke.
`result.json` records `inputs`, `expected_outputs`, `require_visual`,
`mapper_config`, `camera_config`, `unplayed_bag_topics` and `claim`, so the mode
of every run is visible in its own evidence.

Our recording is the T3.5b capture
(`~/rcp-Gappler/log/t59-fastlivo/log/t35b-capture.R0fVks/t35b_proof3`, 74.0 s,
four topics), LiDAR-IMU control run first:

`playback_qos.yaml` must list that recording's own image topic, because a
TRANSIENT_LOCAL recorded image is rejected by both the mapper's volatile
subscription and the readiness gate. Our RealSense colour topic is already
listed. The staged configs also carry this bag's frozen counts and duration, so
`check_replay_configs.py` rejects them against any other recording, including
the standoff re-capture: a different bag needs its own checked config pair.

```bash
export T35_REPLAY_BAG=$HOME/rcp-Gappler/log/t59-fastlivo/log/t35b-capture.R0fVks/t35b_proof3
export T35_MAPPER_CONFIG=t35b_proof3_lio.yaml
export T35_CAMERA_CONFIG=t35b_proof3_camera.yaml
export T35_SOURCE_COMMIT=<commit of the copied bundle's origin>
bash ./run_replay.sh
```

The visual run repeats this with `T35_MAPPER_CONFIG=t35b_proof3_visual.yaml`.
For this 74.0 s bag the default rate 0.25 spends about 296 s of the 600 s window
and 0.2 also fits; 0.18 no longer does. The public 66.7 s bag fits 0.25 and 0.2
but not 0.1.

Entering the command is the confirmation; the script asks only for interactive
sudo (no typed custody prompt). It
holds `/home/rcp2026/rcp-Gappler/log/software-build.lock`, refuses detected build/ROS
processes (including Runner.Worker, bench/run.sh, RealSense and xnode_vehicle)
or any running container, and never stops somebody else's work. It rechecks
conflicts immediately before starting the staged container. The
process scan is conservative, not a complete custody proof; team coordination
and cooperation with the same lock remain required.

It creates one uniquely named container from the existing local image
`t59-fast-livo2:experimental`. There are no downloads, retries, host ROS commands,
bind mounts, device mappings, GPUs, Docker sockets, or root container processes.
The root filesystem is intentionally writable for the source's unconditional
`Log/` output. Docker daemon tar extraction sets UID/GID 10001 directory ownership
before the container starts. The actual runtime probes Log writability and
records any failure; there is no fallback to runtime root/chown.

Evidence is retained under
`/home/rcp2026/rcp-Gappler/log/t59-fastlivo/replays/<container-name>/`.
The stopped container is retained too; nothing is deleted. Inspect:

- `inputs.json`: actual image ID and staged file hashes; source pin is expected
  provenance, not proof of a rebuild in this procedure.
- `image.inspect.json`, `container.prestart.inspect.json`: image and isolation.
- `evidence/result.json`: PASS/FAIL/INCONCLUSIVE, counts, spans, visual retrievals,
  staged config names, played inputs and expected outputs, unplayed bag topics,
  exact child commands, return codes, intentional-cleanup flags, QoS matches.
- `evidence/*.stdout.log` / `*.stderr.log`: individual process output.
- `container.exit.inspect.json`, `host-runner.exit-code`: outer exit status.
- `source-Log/Log/`: mapper's source-tree logs.

PASS also requires exact callback log stamp/count coverage of every played sensor
input (two of them when `img_en=0`), with one source-explained exception. The
stdlib accountant reads only
CDR1 Header prefixes from the reviewed single SQLite database, checks
topics/types, and applies the configured image offset to match the pinned
source's six-decimal logs. This is microsecond-resolution callback evidence,
not full message or estimator proof.

Exception: pinned `imu_cbk` returns before logging for IMU processed before
the first lidar callback (`last_timestamp_lidar < 0`), which can never be
fused without a lidar time base. Such drops are reconciled as
`prestart_drops` only when they form a strict timestamp prefix of the expected
IMU set, no duplicates exist, and their count fits within one 10 Hz lidar
period of IMU (data-driven cap, 21 for this bag). Anything else — mid-stream
gaps, oversized prefixes, duplicates — stays missing/unexpected and fails.
The allowance and disposition are recorded per run, never silent.

PASS requires normal player EOF/exit 0, ten advancing valid messages in each of
odometry/cloud/RGB streams over at least five simulated seconds each, repeated
positive visual retrieval logs, and no recorded invalid outputs or process
errors. Zero player exit is not sufficient: finalized stdout/stderr must contain
no ERROR/FATAL, `Failed to play:` or `Failed to publish message` diagnostics.
First and last observed `/clock` must be within **0.25 simulated seconds** of
the metadata start and start+duration respectively, and span at least duration
minus 0.5 seconds. Expected timing/counts and observed clock bounds are recorded.
Output counts are never targets: the monitor subscribes best-effort, so the same
mapper publishes different numbers of `/rgb_img` messages to it from run to run (606, 389, 384 on
one image). RGB is judged on validity (every message valid, ten advancing over five
seconds) plus one bound: the monitor cannot have seen more RGB messages than the
mapper's own `[T35_DIAG_CLOUD]` rows. Premature exit 0 is FAIL; there is no restart/seek/loop.
Missing/inadequate outputs at otherwise proven EOF are INCONCLUSIVE (nonzero exit).
Startup errors, crashes, deadline failures, invalid outputs and backward time
are FAIL. Total supervisor acceptance budget is 600 seconds including cleanup;
operations stop at 590 seconds, reserving ten seconds for the existing shutdown
escalation. Any observed final elapsed time above 600 seconds fails acceptance.
each readiness phase is bounded at 60 seconds. The host wait has a 660-second
ceiling. `T35_REPLAY_RATE` defaults to 0.25 and allows finite positive rates up to 0.3 (0.3 was added for the 117.9 s handdriven1 bag: 583 s of 600), but only
rates only if playback plus 60s startup, 120s drain and 10s cleanup fit within 600s; actual
remaining time is checked again before resuming. For this bag, 0.2 fits but 0.1
does not. Increasing custody or CPU limits is not an automatic fallback.

After player EOF, wait up to 120s (within the overall deadline) for each terminal
sensor callback and five seconds of mapper stdout/stderr inactivity. Every
coverage gap/duplicate is still an error. Log quiet is only a shutdown heuristic:
`estimator_completion_proven` is always false. It cannot prove an empty internal
estimator queue or that a final logged callback finished processing.

Startup markers and ten-second progress summaries stream to the host terminal:
phase, elapsed time, clock, callback counts and output counts. A missing update
can still mean a blocked native ROS call; the outer watchdog remains necessary.
After initial `sudo -v`, Docker calls use `sudo -n` so expired credentials fail
rather than prompting inside cleanup. Timeout cleanup calls have kill-after
limits. The bounded log follower closes the custody-lock descriptor and is reaped.

Every registered-cloud XYZ coordinate must be finite FLOAT32/FLOAT64,
with validated fields, byte order, point/row strides and lengths. RGB must be
`bgr8` with complete three-byte-pixel rows. Full-cloud validation consumes CPU;
its wall time is recorded under the two-CPU container limit. This is not a
realtime benchmark. Cleanup reaps leaders and checks whole recorded process
groups for SIGINT/5s, SIGTERM/3s and SIGKILL/2s. Needing SIGKILL, surviving groups
or abnormal final return codes all fail the run.

Ctrl-C signals only this run's exact named container: SIGINT then a 20-second
wait; if not confirmed stopped, SIGKILL then a 10-second wait and inspection.
Docker shutdown/inspection calls themselves also have finite timeouts. Final
file extraction occurs **only after confirmed stopped state**. Unknown/running
state produces `CRITICAL custody unresolved`, nonzero host exit, partial logs
and `container.state-unconfirmed.inspect.json`, not final evidence.

If Docker cannot confirm shutdown, a tiny ordinary-user **host lock-holder**
inherits FD 9 and retains the actual cooperative kernel lock. The wrapper exits
nonzero promptly rather than hanging; `software-build.lock.custody-unresolved`
also blocks later replay attempts. The keeper runs no Docker/ROS commands.
Its PID/readiness/log are recorded as `custody-lock-keeper.*`. A human must
coordinate custody and manually verify the exact container stopped before
clearing that marker; the keeper then exits and releases the lock. The runner
never clears it automatically. If keeper startup fails, an explicit CRITICAL
warning states that lock retention is unconfirmed and needs immediate attention.

## Explicit limits

- This bundle is locally unit/syntax checked, not Docker/ROS runtime validated.
- It assumes installed Humble executables, bag player resume service, rclpy,
  image compressed transport and PyYAML already exist in the image. Missing
  dependencies are failures, not installation requests.
- Played input topics/types come from the staged mapper config: Livox driver2
  CustomMsg, IMU, and a plain `Image` (pre-decoded bgr8 in the public bag). Bag
  topics the mapper does not play are recorded as unplayed, never parsed. A
  missing or mistyped played topic fails readiness.
- Only the reviewed Pinhole remote-parameter path is accepted. The mapper's
  short Vikit discovery wait can still fail; there is deliberately no retry.
- Output stamps reflect mapper ROS time, not original sensor measurement time.
  The runner preserves original bag/header quirks and config time offsets.
- Positive retrievals enter the visual EKF path but do not establish useful
  correction magnitude, calibrated extrinsics, accuracy, or hardware readiness.
- The Docker main-process OOM flag does not diagnose every child OOM. Child
  abnormal exit codes are retained; kernel-level OOM attribution is not claimed.
- Cooperative locking cannot exclude uncooperative jobs started afterwards.
  Ordinary Docker isolation is not a formal safety/security certification.

## AddressSanitizer runs

Set `T35_REPLAY_IMAGE` to an ASan-instrumented image tag (built per the recipe
README) to replay under AddressSanitizer; default behavior is unchanged.
`ASAN_OPTIONS` defaults to `detect_leaks=0:halt_on_error=1:abort_on_error=1`
and can be overridden with `T35_ASAN_OPTIONS`. Set
`T35_LD_PRELOAD='/lib/x86_64-linux-gnu/libasan.so.6:/lib/x86_64-linux-gnu/libstdc++.so.6'`
for the existing ASan image. ASan alone caused a Python startup interceptor
failure (`real___cxa_throw` unresolved); the two-library preload completed the
paused diagnostic. This does not validate a full replay. Leave preload unset for
normal images. Extra environment entries do not weaken container validation.

Actual build flags confirm ASan/debug flags in `laser_mapping`, but Vikit's
CMake overwrote them and retained `-fomit-frame-pointer`. Mixed instrumentation
limits coverage; it does not itself establish the original crash's cause.
The latest full instrumented replay aborted with an invalid-ROS-context publisher
exception, without an ASan memory report. A clean sanitizer run would not prove
absence of memory errors or establish a threading race.

## 2026-10-16 candidate boundary

The callback-drain/rate/progress changes are pure-tested scratch tooling. Docker
log streaming, ROS timing and shutdown behavior still require an attended run.
No mapper patch, image rebuild, hardware command or acceptance claim accompanies
these changes. Existing replay bundle and evidence are retained unchanged when
the candidate is staged in a separate sibling directory.
