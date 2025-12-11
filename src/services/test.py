import numpy as np
from matplotlib import rcParams
from projectaria_tools.core import calibration, data_provider

# from projectaria_tools.core.calibration import CameraCalibration, KANNALA_BRANDT_K3

rcParams["figure.figsize"] = 16, 32

import os

from PIL import Image


def undistort_aria(image_array, provider, sensor_name, focal_length, size):
    device_calib = provider.get_device_calibration()
    src_calib = device_calib.get_camera_calib(sensor_name)

    # create output calibration: a linear model of image size 512x512 and focal length 150
    # Invisible pixels are shown as black.
    dst_calib = calibration.get_linear_camera_calibration(
        size, size, focal_length, sensor_name
    )

    # distort image
    rectified_array = calibration.distort_by_calibration(
        image_array, dst_calib, src_calib
    )
    return (
        rectified_array,
        dst_calib.get_principal_point(),
        dst_calib.get_focal_lengths(),
    )


aria_path = os.path.join(aria_dir, f"{ego_cam_name}.vrs")
vrs_data_provider = data_provider.create_vrs_data_provider(aria_path)

img = ego_frame
img = img.rotate(90)
image_array = np.asarray(img)
rectified_array, principal_points, focal_lengths = undistort_aria(
    image_array, vrs_data_provider, "camera-rgb", 150, 512
)
undistorted_frame = Image.fromarray(rectified_array, "RGB")
