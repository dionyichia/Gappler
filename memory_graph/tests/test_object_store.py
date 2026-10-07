"""S11: insert or merge (T6.4c)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import fit_box, voxel_downsample
from memory_graph.object_store import ObjectStore
from memory_graph.stage_types import Candidate

CFG = MemoryGraphConfig()
SIDE = 0.4          # the test object is a 0.4 m square panel
THICKNESS = 0.02    # with +-1 cm of depth noise


def panel_view(seed, centre=(0.0, 0.0, 1.0), label="chair", conf=0.9, clip=None):
    """One sighting of a flat square panel: a 1 cm grid of points with fresh
    noise for every seed, cleaned as S8 would (voxel grid, then a box)."""
    rng = np.random.default_rng(seed)
    g = np.arange(-SIDE / 2, SIDE / 2, 0.01)
    x, y = np.meshgrid(g, g)
    pts = np.stack([x.ravel(), y.ravel(), np.zeros(x.size)], axis=1)
    pts[:, :2] += rng.uniform(0, 0.01, size=(len(pts), 2))
    pts[:, 2] += rng.uniform(-THICKNESS / 2, THICKNESS / 2, size=len(pts))
    pts += np.asarray(centre)
    pts, cols = voxel_downsample(pts, np.full_like(pts, 0.5), CFG.voxel_size_m)
    return Candidate(points=pts, colors=cols, box=fit_box(pts), label=label, conf=conf,
                     clip=clip, mask_pixels=1000 + seed)


class TenViewsTest(unittest.TestCase):
    def test_ten_views_give_one_entry(self):
        """The T6.4c done-when: 10 views of one object give 1 entry with 10
        labels and 10 sightings and a bounded point count."""
        store = ObjectStore(CFG)
        fed = 0
        for view in range(10):
            cand = panel_view(view)
            fed += len(cand.points)
            self.assertEqual(store.integrate([cand], anchor=100 + view), [0])
            self.assertEqual(store.check_invariants(), [])
        self.assertEqual(len(store), 1)
        entry = store.get(0)
        self.assertEqual(len(entry.labels), 10)
        self.assertEqual(entry.sightings, 10)
        self.assertEqual(store.graph.degree(0), 10)
        # Bounded by the voxels the panel can touch, however many views arrive.
        v = CFG.voxel_size_m
        voxels = (SIDE / v + 1) ** 2 * (THICKNESS / v + 1)
        self.assertLessEqual(len(entry.points), voxels)
        self.assertLess(len(entry.points), fed / 4)

    def test_each_sighting_records_its_anchor(self):
        """The hook for D-MG9: an entry can be rebuilt from its anchors."""
        store = ObjectStore(CFG)
        for view in range(3):
            store.integrate([panel_view(view)], anchor=100 + view)
        self.assertEqual(store.get(0).anchor_ids, [100, 101, 102])
        self.assertEqual(store.graph.anchors_of(0), frozenset({100, 101, 102}))

    def test_an_entry_outlives_its_anchors(self):
        """The graph forgets an object with no anchor left. The store does not."""
        store = ObjectStore(CFG)
        store.integrate([panel_view(0)], anchor=1)
        store.graph.remove_anchor(1)
        self.assertEqual(store.graph.objects(), frozenset())
        self.assertEqual(store.ids(), [0])
        self.assertEqual(store.check_invariants(), [])
        self.assertEqual(store.integrate([panel_view(1)], anchor=2), [0])    # and it still matches

    def test_an_object_elsewhere_is_a_new_entry(self):
        store = ObjectStore(CFG)
        store.integrate([panel_view(0)], anchor=1)
        went_to = store.integrate([panel_view(1), panel_view(2, centre=(2.0, 0.0, 1.0), label="sofa")], anchor=2)
        self.assertEqual(went_to, [0, 1])
        self.assertEqual(store.ids(), [0, 1])
        self.assertEqual(store.get(1).sightings, 1)
        self.assertEqual(store.graph.objects_of(2), frozenset({0, 1}))
        self.assertEqual(store.check_invariants(), [])

    def test_the_box_follows_the_merged_cloud(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0)], [None], anchor=1)
        store.apply([panel_view(1, centre=(0.3, 0.0, 1.0))], [0], anchor=2)
        entry = store.get(0)
        self.assertAlmostEqual(float(entry.box.center[0]), 0.15, delta=0.03)
        self.assertAlmostEqual(float(max(entry.box.extent)), 0.7, delta=0.05)


class FeatureTest(unittest.TestCase):
    A = np.array([1.0, 0.0, 0.0])
    B = np.array([0.0, 1.0, 0.0])

    def test_feature_is_the_sighting_average_renormalised(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0, clip=self.A)], [None], anchor=1)
        store.apply([panel_view(1, clip=self.A)], [0], anchor=2)
        store.apply([panel_view(2, clip=self.B)], [0], anchor=3)
        expected = np.array([2.0, 1.0, 0.0]) / np.sqrt(5.0)
        np.testing.assert_allclose(store.get(0).clip, expected)
        self.assertAlmostEqual(float(np.linalg.norm(store.get(0).clip)), 1.0)

    def test_a_sighting_without_a_feature_does_not_dilute_it(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0, clip=self.A)], [None], anchor=1)
        store.apply([panel_view(1)], [0], anchor=2)
        np.testing.assert_allclose(store.get(0).clip, self.A)
        self.assertEqual(store.get(0).clip_count, 1)
        self.assertEqual(store.get(0).sightings, 2)

    def test_no_feature_at_all_is_none(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0)], [None], anchor=1)
        self.assertIsNone(store.get(0).clip)

    def test_an_unnormalised_feature_gets_no_extra_weight(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0, clip=10 * self.A)], [None], anchor=1)
        store.apply([panel_view(1, clip=self.B)], [0], anchor=2)
        np.testing.assert_allclose(store.get(0).clip, np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0))


class LabelTest(unittest.TestCase):
    def test_label_is_the_majority_and_the_index_follows_it(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0, label="chair")], [None], anchor=1)
        self.assertEqual(store.ids_with_label("chair"), frozenset({0}))
        store.apply([panel_view(1, label="stool")], [0], anchor=2)
        self.assertEqual(store.get(0).label, "chair")              # a tie goes to the first seen
        store.apply([panel_view(2, label="stool")], [0], anchor=3)
        self.assertEqual(store.get(0).label, "stool")
        # Upstream leaves the entry under "chair" as well. Here it moves.
        self.assertEqual(store.ids_with_label("chair"), frozenset())
        self.assertEqual(store.ids_with_label("stool"), frozenset({0}))
        self.assertEqual(store.check_invariants(), [])


class SamePhotoTest(unittest.TestCase):
    def test_new_candidates_from_one_photo_stay_separate(self):
        store = ObjectStore(CFG)
        went_to = store.integrate([panel_view(0), panel_view(1)], anchor=1)
        self.assertEqual(went_to, [0, 1])

    def test_two_candidates_may_merge_into_one_entry(self):
        """Greedy matching, D-MG8: both are fused, and the one edge counts two."""
        store = ObjectStore(CFG)
        store.integrate([panel_view(0)], anchor=1)
        went_to = store.integrate([panel_view(1), panel_view(2)], anchor=2)
        self.assertEqual(went_to, [0, 0])
        self.assertEqual(store.get(0).sightings, 3)
        self.assertEqual(store.graph.sighting(2, 0).detections, 2)
        self.assertEqual(store.graph.degree(0), 2)
        self.assertEqual(store.check_invariants(), [])


class MergeObjectsTest(unittest.TestCase):
    def setUp(self):
        self.store = ObjectStore(CFG)
        self.store.apply([panel_view(0, label="chair", clip=FeatureTest.A)], [None], anchor=1)
        self.store.apply([panel_view(1, label="stool", clip=FeatureTest.B)], [None], anchor=2)
        self.store.apply([panel_view(2, label="stool", clip=FeatureTest.B)], [1], anchor=3)

    def test_the_survivor_takes_everything(self):
        self.store.merge_objects(0, 1)
        self.assertEqual(self.store.ids(), [0])
        entry = self.store.get(0)
        self.assertEqual(entry.labels, ["chair", "stool", "stool"])
        self.assertEqual(entry.anchor_ids, [1, 2, 3])
        self.assertEqual(entry.label, "stool")
        np.testing.assert_allclose(entry.clip, np.array([1.0, 2.0, 0.0]) / np.sqrt(5.0))
        self.assertEqual(self.store.graph.anchors_of(0), frozenset({1, 2, 3}))
        self.assertEqual(self.store.graph.objects(), frozenset({0}))
        self.assertEqual(self.store.ids_with_label("stool"), frozenset({0}))
        self.assertEqual(self.store.ids_with_label("chair"), frozenset())
        self.assertEqual(self.store.check_invariants(), [])

    def test_ids_are_never_reused(self):
        self.store.merge_objects(0, 1)
        went_to = self.store.apply([panel_view(3, centre=(5.0, 0.0, 1.0))], [None], anchor=4)
        self.assertEqual(went_to, [2])

    def test_merging_an_entry_with_itself_does_nothing(self):
        self.store.merge_objects(1, 1)
        self.assertEqual(self.store.get(1).sightings, 2)


class BadInputTest(unittest.TestCase):
    def test_unknown_target_is_an_error_and_changes_nothing(self):
        store = ObjectStore(CFG)
        with self.assertRaises(KeyError):
            store.apply([panel_view(0), panel_view(1)], [None, 7], anchor=1)
        self.assertEqual(len(store), 0)
        self.assertEqual(len(store.graph), 0)

    def test_targets_must_match_candidates(self):
        with self.assertRaises(ValueError):
            ObjectStore(CFG).apply([panel_view(0)], [], anchor=1)


if __name__ == "__main__":
    unittest.main()
