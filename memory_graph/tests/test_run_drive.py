"""The drive runner's helper (T6.4 step 1): finding each cleaned detection's CLIP
vector among the raw detections'. The gate's pose half is anchor_gate.pose_moved,
tested in test_config_and_filters.py (T6.5)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.run_drive import features_from_raw
from memory_graph.run_photo import stages_after_detection
from memory_graph.tests._fixtures import dets, patch_scene

CFG = MemoryGraphConfig()


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
