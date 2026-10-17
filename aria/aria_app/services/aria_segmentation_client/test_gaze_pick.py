"""Checks the gaze pick rule. numpy only, runs anywhere:
    python -m unittest discover -s aria/aria_app/services/aria_segmentation_client -p "test_gaze_pick.py"
"""

import unittest

import numpy as np

from gaze_pick import mean_gaze, pick_mask


class GazePickTest(unittest.TestCase):
    def setUp(self):
        self.masks = np.zeros((2, 20, 20), dtype=bool)
        self.masks[0, 0:5, 0:5] = True       # x 0-4, y 0-4
        self.masks[1, 10:15, 10:15] = True   # x 10-14, y 10-14

    def test_the_mask_under_the_gaze_wins(self):
        self.assertEqual(pick_mask(self.masks, 12, 12, 3), (1, 0.0))

    def test_else_the_nearest_within_radius(self):
        self.assertEqual(pick_mask(self.masks, 7, 2, 3)[0], 0)

    def test_nothing_in_range_picks_nothing(self):
        self.assertIsNone(pick_mask(self.masks, 7, 7, 1)[0])

    def test_no_masks_picks_nothing(self):
        self.assertEqual(pick_mask(np.zeros((0, 20, 20), bool), 1, 1, 5), (None, np.inf))

    def test_a_tie_goes_to_the_higher_score(self):
        both = np.ones((2, 4, 4), dtype=bool)
        self.assertEqual(pick_mask(both, 1, 1, 0)[0], 0)

    def test_gaze_is_averaged_over_the_window(self):
        samples = [(0.0, 100, 100), (9.5, 10, 20), (10.0, 30, 40)]
        self.assertEqual(mean_gaze(samples, now=10.0, window_s=1.0), (20.0, 30.0))
        self.assertIsNone(mean_gaze(samples, now=20.0, window_s=1.0))


if __name__ == "__main__":
    unittest.main()
