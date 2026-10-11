"""Task conditioning inside the graph (T6.7a).

A stand-in encoder is used here, so the tests need no model. The same scoring
with the real encoder is in test_clip_encoder.py (Use3).
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.anchor_gate import AnchorGate
from memory_graph.config import MemoryGraphConfig
from memory_graph.object_store import ObjectStore
from memory_graph.task import TaskContext
from memory_graph.tests._fixtures import pose
from memory_graph.tests.test_object_store import panel_view

CFG = MemoryGraphConfig()

# A three-number feature space: one axis each for chair, sofa and plant.
CHAIR = np.array([1.0, 0.0, 0.0])
SOFA = np.array([0.0, 1.0, 0.0])
PLANT = np.array([0.0, 0.0, 1.0])
HERE = (0.0, 0.0, 1.0)
THERE = (2.0, 0.0, 1.0)
FAR = (4.0, 0.0, 1.0)


class WordEncoder:
    """Stand-in text encoder: a sentence is the sum of the axes of the words in
    it, at an arbitrary length, as the real encoder's output is not normalised."""

    AXES = {"chair": CHAIR, "sofa": SOFA, "plant": PLANT}

    def __init__(self):
        self.calls = 0

    def encode_text(self, texts):
        self.calls += 1
        return np.array([7.0 * sum((self.AXES[w] for w in t.split() if w in self.AXES), np.zeros(3))
                         for t in texts])


def chair_task(**kwargs):
    return TaskContext.from_text("find a chair", WordEncoder(), **kwargs)


class TaskContextTest(unittest.TestCase):
    def test_the_instruction_is_embedded_and_normalised(self):
        task = chair_task()
        np.testing.assert_allclose(task.feature, CHAIR)
        self.assertEqual(task.instruction, "find a chair")

    def test_score_is_the_cosine(self):
        task = chair_task()
        self.assertAlmostEqual(task.score(CHAIR), 1.0)
        self.assertAlmostEqual(task.score(SOFA), 0.0)
        self.assertAlmostEqual(task.score(-CHAIR), -1.0)
        self.assertAlmostEqual(task.score(CHAIR + SOFA), 1.0 / np.sqrt(2.0))

    def test_score_ignores_the_length_of_the_feature(self):
        task = chair_task()
        self.assertAlmostEqual(task.score(50.0 * (CHAIR + SOFA)), task.score(CHAIR + SOFA))

    def test_no_feature_scores_zero(self):
        task = chair_task()
        self.assertEqual(task.score(None), 0.0)
        self.assertEqual(task.score(np.zeros(3)), 0.0)

    def test_a_feature_from_another_encoder_is_an_error(self):
        with self.assertRaises(ValueError):
            chair_task().score(np.ones(5))

    def test_a_task_needs_a_usable_feature(self):
        for bad in (np.zeros(3), np.array([1.0, np.nan, 0.0]), np.zeros(0)):
            with self.assertRaises(ValueError):
                TaskContext("find a chair", bad)

    def test_photo_score_is_the_sum_over_its_objects(self):
        """Upstream's task_score for a photo (map_elements.py:322)."""
        task = chair_task()
        self.assertAlmostEqual(task.photo_score(np.array([CHAIR, CHAIR, SOFA])), 2.0)
        self.assertAlmostEqual(task.photo_score(np.array([3.0 * CHAIR])), 1.0)
        self.assertEqual(task.photo_score(np.zeros((0, 3))), 0.0)
        self.assertEqual(task.photo_score(None), 0.0)

    def test_class_sets(self):
        task = chair_task(targets=["chair"], related=["table", "chair"])
        self.assertEqual(task.targets, frozenset({"chair"}))
        self.assertEqual(task.related, frozenset({"table"}))     # a target is not also related
        self.assertEqual(task.classes, frozenset({"chair", "table"}))

    def test_new_classes_do_not_embed_the_instruction_again(self):
        encoder = WordEncoder()
        task = TaskContext.from_text("find a chair", encoder, targets=["chair"])
        wider = task.with_classes(["chair", "armchair"], ["table"])
        self.assertEqual(encoder.calls, 1)
        self.assertEqual(wider.targets, frozenset({"chair", "armchair"}))
        np.testing.assert_allclose(wider.feature, task.feature)
        self.assertEqual(task.targets, frozenset({"chair"}))      # the old one is unchanged

    def test_the_classes_feed_the_anchor_gate(self):
        """S3 keeps a photo that shows a target or a related class even when the
        camera has not moved."""
        task = chair_task(targets=["chair"], related=["table"])
        gate = AnchorGate(CFG)
        gate.commit(pose())
        self.assertFalse(gate.check(pose(), ["plant"], task.classes))
        self.assertTrue(gate.check(pose(), ["plant", "table"], task.classes))


class ObjectScoreTest(unittest.TestCase):
    """The score upstream never sets: cos(object feature, task feature), on
    insert and on merge."""

    def test_set_on_insert(self):
        store = ObjectStore(CFG, task=chair_task())
        store.apply([panel_view(0, clip=CHAIR), panel_view(1, centre=THERE, clip=SOFA)], [None, None], anchor=1)
        self.assertAlmostEqual(store.get(0).task_score, 1.0)
        self.assertAlmostEqual(store.get(1).task_score, 0.0)
        self.assertEqual(store.check_invariants(), [])

    def test_follows_the_feature_on_merge(self):
        store = ObjectStore(CFG, task=chair_task())
        store.apply([panel_view(0, clip=CHAIR)], [None], anchor=1)
        store.apply([panel_view(1, clip=SOFA)], [0], anchor=2)
        self.assertAlmostEqual(store.get(0).task_score, 1.0 / np.sqrt(2.0))
        store.apply([panel_view(2, clip=CHAIR)], [0], anchor=3)
        self.assertAlmostEqual(store.get(0).task_score, 2.0 / np.sqrt(5.0))
        self.assertAlmostEqual(store.get(0).task_score, store.task.score(store.get(0).clip))
        self.assertEqual(store.check_invariants(), [])

    def test_follows_the_feature_when_two_entries_are_merged(self):
        store = ObjectStore(CFG, task=chair_task())
        store.apply([panel_view(0, clip=SOFA), panel_view(1, centre=THERE, clip=CHAIR)], [None, None], anchor=1)
        self.assertAlmostEqual(store.get(0).task_score, 0.0)
        store.merge_objects(0, 1)
        self.assertAlmostEqual(store.get(0).task_score, 1.0 / np.sqrt(2.0))
        self.assertEqual(store.check_invariants(), [])

    def test_through_association_too(self):
        """integrate (S10 then S11), not only apply."""
        store = ObjectStore(CFG, task=chair_task())
        for view in range(4):
            store.integrate([panel_view(view, clip=CHAIR)], anchor=view)
            self.assertEqual(store.check_invariants(), [])
        self.assertEqual(len(store), 1)
        self.assertAlmostEqual(store.get(0).task_score, 1.0)

    def test_no_task_or_no_feature_is_zero(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0, clip=CHAIR)], [None], anchor=1)
        self.assertEqual(store.get(0).task_score, 0.0)
        store = ObjectStore(CFG, task=chair_task())
        store.apply([panel_view(0)], [None], anchor=1)
        self.assertEqual(store.get(0).task_score, 0.0)
        self.assertEqual(store.check_invariants(), [])

    def test_a_new_task_rescores_every_entry(self):
        store = ObjectStore(CFG)
        store.apply([panel_view(0, clip=CHAIR), panel_view(1, centre=THERE, clip=SOFA)], [None, None], anchor=1)
        store.set_task(chair_task())
        self.assertEqual([store.get(i).task_score for i in (0, 1)], [1.0, 0.0])
        store.set_task(TaskContext.from_text("find a sofa", WordEncoder()))
        self.assertEqual([store.get(i).task_score for i in (0, 1)], [0.0, 1.0])
        store.set_task(None)
        self.assertEqual([store.get(i).task_score for i in (0, 1)], [0.0, 0.0])
        self.assertEqual(store.check_invariants(), [])

    def test_a_stale_score_is_reported(self):
        store = ObjectStore(CFG, task=chair_task())
        store.apply([panel_view(0, clip=CHAIR)], [None], anchor=1)
        store.get(0).task_score = 0.2
        self.assertEqual(store.check_invariants(), ["object 0 has a stale task score"])

    def test_ranked_by_task(self):
        store = ObjectStore(CFG, task=chair_task())
        store.apply(
            [panel_view(0, clip=SOFA), panel_view(1, centre=THERE, clip=CHAIR),
             panel_view(2, centre=FAR, clip=CHAIR + SOFA)],
            [None, None, None], anchor=1)
        self.assertEqual(store.ranked_by_task(), [1, 2, 0])
        self.assertEqual(store.ranked_by_task([0, 2]), [2, 0])
        store.set_task(None)
        self.assertEqual(store.ranked_by_task(), [0, 1, 2])      # all equal: id order


class ClassLookupTest(unittest.TestCase):
    def setUp(self):
        self.store = ObjectStore(CFG, task=chair_task(targets=["chair"], related=["table"]))
        self.store.apply(
            [panel_view(0, label="chair"), panel_view(1, centre=THERE, label="table"),
             panel_view(2, centre=FAR, label="plant")],
            [None, None, None], anchor=1)

    def test_targets_and_related_by_label(self):
        self.assertEqual(self.store.target_ids(), frozenset({0}))
        self.assertEqual(self.store.related_ids(), frozenset({1}))

    def test_an_entry_leaves_when_its_majority_label_changes(self):
        """Upstream's stale index: it adds an object under its new label and
        never removes it from the old one."""
        for view, anchor in ((3, 2), (4, 3)):
            self.store.apply([panel_view(view, label="plant")], [0], anchor=anchor)
        self.assertEqual(self.store.get(0).label, "plant")
        self.assertEqual(self.store.target_ids(), frozenset())

    def test_an_absorbed_entry_leaves(self):
        self.store.merge_objects(2, 0)
        self.assertEqual(self.store.target_ids(), frozenset())
        self.assertEqual(self.store.check_invariants(), [])

    def test_new_class_sets_change_the_lookup_at_once(self):
        self.store.set_task(self.store.task.with_classes(["plant", "chair"]))
        self.assertEqual(self.store.target_ids(), frozenset({0, 2}))
        self.assertEqual(self.store.related_ids(), frozenset())

    def test_no_task_gives_nothing(self):
        self.store.set_task(None)
        self.assertEqual(self.store.target_ids(), frozenset())
        self.assertEqual(self.store.related_ids(), frozenset())


if __name__ == "__main__":
    unittest.main()
