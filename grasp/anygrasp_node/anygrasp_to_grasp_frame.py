"""Turn an AnyGrasp grasp rotation into grasp_frame's axes (T1.17).

The two name the same directions differently:
  AnyGrasp     x = approach (toward the object), y = the way the fingers close
  grasp_frame  -z = approach, y = the way the fingers close
grasp_frame is set in rm_65_w_gripper.urdf.xacro:15-18. On the box (2026-10-14, live TF) Link6 sits
at +0.147 m z of it and the fingers at +-0.040 m y. moveToPose aims grasp_frame at the candidate
(mtc_planner.cpp setIKFrame), so the candidate must use grasp_frame's axes.
So x_g = z_a, y_g = y_a, z_g = -x_a: a fixed -90 degree turn about y.

Run this file to check the conversion: python3 anygrasp_to_grasp_frame.py
"""
import numpy as np

ANYGRASP_TO_GRASP_FRAME = np.array([[0.0, 0.0, -1.0],
                                    [0.0, 1.0, 0.0],
                                    [1.0, 0.0, 0.0]])


def to_grasp_frame(rotation_matrix):
    return rotation_matrix @ ANYGRASP_TO_GRASP_FRAME


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    for _ in range(100):
        r_a, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        r_a *= np.sign(np.linalg.det(r_a))  # a proper rotation
        r_g = to_grasp_frame(r_a)
        assert np.allclose(-r_g[:, 2], r_a[:, 0]), "approach must be grasp_frame's -z"
        assert np.allclose(r_g[:, 1], r_a[:, 1]), "closing must stay on y"
        assert np.isclose(np.linalg.det(r_g), 1.0), "must stay a rotation"
    print("PASS: AnyGrasp approach -> grasp_frame -z, closing stays on y")
