"""One recorded photo through S2 to S11, from a stored fixture (T6.3).

The lab photo is a frame of the FAST-LIVO hand-driven bag, saved with SAM 3's raw
output and the CLIP vectors by `python -m memory_graph.run_photo --save-fixture`,
so these tests need no GPU and no model. expected.json holds what that run gave.
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.object_store import ObjectStore
from memory_graph.run_photo import PhotoResult, load_photo, save_photo, stages_after_detection
from memory_graph.tests._fixtures import dets, patch_scene

CFG = MemoryGraphConfig()
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fastlivo_photo"


def _replay(path):
    obs, raw, feats = load_photo(path)
    return stages_after_detection(obs, raw, lambda d: feats, frozenset(), CFG)


class SavePhotoTest(unittest.TestCase):
    def test_round_trip(self):
        """What load_photo gives back is what save_photo was given: depth to the
        millimetre, masks and labels exactly, colour to JPEG accuracy."""
        obs, masks = patch_scene([(20, 20, 60, 60, 1.5), (90, 30, 130, 80, 2.2)])
        raw = dets([[20, 20, 60, 60], [90, 30, 130, 80]], [0.9, 0.2], ["chair", "box"], masks)
        feats = np.eye(2, 4)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "photo.npz"
            save_photo(path, PhotoResult(obs, raw, raw, feats, []))
            obs2, raw2, feats2 = load_photo(path)
        self.assertLessEqual(np.abs(obs2.depth - obs.depth).max(), 0.0005 + 1e-6)
        np.testing.assert_array_equal(raw2.masks, raw.masks)
        self.assertEqual(raw2.label, raw.label)
        np.testing.assert_allclose(raw2.conf, raw.conf)
        np.testing.assert_allclose(obs2.T_world_cam, obs.T_world_cam)
        np.testing.assert_allclose(feats2, feats)
        self.assertLess(np.abs(obs2.rgb.astype(int) - obs.rgb.astype(int)).max(), 8)

    def test_stages_after_detection_on_a_synthetic_photo(self):
        """S2 drops the low-confidence non-target, S7 to S9 lift the other."""
        obs, masks = patch_scene([(20, 20, 60, 60, 1.5), (90, 30, 130, 80, 2.2)])
        raw = dets([[20, 20, 60, 60], [90, 30, 130, 80]], [0.9, 0.2], ["chair", "box"], masks)
        res = stages_after_detection(obs, raw, lambda d: np.ones((len(d), 4)), frozenset(), CFG)
        self.assertEqual(res.dets.label, ["chair"])
        self.assertEqual([c.label for c in res.candidates], ["chair"])
        self.assertAlmostEqual(res.candidates[0].box.center[2], 1.5, delta=0.05)


@unittest.skipUnless((FIXTURE / "expected.json").exists(), "lab photo fixture not stored yet")
class LabPhotoTest(unittest.TestCase):
    """T6.3's bench test: one lab photo, every stage after SAM 3."""

    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads((FIXTURE / "expected.json").read_text())
        cls.results = {fid: _replay(FIXTURE / f"photo_{int(fid):04d}.npz") for fid in cls.expected}

    def test_same_objects_as_the_recorded_run(self):
        """Same labels in the same order, centres within 5 cm of the GPU run."""
        for fid, want in self.expected.items():
            got = self.results[fid].candidates
            with self.subTest(frame=fid):
                self.assertEqual([c.label for c in got], [w["label"] for w in want])
                for c, w in zip(got, want):
                    self.assertLess(np.linalg.norm(c.box.center - w["centre"]), 0.05, c.label)

    def test_no_pixel_in_two_masks(self):
        """T6.3d's done-when on real SAM 3 output, after S5."""
        for fid, res in self.results.items():
            with self.subTest(frame=fid):
                self.assertLessEqual(res.dets.masks.sum(axis=0).max(), 1)

    def test_objects_are_in_front_of_the_camera_and_in_range(self):
        for fid, res in self.results.items():
            T_cam_world = np.linalg.inv(res.obs.T_world_cam)
            for c in res.candidates:
                with self.subTest(frame=fid, label=c.label):
                    centre_cam = T_cam_world[:3, :3] @ c.box.center + T_cam_world[:3, 3]
                    self.assertGreater(centre_cam[2], 0.0)
                    self.assertLessEqual(np.linalg.norm(c.box.center - res.obs.camera_position),
                                         CFG.max_object_distance_m + c.box.half_diagonal)

    def test_every_object_has_a_unit_feature(self):
        for res in self.results.values():
            for c in res.candidates:
                self.assertAlmostEqual(float(np.linalg.norm(c.clip)), 1.0, places=4)

    def test_objects_go_into_the_store(self):
        """S10 and S11: every candidate becomes or joins an object entry."""
        store = ObjectStore(CFG)
        n = 0
        for fid, res in self.results.items():
            ids = store.integrate(res.candidates, anchor=int(fid))
            self.assertEqual(len(ids), len(res.candidates))
            n += len(res.candidates)
        self.assertGreater(len(store), 0)
        self.assertLessEqual(len(store), n)


if __name__ == "__main__":
    unittest.main()
