"""Checks segmentation_logic.py on made-up arrays. Needs numpy only: no ROS, torch or GPU.

    python -m unittest discover -s shared_services/segmentation -p "test_*.py"
"""

import math
import unittest

import numpy as np

from segmentation_logic import (
    back_project,
    centroid_on_mask,
    depth_in_metres,
    detections_from_sam3,
    median_depth,
)

# A 640 x 480 camera with its centre exactly mid-image: CameraInfo.k, row by row.
K = [600.0, 0.0, 320.0, 0.0, 600.0, 240.0, 0.0, 0.0, 1.0]


def square_mask(h=480, w=640, x=100, y=50, size=20):
    mask = np.zeros((h, w), dtype=bool)
    mask[y:y + size, x:x + size] = True
    return mask


class FakeTensor:
    """Stands in for a torch tensor: the three methods as_numpy uses."""

    def __init__(self, array, floating):
        self._array, self._floating = array, floating

    def detach(self):
        return self

    def is_floating_point(self):
        return self._floating

    def float(self):
        return FakeTensor(self._array.astype(np.float32), True)

    def cpu(self):
        return self

    def numpy(self):
        return self._array


class DepthUnits(unittest.TestCase):
    def test_millimetres_to_metres(self):
        depth = np.array([[0, 500, 1250]], dtype=np.uint16)
        np.testing.assert_allclose(depth_in_metres(depth, "16UC1"), [[0.0, 0.5, 1.25]])



class MedianDepth(unittest.TestCase):
    def test_skips_zero_and_nan(self):
        depth = np.array([[0.0, 0.5, np.nan, 0.7, 0.9]], dtype=np.float32)
        mask = np.ones_like(depth, dtype=bool)
        self.assertAlmostEqual(median_depth(depth, mask), 0.7, places=6)

    def test_only_under_the_mask(self):
        depth = np.array([[0.4, 2.0]], dtype=np.float32)
        mask = np.array([[True, False]])
        self.assertAlmostEqual(median_depth(depth, mask), 0.4, places=6)

    def test_no_valid_reading_is_nan(self):
        depth = np.array([[0.0, np.nan]], dtype=np.float32)
        self.assertTrue(math.isnan(median_depth(depth, np.ones((1, 2), dtype=bool))))

    def test_too_few_readings_is_nan(self):
        # T1.24 3b: a box too close has no readings, the 2 left of 10 are the background
        depth = np.array([[0.0] * 8 + [1.26, 1.26]], dtype=np.float32)
        mask = np.ones_like(depth, dtype=bool)
        self.assertAlmostEqual(median_depth(depth, mask), 1.26, places=6)
        self.assertTrue(math.isnan(median_depth(depth, mask, 0.5)))

    def test_enough_readings_kept(self):
        depth = np.array([[0.0] * 5 + [0.2] * 5], dtype=np.float32)
        mask = np.ones_like(depth, dtype=bool)
        self.assertAlmostEqual(median_depth(depth, mask, 0.5), 0.2, places=6)

    def test_shape_mismatch_refused(self):
        with self.assertRaises(ValueError):
            median_depth(np.zeros((2, 2)), np.ones((3, 3), dtype=bool))


class BackProject(unittest.TestCase):
    def test_off_centre(self):
        # 60 px right and 30 px down at 1.2 m with f = 600 px: 0.12 m right, 0.06 m down
        x, y, z = back_project(380.0, 270.0, 1.2, K)
        self.assertAlmostEqual(x, 0.12)
        self.assertAlmostEqual(y, 0.06)
        self.assertEqual(z, 1.2)


class FromSam3(unittest.TestCase):
    def state(self, masks, scores):
        return {"masks": np.array(masks), "scores": np.array(scores)}

    def test_box_area_and_centroid_of_a_square(self):
        [det] = detections_from_sam3(self.state([square_mask()], [0.9]), 0.5, 5)
        self.assertEqual(det.bbox, (100, 50, 20, 20))
        self.assertEqual(det.area_px, 400)
        self.assertEqual((det.u, det.v), (109.5, 59.5))

    def test_centroid_on_mask(self):
        [solid] = detections_from_sam3(self.state([square_mask()], [0.9]), 0.5, 5)
        self.assertTrue(centroid_on_mask(solid))
        ring = square_mask(size=40)
        ring[60:80, 110:130] = False   # hollow middle: the centroid lands in the hole
        [hollow] = detections_from_sam3(self.state([ring], [0.9]), 0.5, 5)
        self.assertFalse(centroid_on_mask(hollow))

    def test_sorted_by_score_then_filtered_and_capped(self):
        masks = [square_mask(x=10 * i) for i in range(4)]
        found = detections_from_sam3(self.state(masks, [0.6, 0.95, 0.3, 0.8]), 0.5, 2)
        self.assertEqual([d.score for d in found], [0.95, 0.8])

    def test_empty_mask_skipped(self):
        empty = np.zeros((480, 640), dtype=bool)
        found = detections_from_sam3(self.state([empty, square_mask()], [0.9, 0.7]), 0.5, 5)
        self.assertEqual([d.score for d in found], [0.7])

    def test_nothing_found(self):
        self.assertEqual(detections_from_sam3({"masks": [], "scores": []}, 0.5, 5), [])
        self.assertEqual(detections_from_sam3({}, 0.5, 5), [])

    def test_both_mask_shapes(self):
        flat = self.state([square_mask()], [0.9])
        with_channel = self.state([square_mask()[None]], [0.9])   # (N, 1, H, W)
        a = detections_from_sam3(flat, 0.5, 5)[0]
        b = detections_from_sam3(with_channel, 0.5, 5)[0]
        self.assertEqual((a.bbox, a.u, a.v), (b.bbox, b.u, b.v))

    def test_torch_like_input(self):
        state = {
            "masks": FakeTensor(np.array([square_mask()[None]]), floating=False),
            "scores": FakeTensor(np.array([0.9], dtype=np.float16), floating=True),
        }
        [det] = detections_from_sam3(state, 0.5, 5)
        self.assertAlmostEqual(det.score, 0.9, places=3)

    def test_no_depth_means_no_depth_and_no_point(self):
        [det] = detections_from_sam3(self.state([square_mask()], [0.9]), 0.5, 5)
        self.assertTrue(math.isnan(det.depth_m))
        self.assertIsNone(det.point)

    def test_depth_without_intrinsics_gives_depth_only(self):
        depth = np.full((480, 640), 0.8, dtype=np.float32)
        [det] = detections_from_sam3(self.state([square_mask()], [0.9]), 0.5, 5, depth, [0.0] * 9)
        self.assertAlmostEqual(det.depth_m, 0.8, places=6)
        self.assertIsNone(det.point)

    def test_depth_and_intrinsics_give_the_point(self):
        depth = np.full((480, 640), 0.8, dtype=np.float32)
        [det] = detections_from_sam3(
            self.state([square_mask(x=310, y=230)], [0.9]), 0.5, 5, depth, K
        )
        # a 20 px square from (310, 230) is centred on (319.5, 239.5), half a pixel off the axis
        x, y, z = det.point
        self.assertAlmostEqual(x, -0.5 * 0.8 / 600)
        self.assertAlmostEqual(y, -0.5 * 0.8 / 600)
        self.assertAlmostEqual(z, 0.8, places=6)

    def test_no_valid_depth_gives_no_point(self):
        depth = np.zeros((480, 640), dtype=np.float32)
        [det] = detections_from_sam3(self.state([square_mask()], [0.9]), 0.5, 5, depth, K)
        self.assertTrue(math.isnan(det.depth_m))
        self.assertIsNone(det.point)

    def test_mismatched_counts_refused(self):
        with self.assertRaises(ValueError):
            detections_from_sam3(self.state([square_mask()], [0.9, 0.8]), 0.5, 5)


if __name__ == "__main__":
    unittest.main()
