# Recording spec: the lab drive for the memory graph (T6.2)

What the T6.2 recording must contain so the memory graph (M6) can be built from it, how to
record it, and how to check it before leaving the lab.

- **Who:** Sherman records the drive (T6.2). This spec and the checker are T6.2a (Zongzhe).
- **Check every recording** with `python -m memory_graph.recording_check <bag folder>`. It
  names anything below that is missing. Details in [Checking it](#5-checking-it).
- **Status, 2026-10-14:** written from the code. Nothing here has been recorded yet. Topic names
  are `[inferred]` from `nav/robot_slam/launch/base_camera.launch.py` until a test recording
  confirms them.

## 1. Two things to settle before the drive

1. **Turn on aligned depth in the base camera launch** `[code]`.
   `nav/robot_slam/launch/base_camera.launch.py` turns on colour and depth but not
   `align_depth.enable`. Without it, the depth image is in the depth camera's own frame, not
   pixel for pixel with the colour image. The memory graph assumes they line up
   (`memory_graph/replay_loader.py`, `to_observation`). The wrist camera already records this way
   (`grasp/tools/record_wrist_camera.sh:42`). Three launch arguments to add, the same as the
   wrist camera's:

   ```python
   "align_depth.enable": "true",
   "rgb_camera.color_profile": "640x480x15",
   "depth_module.depth_profile": "640x480x15",
   ```

   That file belongs to nav (Sherman, with Dion for the calibration). This spec does not change it.

2. **The drive may not need to wait for the calibration (T5.5, T5.6)** `[inferred]`. The
   calibration gives the camera's mount, the transform from `robot_base_link` to the camera. The
   replay applies the mount when it reads the recording (`T_base_cam` in `to_observation`), so it
   can use the calibrated one later. This holds only if **the camera is not moved on its mount
   between the drive and the calibration**. Sherman and Dion decide. If they agree, T6.2's
   dependency on T5.6 can move to T6.3b's lab reader.

## 2. What to record

| Topic | Type | Why the memory graph needs it |
|---|---|---|
| `/base_camera/base_d455/color/image_raw` | `sensor_msgs/Image`, rgb8 | The photos. Detection, masks and image features all run on these |
| `/base_camera/base_d455/aligned_depth_to_color/image_raw` | `sensor_msgs/Image`, 16UC1, millimetres | Lifts each mask into 3D |
| `/base_camera/base_d455/color/camera_info` | `sensor_msgs/CameraInfo` | The intrinsics `K`, to turn pixels into rays |
| `/base_camera/base_d455/aligned_depth_to_color/camera_info` | `sensor_msgs/CameraInfo` | Same `K` as colour. Recorded so the two can be compared |
| `/tf` | `tf2_msgs/TFMessage` | Where the base was for each photo: `map` → `odom` from SLAM Toolbox, `odom` → `robot_base_link` from the base driver |
| `/tf_static` | `tf2_msgs/TFMessage` | The mounts as they were on the day: camera, LiDAR, arm |
| `/livox/lidar` | MID-360 driver's type | To recompute the base's poses later if the localisation was poor, and to verify the calibration on the same data |
| `/livox/imu` | `sensor_msgs/Imu` | Same reason. Cheap |

**Do not record** `/cloud_relay` or `/scan`. They are made from `/livox/lidar` and can be made
again. **Do not use `/robot_pose` as the pose** `[code]`: `nav/pose_publisher/pose_publisher.py`
stamps it with the time it was sent, not the time of the pose, and drops the height. The
photo's pose comes from `/tf` at the photo's own timestamp.

The command, on the same `ROS_DOMAIN_ID` as the drivers. `ros2 bag record` only listens, it
publishes nothing:

```bash
ros2 bag record -o <folder>/<date>-t6.2-lab-drive \
  /base_camera/base_d455/color/image_raw /base_camera/base_d455/color/camera_info \
  /base_camera/base_d455/aligned_depth_to_color/image_raw \
  /base_camera/base_d455/aligned_depth_to_color/camera_info \
  /tf /tf_static /livox/lidar /livox/imu
```

Start recording before the base moves, so the drive is in the bag from its first metre. Stop it with
Ctrl+C. `<folder>` must be outside the repo or under the gitignored `assets/recordings/`, as the
wrist camera recordings are.

## 3. Before the drive

1. **Check nobody is using the hardware** (CLAUDE.md): the cameras, the LiDAR, the GPU.
2. **Free space.** Estimated about 25 to 30 MB per second `[inferred]`: colour 0.9 MB and depth
   0.6 MB per frame at 15 Hz, plus the LiDAR. A 10-minute drive is about 15 to 18 GB. `/home`
   had 14 GB free on 2026-09-11. Run `df -h ~` and record to a disk with room.
3. **Localisation is running and has converged** on the saved map
   (`nav/robot_slam/launch/slam_localization.launch.py`), so `map` → `odom` exists from the
   first second.
4. **Make a 30-second test recording standing still and run the checker on it.** Only the
   route checks should fail. Fix anything else before the real drive.

## 4. The drive

The recording has three uses: build the graph (T6.3), count duplicates and false merges against
the ground truth (T6.4, T6.4e), and answer sentence queries (T6.8). So:

- **Pass every object twice, minutes apart, from different directions.** The merge test needs
  the same object seen at different times. The checker counts the share of photos taken where
  the base had already been 30 s or more earlier, and asks for at least 10 %.
- **Go slowly**, about 0.3 m/s or less, and turn slowly. Fast turns blur the colour image and
  smear the depth.
- **Stop and turn towards each object** on the ground-truth list (T6.4e), so it fills part of
  the image at least once.
- **Cover the whole area** of the lab the base can reach. End near the start point.
- **Keep the scene still**: no one walking through the camera's view if it can be helped, lights
  as they will be in the demo.
- **8 to 10 minutes** is enough. Longer costs disk space for little gain.

## 5. Checking it

Straight after the drive, on the box or any machine with the repo's `.venv`:

```bash
python -m memory_graph.recording_check <bag folder>
```

| Check | FAIL when | WARN when |
|---|---|---|
| colour images, aligned depth, camera info | missing, wrong type, under 5 Hz | a gap over 1 s (dropped frames) |
| LiDAR | missing, under 5 Hz | |
| image format | colour not rgb8 or bgr8, depth not 16UC1, mono16 or 32FC1 | |
| depth aligned to colour | depth's size or frame differs from colour's | |
| depth coverage | under half the pixels have a reading (median of 30 frames) | |
| intrinsics | camera info size differs from the image, or a zero focal length | distortion is not zero (the loader does not undistort) |
| camera mount | | no static chain `robot_base_link` → camera frame |
| poses | `map` → `odom` or `odom` → `robot_base_link` missing, or under 90 % of photos have a pose close in time | |
| route length | under 10 m driven | |
| revisits | | under 10 % of photos at a place revisited 30 s or more later |

Exit 0 means no FAIL. Exit 1 means at least one, so do not leave the lab without a recording
that exits 0. The thresholds are in `RecordingSpec` at the top of
[`recording_check.py`](recording_check.py). Topic and frame names can be changed on the command
line (`--color-topic`, `--base-frame`, ...).

## 6. Keep with the recording

A `notes.md` in the bag folder with: the date and who drove, the camera serial
(`mobile_base_camera.serial`), the saved map's name, the mount values in
`shared/global_config.yaml` on the day, the git commit of the repo, and anything that went wrong.
The replay needs the calibrated mount (T5.5) and the D455 depth scale (1000 units per metre),
neither of which the bag can say is correct.

## Changelog

| Date | Who | Change |
|---|---|---|
| 2026-10-14 | Claude Opus 5.5 + Zongzhe | First version, with `recording_check.py` (T6.2a) |
