import os
import cv2
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import torch
import numpy as np

from models.superglue.matching import Matching
from models.superglue.utils import make_matching_plot, AverageTimer, read_image

torch.set_grad_enabled(False)
device = "cpu"


class SuperGlueMatcher:
    """SuperGlue matcher with visualization capabilities."""

    def __init__(self, config=None):
        """Initialize SuperGlue matcher with configuration."""
        if config is None:
            config = {
                "superpoint": {
                    "nms_radius": 2,
                    "keypoint_threshold": 0.0,
                    "max_keypoints": 10000,
                },
                "superglue": {
                    "weights": "indoor",
                    "sinkhorn_iterations": 20,
                    "match_threshold": 0.00001,
                },
            }
        self.matching = Matching(config).eval().to(device)
        self.timer = AverageTimer(newline=True)
        print("SuperGlue matcher initialized")

    def filter_points_by_bbox(self, keypoints, matches, conf, bbox):
        """Filter keypoints and matches to keep only those within the bounding box."""
        x_min, y_min, x_max, y_max = bbox
        valid = (
            (keypoints[:, 0] >= x_min)
            & (keypoints[:, 0] <= x_max)
            & (keypoints[:, 1] >= y_min)
            & (keypoints[:, 1] <= y_max)
        )
        return keypoints[valid], matches[valid], conf[valid], valid

    def match(self, img0_path, img1_path, bbox0):
        """Perform SuperGlue matching between two images."""
        # Load images
        image0, inp0, scales0 = read_image(img0_path, device, [-1], 0, False)
        image1, inp1, scales1 = read_image(img1_path, device, [-1], 0, False)
        self.timer.update("load_image")

        # Perform matching
        pred = self.matching({"image0": inp0, "image1": inp1})
        pred = {k: v[0].cpu().numpy() for k, v in pred.items()}
        kpts0, kpts1 = pred["keypoints0"], pred["keypoints1"]
        matches, conf = pred["matches0"], pred["matching_scores0"]
        self.timer.update("matcher")

        # Filter by bounding box
        kpts0_filtered, matches_filtered, conf_filtered, valid_bbox = (
            self.filter_points_by_bbox(kpts0, matches, conf, bbox0)
        )

        # Get matched keypoints
        valid = matches_filtered > -1
        mkpts0 = kpts0_filtered[valid]
        mkpts1 = kpts1[matches_filtered[valid]]
        mconf = conf_filtered[valid]

        return {
            "image0": image0,
            "image1": image1,
            "kpts0": kpts0,
            "kpts1": kpts1,
            "mkpts0": mkpts0,
            "mkpts1": mkpts1,
            "mconf": mconf,
            "bbox0": bbox0,
        }

    def calculate_matching_points_in_boxes(self, mkpts1, boxes, tolerance=15):
        """Calculate number of matching points in each bounding box."""
        points_per_bbox = []
        for box in boxes:
            x_min, y_min, x_max, y_max = box
            valid = (
                (mkpts1[:, 0] >= x_min - tolerance)
                & (mkpts1[:, 0] <= x_max + tolerance)
                & (mkpts1[:, 1] >= y_min - tolerance)
                & (mkpts1[:, 1] <= y_max + tolerance)
            )
            points_per_bbox.append(np.sum(valid))

        max_bbox_index = np.argmax(points_per_bbox)
        return points_per_bbox, max_bbox_index

    def calculate_midpoint(self, mkpts):
        """Calculate the midpoint of matched keypoints."""
        return np.mean(mkpts, axis=0).astype(int)

    def visualize_matches(self, match_result, save_path="matches_visualization.png"):
        """Visualize matches side by side with bounding box and midpoint."""
        image0 = match_result["image0"]
        image1 = match_result["image1"]
        mkpts0 = match_result["mkpts0"]
        mkpts1 = match_result["mkpts1"]
        mconf = match_result["mconf"]
        bbox0 = match_result["bbox0"]

        # Calculate midpoint
        midpoint = self.calculate_midpoint(mkpts1)

        # Create figure with two subplots
        fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(16, 8))

        # Display first image with bounding box
        ax0.imshow(image0)
        ax0.axis("off")
        ax0.set_title(f"Image 0 - Query Region\nKeypoints: {len(mkpts0)}", fontsize=14)

        # Draw bounding box
        x_min, y_min, x_max, y_max = bbox0
        rect = plt.Rectangle(
            (x_min, y_min),
            x_max - x_min,
            y_max - y_min,
            fill=False,
            edgecolor="red",
            linewidth=2,
        )
        ax0.add_patch(rect)

        # Plot keypoints in image 0
        ax0.scatter(
            mkpts0[:, 0],
            mkpts0[:, 1],
            c="lime",
            s=20,
            marker="o",
            edgecolors="white",
            linewidths=0.5,
            alpha=0.8,
        )

        # Display second image with matches and midpoint
        ax1.imshow(image1)
        ax1.axis("off")
        ax1.set_title(f"Image 1 - Matches Found\nMatches: {len(mkpts1)}", fontsize=14)

        # Plot matched keypoints with confidence-based colors
        colors = cm.jet(mconf)
        ax1.scatter(
            mkpts1[:, 0],
            mkpts1[:, 1],
            c=colors,
            s=20,
            marker="o",
            edgecolors="white",
            linewidths=0.5,
            alpha=0.8,
        )

        # Plot midpoint
        ax1.scatter(
            midpoint[0],
            midpoint[1],
            c="red",
            s=200,
            marker="*",
            edgecolors="white",
            linewidths=2,
            label="Midpoint",
            zorder=10,
        )
        ax1.legend(loc="upper right", fontsize=12)

        # Add match statistics
        fig.suptitle(
            f"SuperGlue Matching Results - Avg Confidence: {mconf.mean():.3f}",
            fontsize=16,
            fontweight="bold",
        )

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Visualization saved to {save_path}")
        plt.show()

        return midpoint


def main():
    """Main execution function."""
    # Initialize matcher
    matcher = SuperGlueMatcher()

    # Setup paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    img0_path = os.path.join(script_dir, "./assets/superglue/test/london_bridge_1.jpg")
    img1_path = os.path.join(script_dir, "./assets/superglue/test/london_bridge_2.jpg")
    bbox0 = [249, 301, 343, 391]  # [x_min, y_min, x_max, y_max]

    # Perform matching
    print("Performing SuperGlue matching...")
    match_result = matcher.match(img0_path, img1_path, bbox0)

    # Print results
    print(f"\nMatching Results:")
    print(f"Matched keypoints in image 0: {len(match_result['mkpts0'])}")
    print(f"Matched keypoints in image 1: {len(match_result['mkpts1'])}")
    print(f"Average confidence: {match_result['mconf'].mean():.4f}")

    # Visualize and get midpoint
    midpoint = matcher.visualize_matches(match_result)
    print(f"Midpoint of matches: {midpoint}")


if __name__ == "__main__":
    main()


# def filter_points_by_bbox(keypoints, matches, conf, bbox):
#     """
#     过滤关键点和匹配，使其仅保留在指定的边界框内的点和匹配。

#     Args:
#         keypoints (numpy.ndarray): 关键点数组，形状为 (N, 2)。
#         matches (numpy.ndarray): 匹配数组，形状为 (N,)。
#         bbox (list): 边界框 [x_min, y_min, x_max, y_max]。

#     Returns:
#         filtered_keypoints (numpy.ndarray): 边界框内的关键点。
#         filtered_matches (numpy.ndarray): 对应的匹配索引。
#         valid (numpy.ndarray): 过滤后的有效点索引。
#     """
#     x_min, y_min, x_max, y_max = bbox
#     valid = (
#         (keypoints[:, 0] >= x_min)
#         & (keypoints[:, 0] <= x_max)
#         & (keypoints[:, 1] >= y_min)
#         & (keypoints[:, 1] <= y_max)
#     )

#     return keypoints[valid], matches[valid], conf[valid], valid[valid]


# def superglue_matching_init():
#     config = {
#         "superpoint": {
#             "nms_radius": 2,
#             "keypoint_threshold": 0.0,
#             "max_keypoints": 10000,
#         },
#         "superglue": {
#             "weights": "indoor",
#             "sinkhorn_iterations": 20,
#             "match_threshold": 0.00001,
#         },
#     }
#     matching = Matching(config).eval().to(device)
#     timer = AverageTimer(newline=True)
#     print("wait for pictures")
#     return matching, timer


# def superglue(matching, img0, img1, bbox0, timer, viz_path="result.png"):
#     from pathlib import Path

#     if not Path(img0).exists():
#         raise FileNotFoundError(f"Image 0 not found: {img0}")
#     if not Path(img1).exists():
#         raise FileNotFoundError(f"Image 1 not found: {img1}")
#     image0, inp0, scales0 = read_image(img0, device, [-1], 0, False)
#     image1, inp1, scales1 = read_image(img1, device, [-1], 0, False)
#     timer.update("load_image")
#     pred = matching({"image0": inp0, "image1": inp1})
#     pred = {k: v[0].cpu().numpy() for k, v in pred.items()}
#     kpts0, kpts1 = pred["keypoints0"], pred["keypoints1"]
#     matches, conf = pred["matches0"], pred["matching_scores0"]
#     timer.update("matcher")

#     # Write the matches to disk.
#     out_matches = {
#         "keypoints0": kpts0,
#         "keypoints1": kpts1,
#         "matches": matches,
#         "match_confidence": conf,
#     }
#     kpts0, matches, conf, valid_bbox = filter_points_by_bbox(
#         kpts0, matches, conf, bbox0
#     )

#     # Keep the matching keypoints.
#     valid = matches > -1
#     mkpts0 = kpts0[valid]
#     mkpts1 = kpts1[matches[valid]]
#     mconf = conf[valid & valid_bbox]
#     # Visualize the matches.
#     color = cm.jet(mconf)
#     text = []
#     small_text = []
#     text = [
#         "SuperGlue",
#         "Keypoints: {}:{}".format(len(kpts0), len(kpts1)),
#         "Matches: {}".format(len(mkpts0)),
#     ]
#     # Display extra parameter info.
#     k_thresh = matching.superpoint.config["keypoint_threshold"]
#     m_thresh = matching.superglue.config["match_threshold"]
#     small_text = [
#         "Keypoint Threshold: {:.6f}".format(k_thresh),
#         "Match Threshold: {:.6f}".format(m_thresh),
#     ]

#     make_matching_plot(
#         image0,
#         image1,
#         kpts0,
#         kpts1,
#         mkpts0,
#         mkpts1,
#         color,
#         text,
#         viz_path,
#         False,
#         False,
#         False,
#         "Matches",
#         small_text,
#     )

#     timer.update("viz_match")
#     return mkpts0, mkpts1, mconf


# def calculate_matching_points_in_box(mkpts1, boxes):
#     points_per_bbox = []
#     for box in boxes:
#         x_min, y_min, x_max, y_max = box
#         # check which mkpt is in box
#         valid = (
#             (mkpts1[:, 0] >= x_min - 15)
#             & (mkpts1[:, 0] <= x_max + 15)
#             & (mkpts1[:, 1] >= y_min - 15)
#             & (mkpts1[:, 1] <= y_max + 15)
#         )
#         # calculate summe
#         points_per_bbox.append(np.sum(valid))

#     max_bbox_index = np.argmax(points_per_bbox)
#     return points_per_bbox, max_bbox_index


# def calculate_mid_kpts(mkpts1):
#     mid_point = np.mean(mkpts1, axis=0).astype(int)
#     return mid_point


# if __name__ == "__main__":
#     matching, timer = superglue_matching_init()

#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     img0_path = os.path.join(script_dir, "./assets/superglue/test/london_bridge_1.jpg")
#     img1_path = os.path.join(script_dir, "./assets/superglue/test/london_bridge_2.jpg")
#     bbox0 = [249, 301, 343, 391]
#     mkpts0, mkpts1, mconf = superglue(
#         matching, img0_path, img1_path, bbox0, timer=timer
#     )
#     print(mkpts1)
#     mid_point = calculate_mid_kpts(mkpts1)
#     print(mid_point)
#     image = cv2.imread(img1_path)
#     cv2.circle(
#         image, (mid_point[0], mid_point[1]), radius=10, color=(0, 255, 0), thickness=-1
#     )
#     cv2.imshow("Keypoints and Midpoint", image)
#     cv2.waitKey(0)
#     cv2.destroyAllWindows()
