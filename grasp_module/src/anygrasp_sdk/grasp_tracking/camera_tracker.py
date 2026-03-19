import argparse
import os

import numpy as np
import open3d as o3d
import pyrealsense2 as rs  # ADDED
from graspnetAPI import GraspGroup
from PIL import Image
from tracker import AnyGraspTracker  # Compiled binary model file

# Argument parsing
parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint_path", required=True, help="Model checkpoint path")
parser.add_argument(
    "--filter",
    type=str,
    default="oneeuro",
    help="Filter to smooth grasp parameters(rotation, width, depth). [oneeuro/kalman/none]",
)
parser.add_argument("--debug", action="store_true", help="Enable visualization")
cfgs = parser.parse_args()


# ADDED - replaces CameraInfo class and create_point_cloud_from_depth_image
def setup_realsense():
    pipeline = rs.pipeline()
    config = rs.config()

    # 1280, 720 number of horizontal and vertical pixels
    # z16 - 16 bit unsigned integer, raw depth
    # rgb8 - 8 bit red green blue green matching demo png
    config.enable_stream(rs.stream.depth, rs.format.z16, 30)
    config.enable_stream(rs.stream.color, rs.format.rgb8, 30)
    # Start pipeline
    profile = pipeline.start(config)

    # Get depth scale from firmware instead of hardcoding
    depth_sensor = profile.get_device().first_depth_sensor()
    depth_scale = depth_sensor.get_depth_scale()

    # Aligning the physically apart depth camera and colour camera with colour cam as base
    align = rs.align(rs.stream.color)

    return pipeline, align, depth_scale


# ADDED - replaces get_data()
def get_data(pipeline, align, depth_scale):
    # Synchronising packets of frames
    frames = pipeline.wait_for_frames()
    # Warp depth image to fit colour image
    aligned = align.process(frames)

    # Pull depth and colour frame from the aligned frames
    depth_frame = aligned.get_depth_frame()
    color_frame = aligned.get_color_frame()
    if not depth_frame or not color_frame:
        return None, None

    # Get intrinsics data from camera feed
    intrinsics = depth_frame.profile.as_video_stream_profile().intrinsics
    fx, fy = intrinsics.fx, intrinsics.fy
    cx, cy = intrinsics.ppx, intrinsics.ppy

    # Get the raw depth and normalised colour frame as np arrays
    colors = np.asanyarray(color_frame.get_data(), dtype=np.float32) / 255.0
    depths = np.asanyarray(depth_frame.get_data())

    # Apply transformations required to get real-life x,y,z positions
    xmap, ymap = np.arange(depths.shape[1]), np.arange(depths.shape[0])
    xmap, ymap = np.meshgrid(xmap, ymap)
    points_z = depths * depth_scale
    points_x = (xmap - cx) * points_z / fx
    points_y = (ymap - cy) * points_z / fy
    points = np.stack([points_x, points_y, points_z], axis=-1)

    # Apply mask of 1.5m
    mask = (points[:, :, 2] > 0) & (points[:, :, 2] < 1.5)
    points = points[mask]
    colors = colors[mask]

    return points, colors


def demo(data_dir_list, indices):
    # intialization
    anygrasp_tracker = AnyGraspTracker(cfgs)
    anygrasp_tracker.load_net()

    grasp_ids = [0]

    pipeline, align, depth_scale = setup_realsense()  # ADDED

    vis = o3d.visualization.Visualizer()
    vis.create_window(height=720, width=1280)

    frame_idx = 0  # ADDED - replaces loop over pre-defined indices list

    try:  # ADDED
        while True:  # ADDED - replaces for loop over indices
            points, colors = get_data(pipeline, align, depth_scale)
            if points is None:  # ADDED
                continue

            target_gg, curr_gg, target_grasp_ids, corres_preds = (
                anygrasp_tracker.update(points, colors, grasp_ids)
            )

            # CHANGED - removed hardcoded 3D bounding box selection
            # TODO: replace with SAM segmentation mask in step 2
            if frame_idx == 0:
                grasp_ids = np.arange(len(curr_gg))[:30:6]
                target_gg = curr_gg[grasp_ids]
            else:
                # Fallback: if tracking is lost reset to frame 0 detection
                if target_grasp_ids is None or len(target_grasp_ids) == 0:
                    print("Tracking lost, resetting to detection mode")
                    frame_idx = 0
                    grasp_ids = [0]
                    continue
                grasp_ids = target_grasp_ids

            print(frame_idx, target_grasp_ids)

            if cfgs.debug:
                trans_mat = np.array(
                    [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]
                )
                cloud = o3d.geometry.PointCloud()
                cloud.points = o3d.utility.Vector3dVector(points)
                cloud.colors = o3d.utility.Vector3dVector(colors)
                cloud.transform(trans_mat)
                grippers = target_gg.to_open3d_geometry_list()
                for gripper in grippers:
                    gripper.transform(trans_mat)
                vis.add_geometry(cloud)
                for gripper in grippers:
                    vis.add_geometry(gripper)
                vis.poll_events()
                vis.remove_geometry(cloud)
                for gripper in grippers:
                    vis.remove_geometry(gripper)

            frame_idx += 1  # ADDED

    finally:  # ADDED
        pipeline.stop()  # ADDED


if __name__ == "__main__":
    data_dir = "example_data"
    data_dir_list = [x for x in range(30)]
    demo(data_dir, data_dir_list)
