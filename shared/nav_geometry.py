"""Planar goal geometry with a camera origin distinct from the mobile base."""
import math


def camera_goal_xy(target_x: float, target_y: float, yaw: float,
                   camera_x: float, camera_y: float, clearance: float) -> tuple[float, float]:
    """Place the camera clearance metres behind the target along robot heading.

    Camera x/y are the TF-derived origin in robot_base_link. Vertical distance
    and optical rotation are deliberately excluded from this planar Nav2 goal.
    """
    if not all(math.isfinite(v) for v in (target_x, target_y, yaw, camera_x, camera_y, clearance)) or clearance <= 0:
        raise ValueError('camera goal requires finite geometry and positive clearance')
    forward = camera_x + clearance
    return (target_x - math.cos(yaw) * forward + math.sin(yaw) * camera_y,
            target_y - math.sin(yaw) * forward - math.cos(yaw) * camera_y)
