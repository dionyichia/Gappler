# models/grounding_sam.py
import torch
import numpy as np
import cv2
import supervision as sv
from PIL import Image
from pathlib import Path
from typing import Tuple, List
import pycocotools.mask as mask_util
import json
import logging

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor
from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
from supervision.draw.color import ColorPalette
from utils.supervision_utils import CUSTOM_COLOR_MAP

logger = logging.getLogger(__name__)


class GroundingSAM:
    """Unified Grounding DINO + SAM2 model for object detection and segmentation"""

    def __init__(self, config):
        self.config = config
        self.device = config.device

        # Initialize SAM2
        self.sam2_model = build_sam2(
            config.sam2_model_config, str(config.sam2_checkpoint), device=self.device
        )
        self.sam2_predictor = SAM2ImagePredictor(self.sam2_model)

        # Initialize Grounding DINO
        self.processor = AutoProcessor.from_pretrained(config.grounding_model)
        self.grounding_model = AutoModelForZeroShotObjectDetection.from_pretrained(
            config.grounding_model
        ).to(self.device)

        logger.info(f"GroundingSAM initialized on {self.device}")

    def detect_and_segment(
        self,
        image: Image.Image,
        text_prompt: str,
        output_dir: Path,
        box_threshold: float = 0.3,
        text_threshold: float = 0.3,
        dump_json: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Detect and segment objects in image based on text prompt

        Args:
            image: PIL Image
            text_prompt: Text description (must end with '.')
            output_dir: Directory to save visualizations
            box_threshold: Detection confidence threshold
            text_threshold: Text matching threshold
            dump_json: Whether to save results as JSON

        Returns:
            Tuple of (masks, boxes) as numpy arrays
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare image for SAM2
        self.sam2_predictor.set_image(np.array(image.convert("RGB")))

        # Run Grounding DINO
        inputs = self.processor(images=image, text=text_prompt, return_tensors="pt").to(
            self.device
        )

        with torch.no_grad():
            outputs = self.grounding_model(**inputs)

        results = self.processor.post_process_grounded_object_detection(
            outputs,
            inputs.input_ids,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            target_sizes=[image.size[::-1]],
        )

        # Check if any objects detected
        input_boxes = results[0]["boxes"].cpu().numpy()
        if len(input_boxes) == 0:
            logger.warning(f"No objects detected for prompt: {text_prompt}")
            return np.array([]), np.array([])

        # Run SAM2 segmentation
        masks, scores, logits = self.sam2_predictor.predict(
            point_coords=None,
            point_labels=None,
            box=input_boxes,
            multimask_output=False,
        )

        # Process masks
        if masks.ndim == 4:
            masks = masks.squeeze(1)

        # Extract metadata
        confidences = results[0]["scores"].cpu().numpy().tolist()
        class_names = results[0]["labels"]
        class_ids = np.array(list(range(len(class_names))))

        # Visualize results
        self._visualize_results(
            image, masks, input_boxes, class_names, confidences, class_ids, output_dir
        )

        # Save JSON results
        if dump_json:
            self._save_json_results(
                image, masks, input_boxes, class_names, scores, output_dir
            )

        return masks, input_boxes

    def _visualize_results(
        self,
        image: Image.Image,
        masks: np.ndarray,
        boxes: np.ndarray,
        class_names: List[str],
        confidences: List[float],
        class_ids: np.ndarray,
        output_dir: Path,
    ):
        """Create and save annotated visualizations"""
        img = np.array(image)

        detections = sv.Detections(
            xyxy=boxes,
            mask=masks.astype(bool),
            class_id=class_ids,
        )

        labels = [f"{name} {conf:.2f}" for name, conf in zip(class_names, confidences)]

        # Annotate with boxes
        box_annotator = sv.BoxAnnotator(color=ColorPalette.from_hex(CUSTOM_COLOR_MAP))
        annotated_frame = box_annotator.annotate(
            scene=img.copy(), detections=detections
        )

        # Annotate with labels
        label_annotator = sv.LabelAnnotator(
            color=ColorPalette.from_hex(CUSTOM_COLOR_MAP)
        )
        annotated_frame = label_annotator.annotate(
            scene=annotated_frame, detections=detections, labels=labels
        )

        cv2.imwrite(
            str(output_dir / "annotated_boxes.jpg"), annotated_frame[:, :, ::-1]
        )

        # Annotate with masks
        mask_annotator = sv.MaskAnnotator(color=ColorPalette.from_hex(CUSTOM_COLOR_MAP))
        annotated_frame = mask_annotator.annotate(
            scene=annotated_frame, detections=detections
        )

        cv2.imwrite(
            str(output_dir / "annotated_masks.jpg"), annotated_frame[:, :, ::-1]
        )

    def _save_json_results(
        self,
        image: Image.Image,
        masks: np.ndarray,
        boxes: np.ndarray,
        class_names: List[str],
        scores: np.ndarray,
        output_dir: Path,
    ):
        """Save detection results in JSON format"""

        def single_mask_to_rle(mask):
            rle = mask_util.encode(
                np.array(mask[:, :, None], order="F", dtype="uint8")
            )[0]
            rle["counts"] = rle["counts"].decode("utf-8")
            return rle

        mask_rles = [single_mask_to_rle(mask) for mask in masks]
        boxes_list = boxes.tolist()
        scores_list = scores.tolist()

        results = {
            "annotations": [
                {
                    "class_name": class_name,
                    "bbox": box,
                    "segmentation": mask_rle,
                    "score": score,
                }
                for class_name, box, mask_rle, score in zip(
                    class_names, boxes_list, mask_rles, scores_list
                )
            ],
            "box_format": "xyxy",
            "img_width": image.width,
            "img_height": image.height,
        }

        with open(output_dir / "detection_results.json", "w") as f:
            json.dump(results, f, indent=4)
