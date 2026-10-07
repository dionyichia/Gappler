"""Network-preserving LiDAR includes; construct ROS actions, never execute them."""
import ast
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
LAUNCHES = (
    "nav/robot_slam/launch/slam_mapping.launch.py",
    "nav/robot_slam/launch/slam_localization.launch.py",
    "nav/robot_navigation/launch/navigation.launch.py",
)


class NavigationLaunchTests(unittest.TestCase):
    def test_launches_do_not_mutate_network(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                tree = ast.parse((REPO / relative).read_text())
                strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
                self.assertFalse(any("ip addr" in value or "sudo" in value or "ifconfig" in value for value in strings))
                self.assertFalse(any(isinstance(node, ast.Name) and node.id == "network_setup" for node in ast.walk(tree)))

    def test_all_entry_points_use_owned_lidar_launch(self):
        for relative in LAUNCHES:
            with self.subTest(launch=relative):
                tree = ast.parse((REPO / relative).read_text())
                include = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                               any(isinstance(target, ast.Name) and target.id == "livox_launch" for target in node.targets))
                strings = [node.value for node in ast.walk(include) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
                self.assertIn("robot_slam", strings)
                self.assertIn("launch", strings)
                self.assertEqual(strings.count("lidar_only.launch.py"), 1)
                self.assertNotIn("msg_MID360_launch.py", strings)
                description = next(node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                                   isinstance(node.func, ast.Name) and node.func.id == "LaunchDescription")
                self.assertTrue(any(isinstance(node, ast.Name) and node.id == "livox_launch"
                                    for node in description.args[0].elts), "LiDAR include constructed but not returned")


def runtime_check() -> None:
    """Use source-backed package shares without changing the installed overlay."""
    try:
        from launch import LaunchContext
        from launch.actions import IncludeLaunchDescription
        from launch.launch_description_sources import PythonLaunchDescriptionSource
        from launch.utilities import normalize_to_list_of_substitutions, perform_substitutions
        from launch_ros.actions import Node
    except ImportError as error:
        print(f"SKIP: ROS launch construction unavailable: {error}")
        sys.exit(3)
    (REPO / "log").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=REPO / "log") as folder:
        prefix = Path(folder)
        index = prefix / "share/ament_index/resource_index/packages"
        index.mkdir(parents=True)
        for package in ("robot_slam", "robot_navigation"):
            (index / package).touch()
            (prefix / "share" / package).symlink_to(REPO / "nav" / package, target_is_directory=True)
        environment = {"AMENT_PREFIX_PATH": str(prefix) + os.pathsep + os.environ.get("AMENT_PREFIX_PATH", ""),
                       "PYTHONPATH": str(REPO / "shared") + os.pathsep + os.environ.get("PYTHONPATH", "")}
        sys.path.insert(0, str(REPO / "shared"))
        # Construction fixtures only: nonempty bytes are NOT valid serialized maps.
        maps = prefix / "maps with spaces"
        maps.mkdir()
        for suffix in (".posegraph", ".data"):
            (maps / ("completed_map" + suffix)).write_bytes(b"construction fixture only")
        environment["GAPPLER_MAP_DIR"] = str(maps)
        try:
            with patch.dict(os.environ, environment):
                context = LaunchContext()
                with patch.dict(os.environ, {"GAPPLER_MAP_DIR": str(prefix / "missing maps")}), \
                        patch("launch_ros.actions.Node") as hardware_node, \
                        patch("launch.actions.IncludeLaunchDescription") as hardware_include:
                    module = runpy.run_path(str(REPO / LAUNCHES[1]))
                    try:
                        module["generate_launch_description"]()
                    except ValueError as error:
                        assert "serialized map" in str(error)
                    else:
                        raise AssertionError("missing serialized map did not refuse startup")
                    hardware_node.assert_not_called()
                    hardware_include.assert_not_called()
                print("PASS missing-map refusal before node/include construction; no actions executed")
                for relative in LAUNCHES:
                    locations = []
                    sources = {}
                    includes = []

                    def source(location):
                        resolved = perform_substitutions(context, normalize_to_list_of_substitutions(location))
                        locations.append(resolved)
                        if not Path(resolved).is_file():
                            raise RuntimeError(f"included launch missing: {resolved}")
                        description_source = PythonLaunchDescriptionSource(location)
                        sources[description_source] = resolved
                        return description_source

                    def include(description_source, *args, **kwargs):
                        action = IncludeLaunchDescription(description_source, *args, **kwargs)
                        includes.append((action, sources[description_source]))
                        return action

                    with patch("launch.launch_description_sources.PythonLaunchDescriptionSource", side_effect=source), \
                            patch("launch.actions.IncludeLaunchDescription", side_effect=include):
                        module = runpy.run_path(str(REPO / relative))
                        description = module["generate_launch_description"]()
                    assert description.entities, "empty launch description"
                    expected = str(prefix / "share/robot_slam/launch/lidar_only.launch.py")
                    assert locations.count(expected) == 1, f"owned LiDAR include missing: {locations}"
                    lidar_actions = [action for action, location in includes if location == expected]
                    assert len(lidar_actions) == 1 and lidar_actions[0] in description.entities, "LiDAR include not returned"
                    assert all("msg_MID360_launch.py" not in location for location in locations)
                    print(f"PASS construction and resolved includes: {relative}")
                with patch("launch_ros.actions.Node", wraps=Node) as constructor:
                    module = runpy.run_path(str(REPO / "nav/robot_slam/launch/lidar_only.launch.py"))
                    description = module["generate_launch_description"]()
                    assert len(description.entities) == 1
                    parameters = constructor.call_args.kwargs["parameters"][0]
                    assert parameters["xfer_format"] == 0 and parameters["publish_freq"] == 10.0
                    assert parameters["frame_id"] == "livox_frame"
                    assert Path(parameters["user_config_path"]).is_file()
                print("PASS owned LiDAR parameters/config; source-backed shares, no actions executed")
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    if "--runtime" in sys.argv:
        runtime_check()
    else:
        unittest.main()
