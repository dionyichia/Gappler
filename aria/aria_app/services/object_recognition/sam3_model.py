import os
from typing import Optional

import numpy as np
import sam3
import torch
from sam3 import build_sam3_image_model
from sam3.model.sam3_image_processor import Sam3Processor

from config import Settings


class SAM3Model:
    def __init__(
        self,
        checkpoint_path: str,
        bpe_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        load_from_hf: bool = False,
        device: str = Settings.DEVICE,
    ):
        """
        Initialize SAM3 segmentation model.

        Args:
            checkpoint_path: Path to model checkpoint
            bpe_path: Path to BPE vocabulary file (defaults to assets folder)
            confidence_threshold: Confidence threshold for predictions
            load_from_hf: Whether to load from HuggingFace
            device: Device to run model on
        """
        self.device = device
        self.confidence_threshold = confidence_threshold

        # Setup paths
        sam3_root = os.path.join(os.path.dirname(sam3.__file__))
        self.bpe_path = bpe_path or f"{sam3_root}/assets/bpe_simple_vocab_16e6.txt.gz"

        # Configure CUDA settings
        self._configure_cuda()

        # Load model
        self.model = build_sam3_image_model(
            bpe_path=self.bpe_path,
            load_from_HF=load_from_hf,
            checkpoint_path=checkpoint_path,
        )

        # Initialize processor
        self.processor = Sam3Processor(
            self.model, confidence_threshold=confidence_threshold
        )

        self.current_inference_state = None

    def _configure_cuda(self):
        """Configure CUDA settings for optimal performance."""
        if self.device == "cuda" and torch.cuda.is_available():
            # Enable tfloat32 for Ampere GPUs
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            # Enable bfloat16 autocast
            torch.autocast("cuda", dtype=torch.bfloat16).__enter__()

    def process_text_prompt(self, image: np.ndarray, prompt: str) -> dict:
        """
        Process image with text prompt for segmentation.

        Args:
            image: Numpy array Image to process
            prompt: Text prompt describing what to segment

        Returns:
            Inference state with segmentation results
        """
        inference_state = self.processor.set_image(image)
        self.processor.reset_all_prompts(inference_state)
        inference_state = self.processor.set_text_prompt(
            state=inference_state, prompt=prompt
        )
        self.current_inference_state = inference_state
        return inference_state

