"""S1 and S4 from SAM 3, through S2 and S5 (T6.3d, and S1 of T6.3c).

SAM 3 itself is not loaded. FakeSam3 hands back results in the shape the real
processor does: bool masks (N, 1, H, W), pixel boxes (N, 4), scores (N,).
"""

from memory_graph.tests import _requires_numpy  # noqa: F401  (skips without numpy)

import unittest

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.sam3_adapter import detect, detections_from_state, segment_photo

try:
    import torch
except ImportError:  # pragma: no cover - depends on the machine
    torch = None

CFG = MemoryGraphConfig()
H, W = 60, 80
RGB = np.zeros((H, W, 3), dtype=np.uint8)


def rect(v0, v1, u0, u1):
    m = np.zeros((H, W), dtype=bool)
    m[v0:v1, u0:u1] = True
    return m


def found(*items):
    """A SAM 3 result. Each item is ((v0, v1, u0, u1), score): a filled
    rectangle as the mask, its outline as the box."""
    masks = np.zeros((len(items), 1, H, W), dtype=bool)
    boxes = np.zeros((len(items), 4))
    for i, ((v0, v1, u0, u1), _score) in enumerate(items):
        masks[i, 0] = rect(v0, v1, u0, u1)
        boxes[i] = (u0, v0, u1, v1)
    return {"masks": masks, "boxes": boxes, "scores": np.array([s for _, s in items], dtype=float)}


class FakeSam3:
    """Stands in for SAM3Model: a fixed result per phrase, and a record of calls."""

    def __init__(self, results):
        self.results = results
        self.calls = []

    def process_text_prompt(self, image, prompt):
        self.calls.append((image, prompt))
        return self.results.get(prompt, found())


class FakeBatchedSam3(FakeSam3):
    """Stands in for sam3_batched.BatchedSam3: the same results, all phrases in one call."""

    def __init__(self, results):
        super().__init__(results)
        self.batch_calls = []

    def process_text_prompts(self, image, prompts):
        self.batch_calls.append((image, list(prompts)))
        return [self.results.get(prompt, found()) for prompt in prompts]


TABLE = (10, 50, 10, 70)
CUP = (20, 30, 30, 40)


class ResultShapeTest(unittest.TestCase):
    def test_one_prompt_becomes_detections(self):
        d = detections_from_state(found((TABLE, 0.9), (CUP, 0.8)), "thing", 4, (H, W))
        self.assertEqual(len(d), 2)
        self.assertEqual(d.masks.shape, (2, H, W))
        self.assertEqual(d.masks.dtype, bool)
        np.testing.assert_array_equal(d.masks[1], rect(*CUP))
        np.testing.assert_array_equal(d.xyxy[1], [30, 20, 40, 30])
        np.testing.assert_allclose(d.conf, [0.9, 0.8])
        self.assertEqual(d.label, ["thing", "thing"])
        np.testing.assert_array_equal(d.class_id, [4, 4])

    def test_masks_without_the_extra_axis_also_work(self):
        state = found((CUP, 0.8))
        state["masks"] = state["masks"][:, 0]
        self.assertEqual(detections_from_state(state, "cup", 0, (H, W)).masks.shape, (1, H, W))

    def test_nothing_found(self):
        for state in (found(), {}, {"masks": None}):
            d = detections_from_state(state, "cup", 0, (H, W))
            self.assertEqual(len(d), 0)
            self.assertEqual(d.masks.shape, (0, H, W))

    def test_a_mask_of_the_wrong_size_is_an_error(self):
        with self.assertRaises(ValueError):
            detections_from_state(found((CUP, 0.8)), "cup", 0, (H + 1, W))

    @unittest.skipIf(torch is None, "needs torch")
    def test_torch_tensors_as_sam3_returns_them(self):
        """The wrapper runs in bfloat16, which numpy cannot hold."""
        state = found((TABLE, 0.75), (CUP, 0.5))
        state = {
            "masks": torch.from_numpy(state["masks"]),
            "boxes": torch.from_numpy(state["boxes"]).to(torch.bfloat16),
            "scores": torch.from_numpy(state["scores"]).to(torch.bfloat16),
        }
        d = detections_from_state(state, "thing", 0, (H, W))
        self.assertEqual(d.masks.shape, (2, H, W))
        self.assertEqual(d.masks.dtype, bool)
        np.testing.assert_allclose(d.conf, [0.75, 0.5])
        np.testing.assert_array_equal(d.xyxy[1], [30, 20, 40, 30])


class DetectTest(unittest.TestCase):
    def test_one_call_per_phrase_in_vocabulary_order(self):
        sam = FakeSam3({"table": found((TABLE, 0.9)), "cup": found((CUP, 0.8))})
        d = detect(sam, RGB, ["chair", "table", "cup"])
        self.assertEqual([prompt for _, prompt in sam.calls], ["chair", "table", "cup"])
        self.assertTrue(all(image is RGB for image, _ in sam.calls))
        self.assertEqual(d.label, ["table", "cup"])
        np.testing.assert_array_equal(d.class_id, [1, 2])           # positions in the vocabulary
        self.assertEqual(d.masks.shape, (2, H, W))

    def test_nothing_found_for_any_phrase(self):
        d = detect(FakeSam3({}), RGB, ["chair", "table"])
        self.assertEqual(len(d), 0)
        self.assertEqual(d.masks.shape, (0, H, W))

    def test_empty_vocabulary(self):
        self.assertEqual(len(detect(FakeSam3({}), RGB, [])), 0)


class BatchedDetectTest(unittest.TestCase):
    RESULTS = {"table": found((TABLE, 0.9)), "cup": found((CUP, 0.8), ((0, 5, 0, 5), 0.6))}
    VOCAB = ["chair", "table", "cup"]

    def assert_same(self, a, b):
        np.testing.assert_array_equal(a.xyxy, b.xyxy)
        np.testing.assert_array_equal(a.conf, b.conf)
        np.testing.assert_array_equal(a.class_id, b.class_id)
        self.assertEqual(a.label, b.label)
        np.testing.assert_array_equal(a.masks, b.masks)

    def test_one_call_for_the_whole_vocabulary(self):
        sam = FakeBatchedSam3(self.RESULTS)
        d = detect(sam, RGB, self.VOCAB)
        self.assertEqual(sam.batch_calls, [(RGB, self.VOCAB)])
        self.assertEqual(sam.calls, [])                              # no per-phrase calls
        self.assertEqual(d.label, ["table", "cup", "cup"])
        np.testing.assert_array_equal(d.class_id, [1, 2, 2])        # positions in the vocabulary

    def test_same_detections_as_one_call_per_phrase(self):
        sam = FakeBatchedSam3(self.RESULTS)
        self.assert_same(detect(sam, RGB, self.VOCAB, batched=True),
                         detect(sam, RGB, self.VOCAB, batched=False))
        self.assertEqual([p for _, p in sam.calls], self.VOCAB)

    def test_a_segmenter_without_the_batch_method_gets_one_call_per_phrase(self):
        sam = FakeSam3(self.RESULTS)
        self.assert_same(detect(sam, RGB, self.VOCAB), detect(FakeBatchedSam3(self.RESULTS), RGB, self.VOCAB))
        self.assertEqual(len(sam.calls), 3)

    def test_a_result_missing_for_a_phrase_is_an_error(self):
        sam = FakeBatchedSam3(self.RESULTS)
        sam.process_text_prompts = lambda image, prompts: [found()]
        with self.assertRaises(ValueError):
            detect(sam, RGB, self.VOCAB)

    def test_empty_vocabulary_makes_no_call(self):
        sam = FakeBatchedSam3(self.RESULTS)
        self.assertEqual(len(detect(sam, RGB, [])), 0)
        self.assertEqual(sam.batch_calls, [])

    def test_segment_photo_gives_the_same_either_way(self):
        sam = FakeBatchedSam3(self.RESULTS)
        both = [segment_photo(sam, RGB, self.VOCAB, set(), CFG) for sam in (sam, FakeSam3(self.RESULTS))]
        self.assert_same(*both)


class SegmentPhotoTest(unittest.TestCase):
    def test_the_cup_is_cut_out_of_the_table(self):
        """The T6.3d done-when, starting from SAM 3's output: the table mask has
        a hole where the cup is and no pixel belongs to two masks."""
        sam = FakeSam3({"table": found((TABLE, 0.9)), "cup": found((CUP, 0.8))})
        d = segment_photo(sam, RGB, ["table", "cup"], set(), CFG)
        self.assertEqual(d.label, ["table", "cup"])
        table, cup = d.masks
        self.assertGreater(cup.sum(), 0)
        self.assertFalse((table & cup).any())
        self.assertFalse(table[25, 35])                 # the middle of the cup
        self.assertTrue(table[40, 20])                  # table, away from the cup
        # Eroded by one pixel: the cup lost its rim, the table its outer edge.
        self.assertEqual(int(cup.sum()), 8 * 8)
        self.assertFalse(table[10, 10])

    def test_sorted_by_confidence_across_phrases(self):
        sam = FakeSam3({
            "cup": found(((5, 15, 5, 15), 0.4), ((5, 15, 60, 70), 0.95)),
            "book": found(((40, 50, 30, 40), 0.7)),
        })
        d = segment_photo(sam, RGB, ["cup", "book"], set(), CFG)
        self.assertEqual(d.label, ["cup", "book", "cup"])
        np.testing.assert_allclose(d.conf, [0.95, 0.7, 0.4])
        np.testing.assert_array_equal(d.class_id, [0, 1, 0])
        self.assertTrue(d.masks[1][45, 35])             # each mask stayed with its detection

    def test_a_weak_target_is_kept_and_a_weak_non_target_is_dropped(self):
        sam = FakeSam3({"cup": found(((5, 15, 5, 15), 0.15)), "book": found(((40, 50, 30, 40), 0.15))})
        d = segment_photo(sam, RGB, ["cup", "book"], {"cup"}, CFG)
        self.assertEqual(d.label, ["cup"])

    def test_background_classes_are_dropped(self):
        sam = FakeSam3({"wall": found(((0, 60, 0, 80), 0.99)), "cup": found((CUP, 0.8))})
        d = segment_photo(sam, RGB, ["wall", "cup"], set(), CFG)
        self.assertEqual(d.label, ["cup"])

    def test_one_object_found_under_two_phrases_is_kept_once(self):
        sam = FakeSam3({"chair": found((TABLE, 0.6)), "armchair": found((TABLE, 0.8))})
        d = segment_photo(sam, RGB, ["chair", "armchair"], set(), CFG)
        self.assertEqual(d.label, ["armchair"])         # the more confident phrase wins

    def test_nothing_found(self):
        d = segment_photo(FakeSam3({}), RGB, ["chair"], set(), CFG)
        self.assertEqual(len(d), 0)
        self.assertEqual(d.masks.shape, (0, H, W))


if __name__ == "__main__":
    unittest.main()
