"""Checks the gaze pick rule. numpy only, runs anywhere:
    python -m unittest discover -s aria/aria_app/services/aria_segmentation_client -p "test_gaze_pick.py"
"""

import unittest

import numpy as np

from gaze_pick import pick_mask, vote


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

    def test_the_vote_picks_the_mask_looked_at_longer(self):
        # 3 points on mask 1, 2 on mask 0: their mean (7.6, 7.6) is on neither mask
        points = [(2, 2)] * 2 + [(12, 12)] * 3
        mean = np.mean(points, axis=0)
        self.assertIsNone(pick_mask(self.masks, *mean, 1)[0])
        self.assertEqual(vote(self.masks, points, 1, 0.5), (1, 0.6, 0.0))

    def test_no_mask_with_the_minimum_share_picks_nothing(self):
        # 2 of 5 on mask 1, 1 on mask 0, 2 on nothing: the best share is 0.4
        points = [(12, 12)] * 2 + [(2, 2)] + [(7, 7)] * 2
        self.assertEqual(vote(self.masks, points, 1, 0.5)[:2], (None, 0.4))
        self.assertEqual(vote(self.masks, points, 1, 0.4)[0], 1)

    def test_a_vote_tie_goes_to_the_higher_score(self):
        self.assertEqual(vote(self.masks, [(12, 12), (2, 2)], 1, 0.5)[0], 0)

    def test_no_points_or_none_in_range_picks_nothing(self):
        self.assertEqual(vote(self.masks, [], 1, 0.5), (None, 0.0, np.inf))
        self.assertIsNone(vote(self.masks, [(7, 7)], 1, 0.5)[0])


if __name__ == "__main__":
    unittest.main()
