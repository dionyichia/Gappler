"""S12: store each accepted photo as an anchor (T6.4d)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import math
import unittest

import numpy as np

from memory_graph.anchor_store import (
    AnchorStore, resize_bilinear, resize_boxes, resize_intrinsics, resize_nearest,
)
from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import build_candidates
from memory_graph.object_store import ObjectStore
from memory_graph.tests._fixtures import H, K, W, dets, patch_scene, pose

# Stored smaller than the camera image and with a different shape, so a width
# and height swap or an unscaled K cannot pass by accident.
CFG = MemoryGraphConfig.from_dict({"anchor_height": 96, "anchor_width": 64})

# Two flat objects in front of a wall, as (u0, v0, u1, v1, depth in metres),
# seen by a camera at the origin.
PATCHES = [(30, 30, 70, 70, 1.5), (100, 40, 140, 90, 2.0)]
FX = K[0, 0]


def photo(frame_id, shift_m=0.0, patches=PATCHES):
    """The same scene from a camera moved `shift_m` to its right. Each object
    moves left in the image by fx * shift / depth pixels."""
    moved = []
    for u0, v0, u1, v1, d in patches:
        du = int(round(FX * shift_m / d))
        moved.append((u0 - du, v0, u1 - du, v1, d))
    obs, masks = patch_scene(moved, T_world_cam=pose(t=(shift_m, 0.0, 0.0)), seed=frame_id)
    obs.frame_id = frame_id
    boxes = [p[:4] for p in moved]
    return obs, dets(boxes, [0.9, 0.8][: len(moved)], ["chair", "table"][: len(moved)], masks=masks)


def store_photo(objects, anchors, obs, d, **kwargs):
    cands = build_candidates(obs, d, objects.cfg)
    ids = objects.integrate(cands, anchor=obs.frame_id)
    return anchors.add(obs, d, cands, ids, **kwargs)


def new_stores(cfg=CFG):
    objects = ObjectStore(cfg)
    return objects, AnchorStore(cfg, objects.graph)


def inside(uv, box):
    return box[0] <= uv[0] <= box[2] and box[1] <= uv[1] <= box[3]


class DoneWhenTest(unittest.TestCase):
    """The T6.4d done-when: no invariant violations after every photo, and each
    object's centre, projected through the stored intrinsics and pose, lands
    inside its box on the stored image."""

    SHIFTS = [0.0, 0.15, 0.3, 0.15, 0.0]

    def run_drive(self, cfg):
        objects, anchors = new_stores(cfg)
        for frame_id, shift in enumerate(self.SHIFTS):
            store_photo(objects, anchors, *photo(frame_id, shift))
            self.assertEqual(objects.check_invariants(), [])
            self.assertEqual(anchors.check_invariants(), [])
        return objects, anchors

    def check_centres(self, objects, anchors):
        checked = 0
        for anchor in anchors.ids():
            record = anchors.get(anchor)
            for obj in objects.graph.objects_of(anchor):
                uv = record.project(objects.get(obj).box.center)
                self.assertIsNotNone(uv)
                self.assertTrue(inside(uv, record.object_boxes[obj]),
                                f"anchor {anchor} object {obj}: {uv} not in {record.object_boxes[obj]}")
                checked += 1
        return checked

    def test_invariants_hold_and_centres_land_in_their_boxes(self):
        objects, anchors = self.run_drive(CFG)
        # The five photos show the same two objects, so the views were merged.
        self.assertEqual(len(objects), 2)
        self.assertEqual(len(anchors), 5)
        self.assertEqual(self.check_centres(objects, anchors), 10)

    def test_same_at_the_default_stored_size(self):
        objects, anchors = self.run_drive(MemoryGraphConfig())
        self.assertEqual(anchors.get(0).rgb.shape, (448, 448, 3))
        self.assertEqual(self.check_centres(objects, anchors), 10)

    def test_same_at_the_camera_size(self):
        objects, anchors = self.run_drive(
            MemoryGraphConfig.from_dict({"anchor_height": 0, "anchor_width": 0}))
        self.assertEqual(anchors.get(0).size, (H, W))
        np.testing.assert_allclose(anchors.get(0).K, K)
        self.assertEqual(self.check_centres(objects, anchors), 10)

    def test_the_check_catches_unscaled_intrinsics(self):
        """The pitfall the done-when is there for: keep the camera's K on a
        resized image and the centres leave their boxes."""
        objects, anchors = self.run_drive(CFG)
        misses = 0
        for anchor in anchors.ids():
            record = anchors.get(anchor)
            record.K = K.copy()
            for obj in objects.graph.objects_of(anchor):
                misses += not inside(record.project(objects.get(obj).box.center), record.object_boxes[obj])
        self.assertGreater(misses, 0)

    def test_edges_run_both_ways(self):
        objects, anchors = self.run_drive(CFG)
        for anchor in anchors.ids():
            for obj in objects.graph.objects_of(anchor):
                self.assertIn(anchor, objects.graph.anchors_of(obj))
                self.assertIn(anchor, objects.get(obj).anchor_ids)


class RecordTest(unittest.TestCase):
    def setUp(self):
        self.objects, self.anchors = new_stores()
        self.obs, self.dets = photo(7)
        self.record = store_photo(self.objects, self.anchors, self.obs, self.dets)

    def test_sizes_are_height_then_width(self):
        self.assertEqual(self.record.rgb.shape, (96, 64, 3))
        self.assertEqual(self.record.depth.shape, (96, 64))
        self.assertEqual(self.record.rgb.dtype, np.uint8)
        self.assertEqual(self.record.depth.dtype, np.float32)

    def test_field_of_view_is_unchanged_by_the_resize(self):
        """2 atan(W / (2 fx)). Upstream's 2 atan(W / fx) would give 116 degrees
        for this 77 degree camera."""
        self.assertAlmostEqual(self.record.fov_x, 2 * math.atan(W / (2 * FX)))
        self.assertAlmostEqual(self.record.fov_y, 2 * math.atan(H / (2 * K[1, 1])))
        self.assertAlmostEqual(math.degrees(self.record.fov_x), 77.32, places=2)

    def test_depth_is_never_blended(self):
        """Every stored depth is a depth the camera measured. Bilinear resizing
        would put values between an object and the wall at each edge."""
        self.assertTrue(np.isin(self.record.depth, self.obs.depth).all())
        between = (self.record.depth > 2.1) & (self.record.depth < 2.9)
        self.assertFalse(between.any())

    def test_invalid_depth_stays_invalid(self):
        objects, anchors = new_stores()
        obs, d = photo(1)
        obs.depth[:, :10] = 0.0
        record = store_photo(objects, anchors, obs, d)
        self.assertTrue((record.depth[:, :3] == 0).all())
        self.assertTrue(np.isin(record.depth, obs.depth).all())

    def test_stored_depth_lifts_a_box_back_to_the_object(self):
        """What the stored depth and K are kept for: back-project the pixels in
        an object's box and get the object's position back."""
        for obj in self.objects.ids():
            x0, y0, x1, y1 = self.record.object_boxes[obj]
            v, u = np.mgrid[math.ceil(y0):math.floor(y1) + 1, math.ceil(x0):math.floor(x1) + 1]
            z = self.record.depth[v, u].astype(float)
            Ks = self.record.K
            cam = np.stack([(u - Ks[0, 2]) * z / Ks[0, 0], (v - Ks[1, 2]) * z / Ks[1, 1], z], axis=-1)
            world = cam.reshape(-1, 3) @ self.record.T_world_cam[:3, :3].T + self.record.T_world_cam[:3, 3]
            gap = np.linalg.norm(world.mean(axis=0) - self.objects.get(obj).box.center)
            self.assertLess(gap, 0.03)

    def test_record_keeps_pose_labels_and_a_copy(self):
        np.testing.assert_allclose(self.record.T_world_cam, self.obs.T_world_cam)
        self.assertEqual(self.record.labels, frozenset({"chair", "table"}))
        self.assertIsNone(self.record.detections.masks)
        self.obs.T_world_cam[0, 3] = 99.0
        self.assertEqual(self.record.T_world_cam[0, 3], 0.0)

    def test_raw_detections_are_stored_when_given(self):
        objects, anchors = new_stores()
        obs, d = photo(1)
        raw = dets([[0, 0, 160, 120], *d.xyxy], [0.95, 0.9, 0.8], ["wall", "chair", "table"])
        record = store_photo(objects, anchors, obs, d, raw_detections=raw)
        self.assertEqual(record.detections.label, ["wall", "chair", "table"])
        np.testing.assert_allclose(record.detections.xyxy[0], [-0.3, -0.1, 63.7, 95.9])
        self.assertEqual(set(record.object_boxes), set(objects.ids()))

    def test_behind_the_camera_projects_to_none(self):
        self.assertIsNone(self.record.project([0.0, 0.0, -1.0]))


class ResizeTest(unittest.TestCase):
    def test_nearest_picks_existing_values(self):
        image = np.arange(12, dtype=np.float32).reshape(3, 4)
        np.testing.assert_array_equal(resize_nearest(image, 3, 4), image)
        np.testing.assert_array_equal(resize_nearest(image, 6, 8)[::2, ::2], image)

    def test_bilinear_keeps_a_flat_image_flat_and_its_type(self):
        image = np.full((30, 40, 3), 128, dtype=np.uint8)
        out = resize_bilinear(image, 17, 23)
        self.assertEqual(out.dtype, np.uint8)
        self.assertTrue((out == 128).all())

    def test_bilinear_halving_averages_pixel_pairs(self):
        image = np.array([[0, 10, 20, 30]], dtype=np.float64)
        np.testing.assert_allclose(resize_bilinear(image, 1, 2), [[5, 25]])

    def test_intrinsics_and_boxes_use_the_same_mapping(self):
        """A point projected with the resized K lands where its original pixel
        is moved by resize_boxes."""
        point = np.array([0.3, -0.2, 2.0])
        uv = (K @ point)[:2] / point[2]
        K2 = resize_intrinsics(K, 0.4, 0.8)
        uv2 = (K2 @ point)[:2] / point[2]
        np.testing.assert_allclose(resize_boxes([[*uv, *uv]], 0.4, 0.8)[0, :2], uv2)


class BookkeepingTest(unittest.TestCase):
    def setUp(self):
        self.objects, self.anchors = new_stores()
        for frame_id, shift in enumerate([0.0, 0.3]):
            store_photo(self.objects, self.anchors, *photo(frame_id, shift))

    def test_a_photo_with_no_objects_is_not_stored(self):
        obs, d = photo(5)
        self.assertIsNone(self.anchors.add(obs, d, [], []))
        self.assertNotIn(5, self.anchors)
        self.assertEqual(self.anchors.check_invariants(), [])

    def test_the_same_photo_twice_is_an_error(self):
        obs, d = photo(0)
        cands = build_candidates(obs, d, CFG)
        with self.assertRaises(ValueError):
            self.anchors.add(obs, d, cands, [0, 1])

    def test_add_before_integrate_is_an_error(self):
        obs, d = photo(9)
        cands = build_candidates(obs, d, CFG)
        with self.assertRaises(ValueError):
            self.anchors.add(obs, d, cands, [0, 1])
        self.assertNotIn(9, self.anchors)

    def test_a_missing_record_is_reported(self):
        obs, d = photo(9, 0.15)
        self.objects.integrate(build_candidates(obs, d, CFG), anchor=9)
        self.assertEqual(self.anchors.check_invariants(), ["graph holds anchor 9 that has no record"])

    def test_remove_takes_the_edges_too(self):
        self.anchors.remove(0)
        self.assertNotIn(0, self.anchors)
        self.assertEqual(self.objects.graph.anchors(), frozenset({1}))
        self.assertEqual(self.anchors.check_invariants(), [])
        self.assertEqual(self.objects.check_invariants(), [])

    def test_records_follow_a_prune(self):
        kept, evicted = self.objects.graph.prune(kappa=1)
        self.assertEqual(len(self.anchors.check_invariants()), len(evicted))
        self.assertEqual(self.anchors.drop_pruned(), sorted(evicted))
        self.assertEqual(self.anchors.ids(), sorted(kept))
        self.assertEqual(self.anchors.check_invariants(), [])

    def test_records_follow_an_object_merge(self):
        self.objects.merge_objects(0, 1)
        self.assertNotEqual(self.anchors.check_invariants(), [])
        before = {a: self.anchors.get(a).object_boxes.copy() for a in self.anchors.ids()}
        self.anchors.merge_objects(0, 1)
        self.assertEqual(self.anchors.check_invariants(), [])
        for anchor, boxes in before.items():
            merged = self.anchors.get(anchor).object_boxes
            self.assertEqual(set(merged), {0})
            np.testing.assert_allclose(merged[0][:2], np.minimum(boxes[0][:2], boxes[1][:2]))
            np.testing.assert_allclose(merged[0][2:], np.maximum(boxes[0][2:], boxes[1][2:]))

    def test_two_detections_of_one_object_share_a_box(self):
        """Greedy matching (D-MG8) lets two candidates from one photo go to the
        same entry. The anchor then keeps the box around both."""
        objects, anchors = new_stores()
        store_photo(objects, anchors, *photo(0))
        obs, d = photo(1)
        cands = build_candidates(obs, d, CFG)
        ids = objects.apply(cands, [0, 0], anchor=1)
        record = anchors.add(obs, d, cands, ids)
        self.assertEqual(set(record.object_boxes), {0})
        np.testing.assert_allclose(record.object_boxes[0], resize_boxes([[30, 30, 140, 90]], 0.4, 0.8)[0])
        self.assertEqual(anchors.check_invariants(), [])


class ConfigTest(unittest.TestCase):
    def test_negative_size_is_an_error(self):
        with self.assertRaises(ValueError):
            MemoryGraphConfig.from_dict({"anchor_width": -1})


if __name__ == "__main__":
    unittest.main()
