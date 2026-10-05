"""S4 erosion and S5 mask cleanup (T6.3d), S6 crops and normalising (T6.3f)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.image_feature import image_features, l2_normalise, padded_crops
from memory_graph.masks import clean_masks, erode_one_pixel, filter_masks, subtract_contained
from memory_graph.tests._fixtures import dets

CFG = MemoryGraphConfig()
H, W = 60, 80
# The area floor is min(ratio * H * W, 25 px). On this 60x80 test image the ratio
# term is under 1 px, so raise it to make the 25 px floor the one that applies,
# as it does on a 640x480 image.
AREA_CFG = MemoryGraphConfig(mask_area_ratio=0.01)


def rect(v0, v1, u0, u1):
    m = np.zeros((H, W), dtype=bool)
    m[v0:v1, u0:u1] = True
    return m


class ErosionTest(unittest.TestCase):
    def test_square_shrinks_by_one_pixel(self):
        out = erode_one_pixel(rect(10, 15, 10, 15))
        np.testing.assert_array_equal(out, rect(11, 14, 11, 14))

    def test_image_border_is_removed(self):
        out = erode_one_pixel(np.ones((H, W), dtype=bool))
        self.assertFalse(out[0].any() or out[-1].any() or out[:, 0].any() or out[:, -1].any())
        self.assertTrue(out[1:-1, 1:-1].all())


class MaskCleanupTest(unittest.TestCase):
    def cup_on_table(self):
        table = rect(20, 50, 5, 75)
        cup = rect(25, 35, 30, 40)
        return dets([[5, 20, 75, 50], [30, 25, 40, 35]], [0.9, 0.8], ["table", "cup"], [table, cup])

    def test_cup_cut_out_of_table(self):
        out = subtract_contained(self.cup_on_table(), CFG)
        table, cup = out.masks
        self.assertFalse(table[25:35, 30:40].any())          # a hole where the cup is
        self.assertTrue(cup[25:35, 30:40].all())
        self.assertFalse((table & cup).any())                # no pixel in two masks
        self.assertTrue(table[45, 10])                       # the rest of the table stays

    def test_side_by_side_objects_untouched(self):
        a, b = rect(10, 30, 5, 25), rect(10, 30, 30, 50)
        d = dets([[5, 10, 25, 30], [30, 10, 50, 30]], [0.9, 0.8], ["a", "b"], [a, b])
        out = subtract_contained(d, CFG)
        np.testing.assert_array_equal(out.masks, d.masks)

    def test_tiny_and_duplicate_masks_dropped(self):
        big = rect(10, 40, 10, 40)
        near_copy = big.copy()
        near_copy[10, 10] = False            # IoU just under 1
        tiny = rect(50, 52, 50, 52)          # 4 px, below the 25 px floor
        d = dets([[10, 10, 40, 40]] * 2 + [[50, 50, 52, 52]], [0.9, 0.8, 0.7],
                 ["a", "a_dup", "tiny"], [big, near_copy, tiny])
        out = filter_masks(d, AREA_CFG)
        self.assertEqual(out.label, ["a"])   # the higher-confidence copy is kept

    def test_clean_masks_reports_input_indices(self):
        tiny = rect(50, 52, 50, 52)
        table = rect(20, 50, 5, 75)
        d = dets([[50, 50, 52, 52], [5, 20, 75, 50]], [0.9, 0.8], ["tiny", "table"], [tiny, table])
        out, idx = clean_masks(d, AREA_CFG)
        self.assertEqual(out.label, ["table"])
        self.assertEqual(idx.tolist(), [1])
        np.testing.assert_array_equal(out.masks[0], erode_one_pixel(table))


class MeanColourEncoder:
    """A stand-in for CLIP: the crop's mean colour, centred. Enough to test the
    plumbing; it says nothing about how good a real encoder is."""

    def encode(self, crops):
        return np.stack([c.reshape(-1, 3).mean(axis=0) - 127.5 for c in crops])


class ImageFeatureTest(unittest.TestCase):
    def test_padding_is_relative_to_the_box(self):
        rgb = np.zeros((200, 200, 3), dtype=np.uint8)
        small, large = padded_crops(rgb, np.array([[90, 90, 110, 110], [50, 50, 150, 150]]), 0.1)
        self.assertEqual(small.shape[:2], (24, 24))      # 20 px box, 2 px each side
        self.assertEqual(large.shape[:2], (120, 120))    # 100 px box, 10 px each side

    def test_padding_clamped_to_image(self):
        rgb = np.zeros((50, 50, 3), dtype=np.uint8)
        (crop,) = padded_crops(rgb, np.array([[0, 0, 50, 50]]), 0.5)
        self.assertEqual(crop.shape[:2], (50, 50))

    def test_features_are_unit_length_and_same_object_scores_high(self):
        rgb = np.zeros((100, 200, 3), dtype=np.uint8)
        rgb[:, :100] = (200, 30, 30)       # a red thing on the left
        rgb[:, 100:] = (30, 30, 200)       # a blue thing on the right
        boxes = np.array([[10, 10, 40, 40], [50, 50, 90, 90], [120, 20, 180, 80]], dtype=float)
        f = image_features(rgb, boxes, MeanColourEncoder(), CFG)
        np.testing.assert_allclose(np.linalg.norm(f, axis=1), 1.0)
        self.assertGreater(f[0] @ f[1], 0.8)          # two crops of the red thing
        self.assertLess(f[0] @ f[2], f[0] @ f[1])     # red against blue

    def test_zero_vector_stays_zero(self):
        out = l2_normalise(np.array([[0.0, 0.0], [3.0, 4.0]]))
        np.testing.assert_allclose(out, [[0, 0], [0.6, 0.8]])

    def test_wrong_encoder_output_rejected(self):
        class Broken:
            def encode(self, crops):
                return np.zeros((len(crops) + 1, 4))
        with self.assertRaises(ValueError):
            image_features(np.zeros((10, 10, 3), np.uint8), np.array([[0, 0, 5, 5]]), Broken(), CFG)


if __name__ == "__main__":
    unittest.main()
