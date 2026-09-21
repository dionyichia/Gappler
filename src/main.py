import warnings

warnings.filterwarnings("ignore", message=".*pkg_resources is deprecated.*")

import argparse
import logging
import multiprocessing
import os
import subprocess
import sys
from ipaddress import IPv4Address
from time import sleep
from typing import Optional

import rclpy

from config import Settings
from gappler_common import path
from schemas.application import ApplicationConfig
from services.process_manager import ProcessManager
from utils import exit_keypress, safe_update_iptables, setup_logging

# Logging setup
setup_logging()
logger = logging.getLogger(__name__)

# Our own calibration file, handed to the external OpenVINS binary.
ESTIMATOR_CONFIG = (
    Settings.PROJECT_ROOT / "src/services/aria_device/calibration/estimator_config.yaml"
)
# The OpenVINS build we launch. It lives outside this repo: `openvins_ws` in global_config.yaml.
OPENVINS_WS = path("openvins_ws")

if not rclpy.ok():
    rclpy.init()


class ProcessPipelineBuilder:
    """Builder for constructing the processing pipeline."""

    def __init__(self, process_manager: ProcessManager):
        self._process_manager = process_manager
        self.config_queue = multiprocessing.Queue()

    def add_streaming(
        self, device_ip: Optional[IPv4Address], profile_name: str
    ) -> "ProcessPipelineBuilder":
        from services.aria_device import start_aria_stream

        self._process_manager.add_process(
            target=start_aria_stream, args=(device_ip, profile_name, self.config_queue)
        )
        return self

    def add_audio_streaming(self) -> "ProcessPipelineBuilder":
        """Add audio streaming process to the pipeline."""
        from services.aria_device import stream_audio

        self._process_manager.add_thread(target=stream_audio)

        return self

    def add_image_streaming(
        self, sensors_calib_json_str: str
    ) -> "ProcessPipelineBuilder":
        """Add image streaming thread to the pipeline."""
        from services.aria_device import stream_visual_feed

        self._process_manager.add_thread(
            target=stream_visual_feed, args=(sensors_calib_json_str,)
        )
        return self

    def add_pose_streaming(
        self, sensors_calib_json_str: str
    ) -> "ProcessPipelineBuilder":
        from services.aria_device import stream_pose

        self._process_manager.add_thread(
            target=stream_pose, args=(sensors_calib_json_str,)
        )
        return self

    def add_visualization(self) -> "ProcessPipelineBuilder":
        """Add visualization process to the pipeline."""
        from services.visualizer import visualize_feed

        self._process_manager.add_process(target=visualize_feed)
        return self

    def add_object_recognition(self) -> "ProcessPipelineBuilder":
        """Add object recognition process to the pipeline."""
        from services.object_recognition.object_recognition_pipeline import (
            generate_mask,
        )

        self._process_manager.add_process(target=generate_mask)
        return self

    def add_feature_matching(self) -> "ProcessPipelineBuilder":
        """Add feature matching process to the pipeline."""
        from services.feature_matching import feature_matching

        self._process_manager.add_process(target=feature_matching)
        return self

    def build_common_pipeline(self) -> "ProcessPipelineBuilder":
        """Build the common processing pipeline used by both modes."""
        return self.add_visualization().add_object_recognition()

    def build_streaming_pipeline(
        self, device_ip: Optional[IPv4Address], profile_name: str
    ) -> "ProcessPipelineBuilder":
        """Build the complete pipeline for live streaming mode."""
        self.add_streaming(device_ip, profile_name)
        # self.add_visualization()
        # self.add_object_recognition()
        self.add_audio_streaming()
        sensors_calib_json_str = self.config_queue.get()
        # self.add_image_streaming(sensors_calib_json_str)
        # self.add_pose_streaming(sensors_calib_json_str)
        return self


# TODO: Fix Recording Mode
class RecordingModeRunner:
    """Handler for recording playback mode."""

    def __init__(self):
        self.process_manager = ProcessManager()

    def run(self, recording_path: str) -> None:
        """Execute the application in recording playback mode.

        Args:
            recording_path: Path to the recording directory.
        """
        try:
            from services.playback_controller import playback

            logger.info(f"Starting playback mode with recording: {recording_path}")

            # Setup processing pipeline
            self.process_manager.aria_streaming_started.set()
            ProcessPipelineBuilder(self.process_manager).build_common_pipeline()
            logger.info("All processes started successfully")

            # Start playback
            playback(recording_path)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Error in recording playback mode: {e}", exc_info=True)
            raise
        finally:
            self.process_manager.cleanup()
            logger.info("Cleanup completed")


class LiveModeRunner:
    """Handler for live streaming mode."""

    def __init__(self):
        self.process_manager = ProcessManager()

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
        """Run a single streaming session.

        Args:
            device_ip: IP address of the Aria device.
            profile_name: Name of the streaming profile to use.
        """

        # Setup and start processing pipeline
        ProcessPipelineBuilder(self.process_manager).build_streaming_pipeline(
            device_ip=device_ip, profile_name=profile_name
        )
        logger.info("All processes started successfully")

        # In VMs, the Aria USB network interface isn't available at boot — it only appears
        # once the device starts streaming. Block here until the user starts streaming,
        # then configure the interface before proceeding.
        if self._is_virtual_machine():
            self._setup_aria_network()

        while not exit_keypress():
            sleep(1.0)

    def _is_virtual_machine(self) -> bool:
        """Check if running inside a virtual machine."""
        try:
            result = subprocess.run(
                ["systemd-detect-virt"], capture_output=True, text=True
            )
            return result.stdout.strip() != "none"
        except FileNotFoundError:
            return False

    def _setup_aria_network(self):
        """Wait for Aria USB interface and configure network."""
        try:
            while not os.path.exists("/sys/class/net/aria"):
                sleep(0.1)
            subprocess.run(["sudo", "ip", "link", "set", "aria", "up"], check=True)
            subprocess.run(
                ["sudo", "ip", "addr", "add", "192.168.42.1/24", "dev", "aria"],
                check=True,
                capture_output=True,
            )
            logger.info("Aria network configured successfully")
        except subprocess.CalledProcessError as e:
            # Check if the error is just that the file exists
            if "File exists" in e.stderr.decode():
                logger.info("Network interface already configured, continuing...")
            else:
                logger.error(f"Aria network setup error: {e}", exc_info=True)


class AriaApplication:
    """Main application orchestrator."""

    def __init__(self, config: ApplicationConfig):
        self.config = config
        self._realsense_process: Optional[subprocess.Popen] = None

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
        finally:
            self._stop_realsense()

    def _setup_environment(self) -> None:
        """Setup the execution environment."""
        if self.config.update_iptables:
            logger.info("Attempting to update iptables...")
            if not safe_update_iptables():
                logger.warning("Failed to update iptables.")
        self._start_realsense()
        if self.config.track_pose:
            self._start_openvins()
            self._start_rviz2()

    def _start_realsense(self) -> None:
        """Launch the RealSense camera ROS2 node."""
        logger.info("Launching RealSense camera node...")
        try:
            self._realsense_process = subprocess.Popen(
                [
                    "ros2",
                    "launch",
                    "realsense2_camera",
                    "rs_launch.py",
                    "align_depth.enable:=true",
                    "pointcloud.enable:=true",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            logger.info(f"RealSense node started (PID {self._realsense_process.pid}), ")

            # Check the process didn't immediately crash
            if self._realsense_process.poll() is not None:
                stderr = self._realsense_process.stderr.read().decode()
                raise RuntimeError(f"RealSense node failed to start:\n{stderr}")

            logger.info("RealSense camera node is ready.")
        except FileNotFoundError:
            raise RuntimeError(
                "ros2 command not found. Ensure ROS2 is installed and sourced."
            )

    def _start_openvins(self) -> None:
        """Launch the OpenVINS MSCKF subscriber node."""
        logger.info("Launching OpenVINS MSCKF node...")
        try:
            self._openvins_process = subprocess.Popen(
                [
                    "bash",
                    "-c",
                    f"source {OPENVINS_WS}/install/setup.bash && "
                    f"{OPENVINS_WS}/install/ov_msckf/lib/ov_msckf/run_subscribe_msckf "
                    "--ros-args "
                    f"-p config_path:={ESTIMATOR_CONFIG} "
                    "-r __ns:=/ov_msckf",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            logger.info(f"OpenVINS node started (PID {self._openvins_process.pid})")

            if self._openvins_process.poll() is not None:
                stderr = self._openvins_process.stderr.read().decode()
                raise RuntimeError(f"OpenVINS node failed to start:\n{stderr}")

            logger.info("OpenVINS node is ready.")
        except FileNotFoundError:
            raise RuntimeError("OpenVINS binary not found. Check the install path.")

    def _start_rviz2(self) -> None:
        """Launch rviz2 with the OpenVINS display config."""
        logger.info("Launching rviz2...")
        try:
            self._rviz2_process = subprocess.Popen(
                [
                    "rviz2",
                    "-d",
                    str(OPENVINS_WS / "src/open_vins/ov_msckf/launch/display_ros2.rviz"),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            logger.info(f"rviz2 started (PID {self._rviz2_process.pid})")
        except FileNotFoundError:
            raise RuntimeError("rviz2 not found. Ensure ROS2 is installed and sourced.")

    def _stop_realsense(self) -> None:
        """Terminate the RealSense camera ROS2 node if running."""
        if self._realsense_process and self._realsense_process.poll() is None:
            logger.info("Shutting down RealSense camera node...")
            self._realsense_process.terminate()
            try:
                self._realsense_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "RealSense node did not terminate in time, force killing..."
                )
                self._realsense_process.kill()
            logger.info("RealSense camera node stopped.")

    def _execute_mode(self) -> None:
        """Execute the appropriate mode based on configuration."""
        if self.config.mode == "recording":
            RecordingModeRunner().run(self.config.recording_path)
        else:
            LiveModeRunner().run(self.config.device_ip, self.config.profile_name)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


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
        "--track-pose",
        action="store_true",
        default=False,
        help="Launch OpenVINS MSCKF and rviz2 on startup",
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
        track_pose=args.track_pose,
        update_iptables=args.update_iptables,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    multiprocessing.set_start_method("spawn", force=True)
    config = parse_arguments()
    AriaApplication(config).run()


if __name__ == "__main__":
    main()
