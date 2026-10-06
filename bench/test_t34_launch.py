"""Inspect LiDAR-only launch wiring; optional ROS construction executes no nodes."""
import ast
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
import static

REPO = Path(__file__).resolve().parents[1]
LAUNCH = REPO / "nav/robot_slam/launch/lidar_only.launch.py"


class LidarLaunchTests(unittest.TestCase):
    def test_cmake_project_name_component_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "CMakeLists.txt").write_text(
                'rclcpp_components_register_node(${PROJECT_NAME} PLUGIN "demo::Driver" EXECUTABLE ${PROJECT_NAME}_node)'
            )
            launch = root / "probe.launch.py"
            with patch("static.REPO", root), patch("static.repo_packages", return_value={"demo": root}), \
                    patch("static.walk", return_value=[launch]):
                launch.write_text('Node(package="demo", executable="demo_node")')
                self.assertTrue(static.check_launch_executables().ok)
                launch.write_text('Node(package="demo", executable="demo_typo")')
                self.assertFalse(static.check_launch_executables().ok)

    def test_only_lidar_node_no_network_or_autonomy(self):
        tree = ast.parse(LAUNCH.read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        nodes = [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "Node"]
        self.assertEqual(len(nodes), 1)
        args = {kw.arg: kw.value for kw in nodes[0].keywords}
        self.assertEqual(ast.literal_eval(args["package"]), "livox_ros_driver2")
        self.assertEqual(ast.literal_eval(args["executable"]), "livox_ros_driver2_node")
        parameters = args["parameters"].elts[0]
        values = {ast.literal_eval(key): value for key, value in zip(parameters.keys, parameters.values)}
        self.assertEqual(ast.literal_eval(values["xfer_format"]), 0)
        self.assertEqual(ast.literal_eval(values["publish_freq"]), 10.0)
        self.assertEqual(ast.literal_eval(values["frame_id"]), "livox_frame")
        self.assertNotIn("ExecuteProcess", LAUNCH.read_text())
        self.assertNotIn("IncludeLaunchDescription", LAUNCH.read_text())
        self.assertNotIn("sudo", LAUNCH.read_text())


def runtime_check() -> None:
    """Build the real ROS launch description, but never visit/execute actions."""
    try:
        from launch_ros.actions import Node
    except ImportError as error:
        print(f"SKIP: launch construction requires ROS: {error}")
        sys.exit(3)
    with patch("launch_ros.actions.Node", wraps=Node) as constructor:
        module = runpy.run_path(str(LAUNCH))
        description = module["generate_launch_description"]()
        assert len(description.entities) == 1
        kwargs = constructor.call_args.kwargs
        assert kwargs["package"] == "livox_ros_driver2"
        assert kwargs["executable"] == "livox_ros_driver2_node"
        parameters = kwargs["parameters"][0]
        assert parameters["xfer_format"] == 0
        assert Path(parameters["user_config_path"]).is_file(), "installed MID360_config.json missing"
    print("PASS: real LiDAR-only launch construction and config path; no actions executed")


if __name__ == "__main__":
    if "--runtime" in sys.argv:
        runtime_check()
    else:
        unittest.main()
