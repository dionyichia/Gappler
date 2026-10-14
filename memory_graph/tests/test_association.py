"""S10: overlap score (T6.4a) and the match decision (T6.4b)."""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.association import (
    appearance_matrix, associate, boxes_intersect, combined_scores, match, overlap_matrix,
)
from memory_graph.config import MemoryGraphConfig
from memory_graph.geometry import fit_box
from memory_graph.stage_types import Candidate, OrientedBox
from memory_graph.tests._fixtures import rot_z

CFG = MemoryGraphConfig()
ONE_TO_ONE = MemoryGraphConfig(association_mode="one_to_one")


def box_surface(size, centre, spacing=0.01):
    """Points on the faces of an axis-aligned box, with each face's outward normal."""
    sx, sy, sz = size
    pts, normals = [], []
    for axis in range(3):
        others = [a for a in range(3) if a != axis]
        g0 = np.arange(-size[others[0]] / 2, size[others[0]] / 2 + 1e-9, spacing)
        g1 = np.arange(-size[others[1]] / 2, size[others[1]] / 2 + 1e-9, spacing)
        a, b = np.meshgrid(g0, g1)
        for sign in (-1, 1):
            p = np.zeros((a.size, 3))
            p[:, others[0]], p[:, others[1]] = a.ravel(), b.ravel()
            p[:, axis] = sign * size[axis] / 2
            n = np.zeros(3)
            n[axis] = sign
            pts.append(p)
            normals.append(np.tile(n, (len(p), 1)))
    return np.vstack(pts) + np.asarray(centre), np.vstack(normals)


def seen_from(points, normals, camera):
    """The surface points whose face points toward the camera."""
    return points[np.einsum("ij,ij->i", normals, camera - points) > 0]


def cand(points, clip=(1.0, 0.0), label="chair"):
    return Candidate(points=points, colors=np.zeros_like(points), box=fit_box(points),
                     label=label, conf=0.9, clip=np.asarray(clip, dtype=float))


class BoxIntersectionTest(unittest.TestCase):
    def test_separated_touching_and_rotated(self):
        a = OrientedBox(np.zeros(3), np.eye(3), np.ones(3))
        self.assertTrue(boxes_intersect(a, OrientedBox(np.array([0.9, 0, 0]), np.eye(3), np.ones(3))))
        self.assertTrue(boxes_intersect(a, OrientedBox(np.array([1.0, 0, 0]), np.eye(3), np.ones(3))))
        self.assertFalse(boxes_intersect(a, OrientedBox(np.array([1.2, 0, 0]), np.eye(3), np.ones(3))))
        # A box turned 45 degrees: its corner reaches 0.707 from its centre.
        turned = OrientedBox(np.array([1.15, 0, 0]), rot_z(45), np.ones(3))
        self.assertTrue(boxes_intersect(a, turned))
        turned = OrientedBox(np.array([1.25, 0, 0]), rot_z(45), np.ones(3))
        self.assertFalse(boxes_intersect(a, turned))


class OverlapTest(unittest.TestCase):
    def test_same_points_full_overlap_far_points_none(self):
        pts, _ = box_surface((0.4, 0.4, 0.8), (2, 0, 0.4))
        near = cand(pts + 0.005)
        far = cand(pts + np.array([1.0, 0, 0]))
        stored = [cand(pts)]
        out = overlap_matrix([near, far], stored, CFG)
        self.assertGreater(out[0, 0], 0.95)
        self.assertEqual(out[1, 0], 0.0)

    def test_no_objects_or_no_candidates(self):
        pts, _ = box_surface((0.4, 0.4, 0.4), (0, 0, 0))
        self.assertEqual(overlap_matrix([], [cand(pts)], CFG).shape, (0, 1))
        self.assertEqual(overlap_matrix([cand(pts)], [], CFG).shape, (1, 0))


class MatchTest(unittest.TestCase):
    def test_same_chair_from_views_30_degrees_apart_matches(self):
        """Done-when for S10: the same object from two poses 30 degrees apart matches."""
        centre = np.array([3.0, 0.0, 0.45])
        pts, normals = box_surface((0.45, 0.45, 0.9), centre)
        cam_a = centre + np.array([-2.5, 0.0, 0.0])
        cam_b = centre + rot_z(30) @ np.array([-2.5, 0.0, 0.0])
        stored = [cand(seen_from(pts, normals, cam_a))]
        new = cand(seen_from(pts, normals, cam_b))
        self.assertEqual(associate([new], stored, CFG), [0])

    def test_two_identical_chairs_side_by_side_do_not_merge(self):
        """Done-when for S10: identical appearance, no 3D overlap, no match."""
        pts, _ = box_surface((0.45, 0.45, 0.9), (0, 0, 0.45))
        stored = [cand(pts)]
        twin = cand(pts + np.array([0.6, 0, 0]))
        self.assertEqual(associate([twin], stored, CFG), [None])

    def test_appearance_alone_cannot_merge_with_upstream_weights(self):
        scores = combined_scores(np.zeros((1, 1)), np.ones((1, 1)), CFG)
        self.assertAlmostEqual(scores[0, 0], 0.5)
        self.assertEqual(match(scores, CFG), [None])

    def test_greedy_lets_two_candidates_share_an_object(self):
        scores = np.array([[1.4, 0.0], [1.2, 0.9]])
        self.assertEqual(match(scores, CFG), [0, 0])

    def test_one_to_one_gives_each_object_at_most_one(self):
        scores = np.array([[1.4, 0.0], [1.2, 0.9]])
        self.assertEqual(match(scores, ONE_TO_ONE), [0, 1])
        scores = np.array([[1.4, 0.0], [1.2, 0.1]])          # second has no other option
        self.assertEqual(match(scores, ONE_TO_ONE), [0, None])

    def test_appearance_matrix_handles_missing_features(self):
        a = cand(np.zeros((5, 3)) + np.arange(5)[:, None] * 0.1, clip=(1.0, 0.0))
        b = cand(np.zeros((5, 3)) + np.arange(5)[:, None] * 0.1, clip=(0.0, 2.0))
        a_none = Candidate(a.points, a.colors, a.box, "x", 0.5)
        out = appearance_matrix([a, a_none], [a, b])
        np.testing.assert_allclose(out, [[1.0, 0.0], [0.0, 0.0]])


if __name__ == "__main__":
    unittest.main()
