import argparse
import inspect
import os

import numpy as np
import open3d as o3d
import torch
from graspnetAPI import GraspGroup  # OS library providing grasp data structures
from gsnet import AnyGrasp  # Compiled binary model file
from PIL import Image

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
cfgs = parser.parse_args()  # Create object with all arguments
cfgs.max_gripper_width = max(
    0, min(0.1, cfgs.max_gripper_width)
)  # Set gripper width variable

# add something something


# Image (png) -> Pose
def demo(data_dir):  # where data dir is the location of the image
    anygrasp = AnyGrasp(cfgs)  # Loads the model with the configurations given
    anygrasp.load_net()
    # print(anygrasp)
    # print(dir(anygrasp))
    # print(type(anygrasp))
    print(anygrasp.load_net.__doc__)

    # get data
    colors = (
        np.array(Image.open(os.path.join(data_dir, "color.png")), dtype=np.float32)
        / 255.0
    )
    depths = np.array(Image.open(os.path.join(data_dir, "depth.png")))
    # get camera intrinsics - from realsense camera
    fx, fy = 927.17, 927.37
    cx, cy = 651.32, 349.62
    scale = 1000.0
    # set workspace to filter output grasps
    # Based on reachable volume in the camera space
    xmin, xmax = -0.19, 0.12
    ymin, ymax = 0.02, 0.15
    zmin, zmax = 0.0, 1.0
    lims = [xmin, xmax, ymin, ymax, zmin, zmax]

    # get point cloud
    # Instead of storing a 3D vector, store as 3 2D vectors, indexing
    xmap, ymap = np.arange(depths.shape[1]), np.arange(depths.shape[0])
    xmap, ymap = np.meshgrid(xmap, ymap)
    points_z = depths / scale  # Converting from mm to m
    points_x = (
        (xmap - cx) / fx * points_z
    )  # 2D Array that provides the x value as measured from the centre of the image
    points_y = (
        (ymap - cy) / fy * points_z
    )  # 2D Array that provides the y value as measured from the centre of the image

    # set your workspace to crop point cloud
    mask = (
        (points_z > 0) & (points_z < 1)
    )  # A 2D array corresponding to the original image size that is populated with boolean values

    points = np.stack([points_x, points_y, points_z], axis=-1)  # Creates a 3D block
    # Block is structured as a 2D array. Each cell in the array has a triplet of values for (x,y,z)
    points = points[
        mask
    ].astype(
        np.float32
    )  # Applying the boolean mask to the 3D block, each of the corresponding pixels' value triplets are appended to a list
    # This gives you a (N,3) array, where N corresponds to the number of pixels which were marked as true
    colors = colors[
        mask
    ].astype(
        np.float32
    )  # Applying the boolean mask to the colour block, each of the corresponding pixels also have a normalised colour value attached to it
    print(
        points.min(axis=0), points.max(axis=0)
    )  # print the bounding box of filtered point cloud - i.e where does the model predict grasps?

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

    gg = gg.nms().sort_by_score()  # Non-maximum supression, looks for grasps that overlap too much and keeps only the best one in the local area
    gg_pick = gg[0:20]  # Gets the grasps with the 20 highest confidence scores
    print(gg_pick.scores)
    print(
        "grasp score:", gg_pick[0].score
    )  # Prints the confidence score of the highest scoring grasp
    # Print the
    # print(gg_pick[0])
    # print(dir(gg_pick[0]))
    # print(type(gg_pick[0]))

    # visualization
    if cfgs.debug:
        # Transformation to flip from camera coordinate systems where Z points forward
        # to open3d world type coordinate systems where Z points up
        # reflection on the XY plane
        trans_mat = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]])
        cloud.transform(trans_mat)
        grippers = gg.to_open3d_geometry_list()
        for gripper in grippers:
            gripper.transform(trans_mat)
        o3d.visualization.draw_geometries([*grippers, cloud])
        o3d.visualization.draw_geometries([grippers[0], cloud])


if __name__ == "__main__":
    demo("./example_data/")
