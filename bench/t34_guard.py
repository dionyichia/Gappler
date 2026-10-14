"""Require the fixed, local T3.4 test domain to be empty before starting nodes."""
import os
import json
from pathlib import Path
import subprocess
import sys
import time


def check_domain(domain: str, localhost: str) -> None:
    """Refuse unapproved domains, busy graphs and uncertain discovery results."""
    if domain != "127" or localhost != "1":
        raise RuntimeError("T3.4 tests require ROS_DOMAIN_ID=127 and ROS_LOCALHOST_ONLY=1")
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--discover"],
                                capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"discovery failed: {error}") from error
    if result.returncode or result.stderr.strip():
        raise RuntimeError(f"discovery failed: {result.stderr.strip()} (exit {result.returncode})")
    try:
        graph = json.loads(result.stdout)
        nodes, topics = graph["nodes"], graph["topics"]
        if not isinstance(nodes, list) or not isinstance(topics, list) or not all(isinstance(name, str) for name in nodes + topics):
            raise ValueError("invalid graph lists")
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f"discovery failed: invalid snapshot: {error}") from error
    busy = set(nodes) | (set(topics) - {"/parameter_events", "/rosout"})
    if busy:
        raise RuntimeError(f"test domain occupied: {sorted(busy)}")


def discover() -> None:
    """Snapshot native graph APIs including hidden names, excluding only ourselves."""
    import rclpy

    rclpy.init()
    node = rclpy.create_node(f"_t34_discovery_{os.getpid()}", start_parameter_services=False)
    try:
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)
        names = [namespace.rstrip("/") + "/" + name for name, namespace in node.get_node_names_and_namespaces()]
        names.remove(node.get_fully_qualified_name())
        print(json.dumps({"nodes": names, "topics": [name for name, _ in node.get_topic_names_and_types()]}))
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    if "--discover" in sys.argv:
        discover()
        sys.exit(0)
    try:
        check_domain(os.environ.get("ROS_DOMAIN_ID", ""), os.environ.get("ROS_LOCALHOST_ONLY", ""))
    except RuntimeError as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        sys.exit(1)
    print("guards ok: domain 127 empty, localhost only")
