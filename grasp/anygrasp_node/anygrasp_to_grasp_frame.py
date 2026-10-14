"""Turn an AnyGrasp grasp into grasp_frame's axes and position (T1.17).

The two name the same directions differently:
  AnyGrasp     x = approach (toward the object), y = the way the fingers close
  grasp_frame  -z = approach, y = the way the fingers close
grasp_frame is set in rm_65_w_gripper.urdf.xacro:15-18. On the box (2026-10-14, live TF) Link6 sits
at +0.147 m z of it and the fingers at +-0.040 m y. moveToPose aims grasp_frame at the candidate
(mtc_planner.cpp setIKFrame), so the candidate must use grasp_frame's axes.
So x_g = z_a, y_g = y_a, z_g = -x_a: a fixed -90 degree turn about y.

Position: grasp_frame is at the fingertips (147.5 mm from the flange, measured 2026-10-14).
AnyGrasp's point is not: its fingers reach `depth` past it along the approach
(graspnetAPI utils.py plot_gripper_pro_max). So the fingertips go to point + depth * x_a.

Run this file to check the conversion: python3 anygrasp_to_grasp_frame.py
"""
import numpy as np

ANYGRASP_TO_GRASP_FRAME = np.array([[0.0, 0.0, -1.0],
                                    [0.0, 1.0, 0.0],
                                    [1.0, 0.0, 0.0]])


def to_grasp_frame(rotation_matrix):
    return rotation_matrix @ ANYGRASP_TO_GRASP_FRAME


def fingertip_position(translation, rotation_matrix, depth):
    """Where grasp_frame goes: AnyGrasp's point moved `depth` along its approach."""
    return translation + depth * rotation_matrix[:, 0]


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    for _ in range(100):
        r_a, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        r_a *= np.sign(np.linalg.det(r_a))  # a proper rotation
        r_g = to_grasp_frame(r_a)
        assert np.allclose(-r_g[:, 2], r_a[:, 0]), "approach must be grasp_frame's -z"
        assert np.allclose(r_g[:, 1], r_a[:, 1]), "closing must stay on y"
        assert np.isclose(np.linalg.det(r_g), 1.0), "must stay a rotation"
        point = rng.normal(size=3)
        tip = fingertip_position(point, r_a, 0.03)
        assert np.allclose(tip - point, -0.03 * r_g[:, 2]), "tips 0.03 m further along the approach"
    print("PASS: AnyGrasp approach -> grasp_frame -z, closing stays on y, tips depth past the point")
