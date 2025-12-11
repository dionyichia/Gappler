import os
import matplotlib

matplotlib.use("TkAgg")  # Use TkAgg backend for displaying plots in .py files
import matplotlib.pyplot as plt
import numpy as np
import sam3
from PIL import Image
from sam3 import build_sam3_image_model
from sam3.model.box_ops import box_xywh_to_cxcywh
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.visualization_utils import draw_box_on_image, normalize_bbox, plot_results

import torch

# Turn on tfloat32 for Ampere GPUs
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# Use bfloat16 for the entire notebook
torch.autocast("cuda", dtype=torch.bfloat16).__enter__()

# Paths
sam3_root = os.path.join(os.path.dirname(sam3.__file__), "..")
bpe_path = f"{sam3_root}/assets/bpe_simple_vocab_16e6.txt.gz"
checkpoint_path = "/home/iot22/GitHub/Renaissance-Capstone-Project/sam3/sam3.pt"

print("Loading SAM3 model...")
model = build_sam3_image_model(
    bpe_path=bpe_path,
    load_from_HF=False,
    checkpoint_path=checkpoint_path,
)
print("Model loaded successfully!")

# Image paths
# image_path = "/home/iot22/GitHub/Renaissance-Capstone-Project/v1/aria_pkg/recordings/dual_stream_20251211_115821/aria/frames/1765425503872.347.png"

# if not os.path.exists(image_path):
#     print(f"Warning: Image not found at {image_path}")
#     # Fallback to test image
#     image_path = f"{sam3_root}/assets/images/test_image.jpg"
#     print(f"Using fallback image: {image_path}")

# print(f"Loading image from: {image_path}")
# image = Image.open(image_path)
# width, height = image.size
# print(f"Image size: {width}x{height}")

# # Initialize processor
# print("Initializing processor...")
# processor = Sam3Processor(model, confidence_threshold=0.5)

# # Set image and generate inference
# print("Setting image for inference...")
# inference_state = processor.set_image(image)
# processor.reset_all_prompts(inference_state)

# # Set text prompt
# prompt = "robot"
# print(f"Running inference with prompt: '{prompt}'")
# inference_state = processor.set_text_prompt(state=inference_state, prompt=prompt)

# # Plot results
# print("Plotting results...")
# img0 = Image.open(image_path)
# plot_results(img0, inference_state)

# # Save the figure to file
# output_dir = "/home/iot22/GitHub/Renaissance-Capstone-Project/v1/aria_pkg/output"
# os.makedirs(output_dir, exist_ok=True)
# output_path = os.path.join(output_dir, "sam3_prediction.png")
# plt.savefig(output_path, dpi=150, bbox_inches="tight")
# print(f"Saved visualization to: {output_path}")

# # Show the plot (this will block until window is closed)
# print("Displaying visualization (close window to continue)...")
# plt.show()

# print("Done!")


# Function for generating masks programmatically
def generate_mask(image, prompt, save_path=None):
    """
    Generate segmentation mask for given image and text prompt.

    Args:
        image_path: Path to input image
        prompt: Text prompt for segmentation
        save_path: Optional path to save visualization

    Returns:
        inference_state: Dictionary containing masks, boxes, and scores
    """
    print(f"\nGenerating mask for prompt: '{prompt}'")

    if isinstance(image, str):
        # If string path provided, load the image
        image = Image.open(image)
    elif isinstance(image, np.ndarray):
        # If numpy array, convert to PIL Image
        image = Image.fromarray(image)
    elif not isinstance(image, Image.Image):
        raise TypeError(
            f"image must be numpy.ndarray, PIL.Image, or str path, got {type(image)}"
        )

    # Initialize processor and inference
    processor_local = Sam3Processor(model, confidence_threshold=0.5)
    inference_state = processor_local.set_image(image)
    processor_local.reset_all_prompts(inference_state)
    inference_state = processor_local.set_text_prompt(
        state=inference_state, prompt=prompt
    )

    # Check results
    masks = inference_state.get("masks")
    if masks is not None and len(masks) > 0:
        print(f"Found {len(masks)} object(s)")

        # Visualize
        plt.figure(figsize=(12, 8))
        plot_results(image, inference_state)

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"Saved to: {save_path}")

        plt.show()
        return inference_state
    else:
        print("No objects detected")
        return None


# Example usage
if __name__ == "__main__":
    # You can test with different prompts
    test_prompts = ["robot", "person", "table"]

    for test_prompt in test_prompts:
        output_file = os.path.join(output_dir, f"sam3_{test_prompt}.png")
        result = generate_mask(image_path, test_prompt, save_path=output_file)

        if result:
            print(f"Successfully processed: {test_prompt}")
        else:
            print(f"No detections for: {test_prompt}")
        print("-" * 50)
