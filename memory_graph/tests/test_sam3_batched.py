"""The batched SAM 3 path's own logic (sam3_batched.py), without SAM 3.

split_outputs gets made-up forward_grounding outputs. The pass splitting is
checked with a stand-in processor and a stand-in forward. Needs torch, so it is
skipped where torch is missing. The real model runs only on the lab box (T6.3c).
"""

import unittest

try:
    import torch
except ImportError as exc:  # pragma: no cover - depends on the machine
    raise unittest.SkipTest(f"needs torch: {exc}")

from memory_graph.sam3_batched import BatchedSam3, split_outputs

H, W = 40, 80      # the image
MH, MW = 10, 20    # the mask grid SAM 3 predicts on


def logit(p):
    return torch.logit(torch.tensor(p))


def outputs(scores, presence, boxes):
    """forward_grounding outputs for N queries with Q slots each.
    scores (N, Q) and presence (N,) are probabilities, boxes (N, Q, 4) are
    centre and size in 0 to 1. Every mask is the left half of the grid."""
    n, q = len(scores), len(scores[0])
    masks = torch.full((n, q, MH, MW), -10.0)
    masks[..., : MW // 2] = 10.0
    return {
        "pred_logits": logit(scores).reshape(n, q, 1),
        "presence_logit_dec": logit(presence).reshape(n, 1),
        "pred_boxes": torch.tensor(boxes, dtype=torch.float32),
        "pred_masks": masks,
    }


BOX = [0.5, 0.25, 0.5, 0.5]          # centred at (40, 10) px, 40 x 20 px


class SplitOutputsTest(unittest.TestCase):
    def test_one_result_per_query_in_order(self):
        out = outputs([[0.9, 0.2], [0.1, 0.1], [0.8, 0.7]], [0.99, 0.99, 0.99], [[BOX, BOX]] * 3)
        results = split_outputs(out, 0.5, (H, W))
        self.assertEqual([len(r["scores"]) for r in results], [1, 0, 2])

    def test_score_is_logit_times_presence(self):
        # 0.9 x 0.5 = 0.45 is under 0.5: the phrase is judged absent, as the processor does
        out = outputs([[0.9], [0.9]], [0.5, 0.99], [[BOX], [BOX]])
        results = split_outputs(out, 0.5, (H, W))
        self.assertEqual(len(results[0]["scores"]), 0)
        self.assertAlmostEqual(float(results[1]["scores"][0]), 0.9 * 0.99, places=5)

    def test_boxes_are_pixel_corners(self):
        results = split_outputs(outputs([[0.9]], [0.99], [[BOX]]), 0.5, (H, W))
        torch.testing.assert_close(results[0]["boxes"], torch.tensor([[20.0, 0.0, 60.0, 20.0]]))

    def test_masks_are_resized_to_the_image_and_bool(self):
        masks = split_outputs(outputs([[0.9]], [0.99], [[BOX]]), 0.5, (H, W))[0]["masks"]
        self.assertEqual(tuple(masks.shape), (1, 1, H, W))
        self.assertEqual(masks.dtype, torch.bool)
        self.assertTrue(bool(masks[0, 0, :, : W // 2 - 2].all()))
        self.assertFalse(bool(masks[0, 0, :, W // 2 + 2 :].any()))

    def test_nothing_kept_gives_empty_results_of_the_right_shape(self):
        r = split_outputs(outputs([[0.1]], [0.99], [[BOX]]), 0.5, (H, W))[0]
        self.assertEqual(tuple(r["masks"].shape), (0, 1, H, W))
        self.assertEqual(tuple(r["boxes"].shape), (0, 4))


class FakeProcessor:
    confidence_threshold = 0.5

    def __init__(self):
        self.images = 0

    def set_image(self, image):
        self.images += 1
        return {"original_height": H, "original_width": W, "backbone_out": {}}


class CountingBatchedSam3(BatchedSam3):
    """The real pass splitting, with a stand-in forward: query i finds one
    object with score 0.6 + i / 100, so the order can be read back."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passes = []

    def _forward(self, state, prompts):
        self.passes.append(list(prompts))
        start = sum(len(p) for p in self.passes[:-1])
        scores = [[0.6 + (start + i) / 100] for i in range(len(prompts))]
        return outputs(scores, [0.999] * len(prompts), [[BOX]] * len(prompts))


class PassesTest(unittest.TestCase):
    def test_the_image_is_encoded_once_and_phrases_go_in_passes(self):
        sam = CountingBatchedSam3(FakeProcessor(), max_prompts_per_pass=2)
        results = sam.process_text_prompts("image", ["a", "b", "c", "d", "e"])
        self.assertEqual(sam.processor.images, 1)
        self.assertEqual(sam.passes, [["a", "b"], ["c", "d"], ["e"]])
        scores = [round(float(r["scores"][0]) / 0.999, 4) for r in results]
        self.assertEqual(scores, [0.6, 0.61, 0.62, 0.63, 0.64])      # results stay in phrase order

    def test_no_phrases_no_work(self):
        sam = CountingBatchedSam3(FakeProcessor())
        self.assertEqual(sam.process_text_prompts("image", []), [])
        self.assertEqual(sam.processor.images, 0)

    def test_a_pass_needs_at_least_one_phrase(self):
        with self.assertRaises(ValueError):
            BatchedSam3(FakeProcessor(), max_prompts_per_pass=0)


if __name__ == "__main__":
    unittest.main()
