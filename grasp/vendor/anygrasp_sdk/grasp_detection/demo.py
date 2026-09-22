import argparse
import os

import numpy as np
import open3d as o3d
import torch
from graspnetAPI import GraspGroup  # OS library providing grasp data structures
from gsnet import AnyGrasp  # Compiled binary model file
from PIL import Image


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint_path", required=True, help="Model checkpoint path")
parser.add_argument(
    "--max_gripper_width",
    type=float,
    default=0.1,
    help="Maximum gripper width (<=0.1m)",
)
parser.add_argument("--gripper_height", type=float, default=0.03, help="Gripper height")
parser.add_argument(
    "--top_down_grasp", action="store_true", help="Output top-down grasps."
)
parser.add_argument("--debug", action="store_true", help="Enable debug mode")

cfgs = parser.parse_args()
cfgs.max_gripper_width = max(0, min(0.1, cfgs.max_gripper_width))


# ---------------------------------------------------------------------------
# Main demo: Image (png) -> Pose
# ---------------------------------------------------------------------------


def demo(data_dir):
    # Load model
    anygrasp = AnyGrasp(cfgs)
    anygrasp.load_net()

    # ---- Determine API calls -----------------------------------------------
    print(anygrasp.load_net.__doc__)

    # ---- Load images -------------------------------------------------------
    colors = (
        np.array(Image.open(os.path.join(data_dir, "color.png")), dtype=np.float32)
        / 255.0
    )
    depths = np.array(Image.open(os.path.join(data_dir, "depth.png")))

    # ---- Camera intrinsics (RealSense) -------------------------------------
    fx, fy = 927.17, 927.37
    cx, cy = 651.32, 349.62
    scale = 1000.0  # depth unit: mm -> m

    # ---- Workspace limits (camera space) -----------------------------------
    # Defines the reachable volume used to filter output grasps
    xmin, xmax = -0.19, 0.12
    ymin, ymax = 0.02, 0.15
    zmin, zmax = 0.0, 1.0
    lims = [xmin, xmax, ymin, ymax, zmin, zmax]

    # ---- Build point cloud -------------------------------------------------
    # Use three 2D arrays (one per axis) instead of a single 3D vector array
    xmap, ymap = np.meshgrid(np.arange(depths.shape[1]), np.arange(depths.shape[0]))

    points_z = depths / scale  # depth in metres
    points_x = (xmap - cx) / fx * points_z  # x offset from image centre
    points_y = (ymap - cy) / fy * points_z  # y offset from image centre

    # Boolean mask: keep only pixels with valid depth
    mask = (points_z > 0) & (points_z < 1)

    # Stack into (N, 3) arrays by applying the mask
    points = np.stack([points_x, points_y, points_z], axis=-1)[mask].astype(np.float32)
    colors = colors[mask].astype(np.float32)

    # Print the bounding box of the filtered point cloud
    print(points.min(axis=0), points.max(axis=0))

    # ---- Grasp prediction --------------------------------------------------
    gg, cloud = anygrasp.get_grasp(
        points,
        colors,
        lims=lims,
        apply_object_mask=True,
        dense_grasp=False,
        collision_detection=True,
    )

    if len(gg) == 0:
        print("No Grasp detected after collision detection!")

    # NMS: remove overlapping grasps, keep the highest-scoring one per region
    gg = gg.nms().sort_by_score()
    gg_pick = gg[0:20]  # Top-20 by confidence score

    print(gg_pick.scores)
    print("grasp score:", gg_pick[0].score)

    # Determine object information
    # print(gg_pick[0])
    # print(dir(gg_pick[0]))
    # print(type(gg_pick[0]))

    # ---- Visualisation (debug only) ----------------------------------------
    if cfgs.debug:
        # Flip from camera coords (Z forward) to Open3D world coords (Z up)
        # i.e. reflect across the XY plane
        trans_mat = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])

        cloud.transform(trans_mat)

        grippers = gg.to_open3d_geometry_list()
        for gripper in grippers:
            gripper.transform(trans_mat)

        o3d.visualization.draw_geometries([*grippers, cloud])
        o3d.visualization.draw_geometries([grippers[0], cloud])


if __name__ == "__main__":
    demo("./example_data/")
