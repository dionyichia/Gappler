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

Twin (T1.33): the gripper is symmetric, so a grasp turned 180 degrees about its approach is the
same grasp. AnyGrasp picks either at random, and on 2026-10-14 (step 7d) the wrist turned 180
degrees to reach it. nearer_twin keeps the one whose closing axis points the gripper's way, so the
wrist never turns more than 90. The camera is on the wrist, so in its frame the gripper's closing
axis is fixed: -x of camera_color_optical_frame (rm_65_w_gripper.urdf.xacro grasp_frame_joint and
sensor_d435 origin, D435 nominal optical frame). Approach is +z, straight out of the lens.

Fit (T1.32): AnyGrasp is told the gripper opens 0.10 m (grasp_config.yaml), so it no longer checks
the object fits the real one. fits_gripper measures it from the masked points: the slice the pads
sweep (finger_height tall, through the grasp centre), from the tips back max_depth along the
approach. Width is that slice's spread along the closing axis. Depth is how far the tips go past
its nearest point. Percentiles, not min and max, so stray edge points (flying pixels) are ignored.
The camera sees only the faces turned to it, but the node keeps grasps within 40 deg of its view,
so the closing axis runs across the image, where the full width is visible [inferred].

Run this file to check the conversion: python3 anygrasp_to_grasp_frame.py
"""
import numpy as np

ANYGRASP_TO_GRASP_FRAME = np.array([[0.0, 0.0, -1.0],
                                    [0.0, 1.0, 0.0],
                                    [1.0, 0.0, 0.0]])


def to_grasp_frame(rotation_matrix):
    return rotation_matrix @ ANYGRASP_TO_GRASP_FRAME


# ponytail: fixed because the camera is on the wrist. Move the camera off the wrist and this must
# come from TF (the gripper's current y) instead.
GRIPPER_Y_IN_CAMERA = np.array([-1.0, 0.0, 0.0])


def nearer_twin(rotation_matrix, gripper_y=GRIPPER_Y_IN_CAMERA):
    """Of a grasp_frame rotation and its 180 degree twin about z, the one closer to gripper_y."""
    if rotation_matrix[:, 1] @ gripper_y < 0:
        return rotation_matrix @ np.diag([-1.0, -1.0, 1.0])
    return rotation_matrix


def fingertip_position(translation, rotation_matrix, depth):
    """Where grasp_frame goes: AnyGrasp's point moved `depth` along its approach."""
    return translation + depth * rotation_matrix[:, 0]


def fits_gripper(points, translation, rotation_matrix, depth, max_width, max_depth, finger_height,
                 percentile):
    """(fits, width, depth_in) for one AnyGrasp grasp against the real gripper, in metres."""
    tips = fingertip_position(translation, rotation_matrix, depth)
    p = (points - tips) @ rotation_matrix  # columns: along approach, closing, finger height
    slab = p[np.abs(p[:, 2]) <= finger_height / 2]
    if len(slab) == 0:
        return False, float("nan"), float("nan")
    depth_in = -np.percentile(slab[:, 0], percentile)
    between = slab[(slab[:, 0] <= 0) & (slab[:, 0] >= -max_depth), 1]
    if len(between) == 0:
        return False, float("nan"), depth_in
    width = np.percentile(between, 100 - percentile) - np.percentile(between, percentile)
    return bool(width <= max_width and depth_in <= max_depth), width, depth_in


def on_mask(points, mask, fx, fy, cx, cy):
    """For each camera-frame point, does it project onto the image mask (T1.44, OK-Robot style)."""
    h, w = mask.shape
    z = points[:, 2]
    z_safe = np.where(z > 0, z, 1.0)
    u = np.round(points[:, 0] * fx / z_safe + cx).astype(int)
    v = np.round(points[:, 1] * fy / z_safe + cy).astype(int)
    inside = (z > 0) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
    hit = np.zeros(len(points), dtype=bool)
    hit[inside] = mask[v[inside], u[inside]]
    return hit


if __name__ == "__main__":
    # T1.44: a 20 x 20 px mask in a 640 x 480 image, camera fx = fy = 600, centre (320, 240)
    m = np.zeros((480, 640), dtype=bool)
    m[230:250, 310:330] = True
    pts = np.array([[0.0, 0.0, 0.5],      # image centre: on the mask
                    [0.1, 0.0, 0.5],      # u = 440: off the mask
                    [0.0, 0.0, -0.5],     # behind the camera
                    [5.0, 0.0, 0.5]])     # outside the image
    assert on_mask(pts, m, 600, 600, 320, 240).tolist() == [True, False, False, False], "on_mask"
    print("PASS: on_mask keeps points that project onto the mask, drops off-mask, behind, outside")

    rng = np.random.default_rng(0)
    for _ in range(100):
        r_a, _ = np.linalg.qr(rng.normal(size=(3, 3)))
        r_a *= np.sign(np.linalg.det(r_a))  # a proper rotation
        r_g = to_grasp_frame(r_a)
        assert np.allclose(-r_g[:, 2], r_a[:, 0]), "approach must be grasp_frame's -z"
        assert np.allclose(r_g[:, 1], r_a[:, 1]), "closing must stay on y"
        assert np.isclose(np.linalg.det(r_g), 1.0), "must stay a rotation"
        r_t = nearer_twin(r_g)
        assert r_t[:, 1] @ GRIPPER_Y_IN_CAMERA >= 0, "twin must close the gripper's way"
        assert np.allclose(r_t[:, 2], r_g[:, 2]), "twin keeps the approach"
        assert np.isclose(np.linalg.det(r_t), 1.0), "twin must stay a rotation"
        point = rng.normal(size=3)
        tip = fingertip_position(point, r_a, 0.03)
        assert np.allclose(tip - point, -0.03 * r_g[:, 2]), "tips 0.03 m further along the approach"
    print("PASS: AnyGrasp approach -> grasp_frame -z, closing stays on y, tips depth past the point,"
          " twin closes the gripper's way")

    # T1.32: a box seen from the camera (x right, y down, z forward), front face at z 0.40, top face
    # at y -0.05. The grasp comes straight in along z and closes along x (AnyGrasp axes).
    def box(width, n=4000):
        front = np.column_stack([rng.uniform(-width / 2, width / 2, n), rng.uniform(-0.05, 0.05, n),
                                 np.full(n, 0.40)])
        top = np.column_stack([rng.uniform(-width / 2, width / 2, n), np.full(n, -0.05),
                               rng.uniform(0.40, 0.46, n)])
        return np.vstack([front, top])
    r_a = np.column_stack([[0, 0, 1], [1, 0, 0], [0, 1, 0]]).astype(float)
    LIMITS = dict(max_width=0.068, max_depth=0.045, finger_height=0.02, percentile=2)
    point = lambda tips_in: np.array([0.0, 0.0, 0.40 + tips_in - 0.02])  # AnyGrasp's point, depth 0.02
    ok, w, d = fits_gripper(box(0.06), point(0.03), r_a, 0.02, **LIMITS)
    assert ok and abs(w - 0.06) < 0.003 and abs(d - 0.03) < 0.002, ("6 cm box, tips 3 cm in", w, d)
    ok, w, _ = fits_gripper(box(0.08), point(0.03), r_a, 0.02, **LIMITS)
    assert not ok and w > 0.075, ("8 cm box is too wide for the 71 mm gripper", w)
    ok, _, d = fits_gripper(box(0.06), point(0.06), r_a, 0.02, **LIMITS)
    assert not ok and d > 0.055, ("tips 6 cm in: the base of the U pushes the box", d)
    stray = np.column_stack([rng.choice([-0.045, 0.045], 10), rng.uniform(-0.01, 0.01, 10),
                             rng.uniform(0.40, 0.42, 10)])  # flying pixels at the edges, ~1%
    ok, w, _ = fits_gripper(np.vstack([box(0.06), stray]), point(0.03), r_a, 0.02, **LIMITS)
    assert ok and w < 0.065, ("stray edge points must not widen the box", w)
    ok, _, _ = fits_gripper(box(0.06) + [0, 0.5, 0], point(0.03), r_a, 0.02, **LIMITS)
    assert not ok, "no points between the fingers: cannot judge, drop it"
    print("PASS: fits_gripper keeps a 6 cm box, drops 8 cm, drops tips 6 cm in, ignores stray points")
