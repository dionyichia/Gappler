import argparse
import multiprocessing
from pathlib import Path
import sys

from aria_device import AriaDeviceController
from config import AriaConfig
from utils import exit_keypress, safe_update_iptables, TerminalRawMode
from services.image_stream_processor import stream_image
from services.audio_stream_processor import stream_audio
from services.feature_matching import match_features

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--update-iptables",
        dest="update_iptables",
        default=False,
        action="store_true",
        help="Update iptables to enable receiving the data stream, only for Linux.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.update_iptables:
        if not safe_update_iptables():
            print("Warning: Failed to update iptables", file=sys.stderr)

    with AriaDeviceController.get_instance() as aria_controller:
        aria_controller.connect(device_ip=AriaConfig.DEVICE_IP)
        interface = None if AriaConfig.DEVICE_IP else "usb"
        aria_controller.start_streaming(
            profile=AriaConfig.PROFILE_NAME, interface=interface
        )

        # Press ESC or q to exit
        while not exit_keypress():
            print("Starting execution loop...")
            ctx = multiprocessing.get_context("spawn")
            audio_proc = ctx.Process(target=stream_audio, args=(PROJECT_ROOT,))
            img_proc = ctx.Process(target=stream_image, args=(PROJECT_ROOT,))
            # matcher_proc = ctx.Process(target=match_features)

            img_proc.start()
            audio_proc.start()

            img_proc.join()
            print("Image streaming process finished.")

            # matcher_proc.start()

            audio_proc.join()
            # print("Audio streaming process finished.")

            # matcher_proc.join()
            # print("Feature matching process finished.")


if __name__ == "__main__":
    with TerminalRawMode():
        main()
