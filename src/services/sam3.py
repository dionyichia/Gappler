import os
from typing import Optional

import sam3
import torch
from PIL import ImageFile
from sam3 import build_sam3_image_model

from models.sam3.sam3.model.sam3_image_processor import Sam3Processor


class SAM3Segmenter:
    def __init__(
        self,
        checkpoint_path: str,
        bpe_path: Optional[str] = None,
        confidence_threshold: float = 0.5,
        load_from_hf: bool = False,
        device: str = "cuda",
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
        sam3_root = os.path.join(os.path.dirname(sam3.__file__), "..")
        self.bpe_path = bpe_path or f"{sam3_root}/assets/bpe_simple_vocab_16e6.txt.gz"

        # Configure CUDA settings
        self._configure_cuda()

        # Load model
        self.model = self._load_model(checkpoint_path, load_from_hf)

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

    def _load_model(self, checkpoint_path: str, load_from_hf: bool):
        """Load SAM3 model from checkpoint."""
        model = build_sam3_image_model(
            bpe_path=self.bpe_path,
            load_from_HF=load_from_hf,
            checkpoint_path=checkpoint_path,
        )
        return model

    def set_image(self, image: ImageFile.ImageFile):
        """
        Set the image for segmentation.

        Args:
            image: PIL Image to process

        Returns:
            Inference state
        """
        self.current_inference_state = self.processor.set_image(image)
        return self.current_inference_state

    def process_text_prompt(self, image: ImageFile.ImageFile, prompt: str):
        """
        Process image with text prompt for segmentation.

        Args:
            image: PIL Image to process
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


# Usage example
if __name__ == "__main__":
    # Initialize segmenter
    segmenter = SAM3Segmenter(
        checkpoint_path="/home/iot22/GitHub/Renaissance-Capstone-Project/sam3/sam3.pt",
        confidence_threshold=0.5,
    )

    # Process image with text prompt
    from PIL import Image

    image = Image.open("path/to/image.jpg")
    inference_state = segmenter.process_text_prompt(image, "person wearing red shirt")
