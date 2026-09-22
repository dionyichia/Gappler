"""Checks that the contract extractor still sees topics read from config.
Runs in L1 (bench/run.sh). Stdlib only: python3 bench/test_contracts.py"""
import ast

from contracts import REPO, PyExtractor

SRC = '''
from sensor_msgs.msg import Image
from std_msgs.msg import String
class N:
    def __init__(self):
        self.declare_parameter("mask_topic", "/default/mask")
        self.declare_parameter("free_topic", "/default/free")
        self.create_publisher(Image, self.get_parameter("mask_topic").value, 10)
        t = self.get_parameter("free_topic").get_parameter_value().string_value
        self.create_subscription(String, t, self.cb, 10)
        self.create_subscription(String, self.get_parameter("shared").value, self.cb, 10)
        ROSPublisher("n", Image, ROS2Topics.RGB_CAMERA_RAW.value)
'''
CONFIG = {
    "mask_topic": {"/from/yaml/mask"},           # YAML wins over the default
    "rgb_camera_raw": {"/aria/rgb_camera/raw"},  # enum built from config
    "shared": {"/a", "/b"},                      # ambiguous: no default, so unresolved
}

ex = PyExtractor(REPO / "bench/fake.py", SRC, CONFIG)
ex.visit(ast.parse(SRC))
t = ex.out["topics"]
assert t["/from/yaml/mask"]["publishers"], "get_parameter should resolve through YAML"
assert "/default/mask" not in t, "the YAML value should win over the default"
assert t["/default/free"]["subscribers"], "a variable set from get_parameter should resolve"
assert t["/aria/rgb_camera/raw"]["publishers"], "ROSPublisher with an enum-from-config topic"
assert not any(k in t for k in ("/a", "/b")), "an ambiguous key must not guess"
print("test_contracts: PASS")
