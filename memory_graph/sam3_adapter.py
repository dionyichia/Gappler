"""S1 and S4 from SAM 3: detections with their masks (T6.3d, and S1 of T6.3c).

SAM 3 is the detector and the mask model (D-MG6 in docs/MEMORY_GRAPH_DESIGN.md).
One call takes one text prompt and returns boxes, scores and masks together, so
S1 and S4 are one step here, where upstream runs YOLO-World and then MobileSAM.

This file turns SAM 3's result into a Detections and feeds it through the stages
already written: S2 filtering (detection_filter.py), then S4 erosion and S5
cleanup (masks.py).

It does not import SAM 3 or torch. It takes any object with the method the
repo's wrapper has, process_text_prompt(image, prompt)
(aria/aria_app/services/object_recognition/sam3_model.py), so it is tested with
a stand-in and the model can be changed later.

The result it reads is the processor's state dict (sam3_image_processor.py,
_forward_grounding), for N detections on an H x W image:

    "masks"   bool (N, 1, H, W)
    "boxes"   float (N, 4), x0 y0 x1 y1 in pixels
    "scores"  float (N,), already cut at the processor's confidence threshold

Not decided here, left to T6.3c:
  - How the vocabulary maps to prompts. `detect` makes one call per phrase, the
    plain reading of the wrapper. The wrapper encodes the image again on every
    call. The processor can encode it once (set_image) and then take each phrase
    (set_text_prompt), which would be cheaper. Not measured.
  - The processor's own threshold. The wrapper's default is 0.5, which is above
    cfg.confidence_threshold (0.3). S2 keeps a target class at any confidence,
    but it can only keep what SAM 3 hands over, so the wrapper has to be built
    with a low threshold for that rule to mean anything.
"""

from __future__ import annotations

from typing import AbstractSet, Any, List, Mapping, Protocol, Sequence, Tuple

import numpy as np

from memory_graph.config import MemoryGraphConfig
from memory_graph.detection_filter import filter_detections
from memory_graph.masks import clean_masks
from memory_graph.stage_types import Detections


class TextSegmenter(Protocol):
    def process_text_prompt(self, image: np.ndarray, prompt: str) -> Mapping[str, Any]:
        """RGB uint8 image and one phrase -> a dict with "masks", "boxes", "scores"."""
        ...


def _as_numpy(value: Any) -> np.ndarray:
    """A numpy array from a numpy array, a list, or a torch tensor on any device.

    SAM 3's wrapper runs in bfloat16, which numpy cannot hold, so a floating
    tensor is widened to float32 first.
    """
    if hasattr(value, "detach"):                       # a torch tensor
        value = value.detach()
        if value.is_floating_point():
            value = value.float()
        return value.cpu().numpy()
    return np.asarray(value)


def detections_from_state(
    state: Mapping[str, Any], label: str, class_id: int, image_shape: Tuple[int, int]
) -> Detections:
    """One prompt's result as Detections. Every detection gets `label` and
    `class_id`, since SAM 3 was asked for that one phrase. A result with nothing
    in it, or with no "masks" key, gives zero detections."""
    h, w = image_shape
    if state.get("masks") is None or len(state["masks"]) == 0:
        return Detections.empty(image_shape)
    masks = _as_numpy(state["masks"]).astype(bool)
    n = len(masks)
    masks = masks.reshape(n, *masks.shape[-2:])        # (N, 1, H, W) or (N, H, W)
    if masks.shape[1:] != (h, w):
        raise ValueError(f"masks are {masks.shape[1:]}, the image is {(h, w)}")
    return Detections(
        xyxy=_as_numpy(state["boxes"]),
        conf=_as_numpy(state["scores"]),
        class_id=np.full(n, class_id, dtype=np.int64),
        label=[label] * n,
        masks=masks,
    )


def detect(segmenter: TextSegmenter, rgb: np.ndarray, vocabulary: Sequence[str]) -> Detections:
    """S1 and S4: every phrase of the vocabulary, one call each, in one Detections.

    class_id is the phrase's position in `vocabulary`. Not sorted and not
    filtered: that is S2.
    """
    image_shape = rgb.shape[:2]
    parts: List[Detections] = []
    for class_id, phrase in enumerate(vocabulary):
        state = segmenter.process_text_prompt(rgb, phrase)
        parts.append(detections_from_state(state, phrase, class_id, image_shape))
    parts = [p for p in parts if len(p)]
    if not parts:
        return Detections.empty(image_shape)
    return Detections(
        xyxy=np.concatenate([p.xyxy for p in parts]),
        conf=np.concatenate([p.conf for p in parts]),
        class_id=np.concatenate([p.class_id for p in parts]),
        label=[lbl for p in parts for lbl in p.label],
        masks=np.concatenate([p.masks for p in parts]),
    )


def segment_photo(
    segmenter: TextSegmenter,
    rgb: np.ndarray,
    vocabulary: Sequence[str],
    targets: AbstractSet[str],
    cfg: MemoryGraphConfig,
) -> Detections:
    """S1, S2, S4 and S5 for one photo: detect, filter, erode, clean.

    The detections come back sorted by confidence, with one cleaned mask each.
    An object inside another is cut out of it (the cup out of the table). An
    object found under two phrases is kept once, under the more confident one
    (S5's duplicate rule).
    """
    dets = detect(segmenter, rgb, vocabulary)
    dets = filter_detections(dets, rgb.shape[:2], targets, cfg)
    cleaned, _ = clean_masks(dets, cfg)
    return cleaned
