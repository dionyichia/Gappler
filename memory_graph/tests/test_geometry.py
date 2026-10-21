"""S7 back-projection, S8 cleanup and 3D box, S9 range filter (T6.3e)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import (
    back_project, build_candidates, camera_rays, clean_cloud, drop_occluded, fit_box, invert_rigid,
    project_cloud_to_depth, transform_points, voxel_downsample,
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


class InvertRigidTest(unittest.TestCase):
    def test_inverse_undoes_the_transform(self):
        T = pose(rot_z(30) @ rot_y(10), t=(1.0, -2.0, 0.5))
        np.testing.assert_allclose(invert_rigid(T) @ T, np.eye(4), atol=1e-12)


class ProjectCloudToDepthTest(unittest.TestCase):
    """The LiDAR depth path (T6.3b, option b): a world-frame cloud rendered to a
    depth image aligned to the colour camera, the inverse of back_project."""

    def _cam_points(self, pixels):
        """Camera-frame points that land exactly on the given (u, v, depth)."""
        fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
        return np.array([[(u - cx) * z / fx, (v - cy) * z / fy, z] for u, v, z in pixels])

    def test_round_trip_recovers_the_point_at_each_pixel(self):
        """A cloud projected to depth, then back-projected, returns to where it
        came from. This is the done-when: geometry in equals geometry out."""
        T = pose(rot_z(20) @ rot_y(-15), t=(1.0, -2.0, 0.5))
        pixels = [(40, 30, 2.0), (80, 60, 3.0), (120, 90, 1.5)]
        world = transform_points(T, self._cam_points(pixels))
        depth = project_cloud_to_depth(world, T, K, (120, 160))
        for u, v, z in pixels:
            self.assertAlmostEqual(depth[v, u], z, places=4)
        self.assertEqual(depth[0, 0], 0.0)              # no point there

    def test_same_surface_from_two_poses_lands_in_the_same_place(self):
        """T6.3b's done-when on the LiDAR path: one wall seen from two camera
        positions back-projects to the same world plane both times."""
        R = np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]], dtype=float)   # optical axes in world
        wall = np.array([[3.0, y, z] for y in np.linspace(-0.3, 0.3, 7)
                         for z in np.linspace(0.4, 1.0, 7)])
        for cam_x in (0.0, 1.0):
            T = pose(R, t=(cam_x, 0.0, 0.7))
            depth = project_cloud_to_depth(wall, T, K, (120, 160))
            recovered = transform_points(T, camera_rays(depth, K).reshape(-1, 3))
            recovered = recovered[depth.reshape(-1) > 0]
            self.assertGreater(len(recovered), 20)
            self.assertLess(np.abs(recovered[:, 0] - 3.0).max(), 0.02)

    def test_nearest_point_wins_the_pixel(self):
        """Two points on one ray: the z-buffer keeps the closer one, so a near
        surface is never painted over by something behind it."""
        T = pose(t=(0.0, 0.0, 0.0))
        world = self._cam_points([(80, 60, 2.0), (80, 60, 4.0)])
        depth = project_cloud_to_depth(world, T, K, (120, 160))
        self.assertAlmostEqual(depth[60, 80], 2.0, places=4)

    def test_points_behind_the_camera_are_dropped(self):
        T = pose(t=(0.0, 0.0, 0.0))
        world = np.array([[0.1, 0.1, -2.0], [0.2, -0.1, -0.5]])   # z < 0 in the camera
        depth = project_cloud_to_depth(world, T, K, (120, 160))
        self.assertEqual(np.count_nonzero(depth), 0)

    def test_empty_cloud_gives_an_empty_depth_image(self):
        depth = project_cloud_to_depth(np.zeros((0, 3)), pose(), K, (120, 160))
        self.assertEqual(depth.shape, (120, 160))
        self.assertEqual(np.count_nonzero(depth), 0)


class DropOccludedTest(unittest.TestCase):
    def sparse_chair_on_wall(self):
        """A wall at 3 m on every other pixel, a chair at 1 m on a sparser grid in
        front of it: the wall shows through the chair's gaps, as sparse LiDAR does."""
        depth = np.zeros((60, 80), dtype=np.float32)
        depth[::2, ::2] = 3.0
        depth[20:40:3, 30:50:3] = 1.0
        return depth

    def test_wall_behind_the_chair_is_cleared(self):
        depth = self.sparse_chair_on_wall()
        out = drop_occluded(depth, 7, 0.1)
        inside = out[22:38, 32:48]
        self.assertTrue(np.all((inside == 0) | (inside == 1.0)))   # only chair is left there
        np.testing.assert_array_equal(out[out == 1.0], depth[depth == 1.0])
        self.assertEqual(out[0, 0], 3.0)                             # wall far from the chair stays
        self.assertEqual(out[10, 10], 3.0)

    def test_a_flat_or_sloping_surface_keeps_its_points(self):
        """Depth growing slowly across the image (a floor seen at an angle) is not
        occlusion: neighbours within the margin keep each other."""
        depth = np.tile(np.linspace(2.0, 2.15, 80, dtype=np.float32), (60, 1))
        np.testing.assert_array_equal(drop_occluded(depth, 7, 0.1), depth)

    def test_window_of_one_changes_nothing(self):
        depth = self.sparse_chair_on_wall()
        np.testing.assert_array_equal(drop_occluded(depth, 1, 0.1), depth)


if __name__ == "__main__":
    unittest.main()
