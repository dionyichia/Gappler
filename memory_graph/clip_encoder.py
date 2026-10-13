"""The real encoder for S6 (T6.3f): open_clip behind image_feature.ImageEncoder.

Decided 2026-10-07 (D-MG7 in docs/MEMORY_GRAPH_DESIGN.md): open_clip ViT-B-32
with the laion2b_s34b_b79k weights, as upstream (map/map.py:96). The vectors
have 512 numbers.

    encoder = OpenClipEncoder.from_config(cfg)
    features = image_features(rgb, boxes, encoder, cfg)     # one vector per object
    task = encoder.encode_text(["find a chair"])            # same space, same length

Image and text vectors can be compared with a dot product once both are
L2-normalised. Upstream uses that for task scores, for choosing target classes
and for scoring frontier photos (map/map.py:150, :193, :875, habitat/policy.py:178).

This is the only memory graph file that imports torch, and it does so when the
encoder is created, not when the file is imported.

The weights (about 600 MB) are downloaded on first use into
assets/models/open_clip/, which is gitignored. Set OPEN_CLIP_CACHE_DIR to keep
them somewhere else. To fetch them once and check the model loads:

    python -m memory_graph.clip_encoder
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Optional, Sequence

import numpy as np

from memory_graph.config import MemoryGraphConfig

REPO = Path(__file__).resolve().parent.parent


def cache_dir() -> Path:
    return Path(os.environ.get("OPEN_CLIP_CACHE_DIR", REPO / "assets/models/open_clip"))


def weights_present(model: str, pretrained: str) -> bool:
    """True if the weights are already on disk, so loading needs no download."""
    import open_clip

    hub_id = (open_clip.get_pretrained_cfg(model, pretrained) or {}).get("hf_hub", "").strip("/")
    if not hub_id:
        return False
    snapshots = cache_dir() / ("models--" + hub_id.replace("/", "--")) / "snapshots"
    return any(snapshots.glob("*/open_clip_model.*"))


class OpenClipEncoder:
    def __init__(
        self,
        model: str = "ViT-B-32",
        pretrained: str = "laion2b_s34b_b79k",
        device: str = "auto",
        batch_size: int = 64,
        weights_dir: Optional[Path] = None,
    ) -> None:
        import open_clip
        import torch

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.batch_size = batch_size
        self._torch = torch
        weights_dir = Path(weights_dir) if weights_dir else cache_dir()
        weights_dir.mkdir(parents=True, exist_ok=True)
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model, pretrained=pretrained, device=self.device, cache_dir=str(weights_dir)
        )
        self._model.eval()
        self._tokenizer = open_clip.get_tokenizer(model)

    @classmethod
    def from_config(cls, cfg: MemoryGraphConfig) -> "OpenClipEncoder":
        return cls(cfg.clip_model, cfg.clip_pretrained, cfg.clip_device, cfg.clip_batch_size)

    def _precision(self):
        """Decided 2026-10-07 (Zongzhe, D-MG7): follow upstream, float16 on a GPU.
        Upstream wraps both encoders in torch.amp.autocast("cuda")
        (map/map_utils.py:77, :85), which runs most of the model in float16.
        SAM 3's wrapper leaves bfloat16 switched on in its thread
        (sam3_model.py:63). Asking for float16 here overrides that for the CLIP
        call only, so a vector does not depend on whether SAM 3 loaded first.
        On a CPU there is no autocast and the model runs in float32, as upstream."""
        if self.device.type == "cuda":
            return self._torch.autocast("cuda", dtype=self._torch.float16)
        return contextlib.nullcontext()

    def encode(self, crops: Sequence[np.ndarray]) -> np.ndarray:
        """RGB uint8 images, any sizes -> (N, D) float32 array. Not normalised:
        image_features does that. A whole photo works as well as a crop."""
        from PIL import Image

        torch = self._torch
        out = []
        with torch.no_grad(), self._precision():
            for start in range(0, len(crops), self.batch_size):
                batch = torch.stack(
                    [self._preprocess(Image.fromarray(np.ascontiguousarray(c))) for c in crops[start:start + self.batch_size]]
                ).to(self.device)
                out.append(self._model.encode_image(batch).float().cpu().numpy())
        if not out:
            return np.zeros((0, 0), dtype=np.float32)
        return np.concatenate(out)

    def encode_text(self, texts: Sequence[str]) -> np.ndarray:
        """Sentences or class names -> (N, D) float32 array, in the same space
        as the image vectors. Not normalised, like encode."""
        torch = self._torch
        out = []
        with torch.no_grad(), self._precision():
            for start in range(0, len(texts), self.batch_size):
                tokens = self._tokenizer(list(texts[start:start + self.batch_size])).to(self.device)
                out.append(self._model.encode_text(tokens).float().cpu().numpy())
        if not out:
            return np.zeros((0, 0), dtype=np.float32)
        return np.concatenate(out)


if __name__ == "__main__":
    cfg = MemoryGraphConfig()
    encoder = OpenClipEncoder.from_config(cfg)
    vector = encoder.encode([np.zeros((32, 32, 3), dtype=np.uint8)])
    print(f"{cfg.clip_model} {cfg.clip_pretrained} loaded on {encoder.device}, "
          f"vector length {vector.shape[1]}, weights in {cache_dir()}")
