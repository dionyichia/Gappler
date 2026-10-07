"""The real S6 encoder, open_clip ViT-B-32 (T6.3f, D-MG7).

Upstream (HiCo-Nav at ffc1517) uses this model for four things. Each has a test
class below, named Use1 to Use4:

  1. a feature per detected object for the map            map/map.py:671
  2. matching a detection to a stored object, and          map/map.py:838
     averaging the features of matched objects            map/map_elements.py:162
  3. task relevance: a score per photo from the task       map/map.py:150, :875
     text, and choosing target classes from the text      map/map.py:193
  4. scoring a frontier's photo against the task text      habitat/policy.py:178

Uses 3 and 4 are tested at the encoder only: that text and images land in one
space and rank the way those uses need. The functions that compute the scores
inside the graph are not built yet (T6.7a, T6.7b, T6.7d). The averaging in use 2
is T6.4c, also not built, so its test is skipped.

These tests load the model, so they need open_clip, torch and the weights.
Without any of them the whole file is reported as skipped. Nothing is downloaded
here. Fetch the weights once with: python -m memory_graph.clip_encoder
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest
from pathlib import Path

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.association import appearance_matrix, combined_scores
from memory_graph.image_feature import image_features, l2_normalise
from memory_graph.stage_types import Candidate, OrientedBox

try:
    import open_clip  # noqa: F401
    import torch  # noqa: F401
except ImportError as exc:  # pragma: no cover - depends on the machine
    raise unittest.SkipTest(f"needs open_clip and torch: {exc}")

from memory_graph.clip_encoder import OpenClipEncoder, cache_dir, weights_present

CFG = MemoryGraphConfig()
if not weights_present(CFG.clip_model, CFG.clip_pretrained):  # pragma: no cover
    raise unittest.SkipTest(
        f"no {CFG.clip_model} weights in {cache_dir()}: run python -m memory_graph.clip_encoder")

FIXTURES = Path(__file__).parent / "fixtures"
CHAIR_VIEWS = ("chair_view_a.jpg", "chair_view_b.jpg")
OTHER_OBJECTS = ("sofa.jpg", "shelf.jpg", "bench.jpg")


def textured(seed, h, w):
    """A random blocky image, so different seeds look different to the model."""
    blocks = np.random.default_rng(seed).integers(0, 256, (8, 8, 3), dtype=np.uint8)
    return np.kron(blocks, np.ones((h // 8 + 1, w // 8 + 1, 1), dtype=np.uint8))[:h, :w]


def solid(colour, h, w):
    return np.full((h, w, 3), colour, dtype=np.uint8)


RED, BLUE, GREEN = (220, 20, 20), (20, 20, 220), (20, 200, 20)


class EncoderCase(unittest.TestCase):
    """One model for every test in the file. Loading it takes a few seconds."""

    encoder = None

    @classmethod
    def setUpClass(cls):
        if EncoderCase.encoder is None:
            EncoderCase.encoder = OpenClipEncoder.from_config(CFG)
        cls.crops = [textured(0, 40, 60), textured(1, 200, 90), textured(2, 17, 300)]

    def unit_images(self, images):
        return l2_normalise(self.encoder.encode(images))

    def unit_texts(self, texts):
        return l2_normalise(self.encoder.encode_text(texts))


class Use1ObjectFeatureTest(EncoderCase):
    """A feature per detected object."""

    def test_one_finite_vector_per_crop(self):
        f = self.encoder.encode(self.crops)
        self.assertEqual(f.shape, (3, 512))
        self.assertEqual(f.dtype, np.float32)
        self.assertTrue(np.isfinite(f).all())

    def test_same_crop_gives_same_vector(self):
        np.testing.assert_allclose(self.encoder.encode(self.crops), self.encoder.encode(self.crops), atol=1e-5)

    def test_vector_does_not_depend_on_the_batch(self):
        together = self.encoder.encode(self.crops)
        alone = np.concatenate([self.encoder.encode([c]) for c in self.crops])
        np.testing.assert_allclose(together, alone, atol=1e-4)

    def test_small_batches_give_the_same_vectors(self):
        one_at_a_time = OpenClipEncoder.from_config(MemoryGraphConfig(clip_batch_size=1))
        np.testing.assert_allclose(one_at_a_time.encode(self.crops), self.encoder.encode(self.crops), atol=1e-4)

    def test_no_crops(self):
        self.assertEqual(len(self.encoder.encode([])), 0)

    def test_through_image_features(self):
        rgb = textured(3, 240, 320)
        boxes = np.array([[10, 10, 100, 120], [150, 40, 310, 230]], dtype=float)
        f = image_features(rgb, boxes, self.encoder, CFG)
        self.assertEqual(f.shape, (2, 512))
        np.testing.assert_allclose(np.linalg.norm(f, axis=1), 1.0)

    def test_same_chair_scores_above_a_chair_against_other_objects(self):
        """The T6.3f done-when, on photos from the lab. The different objects
        are a sofa, a shelf and a bench (changed from a sink on 2026-10-07)."""
        names = CHAIR_VIEWS + OTHER_OBJECTS
        missing = [n for n in names if not (FIXTURES / n).exists()]
        if missing:
            self.skipTest(f"no test photos {missing} in {FIXTURES.name}/ (see its README)")
        from PIL import Image

        f = self.unit_images([np.asarray(Image.open(FIXTURES / n).convert("RGB")) for n in names])
        same = float(f[0] @ f[1])
        self.assertGreater(same, 0.8, f"same chair scored {same:.3f}")
        for i, name in enumerate(OTHER_OBJECTS, start=2):
            different = max(float(f[0] @ f[i]), float(f[1] @ f[i]))
            self.assertLess(different, same - 0.1, f"chair against {name} {different:.3f}, same chair {same:.3f}")


class Use2AssociationTest(EncoderCase):
    """Matching a detection to a stored object by appearance and overlap."""

    @staticmethod
    def candidate(feature):
        points = np.zeros((1, 3))
        box = OrientedBox(center=np.zeros(3), R=np.eye(3), extent=np.ones(3))
        return Candidate(points=points, colors=points, box=box, label="thing", conf=0.9, clip=feature)

    def test_real_features_rank_the_same_object_first(self):
        # The red thing seen twice at different sizes, and a blue thing.
        red_a, red_b, blue = self.unit_images([solid(RED, 60, 60), solid(RED, 90, 50), solid(BLUE, 60, 60)])
        appearance = appearance_matrix([self.candidate(red_a)], [self.candidate(red_b), self.candidate(blue)])
        self.assertEqual(appearance.shape, (1, 2))
        self.assertGreater(appearance[0, 0], 0.8)
        self.assertGreater(appearance[0, 0], appearance[0, 1] + 0.05)

    def test_blend_with_overlap_uses_phys_bias(self):
        red, blue = self.unit_images([solid(RED, 60, 60), solid(BLUE, 60, 60)])
        appearance = appearance_matrix([self.candidate(red)], [self.candidate(red), self.candidate(blue)])
        overlap = np.array([[0.4, 0.4]])
        scores = combined_scores(overlap, appearance, CFG)
        np.testing.assert_allclose(scores, (1 + CFG.phys_bias) * overlap + (1 - CFG.phys_bias) * appearance)
        self.assertGreater(scores[0, 0], scores[0, 1])     # equal overlap, appearance decides

    @unittest.skip("the merge is not built yet: T6.4c (features averaged by sighting count, then re-normalised)")
    def test_merged_feature_is_the_sighting_weighted_average(self):
        pass


class Use3TaskRelevanceTest(EncoderCase):
    """The task text against class names and against object features."""

    def test_text_and_image_vectors_share_one_space(self):
        text = self.encoder.encode_text(["find a chair", "sink"])
        self.assertEqual(text.shape, (2, 512))
        self.assertEqual(text.dtype, np.float32)
        self.assertTrue(np.isfinite(text).all())
        self.assertEqual(text.shape[1], self.encoder.encode(self.crops[:1]).shape[1])

    def test_same_text_gives_same_vector(self):
        a = self.encoder.encode_text(["find a chair"])
        b = self.encoder.encode_text(["sink", "find a chair"])
        np.testing.assert_allclose(a[0], b[1], atol=1e-4)

    def test_no_texts(self):
        self.assertEqual(len(self.encoder.encode_text([])), 0)

    def test_target_class_chosen_from_the_task_text(self):
        """Upstream's rule (map/map.py:193): keep the classes within 95 % of the best."""
        classes = ["sink", "refrigerator", "chair", "window", "toilet", "bed"]
        similarity = self.unit_texts(classes) @ self.unit_texts(["find a chair"])[0]
        kept = [c for c, s in zip(classes, similarity) if s >= 0.95 * similarity.max()]
        self.assertEqual(kept, ["chair"])

    def test_task_score_is_higher_for_the_photo_with_matching_objects(self):
        """Upstream's task_score (map/map_elements.py:322): the sum over a photo's
        objects of cos(object feature, task feature)."""
        task = self.unit_texts(["a red object"])[0]
        two_red = self.unit_images([solid(RED, 60, 60), solid(RED, 90, 50)])
        two_other = self.unit_images([solid(BLUE, 60, 60), solid(GREEN, 40, 80)])
        self.assertGreater(float(np.sum(two_red @ task)), float(np.sum(two_other @ task)) + 0.1)

    def test_each_colour_matches_its_own_description(self):
        images = self.unit_images([solid(RED, 60, 60), solid(BLUE, 90, 50), solid(GREEN, 40, 80)])
        texts = self.unit_texts(["a red object", "a blue object", "a green object"])
        self.assertEqual((images @ texts.T).argmax(axis=1).tolist(), [0, 1, 2])


class Use4FrontierScoreTest(EncoderCase):
    """A whole photo scored against the task text (habitat/policy.py:178)."""

    def test_whole_photos_rank_by_the_task_text(self):
        frames = self.unit_images([solid(BLUE, 480, 640), solid(RED, 480, 640), solid(GREEN, 480, 640)])
        task = self.unit_texts(["go to the red wall"])[0]
        scores = frames @ task
        self.assertEqual(scores.shape, (3,))
        self.assertEqual(int(scores.argmax()), 1)
        self.assertGreater(scores[1], np.delete(scores, 1).max() + 0.05)


if __name__ == "__main__":
    unittest.main()
