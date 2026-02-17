from ipaddress import IPv4Address
from typing import Optional

from config import AriaConfig


class ApplicationConfig:
    """Container for application configuration."""

    def __init__(
        self,
        mode: str,
        recording_path: Optional[str] = None,
        device_ip: Optional[IPv4Address] = None,
        profile_name: Optional[str] = None,
        update_iptables: bool = False,
    ):
        self.mode = mode
        self.recording_path = recording_path
        self.device_ip = device_ip or AriaConfig.ARIA_DEVICE_IP_ADDRESS
        self.profile_name = profile_name or AriaConfig.ARIA_STREAMING_PROFILE_NAME
        self.update_iptables = update_iptables

    def validate(self) -> None:
        """Validate configuration consistency.

        Raises:
            ValueError: If configuration is invalid.
        """
        if self.mode == "recording" and not self.recording_path:
            raise ValueError("Recording path is required for recording mode")
