"""The T6.4 scorer's rules, on made-up objects and ground truth."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.score_drive import GtObject, load_ground_truth, same_kind, score, with_settings

CLASSES = ["chair", "sofa", "desk", "table", "tv_monitor", "shelf"]


def square(cx, cy, half):
    return np.array([[cx - half, cy - half], [cx + half, cy - half], [cx + half, cy + half], [cx - half, cy + half]])


GT = [
    GtObject(1, "chair", square(0.0, 0.0, 0.3), 0.0, 0.9),
    GtObject(2, "chair", square(2.0, 0.0, 0.3), 0.0, 0.9),
    GtObject(3, "sofa", square(0.0, 3.0, 0.5), 0.0, 0.8),
    GtObject(4, "desk", square(4.0, 3.0, 0.6), 0.0, 0.75),
]


def obj(oid, label, centre, points=None, sightings=1):
    c = np.array(centre, dtype=float)
    if points is None:
        points = c + np.random.default_rng(oid).uniform(-0.1, 0.1, size=(50, 3))
    return SimpleNamespace(id=oid, label=label, box=SimpleNamespace(center=c), points=np.asarray(points), sightings=sightings)


def one_each():
    return [obj(1, "chair", (0, 0, 0.4)), obj(2, "chair", (2, 0, 0.4)),
            obj(3, "sofa", (0, 3, 0.4)), obj(4, "desk", (4, 3, 0.4))]


class ScoreTest(unittest.TestCase):
    def test_one_graph_object_per_real_object_is_clean(self):
        r = score(one_each(), GT, CLASSES)
        self.assertEqual((r["duplicates"], r["false_merges"], r["misses"], r["extras"]), (0, 0, 0, 0))
        self.assertEqual(r["label_ok"], "4 of 4")

    def test_two_objects_on_one_chair_is_a_duplicate(self):
        r = score(one_each() + [obj(5, "chair", (0.25, 0.1, 0.5))], GT, CLASSES)
        self.assertEqual(r["duplicates"], 1)
        self.assertEqual(r["duplicates_same_class"], 1)

    def test_a_part_with_another_label_counts_only_in_the_wide_number(self):
        """A shelf object on the desk: a duplicate in the wide count, not a same-class one."""
        r = score(one_each() + [obj(5, "shelf", (4.2, 3.1, 0.5))], GT, CLASSES)
        self.assertEqual((r["duplicates"], r["duplicates_same_class"]), (1, 0))

    def test_one_object_over_both_chairs_is_a_false_merge(self):
        pts = np.vstack([np.random.default_rng(0).uniform(-0.2, 0.2, (40, 3)) + [0, 0, 0.4],
                         np.random.default_rng(1).uniform(-0.2, 0.2, (40, 3)) + [2, 0, 0.4]])
        merged = obj(1, "chair", (1.0, 0, 0.4), points=pts)
        r = score([merged, obj(3, "sofa", (0, 3, 0.4)), obj(4, "desk", (4, 3, 0.4))], GT, CLASSES)
        self.assertEqual(r["false_merges"], 1)
        self.assertEqual(r["false_merge_objects"][0]["covers"], [1, 2])
        self.assertEqual(r["misses"], 2)            # its centre lands between the chairs, on neither

    def test_a_missing_object_and_a_stray_one(self):
        r = score(one_each()[:3] + [obj(9, "chair", (8, 8, 0.4))], GT, CLASSES)
        self.assertEqual((r["misses"], r["extras"]), (1, 1))
        self.assertEqual(r["extra_objects"][0]["id"], 9)

    def test_the_height_test_keeps_a_tv_off_the_sofa_below(self):
        r = score(one_each() + [obj(5, "tv_monitor", (0, 3, 1.8))], GT, CLASSES)
        self.assertEqual((r["duplicates"], r["extras"]), (0, 1))

    def test_a_table_on_a_marked_desk_is_placed_and_its_label_counts_as_right(self):
        objs = one_each()[:3] + [obj(4, "table", (4, 3, 0.4))]
        r = score(objs, GT, CLASSES)
        self.assertEqual((r["misses"], r["extras"], r["misses_same_class"]), (0, 0, 0))
        self.assertEqual(r["label_ok"], "4 of 4")
        self.assertTrue(same_kind("shelf", "cabinet"))
        self.assertFalse(same_kind("chair", "sofa"))

    def test_unscored_labels_are_left_out(self):
        r = score(one_each() + [obj(5, "book", (0, 0, 0.4))], GT, CLASSES)
        self.assertEqual((r["duplicates"], r["unscored_objects"]), (0, 1))


class LoadAndSettingsTest(unittest.TestCase):
    def test_ground_truth_file_reads_heights_from_the_floor(self):
        j = {"floor_z": -0.2, "classes": ["chair"], "objects": [
            {"id": 7, "class": "chair", "corners": square(1, 1, 0.3).tolist(),
             "z_bottom_above_floor": 0.0, "z_top_above_floor": 0.9}]}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "gt.json"
            p.write_text(json.dumps(j))
            gt, classes = load_ground_truth(p)
        self.assertEqual(classes, ["chair"])
        self.assertAlmostEqual(gt[0].z_bottom, -0.2)
        self.assertAlmostEqual(gt[0].z_top, 0.7)

    def test_settings_are_read_as_the_fields_type(self):
        cfg = with_settings(MemoryGraphConfig(), ["match_radius_m=0.05", "association_mode=one_to_one", "min_points=8"])
        self.assertEqual((cfg.match_radius_m, cfg.association_mode, cfg.min_points), (0.05, "one_to_one", 8))
        with self.assertRaises(ValueError):
            with_settings(MemoryGraphConfig(), ["no_such_field=1"])

    def test_the_committed_ground_truth_loads(self):
        gt, classes = load_ground_truth()
        self.assertEqual(len(gt), 12)
        self.assertIn("chair", classes)


if __name__ == "__main__":
    unittest.main()
