"""S7 back-projection, S8 cleanup and 3D box, S9 range filter (T6.3e)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import (
    back_project, build_candidates, camera_rays, clean_cloud, fit_box, transform_points,
    voxel_downsample,
)
from memory_graph.stage_types import Observation
from memory_graph.tests._fixtures import K, dets, patch_centre_cam, patch_scene, pose, rot_y, rot_z

CFG = MemoryGraphConfig()


class BackProjectionTest(unittest.TestCase):
    def test_centroid_lands_on_the_known_position(self):
        """Done-when for T6.3e: a mask on a known object gives a centroid within a
        few cm of where it is, here with a camera that is moved and turned."""
        patch = (60, 40, 90, 70, 2.0)
        T = pose(rot_z(30) @ rot_y(10), t=(1.0, -2.0, 0.5))
        obs, masks = patch_scene([patch], T_world_cam=T)
        (cloud,) = back_project(obs, masks, CFG)
        expected = transform_points(T, patch_centre_cam(*patch)[None])[0]
        self.assertLess(np.linalg.norm(cloud[0].mean(axis=0) - expected), 0.03)

    def test_same_wall_from_two_poses_lands_in_the_same_place(self):
        """S0's check, on synthetic data: a wall at world x = 3 seen from two
        camera positions back-projects to x = 3 both times."""
        # Columns are the camera axes in the world: x right = -y, y down = -z, z ahead = +x.
        R = np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]], dtype=float)
        for cam_x in (0.0, 1.0):
            T = pose(R, t=(cam_x, 0.0, 1.0))
            depth = np.full((120, 160), 3.0 - cam_x, dtype=np.float32)
            obs = Observation(np.zeros((120, 160, 3), np.uint8), depth, K.copy(), T, 0)
            world = transform_points(T, camera_rays(obs.depth, obs.K).reshape(-1, 3))
            np.testing.assert_allclose(world[:, 0], 3.0, atol=1e-9)

    def test_invalid_depth_and_small_masks(self):
        obs, masks = patch_scene([(10, 10, 13, 15, 1.0), (40, 40, 80, 80, 1.5)])
        obs.depth[40:80, 40:80] = 0.0                  # no valid depth on the second
        # 15 px is below the 16 px minimum. The second has 1600 px, none valid.
        self.assertEqual(back_project(obs, masks, CFG), [None, None])

    def test_point_cap(self):
        obs, masks = patch_scene([(0, 0, 160, 120, 2.0)])
        (cloud,) = back_project(obs, masks, MemoryGraphConfig(max_points=1000))
        self.assertLessEqual(len(cloud[0]), 1000)
        self.assertGreater(len(cloud[0]), 500)


class CloudCleanupTest(unittest.TestCase):
    def test_outliers_one_metre_away_are_removed_and_box_shrinks(self):
        rng = np.random.default_rng(0)
        obj = rng.uniform([0, 0, 0], [0.3, 0.3, 0.3], size=(3000, 3))
        stray = rng.uniform([1.3, 1.3, 1.3], [1.32, 1.32, 1.32], size=(12, 3))
        pts = np.vstack([obj, stray])
        cols = np.zeros_like(pts)
        before = fit_box(pts)
        clean, _ = clean_cloud(pts, cols, CFG)
        self.assertLess(clean.max(axis=0).max(), 0.35)
        after = fit_box(clean)
        self.assertLess(after.half_diagonal, before.half_diagonal / 2)

    def test_voxel_downsample_averages(self):
        pts = np.array([[0.001, 0, 0], [0.009, 0, 0], [0.5, 0, 0]])
        cols = np.array([[1.0, 0, 0], [0.0, 0, 0], [0, 1.0, 0]])
        p, c = voxel_downsample(pts, cols, 0.02)
        self.assertEqual(len(p), 2)
        i = int(np.argmin(p[:, 0]))
        np.testing.assert_allclose(p[i], [0.005, 0, 0])
        np.testing.assert_allclose(c[i], [0.5, 0, 0])

    def test_box_of_rotated_block(self):
        rng = np.random.default_rng(2)
        local = rng.uniform([-0.4, -0.1, -0.05], [0.4, 0.1, 0.05], size=(4000, 3))
        R = rot_z(35)
        pts = local @ R.T + np.array([2.0, 1.0, 0.5])
        box = fit_box(pts)
        np.testing.assert_allclose(box.center, [2.0, 1.0, 0.5], atol=0.02)
        np.testing.assert_allclose(box.extent, [0.8, 0.2, 0.1], atol=0.02)
        self.assertAlmostEqual(abs(box.R[:, 0] @ R[:, 0]), 1.0, places=3)
        self.assertAlmostEqual(np.linalg.det(box.R), 1.0, places=6)


class CandidatesTest(unittest.TestCase):
    def test_range_filter_keeps_arrays_aligned(self):
        """Done-when for T6.3e: an object at 7 m is dropped, one at 5 m is kept,
        and what is kept still matches its own detection."""
        patches = [(10, 40, 40, 70, 7.0), (60, 40, 90, 70, 5.0), (110, 40, 140, 70, 2.0)]
        obs, masks = patch_scene(patches, wall_depth=9.0)
        d = dets([[p[0], p[1], p[2], p[3]] for p in patches], [0.9, 0.8, 0.7],
                 ["far", "mid", "near"], masks)
        features = np.eye(3)
        cands = build_candidates(obs, d, CFG, features)
        self.assertEqual([c.label for c in cands], ["mid", "near"])
        for c in cands:
            np.testing.assert_array_equal(c.clip, features[c.detection_index])
            self.assertEqual(c.label, d.label[c.detection_index])
        self.assertAlmostEqual(cands[0].box.center[2], 5.0, delta=0.05)

    def test_requires_masks(self):
        obs, _ = patch_scene([])
        with self.assertRaises(ValueError):
            build_candidates(obs, dets([[0, 0, 1, 1]], [0.9], ["x"]), CFG)


if __name__ == "__main__":
    unittest.main()
