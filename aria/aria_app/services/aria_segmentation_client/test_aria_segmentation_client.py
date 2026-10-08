"""Checks the aria segmentation client: voice in, Target out. Real ROS messages, no glasses.

Needs ROS 2 Humble and the built segmentation_interfaces, so it runs on the lab box:
    source aria/aria_env.sh && source install/local_setup.bash
    python -m unittest discover -s aria/aria_app/services/aria_segmentation_client -p "test_*.py"
It calls the callback directly and never spins the node. Creating the node still opens its
topics, so ROS starts on a private channel (TEST_DOMAIN, default 78), localhost only.
"""

import os
import unittest

import rclpy
from std_msgs.msg import String

from aria_segmentation_client import AriaSegmentationClient, STOP_KEYWORD


class Recorder:
    def __init__(self):
        self.sent = []

    def publish(self, msg):
        self.sent.append(msg)


class AriaClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ROS_LOCALHOST_ONLY"] = "1"
        rclpy.init(domain_id=int(os.environ.get("TEST_DOMAIN", "78")))

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = AriaSegmentationClient()
        self.addCleanup(self.node.destroy_node)
        self.node.target_pub = Recorder()

    def say(self, words):
        self.node.on_prompt(String(data=words))
        return [m.prompt for m in self.node.target_pub.sent]

    def test_a_word_becomes_a_target(self):
        self.assertEqual(self.say("  Red Cup "), ["red cup"])
        target = self.node.target_pub.sent[0]
        self.assertEqual((target.reference.width, target.reference_mask.width), (0, 0))
        self.assertGreater(target.header.stamp.sec, 0)

    def test_the_stop_word_clears(self):
        self.say("box")
        self.assertEqual(self.say(STOP_KEYWORD.upper()), ["box", ""])

    def test_the_same_word_again_is_not_resent(self):
        self.say("box")
        self.assertEqual(self.say("Box"), ["box"])

    def test_silence_is_ignored(self):
        self.assertEqual(self.say("   "), [])

    def test_stop_with_nothing_set_sends_nothing(self):
        self.assertEqual(self.say(STOP_KEYWORD), [])


if __name__ == "__main__":
    unittest.main()
