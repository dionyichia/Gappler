"""Every vocabulary phrase on one photo in one SAM 3 pass (T6.3c).

The repo's SAM 3 wrappers call Sam3Processor once per phrase, and each call
encodes the image again. The model itself takes a batch of queries, each an
image id and a text id (FindStage, used in sam3/model/sam3_image.py:178), and
SAM 3's own example examples/sam3_image_batched_inference.ipynb runs several
phrases on one image in one forward. This file does the same with the
processor the wrappers already build:

  1. processor.set_image once: the image encoder, the costly part.
  2. forward_text with all the phrases at once.
  3. forward_grounding with one query per phrase, all on image 0.
  4. split the outputs per query, with the same steps as the processor's
     _forward_grounding (sam3_image_processor.py:184).

The fusion encoder, the decoder and the mask head still run once per phrase,
batched on the GPU, so the cost still grows with the vocabulary, more slowly.
At most max_prompts_per_pass phrases go into one forward, because the image
features are copied once per query.

The results are the same dicts the per-phrase path gives (masks, boxes,
scores), one per phrase in order, so sam3_adapter.detect reads either.

torch and SAM 3 are imported on first use, so this module imports anywhere.
Not yet run with the real model: the first run is the lab box check in T6.3c.
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple


def split_outputs(
    outputs: Dict[str, Any], threshold: float, image_shape: Tuple[int, int]
) -> List[Dict[str, Any]]:
    """forward_grounding's outputs for N queries as N result dicts.

    The same steps as Sam3Processor._forward_grounding, done per query instead
    of over the whole batch at once, which would mix the queries together:
    score = sigmoid(logit) x sigmoid(presence), keep score > threshold, boxes
    from centre and size (0 to 1) to pixel corners, masks resized to the image
    and cut at 0.5.
    """
    import torch
    import torch.nn.functional as F

    h, w = image_shape
    probs = outputs["pred_logits"].sigmoid()                       # (N, Q, 1)
    presence = outputs["presence_logit_dec"].sigmoid().unsqueeze(1)  # (N, 1, 1)
    probs = (probs * presence).squeeze(-1)                          # (N, Q)
    scale = torch.tensor([w, h, w, h], device=probs.device)
    results = []
    for q in range(probs.shape[0]):
        keep = probs[q] > threshold
        cx, cy, bw, bh = outputs["pred_boxes"][q][keep].unbind(-1)
        boxes = torch.stack([cx - 0.5 * bw, cy - 0.5 * bh, cx + 0.5 * bw, cy + 0.5 * bh], dim=-1)
        masks = outputs["pred_masks"][q][keep].unsqueeze(1)          # (K, 1, h', w')
        if len(masks):
            masks = F.interpolate(masks, (h, w), mode="bilinear", align_corners=False).sigmoid()
        else:
            masks = masks.new_zeros((0, 1, h, w))
        results.append({"masks": masks > 0.5, "boxes": boxes * scale, "scores": probs[q][keep]})
    return results


class BatchedSam3:
    """SAM 3 with every phrase of a photo in as few passes as possible.

    `processor` is a sam3 Sam3Processor, for example `.processor` of the
    segmentation service's Sam3 (shared_services/segmentation) or of the aria
    SAM3Model. Its confidence threshold applies here too.
    """

    def __init__(self, processor: Any, max_prompts_per_pass: int = 16) -> None:
        if max_prompts_per_pass < 1:
            raise ValueError(f"max_prompts_per_pass must be 1 or more, got {max_prompts_per_pass}")
        self.processor = processor
        self.max_prompts_per_pass = int(max_prompts_per_pass)

    def process_text_prompt(self, image: Any, prompt: str) -> Dict[str, Any]:
        """One phrase, the way the wrappers do it: image encoder, then text.
        Kept so the two paths can be compared on the same model."""
        state = self.processor.set_image(image)
        return self.processor.set_text_prompt(state=state, prompt=prompt)

    def process_text_prompts(self, image: Any, prompts: Sequence[str]) -> List[Dict[str, Any]]:
        """Every phrase on one image: one result dict per phrase, in order."""
        prompts = list(prompts)
        if not prompts:
            return []
        state = self.processor.set_image(image)          # the image encoder, once
        shape = (state["original_height"], state["original_width"])
        results: List[Dict[str, Any]] = []
        step = self.max_prompts_per_pass
        for start in range(0, len(prompts), step):
            outputs = self._forward(state, prompts[start:start + step])
            results += split_outputs(outputs, self.processor.confidence_threshold, shape)
        return results

    def _forward(self, state: Dict[str, Any], prompts: List[str]) -> Dict[str, Any]:
        """One forward_grounding for len(prompts) queries on the one image,
        as set_text_prompt does for one (sam3_image_processor.py:114)."""
        import torch
        from sam3.model.data_misc import FindStage

        model, device, n = self.processor.model, self.processor.device, len(prompts)
        find = FindStage(
            img_ids=torch.zeros(n, device=device, dtype=torch.long),
            text_ids=torch.arange(n, device=device, dtype=torch.long),
            input_boxes=None,
            input_boxes_mask=None,
            input_boxes_label=None,
            input_points=None,
            input_points_mask=None,
        )
        with torch.inference_mode():
            backbone_out = dict(state["backbone_out"])   # leave the image's state as it was
            backbone_out.update(model.backbone.forward_text(prompts, device=device))
            return model.forward_grounding(
                backbone_out=backbone_out,
                find_input=find,
                geometric_prompt=model._get_dummy_prompt(num_prompts=n),
                find_target=None,
            )
