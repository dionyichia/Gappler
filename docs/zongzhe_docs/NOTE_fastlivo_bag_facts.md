# NOTE: the FAST-LIVO hand-driven bag, and the three facts the loader needs

**What this is.** The lab recording for M6 arrived as a FAST-LIVO hand-driven bag, not the
RGB-D recording T6.2 planned for. It has colour, intrinsics and poses, but **no depth image**:
depth has to be synthesised by projecting the LiDAR cloud into the colour camera. Before writing
that loader (T6.3b's "reader for the lab recording") I pulled three facts off the lab box. They
are recorded here so the loader code can cite them. Owner: Zongzhe. Written 2026-10-21.

**The bag.** `rcp2026@lab-box:/home/rcp2026/rcp-Gappler/log/t59-fastlivo/log/`
`t35d-attended-20261020.raLTgE/run/bag/handdriven1/handdriven1_0.db3`. 4.7 GB, 118 s, 8 topics.
Relevant ones: `/camera/camera/color/image_raw`, `/camera/camera/color/camera_info`,
`/aft_mapped_to_init` (FAST-LIVO odometry), `/cloud_registered` (registered LiDAR, world frame).
No depth topic. `[code]` read from the bag's `metadata.yaml` and message blobs 2026-10-21.

## The three facts

### 1. The LiDAR-to-camera extrinsic, and its direction

From the FAST-LIVO visual config used for this capture, `[code]` read 2026-10-21 at
`…/log/t35c-stationary02-B2.w5m73E/replay/config/t35c_stationary02_20261019_visual.yaml`
(source fork `U-AMC/FAST-LIVO2-ROS2 @ a09599a`). The `t35d-attended` run dir keeps only bag
metadata, so the extrinsic is read from the sibling replay config for the same rig.

- **LiDAR to colour optical**, stated by the config's own comment as
  `p_colour_optical = Rcl * p_lidar + Pcl`:
  - `Rcl = [[0, -1, 0], [0, 0, -1], [1, 0, 0]]` (det = +1, the standard ROS-body to
    optical-frame axis swap, so it is a sane rotation).
  - `Pcl = [-0.0115, 0.3425, -0.03915]` metres.
  - So this **is `T_cam_lidar`** (camera-from-lidar). The loader **must invert it** to use it in
    a camera-to-world chain. This is the direction that is easy to get backwards.
- **LiDAR to IMU**, comment `p_imu = R * p_lidar + T`:
  - `extrinsic_R = identity`, `extrinsic_T = [-0.011, -0.02329, 0.04412]` metres. So `T_imu_lidar`.

### 2. The pose frames: `/aft_mapped_to_init`

`header.frame_id = camera_init`, `child_frame_id = aft_mapped`. `[code]` read from the message
blob 2026-10-21. `camera_init` is FAST-LIVO's name for the init world frame, not a camera.
So the message is the **body pose in the world**, `T_world_imu`, used **forward** (no inversion).
`[inferred]`: `aft_mapped` is the IMU body frame, the FAST-LIO convention where odometry is the
IMU pose. Worth one line of confirmation against the fork's source, but low risk: `extrinsic_R`
is identity and the IMU-to-LiDAR offset is about 5 cm, so an IMU-vs-LiDAR mix-up costs under 5 cm
and no rotation.

### 3. The colour encoding

`/camera/camera/color/image_raw` is **`rgb8`**, frame `camera_color_optical_frame`. `[code]` read
from the message blob 2026-10-21. So in `to_observation` set **`bgr=False`** (do not flip). This
is the opposite of the TUM reader, which goes through OpenCV and so is BGR. `/cloud_registered` is
in frame `camera_init` (already world) and carries per-point rgb, so for depth only its xyz and
the camera's world pose are needed, no per-point LiDAR pose.

## The composition the loader does

```
T_world_cam = T_world_imu  @  T_imu_lidar  @  inv(T_cam_lidar)
```

- `T_world_imu`: from the odometry position and quaternion (xyzw), used forward.
- `T_imu_lidar`: translation only, `extrinsic_T` (since `extrinsic_R` is identity).
- `inv(T_cam_lidar)`: invert the `Rcl / Pcl` transform. **Skipping this inversion, or applying
  `Rcl / Pcl` the wrong way, is the pitfall** that puts the whole cloud behind or beside the
  camera.

The result is passed as `to_observation(T_world_base = T_world_cam, T_base_cam = None,
depth_units_per_metre = 1.0, bgr = False)`, with `K` read per frame from
`/camera/camera/color/camera_info`.

## Caveat: the extrinsic is provisional, not calibrated

The config says so in as many words: *"Tape-level positions, eye-estimated mount rotation; four
offline samples show coverage, not target calibration."* And `Pcl` has a **34 cm** lever arm
(`0.3425` m) between the LiDAR and the camera. So LiDAR-synthesised depth will be misaligned from
the true colour geometry by whatever that extrinsic error is. This caps depth accuracy for near
and small objects, and it is a real input to T6.4's weight-and-threshold tuning. It may justify a
proper LiDAR-camera calibration before the merge test is trusted.

Two more, smaller:

- **Clocks are host-receipt, not hardware-synced.** `time_offset.*` are all `0.0` with the comment
  *"Host receipt lags are not measured physical clock offsets. No correction."* So matching
  colour to pose to cloud runs on host stamps. Give `max_dt` slack; fine for a slow handheld drive,
  worth watching.
- **Lens distortion is not corrected.** `camera_info` carries a plumb_bob `D` (`cam_d0 = -0.056`,
  `cam_d1 = 0.066` at 640x480 `[code]` from the camera config), and the loader corrects nothing, so
  LiDAR projected into the uncorrected colour image is slightly off at the edges.

## What this opens

The loader (T6.3b's lab-recording reader) can now be written against real colour, intrinsics and
poses. Depth comes from projecting `/cloud_registered` into the colour frame, so `Observation`
stays the contract and T6.3e's code is unchanged (only its config constants, `min_points`,
`voxel_size_m`, the DBSCAN values, are expected to retune on this sparser depth, under T6.4).
This is a fork from T6.3b's RGB-D assumption and may want its own sub-task; not added yet.

## Changelog

| Date | Who | What |
| --- | --- | --- |
| 2026-10-21 | Claude (Opus 4.8) + Zongzhe | Created. The three facts (extrinsic and direction, pose frames, colour encoding) read off the lab box, the camera-to-world composition, and the provisional-extrinsic caveat, ahead of writing the `FastLivoBag` loader on branch `t6.3b-fastlivo-loader`. |
