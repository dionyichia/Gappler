import os
from pathlib import Path

import cv2
import pandas as pd


def playback_recording(save_path: str, source: str = "aria", playback_fps: int = 30):
    """
    Playback recorded frames with timestamps
    Args:
        save_path: Root save path
        source: 'ros', 'aria', or 'synchronized'
        playback_fps: Playback frame rate
    """
    directory_path = Path(save_path)
    files_list = sorted([p for p in directory_path.iterdir() if p.is_file()])

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

    print("Playback complete")


if __name__ == "__main__":
    playback_recording(
        "/path/to/recordings/dual_stream_20251211_102346",
        source="synchronized",
        playback_fps=15,
    )
