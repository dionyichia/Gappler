"""The drive runner's helpers (T6.4 step 1): the gate's pose half, and finding each
cleaned detection's CLIP vector among the raw detections'."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.run_drive import features_from_raw, moved_enough
from memory_graph.run_photo import stages_after_detection
from memory_graph.tests._fixtures import dets, patch_scene, pose, rot_z

CFG = MemoryGraphConfig()


class MovedEnoughTest(unittest.TestCase):
    def test_first_photo_is_kept(self):
        self.assertTrue(moved_enough(pose(), None, 1.0, np.pi / 4))

    def test_small_move_and_turn_are_not_enough(self):
        self.assertFalse(moved_enough(pose(rot_z(10), t=(0.5, 0, 0)), pose(), 1.0, np.pi / 4))

    def test_a_long_move_or_a_big_turn_is(self):
        self.assertTrue(moved_enough(pose(t=(1.1, 0, 0)), pose(), 1.0, np.pi / 4))
        self.assertTrue(moved_enough(pose(rot_z(50)), pose(), 1.0, np.pi / 4))


class FeaturesFromRawTest(unittest.TestCase):
    def scene(self):
        obs, masks = patch_scene([(20, 20, 60, 60, 1.5), (90, 30, 130, 80, 2.2), (10, 85, 40, 110, 1.8)])
        raw = dets([[20, 20, 60, 60], [90, 30, 130, 80], [10, 85, 40, 110]], [0.2, 0.9, 0.6],
                   ["box", "chair", "sofa"], masks)
        raw_feats = np.eye(3, 8)            # row i is raw detection i's vector
        return obs, raw, raw_feats

    def test_each_cleaned_detection_gets_its_own_vector(self):
        """S2 drops the 0.2 box and sorts the rest by score. The vectors must
        follow their detections, not their positions in the list."""
        obs, raw, raw_feats = self.scene()
        res = stages_after_detection(obs, raw, features_from_raw(raw, raw_feats), frozenset(), CFG)
        self.assertEqual(res.dets.label, ["chair", "sofa"])
        np.testing.assert_array_equal(res.features, raw_feats[[1, 2]])
        for c in res.candidates:
            self.assertEqual(int(np.argmax(c.clip)), raw.label.index(c.label))

    def test_still_right_when_s2_keeps_a_different_set(self):
        """A replay with other S2 settings (the 0.2 box kept as a target) still
        finds every vector."""
        obs, raw, raw_feats = self.scene()
        res = stages_after_detection(obs, raw, features_from_raw(raw, raw_feats), frozenset({"box"}), CFG)
        self.assertEqual(res.dets.label, ["chair", "sofa", "box"])
        np.testing.assert_array_equal(res.features, raw_feats[[1, 2, 0]])

    def test_a_detection_not_in_the_raw_output_is_an_error(self):
        obs, raw, raw_feats = self.scene()
        lookup = features_from_raw(raw, raw_feats)
        other = dets([[0, 0, 5, 5]], [0.5], ["chair"])
        with self.assertRaises(KeyError):
            lookup(other)


if __name__ == "__main__":
    unittest.main()
