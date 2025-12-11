"""
Aria device streaming management.

Provides separate managers for device control and data subscription
for Meta Aria glasses.
"""

import logging
import operator
from functools import reduce
from typing import List, Optional

import aria.sdk as aria

from .streaming_client_observer import BaseStreamingClientObserver

logger = logging.getLogger(__name__)


class AriaStreamClient:
    """
    Subscriber for receiving streaming data from Aria device.

    Handles subscription to data streams via auto-discovery (mDNS).
    Multiple subscribers can connect to a single streaming device.
    """

    def __init__(self):
        """
        Initialize Aria stream subscriber.

        Args:
            log_level: SDK logging verbosity level (default: Info).
        """
        self.streaming_client = aria.StreamingClient()
        self._observer: Optional[BaseStreamingClientObserver] = None
        self._subscribed: bool = False

    def subscribe(
        self,
        data_channels: List[aria.StreamingDataType],
        observer: BaseStreamingClientObserver,
        message_queue_size: int = 1,
        use_ephemeral_certs: bool = False,
    ) -> BaseStreamingClientObserver:
        """
        Subscribe to streaming data from any available Aria device.

        Args:
            data_channels: List of data types to subscribe to
                          (e.g., [aria.StreamingDataType.Rgb, aria.StreamingDataType.Slam]).
            observer: Observer to handle incoming data.
            message_queue_size: Number of messages to buffer per data type.
            use_ephemeral_certs: Whether to use ephemeral certificates.

        Returns:
            The attached observer instance.

        Raises:
            RuntimeError: If already subscribed.
        """
        if self._subscribed:
            raise RuntimeError("Already subscribed. Call unsubscribe() first.")

        # Configure subscription
        config = self.streaming_client.subscription_config
        config.subscriber_data_type = reduce(operator.or_, data_channels)

        # Set queue size for each data type
        for data_type in data_channels:
            config.message_queue_size[data_type] = message_queue_size

        # Configure security
        config.security_options = self._create_security_options(use_ephemeral_certs)
        self.streaming_client.subscription_config = config

        # Attach observer and subscribe
        self.streaming_client.set_streaming_client_observer(observer)
        self.streaming_client.subscribe()

        self._observer = observer
        self._subscribed = True

        logger.info(f"✓ Subscribed to {len(data_channels)} data channel(s)")
        logger.info(f"  Channels: {[dt.name for dt in data_channels]}")
        logger.info(f"  Queue size: {message_queue_size}")

        return observer

    def unsubscribe(self) -> None:
        """
        Unsubscribe from streaming data.

        Stops receiving data and cleans up resources.
        """
        if not self._subscribed:
            logger.warning("Not currently subscribed")
            return

        try:
            self.streaming_client.unsubscribe()
            logger.info("✓ Unsubscribed from data stream")
        except Exception as e:
            logger.error(f"✗ Error during unsubscribe: {e}")
        finally:
            self._observer = None
            self._subscribed = False

    def _create_security_options(
        self, use_ephemeral_certs: bool
    ) -> aria.StreamingSecurityOptions:
        """
        Create security options for streaming.

        Args:
            use_ephemeral_certs: Whether to use ephemeral certificates.

        Returns:
            Configured StreamingSecurityOptions instance.
        """
        options = aria.StreamingSecurityOptions()
        options.use_ephemeral_certs = use_ephemeral_certs
        return options

    @property
    def is_subscribed(self) -> bool:
        """Check if currently subscribed to data stream."""
        return self._subscribed

    @property
    def observer(self) -> Optional[BaseStreamingClientObserver]:
        """Get the current observer instance."""
        return self._observer

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.unsubscribe()
        return False
