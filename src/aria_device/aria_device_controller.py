import logging
from ipaddress import IPv4Address
from typing import Optional

import aria.sdk as aria
from projectaria_tools.core.calibration import (
    device_calibration_from_json_string,
    distort_by_calibration,
    get_linear_camera_calibration,
)

from config import AriaConfig

logger = logging.getLogger(__name__)


class AriaDeviceController:
    """
    Singleton controller for Aria device connection and streaming setup.

    Handles device discovery, connection, and streaming configuration.
    Use this to start/stop streaming on the device itself.

    Only one instance can exist as only one device can be controlled at a time.
    """

    _device: Optional[aria.Device] = None
    _instance: Optional["AriaDeviceController"] = None
    _initialized: bool = False

    def __new__(cls):
        """
        Create or return the singleton instance.

        Returns:
            The singleton AriaDeviceController instance.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_level: aria.Level = AriaConfig.ARIA_LOG_LEVEL):
        """
        Initialize Aria device controller (only once).

        Args:
            log_level: SDK logging verbosity level (default: Info).
        """
        if self._initialized:
            return

        aria.set_log_level(log_level)
        self.device_client = aria.DeviceClient()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> "AriaDeviceController":
        """
        Get the singleton instance.

        Returns:
            The singleton AriaDeviceController instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance.

        Useful for testing or when you need to reconnect to a different device.
        """
        if cls._instance is not None:
            cls._instance.disconnect()
            cls._instance = None
            cls._initialized = False

    def connect(
        self,
        device_ip: Optional[IPv4Address] = None,
    ) -> aria.Device:
        """
        Connect to Aria device.

        Args:
            device_ip: IPv4 address of the device (None for connection via USB).

        Returns:
            Connected Aria device instance.

        Raises:
            ConnectionError: If device connection fails.
            RuntimeError: If already connected to a device.
        """
        if self._device:
            raise RuntimeError(
                "Already connected to a device. Call disconnect() first or use the existing connection."
            )

        # Configure device client if IP provided
        client_config = aria.DeviceClientConfig()
        if device_ip:
            client_config.ip_v4_address = str(device_ip)
        self.device_client.set_client_config(client_config)

        # Connect to device
        self._device = self.device_client.connect()
        self._print_device_status(self._device)

        return self._device

    def start_streaming(
        self,
        profile: str = "profile18",
        interface: Optional[str] = None,
        use_ephemeral_certs: bool = True,
    ) -> None:
        """
        Start streaming on the connected device.

        Args:
            profile: Streaming profile name (e.g., 'profile18').
            interface: Connection interface ('usb' or 'wifi'). None for default (wifi).
            use_ephemeral_certs: Whether to use ephemeral certificates.

        Raises:
            RuntimeError: If device is not connected.
        """
        if not self._device:
            raise RuntimeError("Device not connected. Call connect() first.")

        streaming_manager = self._device.streaming_manager

        # Check if already streaming
        if streaming_manager.streaming_state == aria.StreamingState.Streaming:
            logger.warning("⚠ Device is already streaming")
            return

        streaming_config = self._create_streaming_config(
            profile, interface, use_ephemeral_certs
        )
        streaming_manager.streaming_config = streaming_config

        streaming_manager.start_streaming()

        while streaming_manager.streaming_state != aria.StreamingState.Streaming:
            pass  # Wait until streaming starts

        logger.info("✓ Streaming started")
        logger.info(f"  State: {streaming_manager.streaming_state}")
        logger.info(f"  Profile: {profile}")
        logger.info(f"  Interface: {interface or 'wifi (default)'}")

    def stop_streaming(self) -> None:
        """
        Stop streaming on the device.

        Raises:
            RuntimeError: If device is not connected.
        """
        if not self._device:
            raise RuntimeError("Device not connected")

        try:
            self._device.streaming_manager.stop_streaming()
            logger.info("✓ Streaming stopped")
        except Exception as e:
            logger.error(f"✗ Error stopping streaming: {e}")
            raise

    def disconnect(self) -> None:
        """
        Disconnect from the device.

        Automatically stops streaming if active.
        """
        if not self._device:
            logger.warning("No active device connection")
            return

        try:
            # Stop streaming if active
            if (
                self._device.streaming_manager.streaming_state
                == aria.StreamingState.Streaming
            ):
                self.stop_streaming()

            self.device_client.disconnect(self._device)
            logger.info("✓ Disconnected from device")
        except Exception as e:
            logger.error(f"✗ Error during disconnect: {e}")
        finally:
            self._device = None

    def _create_streaming_config(
        self, profile: str, interface: Optional[str], use_ephemeral_certs: bool
    ) -> aria.StreamingConfig:
        """
        Create streaming configuration.

        Args:
            profile: Streaming profile name.
            interface: Connection interface ('usb', 'wifi', or None for default).
            use_ephemeral_certs: Whether to use ephemeral certificates.

        Returns:
            Configured StreamingConfig instance.
        """
        config = aria.StreamingConfig()
        config.profile_name = profile

        # Set interface (default is wifi)
        if interface and interface.lower() == "usb":
            config.streaming_interface = aria.StreamingInterface.Usb

        config.security_options.use_ephemeral_certs = use_ephemeral_certs

        return config

    def _print_device_status(self, device: aria.Device) -> None:
        """
        Print device status information.

        Args:
            device: Connected Aria device.
        """
        status = device.status
        logger.info("✓ Device connected")
        logger.info(f"  Battery level: {status.battery_level}%")
        if status.wifi_ssid:
            logger.info(f"  WiFi SSID: {status.wifi_ssid}")
        if status.wifi_ip_address:
            logger.info(f"  WiFi IP: {status.wifi_ip_address}")

    def get_rgb_camera_calibration(self) -> Optional[aria.CameraCalibration]:
        """
        Get RGB camera calibration from the connected device.

        Returns:
            CameraCalibration instance for RGB camera, or None if not connected.
        """
        if not self._device:
            logger.warning("Device not connected")
            return None

        streaming_manager = self._device.streaming_manager
        sensors_calib_json = streaming_manager.sensors_calibration()
        sensors_calib = device_calibration_from_json_string(sensors_calib_json)
        rgb_calib = sensors_calib.get_camera_calib("camera-rgb")

        dst_calib = get_linear_camera_calibration(512, 512, 150, "camera-rgb")
        return rgb_calib

    @property
    def device(self) -> Optional[aria.Device]:
        """Get the connected device instance."""
        return self._device

    @property
    def is_connected(self) -> bool:
        """Check if device is currently connected."""
        return self._device is not None

    @property
    def is_streaming(self) -> bool:
        """Check if device is currently streaming."""
        if not self._device:
            return False
        return (
            self._device.streaming_manager.streaming_state
            == aria.StreamingState.Streaming
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.disconnect()
        return False
