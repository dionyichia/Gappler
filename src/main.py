import warnings

warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")

import os

# Environment Configuration
os.environ["QT_QPA_FONTDIR"] = "/usr/share/fonts"

import argparse
import logging
import multiprocessing
import sys
from ipaddress import IPv4Address
from time import sleep
from typing import Optional

import cv2  # DO NOT DELETE! We import cv2 to initialize it to prevent crashing in spawned processes due to conflicts with torch # noqa

from schemas.application import ApplicationConfig
from services.aria_device import AriaDeviceController
from services.process_manager import ProcessManager
from utils import TerminalRawMode, exit_keypress, safe_update_iptables, setup_logging

# Logging setup
setup_logging()
logger = logging.getLogger(__name__)


def parse_arguments() -> ApplicationConfig:
    """Parse and validate command line arguments.

    Returns:
        Application configuration object.

    Raises:
        SystemExit: If required arguments are missing or invalid.
    """
    parser = argparse.ArgumentParser(
        description="Aria streaming application for live and recorded data processing"
    )

    parser.add_argument(
        "--mode",
        choices=["live", "recording"],
        default="live",
        help="Mode to run the application in (default: %(default)s)",
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

    parser.add_argument("--device_ip", type=str, help="IP Address of Aria Glasses")

    parser.add_argument("--profile_name", type=str, help="Profile used for streaming")

    args = parser.parse_args()

    # Validate recording mode requirements
    if args.mode == "recording" and not args.recording_path:
        parser.error("--recording-path is required when --mode is 'recording'")

    # Convert device_ip to IPv4Address if provided
    device_ip = IPv4Address(args.device_ip) if args.device_ip else None

    return ApplicationConfig(
        mode=args.mode,
        recording_path=args.recording_path,
        device_ip=device_ip,
        profile_name=args.profile_name,
        update_iptables=args.update_iptables,
    )


class ProcessPipelineBuilder:
    """Builder for constructing the processing pipeline."""

    def __init__(self, process_manager: ProcessManager):
        self.process_manager = process_manager

    def add_visualization(self) -> "ProcessPipelineBuilder":
        """Add visualization process to the pipeline."""
        from services.visualizer import visualize_feed

        self.process_manager.add_process(target=visualize_feed)
        return self

    def add_object_recognition(self) -> "ProcessPipelineBuilder":
        """Add object recognition process to the pipeline."""
        from services.object_recognition_pipeline import generate_mask

        self.process_manager.add_process(target=generate_mask)
        return self

    def add_feature_matching(self) -> "ProcessPipelineBuilder":
        """Add feature matching process to the pipeline."""
        from services.feature_matching import feature_matching

        self.process_manager.add_process(target=feature_matching)
        return self

    def add_audio_streaming(self) -> "ProcessPipelineBuilder":
        """Add audio streaming process to the pipeline."""
        from services.audio_streaming_pipeline import stream_audio

        self.process_manager.add_process(target=stream_audio)
        return self

    def add_image_streaming(self) -> "ProcessPipelineBuilder":
        """Add image streaming thread to the pipeline."""
        from services.image_streaming_pipeline import stream_visual_feed

        self.process_manager.add_thread(target=stream_visual_feed)
        return self

    def build_common_pipeline(self) -> "ProcessPipelineBuilder":
        """Build the common processing pipeline used by both modes."""
        return self.add_visualization().add_object_recognition().add_feature_matching()

    def build_streaming_pipeline(self) -> "ProcessPipelineBuilder":
        """Build the complete pipeline for live streaming mode."""
        return self.add_audio_streaming().add_image_streaming().build_common_pipeline()


class RecordingModeRunner:
    """Handler for recording playback mode."""

    def __init__(self, process_manager: ProcessManager):
        self.process_manager = process_manager

    def run(self, recording_path: str) -> None:
        """Execute the application in recording playback mode.

        Args:
            recording_path: Path to the recording directory.
        """
        from services.playback_controller import playback

        logger.info(f"Starting playback mode with recording: {recording_path}")

        # Setup processing pipeline
        builder = ProcessPipelineBuilder(self.process_manager)
        builder.build_common_pipeline()

        # Start all processes
        self.process_manager.start_all()
        logger.info("All processes started successfully")

        # Start playback
        playback(recording_path)

        self.process_manager.quit()
        self.process_manager.join_all()


class LiveModeRunner:
    """Handler for live streaming mode."""

    def __init__(self, process_manager: ProcessManager):
        self.process_manager = process_manager

    def run(self, device_ip: Optional[IPv4Address], profile_name: str) -> None:
        """Execute the application in live streaming mode.

        Args:
            device_ip: IP address of the Aria device (None for USB).
            profile_name: Name of the streaming profile to use.
        """
        logger.info("Starting live streaming mode")

        try:
            self._run_streaming_session(device_ip, profile_name)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Error in live streaming mode: {e}", exc_info=True)
            raise
        finally:
            self.process_manager.cleanup()
            logger.info("Cleanup completed")

    def _run_streaming_session(
        self, device_ip: Optional[IPv4Address], profile_name: str
    ) -> None:
        """Run a single streaming session with proper resource management.

        Args:
            device_ip: IP address of the Aria device.
            profile_name: Name of the streaming profile to use.
        """
        with AriaDeviceController.get_instance() as aria_controller:
            # Connect to device
            self._connect_device(aria_controller, device_ip)

            # Start streaming
            self._start_streaming(aria_controller, device_ip, profile_name)

            # Setup and start processing pipeline
            builder = ProcessPipelineBuilder(self.process_manager)
            builder.build_streaming_pipeline()

            self.process_manager.start_all()
            logger.info("All processes started successfully")

            while not exit_keypress():
                sleep(0.1)

            self.process_manager.quit()
            self.process_manager.join_all()

    def _connect_device(
        self, aria_controller: AriaDeviceController, device_ip: Optional[IPv4Address]
    ) -> None:
        """Connect to the Aria device.

        Args:
            aria_controller: Controller instance for the device.
            device_ip: IP address of the device.
        """
        aria_controller.connect(device_ip=device_ip)
        connection_type = device_ip or "USB"
        logger.info(f"Connected to Aria device at {connection_type}")

    def _start_streaming(
        self,
        aria_controller: AriaDeviceController,
        device_ip: Optional[IPv4Address],
        profile_name: str,
    ) -> None:
        """Start streaming from the connected device.

        Args:
            aria_controller: Controller instance for the device.
            device_ip: IP address of the device.
            profile_name: Name of the streaming profile to use.
        """
        interface = None if device_ip else "usb"
        aria_controller.start_streaming(profile=profile_name, interface=interface)
        logger.info(f"Streaming started with profile: {profile_name}")


class AriaApplication:
    """Main application orchestrator."""

    def __init__(self, config: ApplicationConfig):
        self.config = config
        self.process_manager = ProcessManager()

    def run(self) -> None:
        """Run the application based on configuration.

        Raises:
            SystemExit: If application encounters a fatal error.
        """
        try:
            self.config.validate()
            self._setup_environment()
            self._execute_mode()
        except Exception as e:
            logger.error(f"Application error: {e}", exc_info=True)
            sys.exit(1)

    def _setup_environment(self) -> None:
        """Setup the execution environment."""
        if self.config.update_iptables:
            self._update_iptables()

    def _update_iptables(self) -> None:
        """Configure iptables if needed."""
        logger.info("Attempting to update iptables...")
        if not safe_update_iptables():
            logger.warning("Failed to update iptables.")

    def _execute_mode(self) -> None:
        """Execute the appropriate mode based on configuration."""
        if self.config.mode == "recording":
            runner = RecordingModeRunner(self.process_manager)
            runner.run(self.config.recording_path)
        else:
            runner = LiveModeRunner(self.process_manager)
            runner.run(self.config.device_ip, self.config.profile_name)


def main():
    """Application entry point."""
    multiprocessing.set_start_method("spawn", force=True)

    config = parse_arguments()
    app = AriaApplication(config)
    app.run()


if __name__ == "__main__":
    with TerminalRawMode():
        main()
