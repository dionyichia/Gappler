# Foxglove live view

One live view of the whole robot, from your own laptop. Tasks: T0.24.

## What it is

Every `./quickstart_terminals.sh` session opens a `view` window that starts a `foxglove_bridge`
(a process that sends ROS 2 topics to the Foxglove app). Only one bridge runs per box. If one is
already up, the `view` window names it and starts nothing.

The app cannot move anything. The bridge is read-only: its `capabilities` setting is only
`connectionGraph` and `assets`, so Foxglove can read topics but cannot publish, call services or
set parameters. It can never send `/cmd_vel` or `/rm_driver/*_cmd`. Settings:
`shared/foxglove/foxglove_bridge_config.yaml`. RViz stays for MoveIt planning.

## Connect

1. Install the Foxglove desktop app from foxglove.dev/download. It needs a free account.
2. Turn Tailscale on. The bridge listens on the box's Tailscale IP only (set in the config file), so
   only tailnet members can connect. The lab network and campus Wi-Fi cannot.
3. In Foxglove: Open connection, Foxglove WebSocket, `ws://<box Tailscale IP>:8765`. Checked 2026-11-13 with a test publisher: connects and shows data.
4. From the Layouts menu, import `shared/foxglove/gappler_full_layout.json`. Checked 2026-11-13: it imports and the State Transitions panel shows `/pipeline_state`.

## What you see

Checked 2026-11-13 on the box: the state panel (test publisher), the wrist image and the lidar cloud (real sensors, no arm or base). The rest are `[unverified]` until a fuller robot session.

- 3D: the robot model (`/robot_description`), `/map`, `/scan`, the raw lidar cloud `/livox/lidar`, `/robot_pose`, `/aria/fused_pose`,
  `/goal_pose`, and the object and grasp markers.
- Wrist image: `/camera/camera/color/image_raw`.
- Mask image: `/camera/sam/mask`.
- Aria image: `/aria/rgb_camera/raw`.
- State transitions: `/pipeline_state`.
- Gaze plot: `/aria/eye_tracking/gaze_estimate` x and y.
- Raw messages: `/aria/audio/prompt` (the voice prompt).
- Topic graph: who publishes and subscribes to what.

Panels for subsystems that are not running stay empty.

## What does not show

Four perception topics hold Python pickle bytes inside a `UInt8MultiArray`, which Foxglove cannot
decode: `/aria/rgb_camera/object_masks`, `/realman/rgb_camera/object_masks`,
`/combined/object_masks` and `/aria/rgb_camera/feature_match`. Use `/camera/sam/mask` instead.

## Slow connection

Raw camera images and point clouds are heavy over Tailscale. Close panels you do not need. The
bridge only sends topics that an open panel uses.
Measured 2026-11-13: the wrist image is about 14 MB/s and the lidar cloud about 5 MB/s. Together they
overflowed one client's connection and the lidar did not show until the image panel was closed.

## Lidar cloud shows nothing

The cloud is in the frame `livox_frame`. The 3D panel can only draw it if there is a transform from
its display frame. The SLAM launch publishes those transforms. With only the lidar driver running
there are none, so set the 3D panel's Frame to `livox_frame`.

## Changing the layout

Export the layout from Foxglove over `shared/foxglove/gappler_full_layout.json` and commit it.
`bench/test_foxglove_view.py` fails if the layout names a topic the contract
(`bench/golden/contracts.json`) does not know. Add a topic to `STANDARD_TOPICS` in that test only
if it really comes from ROS or a vendor package, not from our code.

Changelog 2026-11-13 (T0.24, Sherman): created. Switched from an SSH tunnel to the box's Tailscale IP (tailnet is team only). Added `/livox/lidar` to the layout, checked the wrist image and lidar live.
