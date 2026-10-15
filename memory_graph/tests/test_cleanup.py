"""S13: periodic clean-up (T6.4f)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.anchor_store import AnchorStore
from memory_graph.cleanup import PeriodicCleanup, denoise_objects, prune_anchors, view_cost
from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import build_candidates, fit_box
from memory_graph.object_store import ObjectStore
from memory_graph.stage_types import Candidate
from memory_graph.target_finder import TargetFinder
from memory_graph.task import TaskContext
from memory_graph.tests._fixtures import H, K, W, dets, patch_scene, pose
from memory_graph.tests.test_object_store import panel_view

SMALL = {"anchor_height": 48, "anchor_width": 64}      # small stored photos keep the tests quick


def config(**values):
    return MemoryGraphConfig.from_dict({**SMALL, **values})


# ---------------------------------------------------------------- the room
#
# Six objects in a row along a wall, 0.6 m apart, 1 m in front of the camera's
# track. The camera moves along the row in 0.3 m steps and looks straight at
# the wall. At 1 m the image is 1.6 m wide, so each photo shows two or three
# objects, and neighbouring photos overlap.

OBJECT_X = [-1.2, -0.6, 0.0, 0.6, 1.2, 1.8]
DEPTH = 1.0
HALF_WIDTH_PX = 15
STOPS = [round(-1.2 + 0.3 * i, 1) for i in range(11)]
FX = K[0, 0]


def room_photo(frame_id, camera_x, conf=0.8):
    """The photo taken from `camera_x`, and the indices of the objects in it.
    An object is in the photo only if all of it is."""
    patches, seen = [], []
    for i, x in enumerate(OBJECT_X):
        u = int(round(W / 2 + FX * (x - camera_x) / DEPTH))
        if u - HALF_WIDTH_PX >= 0 and u + HALF_WIDTH_PX <= W:
            patches.append((u - HALF_WIDTH_PX, 45, u + HALF_WIDTH_PX, 75, DEPTH))
            seen.append(i)
    obs, masks = patch_scene(patches, wall_depth=2.0, T_world_cam=pose(t=(camera_x, 0.0, 0.0)), seed=frame_id)
    obs.frame_id = frame_id
    return obs, dets([p[:4] for p in patches], [conf] * len(patches), ["box"] * len(patches), masks=masks), seen


def store(objects, anchors, obs, d):
    cands = build_candidates(obs, d, objects.cfg)
    return anchors.add(obs, d, cands, objects.integrate(cands, anchor=obs.frame_id))


def new_stores(cfg):
    objects = ObjectStore(cfg)
    return objects, AnchorStore(cfg, objects.graph)


def drive(objects, anchors, first_frame_id, conf=0.8):
    """One pass along the row: a photo at every stop."""
    for i, x in enumerate(STOPS):
        store(objects, anchors, *room_photo(first_frame_id + i, x, conf)[:2])


def consistent(case, objects, anchors):
    case.assertEqual(objects.check_invariants(), [])
    case.assertEqual(anchors.check_invariants(), [])


class DoneWhenTest(unittest.TestCase):
    """The T6.4f done-when: every object keeps at least min(kappa, photos that
    saw it) anchors, and the anchor count stops growing on a second pass
    through a room."""

    def test_the_room_is_six_objects(self):
        objects, anchors = new_stores(config())
        drive(objects, anchors, 0)
        self.assertEqual(len(objects), 6)
        self.assertEqual(len(anchors), 11)
        self.assertEqual(sorted(objects.graph.degree(o) for o in objects.ids()), [3, 3, 5, 5, 5, 5])

    def test_every_object_keeps_enough_anchors(self):
        for kappa in (1, 2, 3, 4, 9):
            with self.subTest(kappa=kappa):
                objects, anchors = new_stores(config(prune_kappa=kappa))
                drive(objects, anchors, 0)
                before = {o: objects.graph.degree(o) for o in objects.ids()}
                report = PeriodicCleanup(objects, anchors).run()
                for obj, seen_by in before.items():
                    self.assertGreaterEqual(objects.graph.degree(obj), min(kappa, seen_by))
                self.assertEqual(len(anchors), report.anchors_after)
                self.assertEqual(len(objects), 6)                 # objects are never deleted
                consistent(self, objects, anchors)

    def test_pruning_removes_photos(self):
        """Not just "keeps enough": with kappa 1, two photos of three objects
        each cover all six."""
        objects, anchors = new_stores(config())
        drive(objects, anchors, 0)
        report = PeriodicCleanup(objects, anchors).run()
        self.assertEqual(report.anchors_before, 11)
        self.assertEqual(report.anchors_after, 2)
        self.assertEqual(len(report.anchors_evicted), 9)

    def test_more_kappa_keeps_more_photos(self):
        kept = []
        for kappa in (1, 2, 3):
            objects, anchors = new_stores(config(prune_kappa=kappa))
            drive(objects, anchors, 0)
            kept.append(PeriodicCleanup(objects, anchors).run().anchors_after)
        self.assertEqual(kept, sorted(kept))
        self.assertLess(kept[0], kept[2])
        self.assertLess(kept[2], 11)

    def test_a_second_pass_does_not_grow_the_anchor_count(self):
        for kappa in (1, 2, 3):
            with self.subTest(kappa=kappa):
                objects, anchors = new_stores(config(prune_kappa=kappa))
                cleanup = PeriodicCleanup(objects, anchors)
                counts = []
                for lap in range(4):
                    drive(objects, anchors, 100 * lap)
                    cleanup.run()
                    counts.append(len(anchors))
                    consistent(self, objects, anchors)
                self.assertEqual(len(objects), 6)                 # and no duplicate objects
                self.assertEqual(counts[1:], [counts[0]] * 3, f"anchors after each lap: {counts}")

    def test_without_the_clean_up_it_does_grow(self):
        """What the second-pass check is there to catch."""
        objects, anchors = new_stores(config())
        drive(objects, anchors, 0)
        drive(objects, anchors, 100)
        self.assertEqual(len(anchors), 22)

    def test_no_kept_photo_is_covered_by_another(self):
        """Upstream's check for kappa 1: no kept photo's objects are a subset
        of another kept photo's."""
        objects, anchors = new_stores(config())
        drive(objects, anchors, 0)
        drive(objects, anchors, 100)
        PeriodicCleanup(objects, anchors).run()
        shown = [objects.graph.objects_of(a) for a in anchors.ids()]
        for i, a in enumerate(shown):
            for j, b in enumerate(shown):
                self.assertFalse(i != j and a <= b)


class DenoiseTest(unittest.TestCase):
    CFG = config()

    def stray_points(self, n=6, at=(1.5, 0.0, 1.0)):
        """A few points far from the object, as a mask that spilled onto the
        wall would add. Too few to be a cluster of their own."""
        pts = np.asarray(at) + np.random.default_rng(1).uniform(-0.02, 0.02, (n, 3))
        return Candidate(points=pts, colors=np.full_like(pts, 0.5), box=fit_box(pts), label="chair", conf=0.5)

    def noisy_store(self, cfg=None):
        objects = ObjectStore(cfg or self.CFG)
        objects.apply([panel_view(0)], [None], anchor=1)
        clean_points = len(objects.get(0).points)
        objects.apply([self.stray_points()], [0], anchor=2)
        return objects, clean_points

    def test_merging_alone_keeps_the_stray_points(self):
        objects, clean_points = self.noisy_store()
        self.assertGreater(len(objects.get(0).points), clean_points)
        self.assertGreater(float(max(objects.get(0).box.extent)), 1.0)     # the box reaches the strays

    def test_denoise_drops_them_and_refits_the_box(self):
        objects, clean_points = self.noisy_store()
        before = len(objects.get(0).points)
        removed = objects.denoise(0)
        self.assertEqual(removed, before - len(objects.get(0).points))
        self.assertEqual(len(objects.get(0).points), clean_points)
        self.assertEqual(len(objects.get(0).colors), clean_points)
        self.assertLess(float(max(objects.get(0).box.extent)), 0.6)        # back to the 0.4 m panel
        self.assertEqual(objects.check_invariants(), [])

    def test_sightings_and_edges_are_untouched(self):
        objects, _ = self.noisy_store()
        objects.denoise(0)
        self.assertEqual(objects.get(0).sightings, 2)
        self.assertEqual(objects.graph.anchors_of(0), frozenset({1, 2}))

    def test_a_clean_object_is_left_alone(self):
        objects = ObjectStore(self.CFG)
        objects.apply([panel_view(0)], [None], anchor=1)
        points = objects.get(0).points.copy()
        self.assertEqual(objects.denoise(0), 0)
        np.testing.assert_array_equal(objects.get(0).points, points)

    def test_too_few_points_left_reverts(self):
        """Upstream's guard (pointcloud.py:787), with the limit set high enough
        to trigger."""
        objects, _ = self.noisy_store(config(denoise_min_points=100000))
        before = objects.get(0).points.copy()
        self.assertEqual(objects.denoise(0), 0)
        np.testing.assert_array_equal(objects.get(0).points, before)

    def test_denoise_objects_reports_what_changed(self):
        objects, _ = self.noisy_store()
        objects.apply([panel_view(3, centre=(5.0, 0.0, 1.0))], [None], anchor=3)      # a clean one
        report = denoise_objects(objects)
        self.assertEqual(report.objects_denoised, [0])
        self.assertEqual(report.points_removed, 6)

    def test_dbscan_off_only_downsamples(self):
        objects, _ = self.noisy_store(config(dbscan_remove_noise=False))
        self.assertEqual(objects.denoise(0), 0)


class PruneChoiceTest(unittest.TestCase):
    """Which photo is kept when several would do."""

    def two_photos_of_the_same_objects(self, confs):
        objects, anchors = new_stores(config())
        for frame_id, conf in enumerate(confs, start=1):
            store(objects, anchors, *room_photo(frame_id, 0.0, conf)[:2])
        return objects, anchors

    def test_the_better_view_is_kept(self):
        objects, anchors = self.two_photos_of_the_same_objects([0.5, 0.9])
        self.assertLess(view_cost(objects, 2), view_cost(objects, 1))
        report = prune_anchors(objects, anchors, kappa=1)
        self.assertEqual(report.anchors_evicted, [1])
        self.assertEqual(anchors.ids(), [2])
        consistent(self, objects, anchors)

    def test_equal_views_keep_the_older_photo(self):
        objects, anchors = self.two_photos_of_the_same_objects([0.8, 0.8])
        prune_anchors(objects, anchors, kappa=1)
        self.assertEqual(anchors.ids(), [1])

    def test_more_objects_beats_a_better_view(self):
        """A sharp photo of two objects does not replace a poor photo of three."""
        objects, anchors = new_stores(config())
        store(objects, anchors, *room_photo(1, 0.0, conf=0.3)[:2])      # three objects, poor
        store(objects, anchors, *room_photo(2, 0.3, conf=0.99)[:2])     # two of them, sharp
        self.assertEqual(len(objects.graph.objects_of(1)), 3)
        self.assertEqual(len(objects.graph.objects_of(2)), 2)
        prune_anchors(objects, anchors, kappa=1)
        self.assertEqual(anchors.ids(), [1])

    def test_view_cost_stays_in_its_narrow_range(self):
        objects, anchors = self.two_photos_of_the_same_objects([0.2, 0.9])
        for anchor in (1, 2):
            self.assertGreaterEqual(view_cost(objects, anchor), 1.0)
            self.assertLessEqual(view_cost(objects, anchor), 1.001)
        self.assertAlmostEqual(view_cost(objects, 2), 1.0)              # the best view of everything it shows

    def test_stores_must_share_a_graph(self):
        objects, _ = new_stores(config())
        with self.assertRaises(ValueError):
            prune_anchors(objects, AnchorStore(config(), ObjectStore(config()).graph), kappa=1)
        with self.assertRaises(ValueError):
            PeriodicCleanup(objects, AnchorStore(config(), ObjectStore(config()).graph))


class ScheduleTest(unittest.TestCase):
    def test_runs_every_n_stored_photos(self):
        objects, anchors = new_stores(config(cleanup_every_photos=4))
        cleanup = PeriodicCleanup(objects, anchors)
        ran = []
        for i, x in enumerate(STOPS):
            if store(objects, anchors, *room_photo(i, x)[:2]) is not None:
                ran.append(cleanup.photo_stored() is not None)
        self.assertEqual(ran, [False, False, False, True, False, False, False, True, False, False, False])
        self.assertEqual(cleanup.photos_since_cleanup, 3)
        consistent(self, objects, anchors)

    def test_a_manual_run_restarts_the_count(self):
        objects, anchors = new_stores(config(cleanup_every_photos=3))
        cleanup = PeriodicCleanup(objects, anchors)
        self.assertIsNone(cleanup.photo_stored())
        self.assertIsNone(cleanup.photo_stored())
        cleanup.run()
        self.assertIsNone(cleanup.photo_stored())

    def test_the_default_is_upstreams_ten_and_one(self):
        cfg = MemoryGraphConfig()
        self.assertEqual((cfg.cleanup_every_photos, cfg.prune_kappa), (10, 1))

    def test_bad_values_are_errors(self):
        for bad in ({"prune_kappa": 0}, {"cleanup_every_photos": 0}):
            with self.assertRaises(ValueError):
                MemoryGraphConfig.from_dict(bad)

    def test_an_empty_graph_is_fine(self):
        objects, anchors = new_stores(config())
        report = PeriodicCleanup(objects, anchors).run()
        self.assertEqual((report.anchors_before, report.anchors_after, report.points_removed), (0, 0, 0))


class AfterCleanupTest(unittest.TestCase):
    """The rest of the graph still works on what the clean-up left."""

    def setUp(self):
        self.objects, self.anchors = new_stores(config())
        self.objects.set_task(TaskContext("find a box", np.array([1.0, 0.0]), frozenset({"box"})))
        drive(self.objects, self.anchors, 0)
        PeriodicCleanup(self.objects, self.anchors).run()

    def test_every_target_still_has_a_stored_photo_and_a_box_on_it(self):
        hits = TargetFinder(self.objects, self.anchors).find()
        self.assertEqual(len(hits), 6)
        for hit in hits:
            self.assertIn(hit.anchor_id, self.anchors)
            u, v = self.anchors.get(hit.anchor_id).project(hit.position)
            x0, y0, x1, y1 = hit.box_on_anchor
            self.assertTrue(x0 <= u <= x1 and y0 <= v <= y1)

    def test_a_revisit_still_matches_the_same_objects(self):
        drive(self.objects, self.anchors, 100)
        self.assertEqual(len(self.objects), 6)
        consistent(self, self.objects, self.anchors)

    def test_each_entry_remembers_every_anchor_it_came_from(self):
        """The D-MG9 hook: `anchor_ids` is a history, so it keeps the ids of
        photos that were pruned."""
        entry = self.objects.get(0)
        self.assertEqual(entry.sightings, len(entry.anchor_ids))
        self.assertGreater(len(set(entry.anchor_ids)), self.objects.graph.degree(0))


if __name__ == "__main__":
    unittest.main()
