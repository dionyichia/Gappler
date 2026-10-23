#!/usr/bin/env python3
"""Count /tf messages per edge for a few seconds and say whether the odom edge has exactly one publisher, by rate. Read-only.

The base driver creates its /tf publisher even with pub_tf off, so a publisher list would false-alarm; the rate cannot. With the mapper and
bridge running, odom -> robot_base_link must arrive at about 10 Hz (the bridge's one final pose per scan; a second publisher would add its
own messages). With the mapper stopped it must be silent (--expect-silent). The mapper's own tree (camera_init -> aft_mapped) must not be on
/tf at all: the container remaps it to /fastlivo/tf.
usage: tf_edge_check.py [--seconds 10] [--expect-silent]     (set ROS_DOMAIN_ID and ROS_LOCALHOST_ONLY first)
Exit 0 pass, 1 fail."""
import argparse
import sys
import time

EDGE = ("odom", "robot_base_link")
LOW_HZ, HIGH_HZ = 8.0, 13.0  # the bridge measures 10.3 to 10.6 Hz on the recorded bag; a second publisher pushes it well above 13


def judge(edges, seconds, expect_silent=False):
    """edges: (parent, child) -> message count. Returns (ok, report lines)."""
    lines, ok = [], True
    n = edges.get(EDGE, 0)
    hz = n / seconds
    lines.append("odom -> robot_base_link: %d messages in %.0f s = %.1f Hz" % (n, seconds, hz))
    if expect_silent:
        if n:
            ok = False
            lines.append("FAIL: the odom edge is not silent although the mapper is stopped: someone else publishes it (a driver with pub_tf on?)")
        else:
            lines.append("PASS: the odom edge is silent")
    elif n == 0:
        ok = False
        lines.append("FAIL: nothing on the odom edge: the bridge is not publishing (no mapper pose yet, or it refused one; read its log)")
    elif hz > HIGH_HZ:
        ok = False
        lines.append("FAIL: rate too high (%.1f Hz > %.0f): a second publisher on odom -> robot_base_link (a base driver with pub_tf on)" % (hz, HIGH_HZ))
    elif hz < LOW_HZ:
        ok = False
        lines.append("FAIL: rate too low (%.1f Hz < %.0f): the bridge is stalling or the mapper pose is slow" % (hz, LOW_HZ))
    else:
        lines.append("PASS: one publisher's worth (%.0f to %.0f Hz expected)" % (LOW_HZ, HIGH_HZ))
    for (parent, child), count in sorted(edges.items()):
        if (parent, child) == EDGE:
            continue
        if parent == "camera_init":
            ok = False
            lines.append("FAIL: %s -> %s is on /tf (%d messages): the mapper's tree must be remapped to /fastlivo/tf" % (parent, child, count))
        else:
            lines.append("other edge: %s -> %s, %d messages (%.1f Hz)" % (parent, child, count, count / seconds))
    return ok, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=10.0)
    ap.add_argument("--expect-silent", action="store_true")
    args = ap.parse_args()
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from tf2_msgs.msg import TFMessage
    rclpy.init()
    node = Node("tf_edge_check")
    edges = {}

    def on_tf(msg):
        for t in msg.transforms:
            key = (t.header.frame_id, t.child_frame_id)
            edges[key] = edges.get(key, 0) + 1
    node.create_subscription(TFMessage, "/tf", on_tf, QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, history=HistoryPolicy.KEEP_LAST, depth=500))
    end = time.monotonic() + args.seconds
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)
    names = sorted(i.node_name for i in node.get_publishers_info_by_topic("/tf") if i.node_name != "tf_edge_check")
    ok, lines = judge(edges, args.seconds, args.expect_silent)
    print("nodes registered as /tf publishers (a silent xnode_vehicle may be listed: it creates the broadcaster even with pub_tf off): %s" % names)
    print("\n".join(lines))
    node.destroy_node()
    rclpy.try_shutdown()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
