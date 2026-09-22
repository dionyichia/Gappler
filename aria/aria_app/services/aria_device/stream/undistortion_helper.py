import numpy as np
from projectaria_tools.core.calibration import (
    CameraCalibration,
)


def build_remap_maps(source_calib: CameraCalibration, dest_calib: CameraCalibration):
    width, height = dest_calib.get_image_size()
    us, vs = np.meshgrid(np.arange(width), np.arange(height))
    pixels = np.stack([us.ravel(), vs.ravel()], axis=1).astype(np.float64)

    # Vectorized unproject then project
    rays = np.array([dest_calib.unproject_no_checks(p) for p in pixels])
    src_pixels = np.array([source_calib.project_no_checks(r) for r in rays])

    map_x = src_pixels[:, 0].reshape(height, width).astype(np.float32)
    map_y = src_pixels[:, 1].reshape(height, width).astype(np.float32)
    return map_x, map_y
