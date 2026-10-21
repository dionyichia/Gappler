"""A whole photo scored against the task text (T6.7d).

A stand-in encoder is used here, so the tests need no model. The same ranking
with the real encoder is in test_clip_encoder.py (Use4).
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.photo_score import PhotoScorer
from memory_graph.task import TaskContext
from memory_graph.tests.test_task import CHAIR, PLANT, SOFA, WordEncoder, chair_task


def photo(*axes):
    """A stand-in photo: an image whose mean colour is the sum of the given
    axes, so the stand-in encoder reads back what the photo shows."""
    return np.full((4, 6, 3), 100 * sum(axes, np.zeros(3)), dtype=np.uint8)


class ColourEncoder:
    """Stand-in image encoder: a photo is its mean colour, red for chair, green
    for sofa, blue for plant, at an arbitrary length, as the real encoder's
    output is not normalised. Counts the photos it encodes."""

    def __init__(self):
        self.calls = 0
        self.photos = 0

    def encode(self, crops):
        self.calls += 1
        self.photos += len(crops)
        return np.array([3.0 * c.reshape(-1, 3).mean(axis=0) for c in crops])


class PhotoScorerTest(unittest.TestCase):
    def setUp(self):
        self.encoder = ColourEncoder()
        self.scorer = PhotoScorer(self.encoder)

    def test_a_photo_of_the_target_ranks_above_one_without_it(self):
        """The done-when."""
        photos = [("sofa", photo(SOFA)), ("chair", photo(CHAIR)), ("plant", photo(PLANT))]
        ranked = self.scorer.ranked(chair_task(), photos)
        self.assertEqual(ranked[0][0], "chair")
        self.assertGreater(ranked[0][1], max(score for _, score in ranked[1:]))

    def test_score_is_the_cosine(self):
        photos = [("chair", photo(CHAIR)), ("sofa", photo(SOFA)), ("both", photo(CHAIR, SOFA))]
        np.testing.assert_allclose(self.scorer.scores(chair_task(), photos), [1.0, 0.0, np.sqrt(0.5)])

    def test_scores_keep_the_order_given(self):
        photos = [("sofa", photo(SOFA)), ("chair", photo(CHAIR))]
        np.testing.assert_allclose(self.scorer.scores(chair_task(), photos), [0.0, 1.0])

    def test_each_photo_is_encoded_once(self):
        first = [("a", photo(CHAIR)), ("b", photo(SOFA))]
        self.scorer.scores(chair_task(), first)
        self.scorer.scores(chair_task(), first + [("c", photo(PLANT))])
        self.assertEqual(self.encoder.photos, 3)
        self.assertEqual(len(self.scorer), 3)

    def test_new_photos_are_encoded_in_one_call(self):
        self.scorer.scores(chair_task(), [("a", photo(CHAIR)), ("b", photo(SOFA)), ("c", photo(PLANT))])
        self.assertEqual(self.encoder.calls, 1)

    def test_nothing_is_encoded_when_every_photo_is_known(self):
        photos = [("a", photo(CHAIR))]
        self.scorer.scores(chair_task(), photos)
        self.scorer.scores(chair_task(), photos)
        self.assertEqual(self.encoder.calls, 1)

    def test_a_key_repeated_in_one_call_is_encoded_once(self):
        scores = self.scorer.scores(chair_task(), [("a", photo(CHAIR)), ("a", photo(CHAIR))])
        np.testing.assert_allclose(scores, [1.0, 1.0])
        self.assertEqual(self.encoder.photos, 1)

    def test_forget_encodes_the_photo_again(self):
        self.scorer.scores(chair_task(), [("a", photo(SOFA))])
        self.scorer.forget("a")
        scores = self.scorer.scores(chair_task(), [("a", photo(CHAIR))])
        np.testing.assert_allclose(scores, [1.0])
        self.assertEqual(self.encoder.photos, 2)

    def test_forget_an_unknown_key_does_nothing(self):
        self.scorer.forget("never seen")
        self.assertEqual(len(self.scorer), 0)

    def test_a_new_task_reuses_the_stored_features(self):
        photos = [("chair", photo(CHAIR)), ("sofa", photo(SOFA))]
        self.scorer.scores(chair_task(), photos)
        sofa_task = TaskContext.from_text("find a sofa", WordEncoder())
        ranked = self.scorer.ranked(sofa_task, photos)
        self.assertEqual(ranked[0][0], "sofa")
        self.assertEqual(self.encoder.calls, 1)

    def test_equal_scores_keep_the_order_given(self):
        photos = [("sofa", photo(SOFA)), ("plant", photo(PLANT)), ("chair", photo(CHAIR))]
        ranked = self.scorer.ranked(chair_task(), photos)
        self.assertEqual([key for key, _ in ranked], ["chair", "sofa", "plant"])

    def test_no_photos_gives_an_empty_result(self):
        self.assertEqual(self.scorer.scores(chair_task(), []).shape, (0,))
        self.assertEqual(self.scorer.ranked(chair_task(), []), [])
        self.assertEqual(self.encoder.calls, 0)

    def test_an_all_black_photo_scores_zero(self):
        np.testing.assert_allclose(self.scorer.scores(chair_task(), [("dark", photo())]), [0.0])

    def test_features_from_another_encoder_are_refused(self):
        class WideEncoder:
            def encode(self, crops):
                return np.ones((len(crops), 5))

        with self.assertRaises(ValueError):
            PhotoScorer(WideEncoder()).scores(chair_task(), [("a", photo(CHAIR))])

    def test_an_encoder_that_drops_a_photo_is_refused(self):
        class ShortEncoder:
            def encode(self, crops):
                return np.ones((len(crops) - 1, 3))

        with self.assertRaises(ValueError):
            PhotoScorer(ShortEncoder()).scores(chair_task(), [("a", photo(CHAIR)), ("b", photo(SOFA))])


if __name__ == "__main__":
    unittest.main()
