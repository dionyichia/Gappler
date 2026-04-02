# Pose Fusion Node

Fuses OpenVINS VIO pose with periodic ArUco marker corrections to produce a stable, drift-corrected pose estimate of the Aria glasses expressed in the robot's SLAM map frame.

## Architecture

It runs alongside OpenVINS as a separate ROS 2 node and corrects its output using ArUco detections as loop-closure anchors.

```
/aria/imu         ──┐
/aria/vio_pose    ──┤  aria_pose_fusion  ──►  /aria/fused_pose
/aria/aruco_pose  ──┘                    └──►  /aria/is_stationary
```

## How It Works

### ArUco correction

Every time the ArUco marker comes into frame, the node recomputes a rigid correction offset that re-anchors the drifting VIO frame to the SLAM map:

```
T_map_camera  = T_map_marker @ inv(T_camera_marker)
T_correction  = T_map_camera @ inv(T_vio_at_detection_time)
fused_pose    = T_correction @ T_vio_current
```

- `T_map_marker` — where the ArUco marker sits in your SLAM map (set via ROS params)
- `T_camera_marker` — the raw ArUco detection result from `/aria/aruco_pose`
- `T_correction` — accumulates the VIO drift since the last ArUco fix

Each new ArUco sighting resets accumulated drift. The more frequently the marker is visible, the tighter the correction.

> **Simplification:** The node currently treats the RGB camera centre as equal to the glasses IMU origin. For sub-centimetre accuracy, chain in the `T_camera_glasses` extrinsic from `kalibr_imucam_chain.yaml` at the marked comment in `_on_aruco_pose`.

## Topics

| Direction | Topic | Type | Description |
|-----------|-------|------|-------------|
| Subscribed | `/aria/vio_pose` | `PoseStamped` | OpenVINS output |
| Subscribed | `/aria/aruco_pose` | `PoseStamped` | ArUco T_camera_marker in camera frame |
| Subscribed | `/aria/imu` | `Imu` | Raw IMU |
| Published | `/aria/fused_pose` | `PoseStamped` | Corrected pose in `map` frame |

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `marker_pos_x` | `0.0` | ArUco marker X position in SLAM map (m) |
| `marker_pos_y` | `0.0` | ArUco marker Y position in SLAM map (m) |
| `marker_pos_z` | `0.0` | ArUco marker Z position in SLAM map (m) |
| `marker_quat_x` | `0.0` | ArUco marker orientation (quaternion) |
| `marker_quat_y` | `0.0` | |
| `marker_quat_z` | `0.0` | |
| `marker_quat_w` | `1.0` | |

## Usage

Measure the ArUco marker's position in your SLAM map (e.g. from the map visualiser or a known reference point), then pass it as params:

```bash
ros2 run <your_package> pose_fusion_node \
    --ros-args \
    -p marker_pos_x:=1.5 \
    -p marker_pos_y:=0.0 \
    -p marker_pos_z:=0.9 \
    -p marker_quat_w:=1.0
```

The node will log each ArUco correction with its translation offset, so you can verify it is working without needing RViz.

## Frame Convention

```
map      — SLAM map origin (robot LiDAR-SLAM frame)
glasses  — Aria glasses IMU / OpenVINS reference frame
camera   — Aria RGB camera optical frame
marker   — ArUco marker body frame
```

The fused pose is always published in the `map` frame, which is the same frame your robot localises in via LiDAR SLAM.
