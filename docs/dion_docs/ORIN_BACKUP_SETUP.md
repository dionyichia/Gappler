# The Orin as a backup for the lab box

The Jetson Orin NX (`ssh orin`, user `nvidia`) is set up so you can run most of your normal tests on
it when the lab box is down. Set up 2026-10-08 for T2.1. The Orin is not shared, unlike the box.

**What runs on the Orin:**
- The quick bench (L0 to L2).
- The build, except one RealMan driver.
- All three arm simulation benches (L4).
- SAM 3 on the GPU.

**What doesn't:**
- Anything with AnyGrasp.
- The real-arm driver.
- Anything that imports the glasses SDK.

## How to use it

```bash
ssh orin
cd ~/rcp-Gappler
git pull                      # shallow clone of t2.1-sam3-service (see "Still owed")
source global_env.sh          # or one subsystem: source shared_services/shared_services_env.sh
./bench/run.sh quick          # L0-L2
./bench/sim_moveit.sh         # L4, one at a time
./bench/estop_delivery.sh
./bench/state_machine_sim.sh
```

Do not run `uv sync` on the Orin. It would replace `.venv` with one that cannot use the GPU. Rebuild
`.venv` with `./docs/dion_docs/orin_backup_setup_venv.sh` instead.

## Results, 2026-10-08

All runs on the Orin, on branch `t2.1-sam3-service` at `e5d3324` `[observed]`.

| Check | Result |
|---|---|
| `./bench/run.sh quick` | L0 and L1 pass, including two checks that skip on a Mac (geometry runtime, D455 model). L2 fails, see below |
| `./build.sh` | 23 of 25 packages build in 12 min 44 s. `rm_driver` fails, `arm_bringup` is skipped because it needs it |
| T2.1 step 1 | `segmentation_interfaces` builds. `ros2 interface show segmentation_interfaces/srv/Segment` prints it. `.venv` Python imports `Segment`, `Detection` and `Target` after `source shared_services/shared_services_env.sh` |
| `./bench/sim_moveit.sh` | PASS. Home (both), zero, max joint error 0.005 rad |
| `./bench/estop_delivery.sh` | PASS. Every stop path delivers, 5 of 5 on `kill -INT` |
| `./bench/state_machine_sim.sh` | PASS. The one XFAIL is the known C7 finding |
| SAM 3, one frame of the box video, prompt "box" | 1 mask, score 0.52. Model loads in 22 s, 3.46 GB GPU memory, about 1.05 s per frame after the first |

SAM 3 was run by calling `sam3` directly with the same settings as `sam3_model.py`, not through
`sam3_model.py`. The reason is finding 1 below.

## Findings

1. **`sam3_model.py` cannot be imported on the Orin.** It imports `config`
   (`sam3_model.py:10`), and `aria/aria_app/config/__init__.py:15` imports the glasses SDK
   (`aria.sdk`). That SDK, `projectaria-client-sdk` 1.1.0, has no Linux ARM build, only x86 Linux
   and Mac `[observed on PyPI]`. So a segmentation service that loads SAM 3 through today's wrapper
   cannot start on the Orin. **Suggested fix:** give the service its own small SAM 3 loader, or make
   `sam3_model.py` read only what it needs (the device) without importing all of `config`. This
   matters for T2.1 step 3, since the service is meant to be shared by all subsystems, not tied to
   the glasses.
   **Decided 2026-10-09 (Dion):** the service loads SAM 3 itself, without aria's wrapper, on
   branch `t2.1-sam3-service`.
2. **`rm_driver` does not build on ARM.** `arm/vendor/rm_driver/CMakeLists.txt:53` links
   `lib/libapi_cpp.so`, which is the x86 copy. RealMan ships an ARM copy in
   `lib/linux_arm64_c++_v1.1.3/`. **Suggested fix:** pick the folder by `CMAKE_SYSTEM_PROCESSOR`.
   Not needed for any Orin test, since the simulation benches never start `rm_driver`.
3. **L2 fails on the Orin, and always will.** `bench/preflight.py:170` treats any Linux machine
   with ROS or `nvidia-smi` as the lab box. All three failures are AnyGrasp: `MinkowskiEngine` not
   in `.venv`, and the two checkpoints missing. AnyGrasp's compiled files are x86-only and its
   licence is tied to the box, so these can never pass on the Orin. `preflight.py --no-lab` drops
   two of them but still fails on `anygrasp-env`. **Suggested fix:** an "AnyGrasp not supported on
   this processor" skip when the machine is not x86, and a way to pass `--no-lab` through
   `run.sh`.
4. **`ros2 interface show` prints the wrong fields for `sensor_msgs/Image`** on this install. It
   shows `CompressedImage`'s fields. The built types are right: Python reports `Detection.mask`
   with `height`, `width` and `encoding`. Cosmetic, a ros2cli display issue.
5. **SAM 3 is about half as fast as on the box.** About 1.05 s per frame here, against about
   0.5 s on the box (119 masks in 61 s, T0.12). Fine for tests, slow for a live grasp.

## What was installed

| What | How | Notes |
|---|---|---|
| JetPack 6.2.1: CUDA 12.6, cuDNN, TensorRT | `sudo apt install nvidia-jetpack` | NVIDIA's apt source was already set up |
| ROS 2 Humble | `ros-humble-ros-base`, `ros-dev-tools` | |
| The box's ROS packages | Every `ros-humble-*` package the box has that exists for ARM: MoveIt, ros2_control, Nav2, rviz, RealSense, slam_toolbox and the rest | Not installed, no ARM build: Gazebo Classic (`ros-humble-gazebo-*`) and `ros-humble-iceoryx-utils`. The box has Gazebo, the Orin does not |
| `.venv` at the repo root | `docs/dion_docs/orin_backup_setup_venv.sh` | See below |
| `aria/aria_app/models/sam3/sam3.pt` | copied from the box | sha256 `9999e234…` matches `docs/ASSETS.md` |
| `assets/recordings/wrist_camera/` | copied from the Mac | sha256 `f86a69ee…` matches `docs/ASSETS.md` |

**`.venv` contents** (`docs/dion_docs/orin_backup_setup_venv.sh`). It holds only what the segmentation
service needs, at the versions `uv.lock` pins on the box:
- **torch 2.10.0, torchvision 0.25.0, triton 3.6.0** from NVIDIA's Jetson index
  (`pypi.jetson-ai-lab.io/jp6/cu126`), not PyPI.
- **`libcudss`** (NVIDIA's sparse solver, Jetson build 0.6.0) copied into torch's `lib/` folder,
  because the Jetson torch needs it and JetPack does not ship it.
- **`sam3`** from the same fork as `pyproject.toml`, installed without its `decord` dependency.
- **`decord2` 3.4.0** in place of `decord`, which has no ARM build. SAM 3 imports it when it loads,
  but only its video code uses it.
- **The rest of SAM 3's dependencies**, plus numpy, opencv and scipy.

The venv can see system packages, so ROS's Python (`rclpy`, message types) works in it.

## What does not work on the Orin, by design

- **AnyGrasp**, and `bench/anygrasp_replay.sh` with it: x86-only compiled files, licence bound to
  the box.
- **The glasses app**: no ARM build of the glasses SDK.
- **The real arm**: `rm_driver` does not build (finding 2). The Orin also has no link to the robot
  network right now.
- **Gazebo**: no ARM build. Nothing in the bench uses it.
- **`./build.sh nav`**: not tried.

## Still owed

- **The clone is shallow** (`--depth 1`, branch `t2.1-sam3-service` only). Its copy of the `.venv`
  script sits at the old path, `shared_services/orin/setup_orin_venv.sh`, as an untracked file.
  Delete it after pulling this branch. To work on another branch, run
  `git fetch origin <branch>` and then `git checkout <branch>`.
- **`install/rm_driver/`** is left over from the failed build. Sourcing `install/` prints one
  harmless "not found" line for it.
- **`./build.sh nav`** has not been tried on the Orin.
- **Lab box parity is a snapshot.** If the box gets new ROS packages, re-run the comparison: diff
  `dpkg-query -W 'ros-humble-*'` on both machines.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-10-08 | Claude Opus 5.5 + Dion | Created: Orin set up as a backup for the lab box, results and findings. |
| 2026-10-09 | Claude Opus 5.5 + Dion | The `.venv` script moved from `shared_services/orin/` to this folder, so the repo holds no machine-specific setup (branch `t0.17-orin-backup`). Finding 1 decision recorded. |
