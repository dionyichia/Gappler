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
4. From the Layouts menu, import `shared/foxglove/gappler_layout.json`. The first, one-screen layout imported and showed live data on 2026-11-13. The five-tab version loaded and showed live data on 2026-11-14.

## What you see

One layout, five tabs. Pick the tab for the work you are doing. Panels for subsystems that are not
running stay empty.

**Keep one tab open during a run.** Opening a tab starts its panels from empty, so a timeline only
remembers what happened while its tab was open (checked live 2026-11-14). To look back over a whole
run, record a bag and open it in Foxglove instead.

| Tab | Use it for | Panels |
|---|---|---|
| Main | Leave open during any session: is everything alive, where is the pipeline | Timeline, one row per channel on one time axis: state machine (`/pipeline_state`), voice word, target sent (`/grasp/target`), nav arrived (`/goal_reached`), handover start (`/manipulation/start`), return to user, release. Warnings and errors from every node (`/rosout`). Small wrist and Aria images |
| Grasp | Arm and grasp debugging | Wrist image with the grasp candidates, AnyGrasp's points and the centroid drawn on it. Depth to the object (`/object_centroid_2d` z), which should step down to 0.18 m in SELECTING. AnyGrasp's best grasp score. A small timeline of the state machine and the target. The mask (`/debug/sam_mask`). 3D arm with the same markers, centred on `base_link` |
| Glasses | Voice and gaze | Aria image, the prompt sent on `/grasp/target`, raw gaze values |
| Nav | Base driving | 3D centred on `map`: base model, `/map`, global costmap, `/plan`, `/scan`, robot pose, goal, user pose, object and glasses markers. The raw lidar cloud is there but off, tick it when needed. Beside it, a plot of `/cmd_vel` (forward and turn speed Nav2 sends the base: flat at zero means Nav2 sends nothing, values with a still base means the base driver) and a timeline of `/goal_reached` and `/manipulation/start` (did it arrive, did the handover fire). Reading `/cmd_vel` is safe, the bridge cannot publish |
| Topics | Is anything publishing | Every topic with its type and message rate |

A timeline row shows the value as a coloured block that lasts until the value changes. The same
value sent twice stays one block, so a repeated event is not visible as a second block. Hover a
block to read its value and time.

The timeline cannot show `/manipulation/done` and `/manipulator/grasp_request`. They are `Empty`
messages, so there is no value to draw.

**No topic graph.** Foxglove's Topic Graph was tried on 2026-11-14 and could not be read: the
camera driver alone publishes about 40 topics. For who publishes and subscribes to a topic, use
`ros2 topic info -v <topic>` on the box. For one node's topics, `ros2 node info <node>`.

Checked live on 2026-11-14 (wrist camera plus a fake pipeline, no arm, base or glasses): all tabs
load, the compressed wrist image, the timeline, the depth plot and gaze show data. Not yet seen
live: the overlays on the wrist image (they need TF from the markers' frames to the camera), the
mask, the 3D arm and nav views, the Aria image and `/cmd_vel` `[unverified]`.

## What does not show

Four perception topics hold Python pickle bytes inside a `UInt8MultiArray`, which Foxglove cannot
decode: `/aria/rgb_camera/object_masks`, `/realman/rgb_camera/object_masks`,
`/combined/object_masks` and `/aria/rgb_camera/feature_match`. Use the mask image in the Grasp tab instead. It shows `/debug/sam_mask`, not `/camera/sam/mask`: the raw
mask holds 0 and 1, which draws as black. `grasp_viz` republishes it as 0 and 255.

## Slow connection

Raw camera images and point clouds are heavy over Tailscale. Close panels you do not need. The
bridge only sends topics that an open panel uses.
Measured 2026-11-13: the raw wrist image is about 14 MB/s and the lidar cloud about 5 MB/s. Together they
overflowed one client's connection and the lidar did not show until the image panel was closed.
So the layout uses the wrist image's `/compressed` topic (the compression plugin is installed on the box,
checked 2026-11-14), and the raw lidar cloud starts switched off.

## Lidar cloud shows nothing

The cloud is in the frame `livox_frame`. The 3D panel can only draw it if there is a transform from
its display frame. The SLAM launch publishes those transforms. With only the lidar driver running
there are none, so set the 3D panel's Frame to `livox_frame`.

## Changing the layout

Export the layout from Foxglove over `shared/foxglove/gappler_layout.json` and commit it.
Keep your own changes in a copy inside Foxglove. Export over the repo file only what the team should get.
`bench/test_foxglove_view.py` fails if the layout names a topic the contract
(`bench/golden/contracts.json`) does not know. Add a topic to `STANDARD_TOPICS` in that test only
if it really comes from ROS, Nav2 or a vendor package, not from our code. A `/compressed` topic passes
when the topic it compresses is known. The check also fails if a panel is in no tab, or the tabs change.

Changelog 2026-11-13 (T0.24, Sherman): created. Switched from an SSH tunnel to the box's Tailscale IP (tailnet is team only). Added `/livox/lidar` to the layout, checked the wrist image and lidar live. 2026-11-14: five tabs (Main, Grasp, Glasses, Nav, Wiring), compressed wrist image, mask from `/debug/sam_mask`, layout file renamed `gappler_layout.json`. Nav gains a `/cmd_vel` plot and a nav timeline, Wiring is the topic graph alone. Live check 2026-11-14: topic graph replaced by a topic list (tab Topics), 3D panels centred on `map` and `base_link`, timeline rows labelled with the state machine first, a grasp score plot and a small timeline on Grasp.
