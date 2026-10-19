"""Checks the aria segmentation client: voice and gaze in, Target and grasp request out.
Real ROS messages, no glasses, a stand-in for the segmentation service.

Needs ROS 2 Humble and the built segmentation_interfaces, so it runs on the lab box:
    source aria/aria_env.sh && source install/local_setup.bash
    python -m unittest discover -s aria/aria_app/services/aria_segmentation_client -p "test_*.py"
It calls the callback directly and never spins the node. Creating the node still opens its
topics, so ROS starts on a private channel (TEST_DOMAIN, default 78), localhost only.
"""

import os
import time
import unittest

import cv2
import numpy as np
import rclpy
from geometry_msgs.msg import Point, PointStamped
from segmentation_interfaces.msg import Detection
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

from aria_segmentation_client import AriaSegmentationClient, STOP_KEYWORD, image_msg


class Recorder:
    def __init__(self):
        self.sent = []

    def publish(self, msg):
        self.sent.append(msg)


class FakeFuture:
    def __init__(self):
        self.callbacks, self.response = [], None

    def add_done_callback(self, cb):
        self.callbacks.append(cb)

    def result(self):
        return self.response

    def finish(self, response):
        self.response = response
        for cb in self.callbacks:
            cb(self)


class FakeServiceClient:
    """Stands in for the Segment client: records requests, replies only when told."""

    def __init__(self):
        self.requests, self.futures = [], []

    def service_is_ready(self):
        return True

    def call_async(self, request):
        self.requests.append(request)
        self.futures.append(FakeFuture())
        return self.futures[-1]


def box(x0, y0, x1, y1, score, size=(40, 60)):
    """A Detection whose mask is the rectangle x0..x1, y0..y1 of a size[0] x size[1] image."""
    mask = np.zeros(size, np.uint8)
    mask[y0:y1 + 1, x0:x1 + 1] = 1
    det = Detection(score=score, mask=image_msg(mask, "mono8"))
    det.bbox.x_offset, det.bbox.y_offset = x0, y0
    det.bbox.width, det.bbox.height = x1 - x0 + 1, y1 - y0 + 1
    return det


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
        self.node.request_pub = Recorder()
        self.node.service = FakeServiceClient()

    def image(self, taken=10.0):
        """A 60 x 40 glasses image taken at glasses time `taken` s, as the glasses app sends it."""
        image = CompressedImage(format="jpeg",
                                data=cv2.imencode(".png", np.full((40, 60, 3), 90, np.uint8))[1].tobytes())
        image.header.stamp.sec, image.header.stamp.nanosec = int(taken), round(taken % 1 * 1e9)
        self.node.on_image(image)

    def gaze(self, x, y, taken=10.0, age=2.0):
        """Gaze at (x, y) taken at glasses time `taken`, which arrived `age` s ago. 2 s ago is from
        while the word was spoken (the window is 1.0 s, ending speech_latency_s 1.5 before the word)."""
        msg = PointStamped(point=Point(x=float(x), y=float(y)))
        msg.header.stamp.sec, msg.header.stamp.nanosec = int(taken), round(taken % 1 * 1e9)
        self.node.on_gaze(msg)
        self.node.gaze[-1] = (time.monotonic() - age, *self.node.gaze[-1][1:])

    def look(self, x, y):
        """A glasses image and gaze at (x, y), both taken at glasses time 10 s, while you spoke."""
        self.image()
        self.gaze(x, y)

    def asked_about(self):
        """The glasses time each service request's image was taken at."""
        return [r.image.header.stamp.sec + r.image.header.stamp.nanosec * 1e-9
                for r in self.node.service.requests]

    def reply(self, *dets):
        self.node.service.futures[-1].finish(Segment.Response(success=True, detections=list(dets)))

    def say(self, words):
        self.node.on_prompt(String(data=words))
        return [m.prompt for m in self.node.target_pub.sent]

    def requests(self):
        return len(self.node.request_pub.sent)

    def test_a_word_becomes_a_target(self):
        self.assertEqual(self.say("  Red Cup "), ["red cup"])
        target = self.node.target_pub.sent[0]
        self.assertEqual((target.reference.width, target.reference_mask.width), (0, 0))
        self.assertGreater(target.header.stamp.sec, 0)

    def test_without_glasses_image_the_service_is_not_asked(self):
        self.say("box")
        self.assertEqual(self.node.service.requests, [])

    def test_the_looked_at_mask_is_sent_as_reference(self):
        self.look(30, 20)
        self.say("box")
        self.assertEqual(self.node.service.requests[0].prompt, "box")
        self.assertEqual(self.node.service.requests[0].image.encoding, "rgb8")
        # the higher score is elsewhere, the gaze is on the second
        self.reply(box(0, 0, 9, 9, 0.9), box(25, 15, 34, 24, 0.5))
        first, second = self.node.target_pub.sent
        self.assertEqual((first.prompt, first.reference.width), ("box", 0))
        self.assertEqual((second.prompt, second.reference.width, second.reference.height), ("box", 10, 10))
        self.assertEqual(second.reference_mask.encoding, "mono8")
        self.assertEqual(second.header.stamp.sec, 10)  # the glasses frame it came from
        self.assertEqual(self.requests(), 1)            # one grasp request per word

    def test_nothing_near_the_gaze_sends_no_reference(self):
        self.look(300, 300)   # beyond pick_radius_px (80) from the only mask
        self.say("box")
        self.reply(box(0, 0, 9, 9, 0.9))
        self.assertEqual(len(self.node.target_pub.sent), 1)

    def test_a_late_reply_after_stop_is_dropped(self):
        self.look(30, 20)
        self.say("box")
        self.say(STOP_KEYWORD)
        self.reply(box(25, 15, 34, 24, 0.5))
        self.assertEqual([m.prompt for m in self.node.target_pub.sent], ["box", ""])

    def test_a_late_reply_after_the_same_word_again_is_dropped(self):
        # "box", stop, "box" inside one service call: only the newest call's reply counts
        self.look(30, 20)
        self.say("box")
        self.say(STOP_KEYWORD)
        self.say("box")
        old, new = self.node.service.futures
        old.finish(Segment.Response(success=True, detections=[box(25, 15, 34, 24, 0.5)]))
        self.assertEqual(len(self.node.target_pub.sent), 3)   # box, stop, box: no reference
        new.finish(Segment.Response(success=True, detections=[box(25, 15, 34, 24, 0.5)]))
        self.assertEqual(self.node.target_pub.sent[-1].reference.width, 10)

    def test_old_gaze_is_not_used(self):
        self.image()
        self.gaze(30, 20, age=5)
        self.say("box")
        self.assertEqual(self.node.service.requests, [])

    def test_gaze_after_the_word_was_spoken_is_not_used(self):
        # the word arrives speech_latency_s after you spoke: gaze since then does not vote
        self.image()
        self.gaze(30, 20, age=0)
        self.say("box")
        self.assertEqual(self.node.service.requests, [])

    def test_the_image_from_when_you_spoke_beats_a_newer_one(self):
        self.look(30, 20)
        self.image(taken=15.0)
        self.say("box")
        self.assertEqual(self.asked_about(), [10.0])

    def test_no_image_from_when_you_spoke_waits_for_one(self):
        self.image(taken=8.0)
        self.gaze(30, 20)
        self.say("box")
        self.assertEqual(self.node.service.requests, [])
        self.image(taken=10.2)   # taken while you spoke, arrived late
        self.assertEqual(self.asked_about(), [10.2])

    def test_after_the_wait_the_nearest_image_needs_gaze_near_it(self):
        self.image(taken=8.0)
        self.gaze(30, 20)
        self.say("box")
        self.node.wait_until -= 10
        self.image(taken=9.0)   # still before you spoke, 1 s from the gaze: nothing votes
        self.assertEqual(self.node.service.requests, [])
        self.assertEqual(self.node.wait_until, -np.inf)

    def test_after_a_wait_the_gaze_is_from_when_the_word_came(self):
        # the image comes 2 s after the word: the gaze window still ends speech_latency_s
        # before the word's arrival, not before the image's
        self.image(taken=8.0)
        self.gaze(30, 20)
        self.say("box")
        self.node.word_at -= 2
        self.node.gaze[-1] = (self.node.word_at - 2.0, *self.node.gaze[-1][1:])
        self.image(taken=10.0)
        self.assertEqual(self.asked_about(), [10.0])

    def test_the_stop_word_ends_the_wait(self):
        self.image(taken=8.0)
        self.gaze(30, 20)
        self.say("box")
        self.say(STOP_KEYWORD)
        self.image(taken=10.0)
        self.assertEqual(self.node.service.requests, [])

    def test_history_is_kept_by_arrival_time(self):
        self.look(30, 20)
        self.node.images[0] = (time.monotonic() - 21, *self.node.images[0][1:])
        self.image(taken=11.0)
        self.assertEqual([t for _, t, _ in self.node.images], [11.0])

    def test_the_stop_word_clears(self):
        self.say("box")
        self.assertEqual(self.say(STOP_KEYWORD.upper()), ["box", ""])

    def test_the_same_word_again_is_resent_and_requested(self):
        # a restarted grasp client gets the word back only when you say it again,
        # and each time you ask is a new grasp (T1.25 gate, T2.6)
        self.say("box")
        self.assertEqual(self.say("Box"), ["box", "box"])
        self.assertEqual(self.requests(), 2)

    def test_silence_is_ignored(self):
        self.assertEqual(self.say("   "), [])

    def test_stop_is_always_sent(self):
        self.assertEqual(self.say(STOP_KEYWORD), [""])

    def test_stop_and_silence_send_no_request(self):
        self.say(STOP_KEYWORD)
        self.say("  ")
        self.assertEqual(self.requests(), 0)


if __name__ == "__main__":
    unittest.main()
