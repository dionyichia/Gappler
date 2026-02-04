import warnings

import numpy as np

warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")

import argparse
import logging
import multiprocessing
import os
import sys
from multiprocessing import Manager
from pathlib import Path

import torch

from aria_device import AriaDeviceController
from config import AriaConfig
from services.audio_stream_processor import stream_audio
from services.feature_matching import dual_stream_matcher
from services.image_stream_processor import stream_image
from services.playback import playback_recording
from utils import TerminalRawMode, safe_update_iptables, setup_logging

torch.set_grad_enabled(False)
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


def extract_aria_calibration(calibration):
    """
    Extract all necessary data from DeviceCalibration object.
    This returns a plain dictionary that can be pickled.
    """
    available_methods = [m for m in dir(calibration) if not m.startswith("_")]

    calib_data = {}
    print(available_methods)
    required_methods = [
        "get_aria_et_camera_calib",
        "get_aria_microphone_calib",
    ]

    try:
        if hasattr(calibration, "__str__"):
            calib_data["string_repr"] = str(calibration)

        for method in available_methods:
            if hasattr(calibration, method):
                try:
                    value = getattr(calibration, method)()

                    # Convert to serializable format
                    if isinstance(value, np.ndarray):
                        calib_data[method] = value.tolist()
                    elif isinstance(value, (list, tuple)):
                        calib_data[method] = list(value)
                    elif hasattr(value, "to_matrix"):  # Transform objects
                        calib_data[method] = value.to_matrix().tolist()
                    elif hasattr(value, "__dict__"):  # Complex objects
                        calib_data[method] = str(value)
                    else:
                        calib_data[method] = value
                        # Verify it's serializable
                    try:
                        import pickle

                        pickle.dumps(value)  # Test if it can be pickled
                    except Exception as e:
                        print(f"✗ Method: {method}")
                        print(f"Data: {value}")

                    print(f"Extracted {method}: {calib_data[method]}")

                except Exception as e:
                    print(f"Could not extract {method}: {e}")

    except Exception as e:
        print(f"Error during extraction: {e}")

    return calib_data


def main():
    args = parse_args()

    if args.mode == "recording":
        # playback_recording()
        pass

    else:
        if args.update_iptables:
            if not safe_update_iptables():
                logger.warning("Warning: Failed to update iptables", file=sys.stderr)

        ctx = multiprocessing.get_context("forkserver")
        manager = Manager()
        shared_data = manager.dict()

        with AriaDeviceController.get_instance() as aria_controller:
            aria_controller.connect(device_ip=AriaConfig.ARIA_DEVICE_IP_ADDRESS)
            interface = None if AriaConfig.ARIA_DEVICE_IP_ADDRESS else "usb"
            aria_controller.start_streaming(
                profile=AriaConfig.ARIA_STREAMING_PROFILE_NAME, interface=interface
            )

            aria_device_calibration = aria_controller.get_device_calibration()
            aria_device_calibration = extract_aria_calibration(aria_device_calibration)

            aria_rgb_calibration = aria_controller.get_rgb_camera_calibration()
            aria_rgb_calibration = extract_aria_calibration(aria_rgb_calibration)

            if not aria_device_calibration or not aria_rgb_calibration:
                logger.error("Error: Failed to retrieve device calibration data")
                return

            shared_data["aria_device_calibration"] = aria_device_calibration
            shared_data["aria_rgb_calibration"] = aria_rgb_calibration

            audio_process, image_process, matcher_process = None, None, None
            # audio_process = ctx.Process(target=stream_audio, args=(PROJECT_ROOT,))
            image_process = ctx.Process(
                target=stream_image,
                args=(PROJECT_ROOT, shared_data),
            )
            # matcher_process = ctx.Process(target=dual_stream_matcher, args=(PROJECT_ROOT,))

            image_process.start()
            # audio_process.start()
            # matcher_process.start()

            if image_process and image_process.is_alive():
                image_process.join()
            # if audio_process and audio_process.is_alive():
            #     audio_process.join()
            # if matcher_process and matcher_process.is_alive():
            #     matcher_process.join()


if __name__ == "__main__":
    with TerminalRawMode():
        main()


def main():
    args = parse_args()
    if args.mode == "recording":
        pass
    else:
        if args.update_iptables:
            if not safe_update_iptables():
                logger.warning("Warning: Failed to update iptables", file=sys.stderr)

        ctx = multiprocessing.get_context("forkserver")
        manager = Manager()
        shared_data = manager.dict()
        shared_data["ready"] = False

        # Start process first
        image_process = ctx.Process(
            target=stream_image, args=(PROJECT_ROOT, shared_data)
        )
        image_process.start()

        # Now get calibration
        with AriaDeviceController.get_instance() as aria_controller:
            aria_controller.connect(device_ip=AriaConfig.ARIA_DEVICE_IP_ADDRESS)
            interface = None if AriaConfig.ARIA_DEVICE_IP_ADDRESS else "usb"
            aria_controller.start_streaming(
                profile=AriaConfig.ARIA_STREAMING_PROFILE_NAME, interface=interface
            )

            # Get the calibration object
            rgb_calibration = aria_controller.get_rgb_camera_calibration()

            # IMPORTANT: Extract data BEFORE storing in shared dict
            calibration_data = extract_aria_calibration(rgb_calibration)

            # Now it's safe to store
            shared_data["aria_device_calibration"] = calibration_data
            shared_data["ready"] = True

        if image_process and image_process.is_alive():
            image_process.join()
