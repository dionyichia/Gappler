#!/usr/bin/env python3
"""Dry check of the slam_mapping.launch.py switches: evaluates every launch condition under four argument sets and lists which actions
WOULD start. Starts nothing, publishes nothing, touches no hardware. Needs ROS (launch, launch_ros) and the robot_slam package on
AMENT_PREFIX_PATH (the staged prefix) plus gappler_common on PYTHONPATH. Exit 0 if every expectation holds, 1 otherwise.
usage: launch_switch_check.py [PATH_TO_slam_mapping.launch.py]"""
import ast
import importlib.util
import sys
from pathlib import Path

from launch import LaunchContext
from launch.actions import DeclareLaunchArgument
from launch.utilities import normalize_to_list_of_substitutions, perform_substitutions

path = Path(sys.argv[1] if len(sys.argv) > 1 else "slam_mapping.launch.py")
tree = ast.parse(path.read_text())
ld_call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "LaunchDescription")
NAMES = [e.id for e in ld_call.args[0].elts]
spec = importlib.util.spec_from_file_location("slam_mapping_launch", path)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
description = module.generate_launch_description()
entities = list(description.entities)
assert len(entities) == len(NAMES), "returned names and entities differ in number"

KEYS = ["echo_launch", "echo_launch_fastlivo", "qos_relay_node", "custom_to_cloud_node", "odom_bridge_node", "delayed_nav2", "slam_toolbox", "pointcloud_to_laserscan"]
SCENARIOS = [
    ("wheel, defaults", {}, dict(echo_launch=1, echo_launch_fastlivo=0, qos_relay_node=1, custom_to_cloud_node=0, odom_bridge_node=0, delayed_nav2=1, xfer="0", yaml="slam_toolbox.yaml")),
    ("fastlivo, defaults", {"odom_source": "fastlivo"}, dict(echo_launch=0, echo_launch_fastlivo=1, qos_relay_node=0, custom_to_cloud_node=1, odom_bridge_node=1, delayed_nav2=1, xfer="1", yaml="slam_toolbox_fastlivo.yaml")),
    ("fastlivo, nav2:=false base_driver:=false (the runbook)", {"odom_source": "fastlivo", "nav2": "false", "base_driver": "false"},
     dict(echo_launch=0, echo_launch_fastlivo=0, qos_relay_node=0, custom_to_cloud_node=1, odom_bridge_node=1, delayed_nav2=0, xfer="1", yaml="slam_toolbox_fastlivo.yaml")),
    ("wheel, base_driver:=false", {"base_driver": "false"}, dict(echo_launch=0, echo_launch_fastlivo=0, qos_relay_node=1, custom_to_cloud_node=0, odom_bridge_node=0, delayed_nav2=1, xfer="0", yaml="slam_toolbox.yaml")),
]
bad = 0
for title, given, want in SCENARIOS:
    ctx = LaunchContext()
    for ent in entities:
        if isinstance(ent, DeclareLaunchArgument):
            default = perform_substitutions(ctx, ent.default_value) if ent.default_value else ""
            ctx.launch_configurations[ent.name] = given.get(ent.name, default)
    active = {}
    for name, ent in zip(NAMES, entities):
        cond = ent.condition
        active[name] = True if cond is None else bool(cond.evaluate(ctx))
    print("== %s" % title)
    print("   would start: %s" % ", ".join(sorted(n for n, a in active.items() if a and not n.endswith("_arg"))))
    print("   would NOT start (conditional): %s" % ", ".join(sorted(n for n in KEYS if not active[n]) or ["none"]))
    for key in ("echo_launch", "echo_launch_fastlivo", "qos_relay_node", "custom_to_cloud_node", "odom_bridge_node", "delayed_nav2"):
        if int(active[key]) != want[key]:
            bad += 1; print("   MISMATCH %s: started %s, expected %s" % (key, active[key], bool(want[key])))
    livox = entities[NAMES.index("livox_launch")]
    text = lambda x: x if isinstance(x, str) else perform_substitutions(ctx, normalize_to_list_of_substitutions(x))
    xfer = [text(v) for k, v in livox.launch_arguments if text(k) == "xfer_format"]
    print("   driver xfer_format: %s (expected %s)" % (xfer, want["xfer"]))
    if xfer != [want["xfer"]]:
        bad += 1; print("   MISMATCH xfer_format")
    node = entities[NAMES.index("slam_toolbox")]
    params = getattr(node, "_Node__parameters", None)
    try:
        chosen = text(getattr(params[0], "param_file", params[0])) if params else "?"  # launch_ros wraps the path in a ParameterFile
    except Exception as err:
        chosen = "unresolved: %s" % err
    print("   SLAM Toolbox parameter file: %s (expected ...%s)" % (Path(str(chosen)).name, want["yaml"]))
    if Path(str(chosen)).name != want["yaml"]:
        bad += 1; print("   MISMATCH parameter file")
print("\nALL SWITCH EXPECTATIONS HOLD" if not bad else "\n%d MISMATCH(ES)" % bad)
sys.exit(1 if bad else 0)
