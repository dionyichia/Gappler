import logging
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
from projectaria_tools.core.sensor_data import (
    AudioData,
    AudioDataRecord,
)
from scipy.signal import resample

from config import AriaConfig, AudioStreamingPipelineConfig
from services.aria_device.stream.base_streaming_client_observer import (
    BaseStreamingClientObserver,
)

MAX_BUFFER_SAMPLES = (
    AriaConfig.AUDIO_SAMPLE_RATE * AudioStreamingPipelineConfig.MAX_BUFFER_SECONDS
)

logger = logging.getLogger(__name__)


class AudioObserver(BaseStreamingClientObserver):
    """
    Receives interleaved 7-channel audio from the Aria device, demultiplexes
    it into per-channel buffers, and exposes helpers to downsample to 16 kHz
    mono for Whisper inference or WAV export.
    """

    def __init__(
        self, save_dir: str = "output/audio_recordings", save_interval: int = 10
    ):
        self.received: bool = False
        self._buffers = np.zeros(
            (AriaConfig.NUM_AUDIO_CHANNELS, MAX_BUFFER_SAMPLES), dtype=np.int32
        )
        self._write_pos = 0
        self._full = False  # True once the buffer has wrapped at least once
        self._lock = threading.Lock()

        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self._save_interval = save_interval  # seconds between WAV exports
        self._saved_sample_count: int = 0
        self._last_save_time: float = time.time()

    def on_audio_received(self, audio_data: AudioData, record: AudioDataRecord):
        raw = np.array(audio_data.data, dtype=np.int32)

        # Demultiplex interleaved channels: sample layout is [ch0, ch1, …, ch6, ch0, …]
        samples_per_channel = len(raw) // AriaConfig.NUM_AUDIO_CHANNELS
        frame = raw.reshape(samples_per_channel, AriaConfig.NUM_AUDIO_CHANNELS).T

        with self._lock:
            end = self._write_pos + samples_per_channel
            if end <= MAX_BUFFER_SAMPLES:
                self._buffers[:, self._write_pos : end] = frame
            else:
                # Wrap around
                first = MAX_BUFFER_SAMPLES - self._write_pos
                self._buffers[:, self._write_pos :] = frame[:, :first]
                self._buffers[:, : end % MAX_BUFFER_SAMPLES] = frame[:, first:]
                self._full = True  # marked on first wrap
            self._write_pos = end % MAX_BUFFER_SAMPLES
        self.received = True

        # Periodically export a WAV chunk.
        # now = time.time()
        # if now - self._last_save_time >= self._save_interval:
        #     resampled = self._resample_new_samples()
        #     if resampled is not None:
        #         try:
        #             save_path = self._save_wav_chunk(
        #                 resampled, AudioStreamingPipelineConfig.WHISPER_SAMPLE_RATE
        #             )
        #             logger.debug(f"Audio saved: {save_path}")
        #         except Exception as e:
        #             logger.error(f"Error saving audio: {e}")
        #     self._last_save_time = now

    def snapshot(self) -> np.ndarray:
        with self._lock:
            if not self._full:
                # Buffer hasn't wrapped — only the filled portion is valid
                return self._buffers[:, : self._write_pos].copy()
            # Reorder so oldest → newest
            return np.concatenate(
                [
                    self._buffers[:, self._write_pos :],
                    self._buffers[:, : self._write_pos],
                ],
                axis=1,
            )

    def get_resampled_audio(self) -> np.ndarray:
        """
        Return the entire buffered audio as a 16 kHz mono float32 array,
        suitable for passing directly to Whisper.

        Amplitude is normalised to [-1, 1] using the actual peak value so
        the output level is independent of the hardware gain setting.
        """
        mono = self._mix_to_mono(self.channel_buffers)
        resampled = self._downsample(mono, len(mono))
        return self._normalise(resampled)

    def _mix_to_mono(self, channels: list[list]) -> np.ndarray:
        """Average all channels into a single mono signal."""
        if not channels:
            return np.array([], dtype=np.float32)

        # Truncate all channels to the length of the shortest one
        min_length = min(len(c) for c in channels)
        trimmed = [np.array(list(c)[:min_length], dtype=np.float32) for c in channels]

        return np.mean(trimmed, axis=0)

    def _downsample(self, mono: np.ndarray, original_length: int) -> np.ndarray:
        """Resample a mono signal from ARIA_SAMPLE_RATE to WHISPER_SAMPLE_RATE."""
        target_length = int(
            original_length
            * AudioStreamingPipelineConfig.WHISPER_SAMPLE_RATE
            / AriaConfig.AUDIO_SAMPLE_RATE
        )
        return resample(mono, target_length)

    def _normalise(self, audio: np.ndarray) -> np.ndarray:
        """Scale audio to [-1, 1] based on its actual peak amplitude."""
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio / peak
        return audio.astype(np.float32)

    def _resample_new_samples(self) -> np.ndarray | None:
        """
        Resample only the new samples recorded since the last save.
        Returns None if no new data is available.
        """
        current_length = len(self.channel_buffers[0])
        if current_length <= self._saved_sample_count:
            return None

        new_samples = [
            list(ch)[self._saved_sample_count :] for ch in self.channel_buffers
        ]
        self._saved_sample_count = current_length

        mono = self._mix_to_mono(new_samples)
        resampled = self._downsample(mono, len(mono))
        return self._normalise(resampled)

    def _save_wav_chunk(self, audio: np.ndarray, sample_rate: int) -> Path:
        """Write a float32 audio array to a 16-bit mono WAV file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        save_path = self.save_dir / f"audio_chunk_{timestamp}.wav"

        # Convert to int16 for WAV format
        audio_int16 = (audio * 32_767).astype(np.int16)

        with wave.open(str(save_path), "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes per sample (int16)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return save_path
