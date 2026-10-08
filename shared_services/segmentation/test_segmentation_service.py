"""Checks the segmentation service node with a fake SAM 3: real ROS messages, no GPU.

Needs ROS 2 Humble and the built segmentation_interfaces, so it runs on the lab box:
    source shared_services/shared_services_env.sh
    python -m unittest discover -s shared_services/segmentation -p "test_segmentation_service.py"
It calls the handler directly and never spins the node. Creating the node still advertises the
service, so ROS starts on a private channel (TEST_DOMAIN, default 78), localhost only.
"""

import math
import os
import unittest

import numpy as np
import rclpy
from segmentation_interfaces.srv import Segment
from sensor_msgs.msg import CameraInfo, Image

from segmentation_service import SegmentationService

H, W = 48, 64
K = [60.0, 0.0, 32.0, 0.0, 60.0, 24.0, 0.0, 0.0, 1.0]


def image_msg(array, encoding, frame_id="camera_color_optical_frame", pad=0):
    """An Image message from an array. pad adds bytes at the end of each row, as drivers may."""
    msg = Image()
    msg.header.frame_id = frame_id
    msg.header.stamp.sec = 7
    msg.height, msg.width = array.shape[:2]
    msg.encoding = encoding
    row = array.reshape(msg.height, -1).view(np.uint8)
    if pad:
        row = np.hstack([row, np.zeros((msg.height, pad), dtype=np.uint8)])
    msg.step = row.shape[1]
    msg.data = row.tobytes()
    return msg


def square(x=10, y=5, size=8):
    mask = np.zeros((H, W), dtype=bool)
    mask[y:y + size, x:x + size] = True
    return mask


class FakeSam3:
    """Returns fixed masks and records what it was asked."""

    def __init__(self, masks=(), scores=()):
        self.masks, self.scores, self.calls = list(masks), list(scores), []

    def process_text_prompt(self, image, prompt):
        self.calls.append((image, prompt))
        return {"masks": np.array(self.masks).reshape(-1, 1, H, W), "scores": np.array(self.scores)}


class FailingSam3:
    def process_text_prompt(self, image, prompt):
        raise RuntimeError("CUDA out of memory")


def request(prompt="box", rgb=None, depth=None, k=None, **fields):
    req = Segment.Request()
    req.prompt = prompt
    req.image = image_msg(rgb if rgb is not None else np.zeros((H, W, 3), np.uint8), "rgb8")
    if depth is not None:
        req.depth = depth
    if k is not None:
        req.camera_info = CameraInfo(k=k)
    for name, value in fields.items():
        setattr(req, name, value)
    return req


class ServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["ROS_LOCALHOST_ONLY"] = "1"
        rclpy.init(domain_id=int(os.environ.get("TEST_DOMAIN", "78")))

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def make(self, model, **params):
        node = SegmentationService(model=model, **params)
        self.addCleanup(node.destroy_node)
        return node

    def call(self, node, req):
        return node.segment(req, Segment.Response())

    # ---- what reaches the model ----
    def test_model_gets_the_rgb_pixels_and_the_prompt(self):
        rgb = np.random.default_rng(0).integers(0, 255, (H, W, 3), dtype=np.uint8)
        model = FakeSam3()
        res = self.call(self.make(model), request("red cup", rgb))
        self.assertTrue(res.success, res.message)
        image, prompt = model.calls[0]
        self.assertEqual(prompt, "red cup")
        np.testing.assert_array_equal(image, rgb)

    def test_padded_rows_are_read_correctly(self):
        rgb = np.random.default_rng(1).integers(0, 255, (H, W, 3), dtype=np.uint8)
        model = FakeSam3()
        req = request(rgb=rgb)
        req.image = image_msg(rgb, "rgb8", pad=16)
        self.assertTrue(self.call(self.make(model), req).success)
        np.testing.assert_array_equal(model.calls[0][0], rgb)

    # ---- refusals: success false, the reason, and the model is never called ----
    def assert_refused(self, req, words):
        model = FakeSam3()
        res = self.call(self.make(model), req)
        self.assertFalse(res.success)
        self.assertIn(words, res.message)
        self.assertEqual(model.calls, [])

    def test_empty_prompt_refused(self):
        self.assert_refused(request(prompt="  "), "prompt")

    def test_bgr8_refused(self):
        req = request()
        req.image.encoding = "bgr8"
        self.assert_refused(req, "rgb8")

    def test_depth_of_another_size_refused(self):
        depth = image_msg(np.zeros((H // 2, W // 2), np.uint16), "16UC1")
        self.assert_refused(request(depth=depth), "depth")

    def test_unknown_depth_encoding_refused(self):
        depth = image_msg(np.zeros((H, W), np.uint8), "8UC1")
        self.assert_refused(request(depth=depth), "8UC1")

    def test_model_failure_is_a_reply_not_a_crash(self):
        res = self.call(self.make(FailingSam3()), request())
        self.assertFalse(res.success)
        self.assertIn("CUDA out of memory", res.message)

    # ---- the reply ----
    def test_reply_copies_the_image_header(self):
        res = self.call(self.make(FakeSam3([square()], [0.9])), request())
        self.assertEqual(res.header.frame_id, "camera_color_optical_frame")
        self.assertEqual(res.header.stamp.sec, 7)
        self.assertGreaterEqual(res.inference_ms, 0.0)

    def test_detection_fields_without_depth(self):
        res = self.call(self.make(FakeSam3([square()], [0.9])), request())
        [det] = res.detections
        self.assertAlmostEqual(det.score, 0.9, places=5)
        self.assertEqual((det.bbox.x_offset, det.bbox.y_offset, det.bbox.width, det.bbox.height),
                         (10, 5, 8, 8))
        self.assertEqual(det.area_px, 64)
        self.assertEqual((det.u, det.v), (13.5, 8.5))
        self.assertTrue(math.isnan(det.depth_m))
        self.assertFalse(det.has_point)

    def test_mask_is_mono8_ones_and_zeros(self):
        res = self.call(self.make(FakeSam3([square()], [0.9])), request())
        mask = res.detections[0].mask
        self.assertEqual((mask.encoding, mask.height, mask.width, mask.step), ("mono8", H, W, W))
        values = np.frombuffer(bytes(mask.data), np.uint8).reshape(H, W)
        np.testing.assert_array_equal(values, square().astype(np.uint8))

    def test_depth_in_millimetres_and_k_give_the_point(self):
        depth = image_msg(np.full((H, W), 800, np.uint16), "16UC1")
        res = self.call(self.make(FakeSam3([square()], [0.9])), request(depth=depth, k=K))
        [det] = res.detections
        self.assertAlmostEqual(det.depth_m, 0.8, places=5)
        self.assertTrue(det.has_point)
        self.assertAlmostEqual(det.point.x, (13.5 - 32) * 0.8 / 60, places=5)
        self.assertAlmostEqual(det.point.y, (8.5 - 24) * 0.8 / 60, places=5)
        self.assertAlmostEqual(det.point.z, 0.8, places=5)

    def test_depth_without_k_gives_no_point(self):
        depth = image_msg(np.full((H, W), 0.8, np.float32), "32FC1")
        res = self.call(self.make(FakeSam3([square()], [0.9])), request(depth=depth))
        self.assertAlmostEqual(res.detections[0].depth_m, 0.8, places=5)
        self.assertFalse(res.detections[0].has_point)

    def test_defaults_and_request_overrides(self):
        masks = [square(x=4 * i) for i in range(4)]
        node = self.make(FakeSam3(masks, [0.95, 0.85, 0.6, 0.4]), min_score=0.5, max_detections=2)
        self.assertEqual([round(d.score, 2) for d in self.call(node, request()).detections],
                         [0.95, 0.85])
        res = self.call(node, request(min_score=0.9, max_detections=3))
        self.assertEqual([round(d.score, 2) for d in res.detections], [0.95])

    def test_nothing_found_is_success_with_no_detections(self):
        res = self.call(self.make(FakeSam3()), request())
        self.assertTrue(res.success)
        self.assertEqual(len(res.detections), 0)


if __name__ == "__main__":
    unittest.main()
