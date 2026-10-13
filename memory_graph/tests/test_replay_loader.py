"""S0: the replay loader (T6.3b).

Three parts: the conversions on their own, a tiny recording in the TUM layout
that the test writes itself, and two real frames of the TUM RGB-D benchmark in
fixtures/tum_fr1_xyz/ (see fixtures/README.md).
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import tempfile
import unittest
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from memory_graph.geometry import camera_rays, transform_points
from memory_graph.replay_loader import (
    TUM_DEPTH_UNITS_PER_METRE, TumSequence, depth_to_metres, nearest_in_time, read_tum_list,
    rigid_transform, to_observation,
)
from memory_graph.tests._fixtures import pose, rot_z

try:
    import cv2
except ImportError:  # pragma: no cover - depends on the machine
    cv2 = None

FIXTURES = Path(__file__).parent / "fixtures"
H, W = 48, 64
K = np.array([[60.0, 0, W / 2], [0, 60.0, H / 2], [0, 0, 1]])
# Columns are the camera axes in the world: x right = -y, y down = -z, z ahead = +x.
LOOK_ALONG_X = np.array([[0, 0, 1], [-1, 0, 0], [0, -1, 0]], dtype=float)


def world_cloud(obs, step=1):
    """Every pixel with a depth reading, back-projected into the world."""
    pts = camera_rays(obs.depth, obs.K)[::step, ::step].reshape(-1, 3)
    return transform_points(obs.T_world_cam, pts[pts[:, 2] > 0])


def seen_again(a, b, T_a=None, T_b=None, step=4):
    """Put photo a's depth pixels in the world, then look at them from photo b.

    For each point that lands on a pixel where b has a reading, the gap in
    metres between the point's depth and the depth b measured there. If both
    poses are right, the same surface is in the same place and the gaps are
    small. Returns the gaps. The poses can be replaced to try wrong ones.
    """
    T_a = a.T_world_cam if T_a is None else T_a
    T_b = b.T_world_cam if T_b is None else T_b
    pts = camera_rays(a.depth, a.K)[::step, ::step].reshape(-1, 3)
    in_b = transform_points(np.linalg.inv(T_b), transform_points(T_a, pts[pts[:, 2] > 0]))
    in_b = in_b[in_b[:, 2] > 0.1]
    u = np.round(in_b[:, 0] * b.K[0, 0] / in_b[:, 2] + b.K[0, 2]).astype(int)
    v = np.round(in_b[:, 1] * b.K[1, 1] / in_b[:, 2] + b.K[1, 2]).astype(int)
    h, w = b.depth.shape
    inside = (u >= 0) & (u < w) & (v >= 0) & (v < h)
    measured = b.depth[v[inside], u[inside]]
    return np.abs(in_b[inside, 2] - measured)[measured > 0]


class ConversionTest(unittest.TestCase):
    def test_depth_in_millimetres_becomes_metres(self):
        raw = np.array([[0, 1000, 2500]], dtype=np.uint16)
        out = depth_to_metres(raw, 1000)
        self.assertEqual(out.dtype, np.float32)
        np.testing.assert_allclose(out, [[0.0, 1.0, 2.5]])

    def test_the_tum_scale(self):
        np.testing.assert_allclose(depth_to_metres(np.array([[5000, 12500]], np.uint16), 5000), [[1.0, 2.5]])

    def test_bad_readings_become_zero(self):
        raw = np.array([[np.nan, np.inf, -1.0, 0.0, 2.0]])
        np.testing.assert_array_equal(depth_to_metres(raw, 1.0), [[0, 0, 0, 0, 2]])

    def test_a_scale_of_zero_is_an_error(self):
        with self.assertRaises(ValueError):
            depth_to_metres(np.zeros((1, 1)), 0)

    def test_quaternion_to_matrix_matches_scipy(self):
        rng = np.random.default_rng(0)
        for _ in range(20):
            q = rng.normal(size=4)
            t = rng.normal(size=3)
            T = rigid_transform(t, 3.0 * q)                  # not unit length on purpose
            np.testing.assert_allclose(T[:3, :3], Rotation.from_quat(q).as_matrix(), atol=1e-12)
            np.testing.assert_allclose(T[:3, 3], t)
            np.testing.assert_array_equal(T[3], [0, 0, 0, 1])

    def test_a_zero_quaternion_is_an_error(self):
        with self.assertRaises(ValueError):
            rigid_transform([0, 0, 0], [0, 0, 0, 0])

    def test_nearest_in_time(self):
        times = np.array([1.0, 2.0, 3.0])
        np.testing.assert_array_equal(nearest_in_time(times, np.array([0.99, 2.4, 2.6, 9.0]), 0.5), [0, 1, 2, -1])
        np.testing.assert_array_equal(nearest_in_time(np.array([5.0]), np.array([5.01, 6.0]), 0.02), [0, -1])
        np.testing.assert_array_equal(nearest_in_time(np.array([]), np.array([1.0]), 0.02), [-1])


class ToObservationTest(unittest.TestCase):
    IMAGE = np.zeros((H, W, 3), dtype=np.uint8)
    IMAGE[..., 0], IMAGE[..., 2] = 200, 10                   # first channel 200, last 10
    DEPTH = np.full((H, W), 1500, dtype=np.uint16)

    def make(self, **changes):
        args = dict(image=self.IMAGE, depth_raw=self.DEPTH, K=K, T_world_base=np.eye(4), frame_id=7,
                    timestamp=1.5, depth_units_per_metre=1000, bgr=False)
        args.update(changes)
        return to_observation(**args)

    def test_fields(self):
        obs = self.make()
        self.assertEqual((obs.frame_id, obs.timestamp), (7, 1.5))
        self.assertEqual(obs.rgb.dtype, np.uint8)
        self.assertEqual(obs.depth.dtype, np.float32)
        np.testing.assert_allclose(obs.depth, 1.5)
        np.testing.assert_array_equal(obs.K, K)

    def test_bgr_is_flipped_and_rgb_is_not(self):
        self.assertEqual(tuple(self.make(bgr=False).rgb[0, 0]), (200, 0, 10))
        self.assertEqual(tuple(self.make(bgr=True).rgb[0, 0]), (10, 0, 200))

    def test_the_mount_is_applied_once(self):
        base = pose(rot_z(90), t=(2.0, 1.0, 0.0))            # the robot, turned left
        mount = pose(LOOK_ALONG_X, t=(0.1, 0.0, 0.8))        # camera 10 cm ahead, 80 cm up
        obs = self.make(T_world_base=base, T_base_cam=mount)
        np.testing.assert_allclose(obs.T_world_cam, base @ mount)
        np.testing.assert_allclose(obs.camera_position, [2.0, 1.1, 0.8], atol=1e-12)
        # The camera looks along the base's forward axis, which now points along world +y.
        np.testing.assert_allclose(obs.T_world_cam[:3, 2], [0, 1, 0], atol=1e-12)

    def test_without_a_mount_the_pose_is_the_cameras(self):
        T = pose(rot_z(30), t=(1.0, 2.0, 3.0))
        np.testing.assert_allclose(self.make(T_world_base=T).T_world_cam, T)

    def test_a_pose_that_is_not_rigid_is_an_error(self):
        scaled = np.eye(4)
        scaled[:3, :3] *= 2.0
        mirrored = np.diag([1.0, 1.0, -1.0, 1.0])
        for bad in (scaled, mirrored, np.eye(3)):
            with self.assertRaises(ValueError):
                self.make(T_world_base=bad)
        with self.assertRaises(ValueError):
            self.make(T_base_cam=scaled)

    def test_depth_and_colour_of_different_sizes_is_an_error(self):
        with self.assertRaises(ValueError):
            self.make(depth_raw=np.zeros((H // 2, W // 2), dtype=np.uint16))

    def test_a_float_image_is_an_error(self):
        with self.assertRaises(ValueError):
            self.make(image=self.IMAGE.astype(np.float32) / 255)


def wall_depth(T_world_cam, wall_x=3.0):
    """Depth image, in metres, of the plane world x = wall_x seen from a pose."""
    u, v = np.meshgrid(np.arange(W, dtype=float), np.arange(H, dtype=float))
    rays = np.stack([(u - K[0, 2]) / K[0, 0], (v - K[1, 2]) / K[1, 1], np.ones_like(u)], axis=-1)
    along_x = rays @ T_world_cam[:3, :3].T[:, 0]
    return (wall_x - T_world_cam[0, 3]) / along_x


def write_tum_folder(root, poses, extra_rgb_times=()):
    """A recording in the TUM layout: one frame per pose, each looking at the
    wall x = 3. Colour, depth and pose times differ by a few milliseconds, as
    they do in the real files. Returns the folder."""
    (root / "rgb").mkdir()
    (root / "depth").mkdir()
    rgb_lines, depth_lines, pose_lines = ["# color images"], ["# depth maps"], ["# ground truth trajectory"]
    for i, T in enumerate(poses):
        t = 100.0 + i
        rgb = np.zeros((H, W, 3), dtype=np.uint8)
        rgb[..., 0], rgb[..., 2] = 200, 10                              # mostly red
        cv2.imwrite(str(root / "rgb" / f"{i}.png"), rgb[:, :, ::-1])    # OpenCV writes BGR
        depth = np.round(wall_depth(T) * TUM_DEPTH_UNITS_PER_METRE).astype(np.uint16)
        depth[0, 0] = 0                                                 # one missing reading
        cv2.imwrite(str(root / "depth" / f"{i}.png"), depth)
        q = Rotation.from_matrix(T[:3, :3]).as_quat()
        rgb_lines.append(f"{t:.4f} rgb/{i}.png")
        depth_lines.append(f"{t + 0.004:.4f} depth/{i}.png")
        pose_lines.append(f"{t - 0.003:.4f} " + " ".join(f"{x:.9f}" for x in (*T[:3, 3], *q)))
    for t in extra_rgb_times:
        rgb_lines.append(f"{t:.4f} rgb/0.png")
    (root / "rgb.txt").write_text("\n".join(rgb_lines) + "\n")
    (root / "depth.txt").write_text("\n".join(depth_lines) + "\n")
    (root / "groundtruth.txt").write_text("\n".join(pose_lines) + "\n")
    return root


@unittest.skipIf(cv2 is None, "needs OpenCV to write and read the image files")
class TumLayoutTest(unittest.TestCase):
    POSES = [pose(LOOK_ALONG_X, t=(0.0, 0.0, 1.0)), pose(rot_z(20) @ LOOK_ALONG_X, t=(1.0, 0.4, 1.2))]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = write_tum_folder(Path(self.tmp.name), self.POSES, extra_rgb_times=(500.0,))
        self.seq = TumSequence(self.root, K=K)

    def test_comment_lines_are_skipped(self):
        rows = read_tum_list(self.root / "rgb.txt")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], (100.0, ["rgb/0.png"]))

    def test_a_frame_with_no_depth_or_pose_nearby_is_left_out(self):
        self.assertEqual(len(self.seq), 2)                   # the colour image at t = 500 has neither
        self.assertEqual([o.frame_id for o in self.seq], [0, 1])
        self.assertEqual([o.timestamp for o in self.seq], [100.0, 101.0])

    def test_max_dt_is_respected(self):
        self.assertEqual(len(TumSequence(self.root, K=K, max_dt=0.001)), 0)

    def test_colour_order_depth_units_and_pose(self):
        obs = self.seq.observation(1)
        self.assertEqual(tuple(obs.rgb[5, 5]), (200, 0, 10))             # RGB, not BGR
        self.assertEqual(obs.depth.dtype, np.float32)
        self.assertEqual(obs.depth[0, 0], 0.0)                           # the missing reading
        np.testing.assert_allclose(obs.depth[1:, 1:], wall_depth(self.POSES[1])[1:, 1:], atol=2e-4)
        np.testing.assert_allclose(obs.T_world_cam, self.POSES[1], atol=1e-6)
        np.testing.assert_array_equal(obs.K, K)

    def test_same_wall_from_two_poses_lands_in_the_same_place(self):
        """The T6.3b done-when, on a recording the test wrote: back-projecting
        the full depth image from two poses puts the wall at x = 3 both times."""
        for obs in self.seq:
            cloud = world_cloud(obs)
            self.assertEqual(len(cloud), H * W - 1)
            np.testing.assert_allclose(cloud[:, 0], 3.0, atol=1e-3)

    def test_a_missing_image_file_is_an_error(self):
        (self.root / "depth" / "1.png").unlink()
        with self.assertRaises(FileNotFoundError):
            self.seq.observation(1)

    def test_the_mount_reaches_every_frame(self):
        mount = pose(t=(0.0, 0.0, 0.5))
        obs = TumSequence(self.root, K=K, T_base_cam=mount).observation(0)
        np.testing.assert_allclose(obs.T_world_cam, self.POSES[0] @ mount, atol=1e-6)


@unittest.skipIf(cv2 is None, "needs OpenCV to read the image files")
class TumRealFramesTest(unittest.TestCase):
    """Two frames of the TUM benchmark's freiburg1_xyz recording: a handheld
    Kinect over a desk, poses from a motion-capture system. The camera moved
    0.40 m and turned 9 degrees between them."""

    ROOT = FIXTURES / "tum_fr1_xyz"

    @classmethod
    def setUpClass(cls):
        cls.seq = TumSequence(cls.ROOT)
        cls.a, cls.b = cls.seq.observation(0), cls.seq.observation(1)

    def test_both_frames_load_in_the_agreed_form(self):
        self.assertEqual(len(self.seq), 2)
        for obs in (self.a, self.b):
            self.assertEqual((obs.rgb.shape, obs.rgb.dtype), ((480, 640, 3), np.uint8))
            self.assertEqual((obs.depth.shape, obs.depth.dtype), ((480, 640), np.float32))
            readings = obs.depth[obs.depth > 0]
            self.assertGreater(len(readings), 0.5 * obs.depth.size)
            self.assertLess(len(readings), obs.depth.size)              # a real sensor has holes
            # A desk scene, in metres. Read as millimetres it would be 4.5 to 18.6.
            self.assertGreater(readings.min(), 0.3)
            self.assertLess(readings.max(), 5.0)
        moved = np.linalg.norm(self.a.camera_position - self.b.camera_position)
        self.assertAlmostEqual(float(moved), 0.40, delta=0.01)

    def test_same_surfaces_from_two_poses_land_in_the_same_place(self):
        """The T6.3b done-when, on a real recording. Measured 2026-10-07:
        median gap 0.8 cm, 95 % of points within 5 cm."""
        gaps = seen_again(self.a, self.b)
        self.assertGreater(len(gaps), 3000)
        self.assertLess(np.median(gaps), 0.02)
        self.assertGreater(np.mean(gaps < 0.05), 0.85)

    def test_the_check_fails_when_the_loader_would_be_wrong(self):
        """The same check with each S0 mistake made on purpose. Measured
        2026-10-07: every one gives a median gap of 20 cm or more."""
        inv = np.linalg.inv
        wrong = {
            "world-to-camera used as the pose": seen_again(self.a, self.b, inv(self.a.T_world_cam), inv(self.b.T_world_cam)),
            "one pose the wrong way round": seen_again(self.a, self.b, T_b=inv(self.b.T_world_cam)),
            "the pose ignored": seen_again(self.a, self.b, T_b=self.a.T_world_cam),
        }
        as_mm = TumSequence(self.ROOT, depth_units_per_metre=1000)
        wrong["depth scale of the wrong sensor"] = seen_again(as_mm.observation(0), as_mm.observation(1))
        for mistake, gaps in wrong.items():
            with self.subTest(mistake=mistake):
                self.assertTrue(len(gaps) == 0 or np.median(gaps) > 0.10, f"{mistake}: median {np.median(gaps):.3f} m")


if __name__ == "__main__":
    unittest.main()
