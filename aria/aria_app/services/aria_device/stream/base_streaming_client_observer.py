from typing import Sequence

import aria.sdk as aria
import numpy as np
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
    BarometerData,
    ImageDataRecord,
    MotionData,
)


class BaseStreamingClientObserver:
    """
    Streaming client observer class. Describes all available callbacks that are invoked by the
    streaming client.
    """

    def on_image_received(self, image: np.array, record: ImageDataRecord) -> None:
        pass

    def on_audio_received(
        self,
        audio_data: AudioData,
        record: AudioDataRecord,
    ) -> None:
        pass

    def on_imu_received(self, samples: Sequence[MotionData], imu_idx: int) -> None:
        pass

    def on_magneto_received(self, sample: MotionData) -> None:
        pass

    def on_baro_received(self, sample: BarometerData) -> None:
        pass

    def on_streaming_client_failure(self, reason: aria.ErrorCode, message: str) -> None:
        pass
