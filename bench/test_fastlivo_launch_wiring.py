"""odom_source:=wheel|fastlivo wiring in the two SLAM launches. Static (AST), constructs and runs nothing.

wheel (the default) must stay exactly what it was. fastlivo: the wheel driver stops publishing its TF (unscoped SetParameter,
because the vendor launch starts the driver in a 15 s TimerAction and a scoped group closes before that fires, measured with stub
nodes on the box), the driver runs CustomMsg, the converter replaces qos_relay, and the bridge publishes odom -> robot_base_link.
"""
import ast
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
LAUNCHES = ("nav/robot_slam/launch/slam_mapping.launch.py", "nav/robot_slam/launch/slam_localization.launch.py")
LIDAR = REPO / "nav/robot_slam/launch/lidar_only.launch.py"


def parse(relative):
    return ast.parse((REPO / relative).read_text())


def calls(tree, name):
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name]


def kw(call, key):
    return next((k.value for k in call.keywords if k.arg == key), None)


def const(node):
    return node.value if isinstance(node, ast.Constant) else None


def assigned(tree, name):
    return next(n.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets))


def returned_names(tree):
    ld = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "LaunchDescription")
    return [e.id for e in ld.args[0].elts if isinstance(e, ast.Name)]


class LaunchWiringTests(unittest.TestCase):
    def test_odom_source_argument_defaults_to_wheel_and_only_allows_two_values(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                tree = parse(relative)
                arg = next(c for c in calls(tree, "DeclareLaunchArgument") if const(c.args[0]) == "odom_source")
                self.assertEqual(const(kw(arg, "default_value")), "wheel")
                self.assertEqual([const(e) for e in kw(arg, "choices").elts], ["wheel", "fastlivo"])
                self.assertIn("odom_source_arg", returned_names(tree))

    def test_pub_tf_is_set_false_once_inside_an_unscoped_group_around_the_vendor_include(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                tree = parse(relative)
                setters = [c for c in calls(tree, "SetParameter")]
                self.assertEqual(len(setters), 1, "wheel mode must never set pub_tf")
                self.assertEqual((const(kw(setters[0], "name")), const(kw(setters[0], "value"))), ("pub_tf", False))
                group = next(g for g in calls(tree, "GroupAction") if setters[0] in list(ast.walk(g)))
                self.assertIs(const(kw(group, "scoped")), False, "a scoped group closes before the vendor 15 s timer fires")
                includes = [i for i in calls(group, "IncludeLaunchDescription")]
                self.assertEqual(len(includes), 1)
                strings = [n.value for n in ast.walk(includes[0]) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                self.assertIn("bringup_basic_ctrl.launch.py", strings)
                self.assertEqual(calls(group, "IfCondition") and len(calls(group, "IfCondition")), 1, "fastlivo only")
                actions = group.keywords[[k.arg for k in group.keywords].index("actions")].value.elts
                self.assertIsInstance(actions[0], ast.Call)
                self.assertEqual(actions[0].func.id, "SetParameter", "the parameter must be set before the include")

    def test_vendor_launch_is_included_in_both_modes_not_copied(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                tree = parse(relative)
                for include in calls(tree, "IncludeLaunchDescription"):
                    strings = [n.value for n in ast.walk(include) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
                    if "bringup_basic_ctrl.launch.py" in strings:
                        self.assertIn("xpkg_demo", strings, "must come from the vendor package, not a copy")
                self.assertEqual(sum("bringup_basic_ctrl.launch.py" in (n.value for n in ast.walk(i) if isinstance(n, ast.Constant) and isinstance(n.value, str))
                                     for i in calls(tree, "IncludeLaunchDescription")), 2, "one wheel include, one fastlivo include")

    def test_wheel_only_and_fastlivo_only_actions_carry_conditions(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                tree = parse(relative)
                self.assertIsNotNone(kw(assigned(tree, "echo_launch"), "condition"), "wheel vendor include is wheel only")
                self.assertEqual(kw(assigned(tree, "qos_relay_node"), "condition").func.id, "UnlessCondition")
                for name in ("custom_to_cloud_node", "odom_bridge_node"):
                    self.assertEqual(kw(assigned(tree, name), "condition").func.id, "IfCondition", name)
                for name in ("echo_launch", "echo_launch_fastlivo", "qos_relay_node", "custom_to_cloud_node", "odom_bridge_node", "odom_source_arg"):
                    self.assertIn(name, returned_names(tree), name)

    def test_bridge_reads_its_parameter_file_from_the_package_share(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                node = assigned(parse(relative), "odom_bridge_node")
                self.assertEqual(const(kw(node, "executable")), "fastlivo_odom_bridge.py")
                strings = [n.value for n in ast.walk(kw(node, "parameters")) if isinstance(n, ast.Constant)]
                self.assertIn("fastlivo_bridge.yaml", strings)

    def test_converter_replaces_qos_relay_on_the_same_topics(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                node = assigned(parse(relative), "custom_to_cloud_node")
                self.assertEqual(const(kw(node, "executable")), "livox_custom_to_cloud.py")
        script = (REPO / "nav/robot_slam/scripts/livox_custom_to_cloud.py").read_text()
        self.assertIn('declare_parameter("input_topic", "/livox/lidar")', script)
        self.assertIn('declare_parameter("output_topic", "/cloud_relay")', script)  # what pointcloud_to_laserscan reads

    def test_lidar_include_passes_the_driver_format_and_defaults_to_the_old_one(self):
        lidar = ast.parse(LIDAR.read_text())
        arg = next(c for c in calls(lidar, "DeclareLaunchArgument") if const(c.args[0]) == "xfer_format")
        self.assertEqual(const(kw(arg, "default_value")), "0", "PointCloud2, as before")
        self.assertNotIn('"xfer_format": 0', LIDAR.read_text(), "the format must come from the launch argument")
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                include = assigned(parse(relative), "livox_launch")
                self.assertIn("xfer_format", [n.value for n in ast.walk(include) if isinstance(n, ast.Constant)])


if __name__ == "__main__":
    unittest.main()
