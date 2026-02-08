import warnings
warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")
import argparse
import logging
import threading
import os
import sys
from pathlib import Path
from aria_device import AriaDeviceController
from config import AriaConfig
from services.audio_stream_processor import stream_audio
from services.feature_matching import dual_stream_matcher
from services.image_stream_processor import stream_image
from services.playback import playback_recording
from utils import TerminalRawMode, safe_update_iptables, setup_logging

os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts"  # Point to system fonts
os.environ["QT_QUICK_BACKEND"] = "software"
setup_logging()

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["live", "recording"],
        default="live",
        help="Mode to run the package in (default: %(default)s)",
    )
    parser.add_argument(
        "--recording-path",
        type=str,
        help="Path to recording folder (required when mode is 'recording')",
    )
    parser.add_argument(
        "--update-iptables",
        action="store_true",
        help="Update iptables to enable receiving the data stream (Linux only)",
    )

    args = parser.parse_args()
    # Validate that recording-path is provided when mode is 'recording'
    if args.mode == "recording" and not args.recording_path:
        parser.error("--recording-path is required when --mode is 'recording'")

    return args


def main():
    args = parse_args()

    if args.mode == "recording":
        # playback_recording()
        pass

    else:
        if args.update_iptables:
            if not safe_update_iptables():
                logger.warning("Warning: Failed to update iptables", file=sys.stderr)

        with AriaDeviceController.get_instance() as aria_controller:
            aria_controller.connect(device_ip=AriaConfig.ARIA_DEVICE_IP_ADDRESS)
            interface = None if AriaConfig.ARIA_DEVICE_IP_ADDRESS else "usb"
            aria_controller.start_streaming(
                profile=AriaConfig.ARIA_STREAMING_PROFILE_NAME, interface=interface
            )

            aria_device_calibration = aria_controller.get_device_calibration()
            aria_rgb_calibration = aria_controller.get_rgb_camera_calibration()

            if not aria_device_calibration or not aria_rgb_calibration:
                logger.error("Error: Failed to retrieve device calibration data")
                return

            # shared_data["aria_device_calibration"] = aria_device_calibration
            # shared_data["aria_rgb_calibration"] = aria_rgb_calibration

            audio_thread, image_thread, matcher_thread = None, None, None

            # audio_thread = threading.Thread(target=stream_audio, args=(PROJECT_ROOT,), daemon=True)
            image_thread = threading.Thread(
                target=stream_image, args=(PROJECT_ROOT), daemon=True
            )
            # matcher_thread = threading.Thread(target=dual_stream_matcher, args=(PROJECT_ROOT,), daemon=True)

            image_thread.start()
            # audio_thread.start()
            # matcher_thread.start()

            if image_thread and image_thread.is_alive():
                image_thread.join()
            # if audio_thread and audio_thread.is_alive():
            #     audio_thread.join()
            # if matcher_thread and matcher_thread.is_alive():
            #     matcher_thread.join()


if __name__ == "__main__":
    with TerminalRawMode():
        main()
