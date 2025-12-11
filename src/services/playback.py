import os

import cv2
import matplotlib.pyplot as plt
import numpy as np
import sam3
import torch
from matplotlib.colors import to_rgb
from PIL import Image
from sam3 import build_sam3_image_model
from sam3.model.box_ops import box_xywh_to_cxcywh
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.visualization_utils import draw_box_on_image, normalize_bbox, plot_results

sam3_root = os.path.join(os.path.dirname(sam3.__file__), "..")


# turn on tfloat32 for Ampere GPUs
# https://pytorch.org/docs/stable/notes/cuda.html#tensorfloat-32-tf32-on-ampere-devices
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# use bfloat16 for the entire notebook
torch.autocast("cuda", dtype=torch.bfloat16).__enter__()
import os
import cv2


def playback_recording(save_path: str, source: str = "aria", playback_fps: int = 30):
    """
    Playback recorded frames with timestamps
    Args:
        save_path: Root save path
        source: 'ros', 'aria', or 'synchronized'
        playback_fps: Playback frame rate
    """
    import pandas as pd

    # Determine CSV path based on source
    if source == "synchronized":
        csv_path = os.path.join(save_path, source, "sync_data.csv")
        frame_dir = os.path.join(save_path, source, "frames")
    else:
        csv_path = os.path.join(save_path, source, "timestamps.csv")
        frame_dir = os.path.join(save_path, source, "frames")

    if not os.path.exists(csv_path):
        print(f"No data found at {csv_path}")
        return

    df = pd.read_csv(csv_path)
    print(f"Found {len(df)} frames for {source}")
    print(f"Timestamp range: {df.iloc[0, 0]} to {df.iloc[-1, 0]}")

    window_name = f"Playback - {source}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    frame_delay = 1.0 / playback_fps
    paused = False

    for idx, row in df.iterrows():
        if source == "synchronized":
            timestamp = row["aria_timestamp [ns]"]
            filename = row["filename"]
            time_diff = row["time_diff [ms]"]
            num_matches = row["num_matches"]
        else:
            timestamp = row["#timestamp [ns]"]
            filename = row["filename"]

        img_path = os.path.join(frame_dir, filename)
        if not os.path.exists(img_path):
            print(f"Image not found: {img_path}")
            continue

        img = cv2.imread(img_path)

        # Add playback info overlay
        info_y = img.shape[0] - 60
        cv2.rectangle(img, (0, info_y), (img.shape[1], img.shape[0]), (0, 0, 0), -1)

        cv2.putText(
            img,
            f"Frame: {idx + 1}/{len(df)}",
            (10, info_y + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )

        if source == "synchronized":
            cv2.putText(
                img,
                f"Time Diff: {time_diff:.2f}ms | Matches: {num_matches}",
                (10, info_y + 50),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

        status = "PAUSED" if paused else "PLAYING"
        cv2.putText(
            img,
            status,
            (img.shape[1] - 150, info_y + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255) if paused else (0, 255, 0),
            2,
        )

        cv2.imshow(window_name, img)

        # Handle key presses
        wait_time = 0 if paused else int(frame_delay * 1000)
        key = cv2.waitKey(wait_time) & 0xFF

        if key == ord("q") or key == 27:  # 'q' or ESC to quit
            break
        elif key == ord(" "):  # Space to pause/resume
            paused = not paused
        elif key == ord("n") and paused:  # 'n' for next frame when paused
            continue
        elif key == ord("b") and paused and idx > 0:  # 'b' for previous frame
            # This is a simple implementation; more complex nav would need loop restructure
            pass

    cv2.destroyAllWindows()
    print("Playback complete")


if __name__ == "__main__":
    # Example: Run with recording enabled
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    # dual_stream_matcher(project_root, enable_recording=True)
    # Example: Playback recorded data
    playback_recording(
        "/home/iot22/GitHub/Renaissance-Capstone-Project/v1/aria_pkg/recordings/dual_stream_20251211_102346",
        source="aria",
        playback_fps=15,
    )
    playback_recording(
        "/path/to/recordings/dual_stream_20251211_102346",
        source="synchronized",
        playback_fps=15,
    )


COLORS = ["red", "blue", "green", "yellow", "cyan", "magenta", "orange", "purple"]


def plot_mask_cv2(img_cv, mask, color="r", alpha=0.5):
    """
    Apply a colored mask overlay to the image
    """
    im_h, im_w = mask.shape
    # Convert matplotlib color name to RGB
    rgb_color = to_rgb(color)
    bgr_color = (
        int(rgb_color[2] * 255),
        int(rgb_color[1] * 255),
        int(rgb_color[0] * 255),
    )

    # Create colored mask
    colored_mask = np.zeros((im_h, im_w, 3), dtype=np.uint8)
    colored_mask[mask > 0] = bgr_color

    # Blend mask with original image
    mask_binary = (mask > 0).astype(np.uint8)
    for c in range(3):
        img_cv[:, :, c] = np.where(
            mask_binary,
            img_cv[:, :, c] * (1 - alpha) + colored_mask[:, :, c] * alpha,
            img_cv[:, :, c],
        )

    return img_cv


def plot_bbox_cv2(
    img_cv,
    img_height,
    img_width,
    box,
    box_format="XYXY",
    relative_coords=True,
    color="r",
    text=None,
    thickness=2,
):
    """
    Draw bounding box on cv2 image
    """
    if box_format == "XYXY":
        x, y, x2, y2 = box
        w = x2 - x
        h = y2 - y
    elif box_format == "XYWH":
        x, y, w, h = box
    elif box_format == "CxCyWH":
        cx, cy, w, h = box
        x = cx - w / 2
        y = cy - h / 2
    else:
        raise RuntimeError(f"Invalid box_format {box_format}")

    if relative_coords:
        x *= img_width
        w *= img_width
        y *= img_height
        h *= img_height

    # Convert to integers
    x, y, w, h = int(x), int(y), int(w), int(h)

    # Convert matplotlib color to BGR
    rgb_color = to_rgb(color)
    bgr_color = (
        int(rgb_color[2] * 255),
        int(rgb_color[1] * 255),
        int(rgb_color[0] * 255),
    )

    # Draw rectangle
    cv2.rectangle(img_cv, (x, y), (x + w, y + h), bgr_color, thickness)

    # Draw text if provided
    if text is not None:
        # Add background for text
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        cv2.rectangle(
            img_cv,
            (x, y - text_height - baseline - 5),
            (x + text_width, y),
            bgr_color,
            -1,  # Filled rectangle
        )
        cv2.putText(
            img_cv,
            text,
            (x, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),  # White text
            1,
        )

    return img_cv


def plot_results_cv2(img, results):
    """
    CV2 implementation of plot_results
    """
    # Convert PIL to OpenCV format
    if isinstance(img, Image.Image):
        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        w, h = img.size
    else:
        img_cv = img.copy()
        h, w = img_cv.shape[:2]

    nb_objects = len(results["scores"])
    print(f"found {nb_objects} object(s)")

    for i in range(nb_objects):
        color = COLORS[i % len(COLORS)]

        # Plot mask
        mask = results["masks"][i].squeeze(0).cpu().numpy()
        img_cv = plot_mask_cv2(img_cv, mask, color=color, alpha=0.5)

        # Plot bounding box
        prob = results["scores"][i].item()
        box = results["boxes"][i].cpu().numpy()
        img_cv = plot_bbox_cv2(
            img_cv,
            h,
            w,
            box,
            text=f"(id={i}, prob={prob:.2f})",
            box_format="XYXY",
            color=color,
            relative_coords=False,
        )

    return img_cv


# Updated main code
if __name__ == "__main__":
    import cv2

    bpe_path = f"{sam3_root}/assets/bpe_simple_vocab_16e6.txt.gz"
    model = build_sam3_image_model(
        bpe_path=bpe_path,
        load_from_HF=False,
        checkpoint_path="/home/iot22/GitHub/Renaissance-Capstone-Project/sam3/sam3.pt",
    )
    recording_folder_path = "/home/iot22/GitHub/Renaissance-Capstone-Project/v1/aria_pkg/recordings/dual_stream_20251211_114812/aria/frames"

    from pathlib import Path

    directory_path = Path(recording_folder_path)
    files_list = sorted([p for p in directory_path.iterdir() if p.is_file()])

    window_name = "SAM3 Detection"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    for frame_num, file_path in enumerate(files_list, start=1):
        image = Image.open(file_path)
        width, height = image.size
        processor = Sam3Processor(model, confidence_threshold=0.5)
        inference_state = processor.set_image(image)
        processor.reset_all_prompts(inference_state)
        inference_state = processor.set_text_prompt(
            state=inference_state, prompt="robot"
        )

        # Use cv2 implementation
        img_cv = plot_results_cv2(image, inference_state)

        # Add frame label
        cv2.putText(
            img_cv,
            f"Frame {frame_num}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2,
        )

        # Display the image
        cv2.imshow(window_name, img_cv)

        # Wait for 1ms (press 'q' to quit)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cv2.destroyAllWindows()
