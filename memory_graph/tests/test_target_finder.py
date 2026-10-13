"""Find targets (T6.8a)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.anchor_store import AnchorStore
from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import build_candidates
from memory_graph.object_store import ObjectStore
from memory_graph.target_finder import RELATED, TARGET, TargetFinder
from memory_graph.task import TaskContext
from memory_graph.tests._fixtures import K, dets, patch_scene, pose

CFG = MemoryGraphConfig.from_dict({"anchor_height": 96, "anchor_width": 64})

# A three-number feature space, one axis per kind of thing.
CHAIR = np.array([1.0, 0.0, 0.0])
SOFA = np.array([0.0, 1.0, 0.0])
PLANT = np.array([0.0, 0.0, 1.0])

# The room: two chairs and a table in front of a wall, as
# (u0, v0, u1, v1, depth in metres) for a camera at the origin. The second
# chair looks half like a sofa, so it scores lower for "find a chair".
PATCHES = [(10, 30, 40, 70, 1.5), (60, 30, 90, 70, 1.5), (110, 40, 150, 90, 2.0)]
LABELS = ["chair", "chair", "table"]
FEATURES = np.array([CHAIR, CHAIR + SOFA, PLANT])
GOOD_CHAIR, ODD_CHAIR, TABLE = 0, 1, 2      # the ids the first photo gives them


def chair_task(targets=("chair",), related=("table",)):
    return TaskContext("find a chair", CHAIR, frozenset(targets), frozenset(related))


def store_photo(objects, anchors, frame_id, shift_m=0.0, conf=0.8, labels=LABELS):
    """Store one photo of the room from a camera moved `shift_m` to its right."""
    moved = []
    for u0, v0, u1, v1, d in PATCHES:
        du = int(round(K[0, 0] * shift_m / d))
        moved.append((u0 - du, v0, u1 - du, v1, d))
    obs, masks = patch_scene(moved, T_world_cam=pose(t=(shift_m, 0.0, 0.0)), seed=frame_id)
    obs.frame_id = frame_id
    d = dets([p[:4] for p in moved], [conf] * 3, list(labels), masks=masks)
    cands = build_candidates(obs, d, CFG, features=FEATURES)
    ids = objects.integrate(cands, anchor=frame_id)
    anchors.add(obs, d, cands, ids)
    return ids


def room(task=None, photos=((1, 0.0, 0.6), (2, 0.09, 0.9), (3, 0.0, 0.7))):
    """The room seen in three photos, as (frame id, camera shift, confidence).
    Photo 2 has the highest confidence, so it is every object's best view."""
    objects = ObjectStore(CFG, task=chair_task() if task is None else task)
    anchors = AnchorStore(CFG, objects.graph)
    for frame_id, shift, conf in photos:
        store_photo(objects, anchors, frame_id, shift, conf)
    return objects, anchors, TargetFinder(objects, anchors)


class FindTest(unittest.TestCase):
    def setUp(self):
        self.objects, self.anchors, self.finder = room()

    def test_the_room_is_three_objects(self):
        self.assertEqual(self.objects.ids(), [GOOD_CHAIR, ODD_CHAIR, TABLE])
        self.assertEqual(len(self.anchors), 3)

    def test_targets_first_then_related_each_by_score(self):
        hits = self.finder.find()
        self.assertEqual([h.object_id for h in hits], [GOOD_CHAIR, ODD_CHAIR, TABLE])
        self.assertEqual([h.kind for h in hits], [TARGET, TARGET, RELATED])
        self.assertEqual([h.label for h in hits], ["chair", "chair", "table"])
        self.assertAlmostEqual(hits[0].task_score, 1.0)
        self.assertAlmostEqual(hits[1].task_score, 1.0 / np.sqrt(2.0))
        self.assertAlmostEqual(hits[2].task_score, 0.0)

    def test_a_related_object_never_outranks_a_target(self):
        """The table is related only. Give the task the table's feature and it
        still comes after both chairs."""
        self.objects.set_task(TaskContext("find a chair", PLANT, frozenset({"chair"}), frozenset({"table"})))
        self.assertEqual([h.object_id for h in self.finder.find()][-1], TABLE)

    def test_targets_only(self):
        self.assertEqual([h.object_id for h in self.finder.find(include_related=False)], [GOOD_CHAIR, ODD_CHAIR])

    def test_a_hit_says_where_the_object_is(self):
        for hit in self.finder.find():
            entry = self.objects.get(hit.object_id)
            np.testing.assert_allclose(hit.position, entry.box.center)
            np.testing.assert_allclose(hit.extent, entry.box.extent)
            self.assertEqual(hit.sightings, 3)
        # The good chair: 15 px left of centre at 1.5 m, with fx = 100.
        chair = self.finder.find()[0]
        self.assertAlmostEqual(float(chair.position[2]), 1.5, delta=0.02)
        self.assertLess(float(chair.position[0]), -0.5)

    def test_a_hit_is_a_copy(self):
        hit = self.finder.find()[0]
        hit.position[:] = 99.0
        self.assertLess(abs(float(self.objects.get(GOOD_CHAIR).box.center[0])), 5.0)

    def test_no_task_finds_nothing(self):
        self.objects.set_task(None)
        self.assertEqual(self.finder.find(), [])

    def test_an_object_of_no_task_class_is_not_a_hit(self):
        self.objects.set_task(chair_task(related=()))
        self.assertEqual([h.object_id for h in self.finder.find()], [GOOD_CHAIR, ODD_CHAIR])

    def test_a_class_is_judged_by_the_majority_label(self):
        """Four more photos call the odd chair a sofa, against three that called
        it a chair. It stops being a target."""
        for frame_id in (4, 5, 6, 7):
            store_photo(self.objects, self.anchors, frame_id, labels=["chair", "sofa", "table"])
        self.assertEqual(self.objects.get(ODD_CHAIR).label, "sofa")
        self.assertEqual([h.object_id for h in self.finder.find()], [GOOD_CHAIR, TABLE])


class BestViewTest(unittest.TestCase):
    def setUp(self):
        self.objects, self.anchors, self.finder = room()

    def test_the_best_view_is_the_most_confident_photo(self):
        for hit in self.finder.find():
            self.assertEqual(hit.anchor_id, 2)

    def test_the_box_is_where_the_object_is_on_that_photo(self):
        """The object's centre, projected into the best photo, is inside the box
        the hit gives. So the box can be shown to a person or a model."""
        for hit in self.finder.find():
            record = self.anchors.get(hit.anchor_id)
            u, v = record.project(hit.position)
            x0, y0, x1, y1 = hit.box_on_anchor
            self.assertTrue(x0 <= u <= x1 and y0 <= v <= y1)

    def test_the_next_best_photo_takes_over_when_one_is_removed(self):
        self.anchors.remove(2)
        self.assertEqual({h.anchor_id for h in self.finder.find()}, {3})     # conf 0.7 beats 0.6

    def test_equal_views_go_to_the_newest_photo(self):
        _, _, finder = room(photos=((1, 0.0, 0.8), (2, 0.0, 0.8)))
        self.assertEqual(finder.best_anchor(TABLE), 2)

    def test_an_object_with_no_photo_left_is_still_a_hit(self):
        for anchor in (1, 2, 3):
            self.anchors.remove(anchor)
        hits = self.finder.find()
        self.assertEqual([h.object_id for h in hits], [GOOD_CHAIR, ODD_CHAIR, TABLE])
        self.assertTrue(all(h.anchor_id is None and h.box_on_anchor is None for h in hits))

    def test_a_photo_without_a_record_is_not_offered(self):
        """Pruned from the graph's side only: the record is still there but the
        edge is gone, so the photo is not a view of the object."""
        self.objects.graph.remove_anchor(2)
        self.assertEqual({h.anchor_id for h in self.finder.find()}, {3})


class RejectTest(unittest.TestCase):
    """The write-back: an object rejected on arrival is not offered again."""

    def setUp(self):
        self.objects, self.anchors, self.finder = room()

    def ids(self):
        return [h.object_id for h in self.finder.find()]

    def test_a_rejected_object_is_not_offered_again(self):
        self.finder.reject(GOOD_CHAIR)
        self.assertEqual(self.ids(), [ODD_CHAIR, TABLE])
        self.assertEqual(self.finder.rejected, frozenset({GOOD_CHAIR}))

    def test_the_robot_runs_out_of_candidates_instead_of_looping(self):
        """Go to the first hit, reject it, ask again. Three objects, so the list
        is empty after three trips, and no object is visited twice."""
        visited = []
        while self.finder.find():
            first = self.finder.find()[0].object_id
            visited.append(first)
            self.finder.reject(first)
            self.assertLess(len(visited), 10)
        self.assertEqual(visited, [GOOD_CHAIR, ODD_CHAIR, TABLE])

    def test_it_stays_rejected_when_seen_again(self):
        self.finder.reject(GOOD_CHAIR)
        store_photo(self.objects, self.anchors, 4)
        self.assertEqual(self.objects.get(GOOD_CHAIR).sightings, 4)
        self.assertEqual(self.ids(), [ODD_CHAIR, TABLE])

    def test_it_stays_rejected_when_the_classes_change(self):
        self.finder.reject(GOOD_CHAIR)
        self.objects.set_task(self.objects.task.with_classes(["chair", "table"]))
        self.assertEqual(self.ids(), [ODD_CHAIR, TABLE])

    def test_a_new_instruction_starts_clean(self):
        self.finder.reject(GOOD_CHAIR)
        self.objects.set_task(TaskContext("find a seat", CHAIR, frozenset({"chair"})))
        self.assertEqual(self.finder.rejected, frozenset())
        self.assertEqual(self.ids(), [GOOD_CHAIR, ODD_CHAIR])

    def test_clear_rejected(self):
        self.finder.reject(GOOD_CHAIR)
        self.finder.clear_rejected()
        self.assertEqual(self.ids(), [GOOD_CHAIR, ODD_CHAIR, TABLE])

    def test_rejecting_an_unknown_object_is_an_error(self):
        with self.assertRaises(KeyError):
            self.finder.reject(77)
        self.assertEqual(self.finder.rejected, frozenset())

    def merge(self, surviving, absorbed):
        self.objects.merge_objects(surviving, absorbed)
        self.anchors.merge_objects(surviving, absorbed)

    def test_a_rejection_follows_the_object_into_a_merge(self):
        """The rejected chair turns out to be part of the other chair's entry.
        That entry is the same physical object, so it is rejected too."""
        self.finder.reject(ODD_CHAIR)
        self.merge(GOOD_CHAIR, ODD_CHAIR)
        self.assertEqual(self.finder.check_invariants(), ["rejected object 1 has no entry"])
        self.finder.merge_objects(GOOD_CHAIR, ODD_CHAIR)
        self.assertEqual(self.finder.check_invariants(), [])
        self.assertEqual(self.finder.rejected, frozenset({GOOD_CHAIR}))
        self.assertEqual(self.ids(), [TABLE])

    def test_a_rejected_survivor_stays_rejected(self):
        self.finder.reject(GOOD_CHAIR)
        self.merge(GOOD_CHAIR, ODD_CHAIR)
        self.finder.merge_objects(GOOD_CHAIR, ODD_CHAIR)
        self.assertEqual(self.ids(), [TABLE])
        self.assertEqual(self.finder.check_invariants(), [])

    def test_a_merge_of_two_good_objects_rejects_nothing(self):
        self.merge(GOOD_CHAIR, ODD_CHAIR)
        self.finder.merge_objects(GOOD_CHAIR, ODD_CHAIR)
        self.assertEqual(self.ids(), [GOOD_CHAIR, TABLE])
        hit = self.finder.find()[0]
        self.assertEqual(hit.sightings, 6)
        self.assertEqual(self.anchors.check_invariants(), [])


class SetupTest(unittest.TestCase):
    def test_the_two_stores_must_share_a_graph(self):
        objects = ObjectStore(CFG)
        with self.assertRaises(ValueError):
            TargetFinder(objects, AnchorStore(CFG, ObjectStore(CFG).graph))

    def test_an_empty_graph_finds_nothing(self):
        objects = ObjectStore(CFG, task=chair_task())
        finder = TargetFinder(objects, AnchorStore(CFG, objects.graph))
        self.assertEqual(finder.find(), [])
        self.assertEqual(finder.check_invariants(), [])


if __name__ == "__main__":
    unittest.main()
