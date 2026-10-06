"""Checks that the contract extractor still sees topics read from config.
Runs in L1 (bench/run.sh). Stdlib only: python3 bench/test_contracts.py"""
import ast
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from contracts import REPO, PyExtractor, extract_cpp, extract_launch, new_bucket

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
        self.create_publisher(Image, TOPICS["cfg_topic"], 10)
        self.create_subscription(Image, TOPIC_CFG_CONST, self.cb, 10)
TOPICS = config("grasp")["topics"]
TOPIC_CFG_CONST = TOPICS["cfg_const"]
'''
CONFIG = {
    "mask_topic": {"/from/yaml/mask"},           # YAML wins over the default
    "rgb_camera_raw": {"/aria/rgb_camera/raw"},  # enum built from config
    "shared": {"/a", "/b"},                      # ambiguous: no default, so unresolved
    "cfg_topic": {"/from/config/subscript"},     # TOPICS["cfg_topic"], gappler_common.config
    "cfg_const": {"/from/config/const"},         # a module constant set from a subscript
}

ex = PyExtractor(REPO / "bench/fake.py", SRC, CONFIG)
ex.visit(ast.parse(SRC))
t = ex.out["topics"]
assert t["/from/yaml/mask"]["publishers"], "get_parameter should resolve through YAML"
assert "/default/mask" not in t, "the YAML value should win over the default"
assert t["/default/free"]["subscribers"], "a variable set from get_parameter should resolve"
assert t["/aria/rgb_camera/raw"]["publishers"], "ROSPublisher with an enum-from-config topic"
assert not any(k in t for k in ("/a", "/b")), "an ambiguous key must not guess"
assert t["/from/config/subscript"]["publishers"], "TOPICS[\"key\"] should resolve through config"
assert t["/from/config/const"]["subscribers"], "a constant set from TOPICS[\"key\"] should resolve"
cpp_out = new_bucket()
extract_cpp(REPO / "bench/fake.cpp", '''
pub_ = this->create_publisher<std_msgs::msg::String>(topic("cfg_topic"), 10);
sub_ = this->create_subscription<std_msgs::msg::String>(
    topic("shared"), 10, cb);
''', cpp_out, CONFIG)
assert cpp_out["topics"]["/from/config/subscript"]["publishers"], "C++ topic(\"key\") should resolve"
assert not any(k in cpp_out["topics"] for k in ("/a", "/b")), "C++: an ambiguous key must not guess"
mount_out = new_bucket()
extract_launch(REPO / "bench/fake.launch.py", '''
from gappler_common import static_transform_args
Node(package="tf2_ros", executable="static_transform_publisher",
     arguments=static_transform_args("arm_mount"))
''', mount_out)
assert len(mount_out["static_tf"]) == 1, "shared mount helper must remain visible to contracts"
assert mount_out["static_tf"][0]["parent"] == "robot_base_link"
assert mount_out["static_tf"][0]["child"] == "base_link"
assert mount_out["static_tf"][0]["xyz_rpy"] == ['0.18', '0.0', '0.48', '3.14159', '0.0', '0.0']
unknown = new_bucket()
extract_launch(REPO / "bench/fake.launch.py", '''
Node(package="tf2_ros", executable="static_transform_publisher",
     arguments=static_transform_args("missing_mount"))
''', unknown)
assert unknown['parse_errors'], 'unknown mount must not silently disappear'
for name in ('arm_mount', 'lidar_mount'):
    for raw in ('{broken}', '{}', json.dumps({'parent': 'a', 'child': 'a', 'xyz_m': [0, 0, 0], 'rpy_rad': [0, 0, 0]}),
                json.dumps({'parent': 'a', 'child': 'b', 'xyz_m': [0, 0], 'rpy_rad': [0, 0, 0]}),
                json.dumps({'parent': 'a', 'child': 'b', 'xyz_m': [float('inf'), 0, 0], 'rpy_rad': [0, 0, 0]})):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'shared').mkdir()
            (root / 'shared/global_config.yaml').write_text('geometry:\n  ' + name + ': ' + raw + '\n')
            invalid = new_bucket()
            with patch('contracts.REPO', root):
                extract_launch(root / 'fake.launch.py',
                               'Node(executable="static_transform_publisher", arguments=static_transform_args("' + name + '"))', invalid)
            assert invalid['parse_errors'] and not invalid['static_tf'], (name, raw)
print("test_contracts: PASS")
