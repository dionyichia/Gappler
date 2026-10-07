"""T3.4 command ownership: one keyboard publisher into one smoother, no second driver."""
import ast
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
TELEOP = REPO / "nav/simple_teleop/simple_teleop/teleop_node.py"
SMOOTHER_CASE = REPO / "bench/nodes/test_velocity_smoother.py"
TELEOP_CASE = REPO / "bench/nodes/test_teleop.py"

SPEED = 0.05
TURN = 0.15
KEY_TIMEOUT = 0.25
NAMESPACE = "/t34_probe"
RAW_TOPIC = "cmd_vel"
REMAPPED_INPUT = "keyboard_input"
SMOOTHED_OUTPUT = "output"
SMOOTHER_PARAMS = {
    "smoothing_frequency": 20.0,
    "max_velocity": [0.05, 0.0, 0.15],
    "min_velocity": [-0.05, 0.0, -0.15],
    "max_accel": [0.1, 0.0, 0.3],
    "max_decel": [-0.2, 0.0, -0.6],
    "velocity_timeout": 0.25,
}


def _declare_defaults(tree):
    """Map declare_parameter(name, default) defaults in the owned teleop node."""
    defaults = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "declare_parameter"):
            continue
        if len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[1], ast.Constant):
            defaults[node.args[0].value] = node.args[1].value
    return defaults


def _assigned_string_list(tree, name):
    """String-only list literal assigned to a name, in source order."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name \
                and isinstance(node.value, ast.List) \
                and all(isinstance(item, ast.Constant) and isinstance(item.value, str)
                        for item in node.value.elts):
            return [item.value for item in node.value.elts]
    raise AssertionError(f"{name} string list not found")


def _cli_values(tokens, flag):
    """Values following each occurrence of a CLI flag in an ordered token stream."""
    return [tokens[index + 1] for index, token in enumerate(tokens[:-1]) if token == flag]


def _remap_namespace(tokens):
    """Split -r tokens into (__ns, {from_: to}) remaps."""
    namespace, remaps = None, {}
    for token in _cli_values(tokens, "-r"):
        name, sep, target = token.partition(":=")
        assert sep, f"remap without :=: {token}"
        if name == "__ns":
            namespace = target
        else:
            remaps[name] = target
    return namespace, remaps


def _param_values(tokens):
    """Map -p name:=value tokens to their raw value strings."""
    params = {}
    for token in _cli_values(tokens, "-p"):
        name, sep, raw = token.partition(":=")
        assert sep, f"parameter without :=: {token}"
        assert name not in params, f"duplicate tested parameter: {name}"
        params[name] = raw
    return params


def _resolve(namespace, remaps, name):
    """Apply remaps then the namespace, the way ROS resolves a relative topic."""
    name = remaps.get(name, name)
    if not name.startswith("/"):
        name = namespace.rstrip("/") + "/" + name
    return name


def _popen_remaps(tree):
    """(namespace, remaps) for each subprocess.Popen launch in a test source."""
    groups = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "Popen":
            strings = [node for node in ast.walk(node)
                       if isinstance(node, ast.Constant) and isinstance(node.value, str)]
            tokens = [node.value for node in sorted(strings, key=lambda node: (node.lineno, node.col_offset))]
            groups.append(_remap_namespace(tokens))
    return groups


def _publish_topics(tree):
    """Topic argument of every create_publisher call, in source order."""
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == "create_publisher" and len(node.args) >= 2
             and isinstance(node.args[1], ast.Constant)]
    return [node.args[1].value for node in sorted(calls, key=lambda node: (node.lineno, node.col_offset))]


def _gated_single_publisher_topics(tree):
    """Topics guarded by a count_publishers(...) == 1 assertion."""
    gated = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.Eq)):
            continue
        sides = [node.left, *node.comparators]
        call = next((side for side in sides if isinstance(side, ast.Call)
                     and isinstance(side.func, ast.Attribute)
                     and side.func.attr == "count_publishers" and len(side.args) >= 1
                     and isinstance(side.args[0], ast.Constant)), None)
        one = any(isinstance(side, ast.Constant) and side.value == 1 for side in sides)
        if call is not None and one:
            gated.add(call.args[0].value)
    return gated


class CommandOwnershipTests(unittest.TestCase):
    def test_teleop_defaults_match_tested_values(self):
        defaults = _declare_defaults(ast.parse(TELEOP.read_text()))
        self.assertEqual(defaults.get("speed"), SPEED)
        self.assertEqual(defaults.get("turn"), TURN)
        self.assertEqual(defaults.get("key_timeout"), KEY_TIMEOUT)

    def test_smoother_arguments_match_tested_values(self):
        argv = _assigned_string_list(ast.parse(SMOOTHER_CASE.read_text()), "arguments")
        self.assertEqual(argv[:4], ["ros2", "run", "nav2_velocity_smoother", "velocity_smoother"])
        params = _param_values(argv)
        for name, expected in SMOOTHER_PARAMS.items():
            self.assertIn(name, params, f"smoother argument moved: {name}")
            self.assertEqual(ast.literal_eval(params[name]), expected, f"smoother argument moved: {name}")
        self.assertEqual(ast.literal_eval(params["max_velocity"]), [SPEED, 0.0, TURN])
        self.assertEqual(ast.literal_eval(params["min_velocity"]), [-SPEED, 0.0, -TURN])
        self.assertEqual(float(params["velocity_timeout"]), KEY_TIMEOUT)

    def test_topic_chain_agrees(self):
        argv = _assigned_string_list(ast.parse(SMOOTHER_CASE.read_text()), "arguments")
        smoother_ns, smoother_remaps = _remap_namespace(argv)
        self.assertEqual(smoother_ns, NAMESPACE)
        self.assertEqual(smoother_remaps, {RAW_TOPIC: REMAPPED_INPUT, "cmd_vel_smoothed": SMOOTHED_OUTPUT})
        groups = _popen_remaps(ast.parse(TELEOP_CASE.read_text()))
        self.assertEqual(len(groups), 2, "both teleop launches must pin the same remap")
        for namespace, remaps in groups:
            self.assertEqual(namespace, NAMESPACE)
            self.assertEqual(remaps, {RAW_TOPIC: REMAPPED_INPUT})
        teleop_output = _resolve(NAMESPACE, groups[0][1], RAW_TOPIC)
        smoother_input = _resolve(smoother_ns, smoother_remaps, RAW_TOPIC)
        smoother_output = _resolve(smoother_ns, smoother_remaps, "cmd_vel_smoothed")
        self.assertEqual(teleop_output, f"{NAMESPACE}/{REMAPPED_INPUT}")
        self.assertEqual(smoother_input, teleop_output, "smoother must listen where teleop publishes")
        self.assertEqual(smoother_output, f"{NAMESPACE}/{SMOOTHED_OUTPUT}")

    def test_no_second_command_publisher(self):
        teleop_pubs = _publish_topics(ast.parse(TELEOP.read_text()))
        self.assertEqual(teleop_pubs, [RAW_TOPIC])
        smoother_pubs = _publish_topics(ast.parse(SMOOTHER_CASE.read_text()))
        self.assertEqual(smoother_pubs, [f"{NAMESPACE}/{REMAPPED_INPUT}"])
        teleop_case_pubs = _publish_topics(ast.parse(TELEOP_CASE.read_text()))
        self.assertEqual(teleop_case_pubs, [])
        # The owned node plus the single test driver are the only publishers on
        # the command chain; nothing constructs the smoother's output topic.
        argv = _assigned_string_list(ast.parse(SMOOTHER_CASE.read_text()), "arguments")
        smoother_ns, smoother_remaps = _remap_namespace(argv)
        smoothed = _resolve(smoother_ns, smoother_remaps, "cmd_vel_smoothed")
        for topic in teleop_pubs + smoother_pubs + teleop_case_pubs:
            resolved = topic if topic.startswith("/") else _resolve(NAMESPACE, {}, topic)
            self.assertNotEqual(resolved, smoothed, "second smoother-output publisher constructed")

    def test_single_publisher_gated_at_runtime(self):
        self.assertIn(f"{NAMESPACE}/{REMAPPED_INPUT}",
                      _gated_single_publisher_topics(ast.parse(TELEOP_CASE.read_text())))
        self.assertIn(f"{NAMESPACE}/{SMOOTHED_OUTPUT}",
                      _gated_single_publisher_topics(ast.parse(SMOOTHER_CASE.read_text())))


if __name__ == "__main__":
    unittest.main()
