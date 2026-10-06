"""Checks the stand-in's depth reading, which decides how far the arm reaches (T1.16).

ROS is stubbed, so this runs on any machine with numpy and needs no robot:
    python3 grasp/tools/test_dummy_mask_publisher.py
    uv run --no-project --with numpy python grasp/tools/test_dummy_mask_publisher.py
"""
import sys
import types
from array import array
from pathlib import Path

# Stub the ROS modules the node imports, so the depth maths can be imported on its own.
for name in ("rclpy", "rclpy.node", "sensor_msgs", "sensor_msgs.msg",
             "geometry_msgs", "geometry_msgs.msg"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["rclpy.node"].Node = object
sys.modules["sensor_msgs.msg"].Image = object
sys.modules["geometry_msgs.msg"].PointStamped = object

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dummy_mask_publisher import DEPTH_SCALE, median_depth_m  # noqa: E402


def depth_bytes(*values_mm: int) -> bytes:
    """A depth image's bytes: uint16, one reading per pixel, same as the RealSense driver."""
    return array("H", values_mm).tobytes()


# Millimetres in, metres out.
assert median_depth_m(depth_bytes(500, 500, 500)) == 0.5
assert DEPTH_SCALE == 0.001, "the driver publishes millimetres"

# Zero means "no reading", not "zero metres". Counting zeros would pull the median toward the
# camera and send the arm reaching short, so they are dropped.
assert median_depth_m(depth_bytes(0, 0, 400, 400, 400)) == 0.4

# A frame with no reading at all publishes no centroid, rather than a centroid at 0 m.
assert median_depth_m(depth_bytes(0, 0, 0)) is None
assert median_depth_m(b"") is None

# An even count still reads as the middle, so one outlier cannot drag it far.
assert median_depth_m(depth_bytes(300, 400, 500, 9000)) == 0.45

print("dummy_mask_publisher: PASS")
