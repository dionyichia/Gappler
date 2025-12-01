import argparse
import logging
import multiprocessing
from pathlib import Path
import sys

import torch

from aria_device import AriaDeviceController
from config import AriaConfig
from utils import safe_update_iptables, TerminalRawMode, setup_logging
from services.image_stream_processor import stream_image
from services.audio_stream_processor import stream_audio
from services.feature_matching import dual_stream_matcher

torch.set_grad_enabled(False)
setup_logging()

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

logger = logging.getLogger(__name__)


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
            logger.warning("Warning: Failed to update iptables", file=sys.stderr)

    with AriaDeviceController.get_instance() as aria_controller:
        aria_controller.connect(device_ip=AriaConfig.ARIA_DEVICE_IP_ADDRESS)
        interface = None if AriaConfig.ARIA_DEVICE_IP_ADDRESS else "usb"
        aria_controller.start_streaming(
            profile=AriaConfig.ARIA_STREAMING_PROFILE_NAME, interface=interface
        )

        ctx = multiprocessing.get_context("spawn")
        audio_process, image_process, matcher_process = None, None, None
        audio_process = ctx.Process(target=stream_audio, args=(PROJECT_ROOT,))
        image_process = ctx.Process(target=stream_image, args=(PROJECT_ROOT,))
        matcher_process = ctx.Process(target=dual_stream_matcher, args=(PROJECT_ROOT,))

        # image_process.start()
        # audio_process.start()
        matcher_process.start()

        if image_process and image_process.is_alive():
            image_process.join()
        if audio_process and audio_process.is_alive():
            audio_process.join()
        if matcher_process and matcher_process.is_alive():
            matcher_process.join()


if __name__ == "__main__":
    with TerminalRawMode():
        main()
