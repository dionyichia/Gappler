"""Guard the Foxglove live view: layout topics exist in the contract, and the bridge stays read-only and off the LAN."""
import ipaddress
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAYOUT = REPO / "shared/foxglove/gappler_layout.json"
BRIDGE = REPO / "shared/foxglove/foxglove_bridge_config.yaml"
QUICKSTART = REPO / "quickstart_terminals.sh"
CONTRACT = REPO / "bench/golden/contracts.json"

# From ROS, Nav2 or vendor packages, so the contract (our own code only) does not track them.
STANDARD_TOPICS = {"/tf", "/tf_static", "/robot_description", "/base/robot_description", "/map",
                   "/rosout", "/global_costmap/costmap", "/plan"}
# image_transport adds this beside an Image topic when the compressed plugin is installed.
COMPRESSED = "/compressed"


def layout_topics(node) -> set:
    """Every string (key or value) starting with "/" is a topic ref; the topic is the part before the first ".")."""
    found = set()
    if isinstance(node, dict):
        for k, v in node.items():
            found |= layout_topics(k) | layout_topics(v)
    elif isinstance(node, list):
        for v in node:
            found |= layout_topics(v)
    elif isinstance(node, str) and node.startswith("/"):
        found.add(node.split(".")[0])
    return found


def layout_leaves(tree, config) -> set:
    """Panel ids placed in a layout tree, following Tab panels into each tab's own tree."""
    if isinstance(tree, str):
        found = {tree}
        for tab in config.get(tree, {}).get("tabs", []) if tree.startswith("Tab!") else []:
            if tab.get("layout"):
                found |= layout_leaves(tab["layout"], config)
        return found
    return layout_leaves(tree["first"], config) | layout_leaves(tree["second"], config)


def unknown_topics(topics, known) -> set:
    """Topics neither known nor the compressed twin of a known topic."""
    return {t for t in topics
            if t not in known and not (t.endswith(COMPRESSED) and t[:-len(COMPRESSED)] in known)}


class FoxgloveViewTests(unittest.TestCase):
    def test_layout_parses_with_required_keys(self) -> None:
        layout = json.loads(LAYOUT.read_text())
        self.assertIn("configById", layout)
        self.assertIn("layout", layout)

    def test_every_layout_panel_has_a_config(self) -> None:
        layout = json.loads(LAYOUT.read_text())
        missing = layout_leaves(layout["layout"], layout["configById"]) - set(layout["configById"])
        self.assertFalse(missing, f"panels without config: {missing}")

    def test_every_config_is_placed(self) -> None:
        layout = json.loads(LAYOUT.read_text())
        orphans = set(layout["configById"]) - layout_leaves(layout["layout"], layout["configById"])
        self.assertFalse(orphans, f"configs no tab shows: {orphans}")

    def test_layout_has_the_five_tabs(self) -> None:
        layout = json.loads(LAYOUT.read_text())
        tabs = layout["configById"][layout["layout"]]["tabs"]
        self.assertEqual([t["title"] for t in tabs], ["Main", "Grasp", "Glasses", "Nav", "Topics"])

    def test_layout_topics_are_in_the_contract(self) -> None:
        layout = json.loads(LAYOUT.read_text())
        known = set(json.loads(CONTRACT.read_text())["topics"]) | STANDARD_TOPICS
        unknown = unknown_topics(layout_topics(layout["configById"]), known)
        self.assertFalse(unknown, f"topics not in contract or STANDARD_TOPICS: {sorted(unknown)}")

    def test_collector_catches_a_bad_name(self) -> None:
        bad = {"paths": [{"value": "/no_such_topic.data"}]}
        self.assertEqual(layout_topics(bad), {"/no_such_topic"})
        known = {"/camera/image_raw"}
        self.assertEqual(unknown_topics({"/camera/image_raw/compressed", "/no_such/compressed"}, known),
                         {"/no_such/compressed"})

    def test_bridge_is_read_only_and_local(self) -> None:
        text = BRIDGE.read_text()
        caps = re.search(r"^\s*capabilities:\s*\[(.*?)\]", text, re.M)
        self.assertIsNotNone(caps, "no capabilities: line")
        self.assertEqual({c.strip() for c in caps.group(1).split(",")}, {"connectionGraph", "assets"})
        # Comments name the banned words on purpose, and ros__parameters is the ROS file header.
        code = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#")).replace("ros__parameters", "")
        for bad in ("clientPublish", "services", "parameters", "parametersSubscribe"):
            self.assertNotIn(bad, code, bad)
        addr = re.search(r"^\s*address:\s*\"?([^\"\s]+)\"?", text, re.M)
        self.assertIsNotNone(addr, "no address: line")
        # Tailscale addresses (100.64.0.0/10) or loopback only: never 0.0.0.0, never a LAN address.
        ip = ipaddress.ip_address(addr.group(1))
        self.assertTrue(ip.is_loopback or ip in ipaddress.ip_network("100.64.0.0/10"), str(ip))

    def test_quickstart_starts_bridge_only_through_the_config(self) -> None:
        text = QUICKSTART.read_text()
        self.assertIn("foxglove_bridge_config.yaml", text)
        self.assertEqual(text.count("--params-file"), 1)


if __name__ == "__main__":
    unittest.main()
