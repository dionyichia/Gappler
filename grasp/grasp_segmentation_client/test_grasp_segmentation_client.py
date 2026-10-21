"""Checks the grasp segmentation client with no service and no camera: real ROS messages.

Needs ROS 2 Humble and the built segmentation_interfaces, so it runs on the lab box:
    source grasp/grasp_env.sh
    python -m unittest discover -s grasp/grasp_segmentation_client -p "test_*.py"
It calls the callbacks directly and never spins the node. Creating the node still opens its
topics, so ROS starts on a private channel (TEST_DOMAIN, default 78), localhost only.
"""

import math
import os
import unittest

import rclpy
from segmentation_interfaces.msg import Detection, Target
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CameraInfo, Image

from grasp_segmentation_client import GraspSegmentationClient, pick_detection


class Recorder:
    """Stands in for a publisher and keeps what was published."""

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

    def __init__(self, ready=True):
        self.ready, self.requests, self.futures = ready, [], []

    def service_is_ready(self):
        return self.ready

    def call_async(self, request):
        self.requests.append(request)
        self.futures.append(FakeFuture())
        return self.futures[-1]


def frame(sec):
    rgb, depth = Image(encoding="rgb8", width=4, height=2), Image(encoding="16UC1", width=4, height=2)
    for msg in (rgb, depth):
        msg.header.stamp.sec = sec
        msg.header.frame_id = "camera_color_optical_frame"
    return rgb, depth


def detection(score, area, u=10.0, v=20.0, depth=0.4, point=(0.1, 0.0, 0.4)):
    det = Detection(score=score, area_px=area, u=u, v=v, depth_m=depth)
    det.mask = Image(encoding="mono8", width=4, height=2, step=4, data=bytes([1] * 8))
    det.has_point = point is not None
    if point is not None:
        det.point.x, det.point.y, det.point.z = point
    return det


def reply(*dets, success=True, sec=5):
    res = Segment.Response(success=success, detections=list(dets))
    res.header.stamp.sec = sec
    res.header.frame_id = "camera_color_optical_frame"
    return res


class PickDetection(unittest.TestCase):
    def test_highest_score(self):
        self.assertEqual(pick_detection([detection(0.6, 900), detection(0.8, 100)]).score,
                         detection(0.8, 100).score)

    def test_tie_goes_to_the_larger_mask(self):
        self.assertEqual(pick_detection([detection(0.7, 100), detection(0.7, 500)]).area_px, 500)

    def test_none_found(self):
        self.assertIsNone(pick_detection([]))


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ROS_LOCALHOST_ONLY"] = "1"
        rclpy.init(domain_id=int(os.environ.get("TEST_DOMAIN", "78")))

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def make(self, default_prompt="box", glasses_running=False, service_ready=True):
        node = GraspSegmentationClient(default_prompt=default_prompt)
        self.addCleanup(node.destroy_node)
        node.count_publishers = lambda topic: 1 if glasses_running else 0
        node.service = FakeServiceClient(service_ready)
        node.mask_pub, node.centroid_pub, node.centroid_viz_pub = Recorder(), Recorder(), Recorder()
        node.on_camera_info(CameraInfo(k=[600.0, 0.0, 320.0, 0.0, 600.0, 240.0, 0.0, 0.0, 1.0]))
        return node

    # ---- which prompt is used ----
    def test_default_prompt_used_without_the_glasses(self):
        node = self.make()
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests[0].prompt, "box")

    def test_default_prompt_not_used_when_the_glasses_client_runs(self):
        node = self.make(glasses_running=True)
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests, [])

    def test_requests_carry_the_grasp_cutoff_not_the_service_default(self):
        # the service's defaults are loosened for the glasses (T2.9), the arm keeps 0.5 and 5
        node = self.make()
        node.on_frames(*frame(1))
        request = node.service.requests[0]
        self.assertAlmostEqual(request.min_score, 0.5)
        self.assertEqual(request.max_detections, 5)

    def test_a_target_replaces_the_default(self):
        node = self.make()
        node.on_target(Target(prompt=" Red Cup "))
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests[0].prompt, "red cup")

    def test_an_empty_target_stops_and_the_default_does_not_come_back(self):
        node = self.make()
        node.on_target(Target(prompt=""))
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests, [])

    def test_no_default_waits_for_a_target(self):
        node = self.make(default_prompt="")
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests, [])

    # ---- what is sent, and when ----
    def test_request_carries_colour_depth_and_camera_info(self):
        node = self.make()
        rgb, depth = frame(1)
        node.on_frames(rgb, depth)
        req = node.service.requests[0]
        self.assertEqual((req.image.header.stamp.sec, req.depth.header.stamp.sec), (1, 1))
        self.assertEqual(req.camera_info.k[0], 600.0)

    def test_nothing_sent_before_camera_info(self):
        node = GraspSegmentationClient(default_prompt="box")
        self.addCleanup(node.destroy_node)
        node.count_publishers = lambda topic: 0
        node.service = FakeServiceClient()
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests, [])

    def test_one_request_at_a_time_then_the_newest_frame(self):
        node = self.make()
        node.on_frames(*frame(1))
        node.on_frames(*frame(2))
        node.on_frames(*frame(3))
        self.assertEqual(len(node.service.requests), 1)
        node.service.futures[0].finish(reply(detection(0.9, 100)))
        self.assertEqual([r.image.header.stamp.sec for r in node.service.requests], [1, 3])

    def test_service_not_up_keeps_the_frame_for_later(self):
        node = self.make(service_ready=False)
        node.on_frames(*frame(1))
        self.assertEqual(node.service.requests, [])
        node.service.ready = True
        node.on_frames(*frame(2))
        self.assertEqual(node.service.requests[0].image.header.stamp.sec, 2)

    def test_no_reply_is_given_up_after_the_timeout(self):
        node = self.make()
        node.on_frames(*frame(1))
        node.on_frames(*frame(2))
        self.assertEqual(len(node.service.requests), 1)    # still waiting on the first
        node.sent_at -= node.timeout_s + 1                  # the service died mid-call
        node.on_frames(*frame(3))
        self.assertEqual([r.image.header.stamp.sec for r in node.service.requests], [1, 3])
        node.service.futures[0].finish(reply(detection(0.9, 100)))   # a late reply is ignored
        self.assertEqual(node.mask_pub.sent, [])
        self.assertEqual(len(node.service.requests), 2)

    # ---- what is published ----
    def test_publishes_mask_centroid_and_point_of_the_best(self):
        node = self.make()
        node.on_frames(*frame(1))
        node.service.futures[0].finish(reply(detection(0.6, 900, u=1.0),
                                             detection(0.9, 100, u=50.0, v=60.0, depth=0.36)))
        [mask], [c2d], [c3d] = (node.mask_pub.sent, node.centroid_pub.sent,
                                node.centroid_viz_pub.sent)
        self.assertEqual(mask.encoding, "mono8")
        self.assertEqual(mask.header.stamp.sec, 5)
        self.assertEqual((c2d.point.x, c2d.point.y), (50.0, 60.0))
        self.assertAlmostEqual(c2d.point.z, 0.36, places=5)
        self.assertEqual(c2d.header.frame_id, "camera_color_optical_frame")
        self.assertEqual(c2d.header.stamp.sec, 5)
        self.assertAlmostEqual(c3d.point.z, 0.4, places=5)

    def test_no_depth_publishes_the_mask_only(self):
        node = self.make()
        node.on_frames(*frame(1))
        node.service.futures[0].finish(reply(detection(0.9, 100, depth=math.nan, point=None)))
        self.assertEqual(len(node.mask_pub.sent), 1)
        self.assertEqual((node.centroid_pub.sent, node.centroid_viz_pub.sent), ([], []))

    def test_nothing_found_or_failed_publishes_nothing(self):
        node = self.make()
        node.on_frames(*frame(1))
        node.service.futures[0].finish(reply())
        node.on_frames(*frame(2))
        node.service.futures[1].finish(reply(detection(0.9, 100), success=False))
        self.assertEqual(node.mask_pub.sent, [])

    def test_reply_for_an_old_prompt_is_dropped(self):
        node = self.make()
        node.on_frames(*frame(1))
        node.on_target(Target(prompt="cup"))
        node.service.futures[0].finish(reply(detection(0.9, 100)))
        self.assertEqual(node.mask_pub.sent, [])


if __name__ == "__main__":
    unittest.main()
