"""Where grasp_viz draws the gripper for one grasp candidate (T1.34).

A candidate's pose is grasp_frame (anygrasp_to_grasp_frame.py:1-13): its position is the
fingertips, the fingers close along its y axis, and the gripper approaches along -z. So the
fingers and palm lie behind the tips along +z, and the approach arrow points along -z.

Stdlib only, so the check runs anywhere: python3 gripper_drawing.py
"""


def grasp_axes(q):
    """grasp_frame's y (closing) and z (approach is -z) axes from a quaternion (x, y, z, w)."""
    x, y, z, w = q
    gy = (2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x))
    gz = (2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y))
    return gy, gz


def along(point, axis, distance):
    return tuple(p + distance * a for p, a in zip(point, axis))


def gripper_points(tips, q, open_width, finger_length, palm_length, arrow_length):
    """Centres of the two fingers and the palm, and the arrow (tail, head), all in tips' frame."""
    gy, gz = grasp_axes(q)
    finger_mid = along(tips, gz, finger_length / 2)
    return {
        "fingers": [along(finger_mid, gy, -open_width / 2), along(finger_mid, gy, open_width / 2)],
        # palm's front face at the base of the U, finger_length behind the tips
        "palm": along(tips, gz, finger_length + palm_length / 2),
        "arrow": (tips, along(tips, gz, -arrow_length)),
    }


if __name__ == "__main__":
    import math

    def close(a, b):
        return all(math.isclose(x, y, abs_tol=1e-9) for x, y in zip(a, b))

    # grasp_frame turned 90 deg about base x: its y is base +z, its z is base -y.
    # So the fingers close along base z and the approach (-z) is base +y.
    s = math.sqrt(0.5)
    p = gripper_points((1.0, 2.0, 3.0), (s, 0.0, 0.0, s), open_width=0.071, finger_length=0.05,
                       palm_length=0.04, arrow_length=0.08)
    left, right = p["fingers"]
    assert close(left, (1.0, 1.975, 3.0 - 0.0355)) and close(right, (1.0, 1.975, 3.0 + 0.0355)), \
        ("fingers must close along grasp y and sit half a finger behind the tips", p["fingers"])
    assert close(p["arrow"][0], (1.0, 2.0, 3.0)) and close(p["arrow"][1], (1.0, 2.08, 3.0)), \
        ("arrow must start at the tips and point along the approach (-z)", p["arrow"])
    assert close(along(p["palm"], (0.0, -1.0, 0.0), -0.02), (1.0, 1.95, 3.0)), \
        ("palm's front face must be 0.05 m behind the tips, away from the object", p["palm"])
    print("PASS: fingers close along grasp y, arrow along -z from the tips, palm 0.05 m behind")
