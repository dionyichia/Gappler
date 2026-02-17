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

from services.aria.base_streaming_client_observer import BaseStreamingClientObserver


class AudioObserver(BaseStreamingClientObserver):
    def __init__(self, save_dir="output/audio_recordings"):
        self.whisper_rate = 16000  # sample rate faster-whisper = 16000
        self.aria_rate = 48000  # sample rate Aria = 48000
        self.audio = []
        self.audios = [[] for c in range(7)]
        self.sampled_audios = np.zeros(self.aria_rate * 1, dtype=np.int8)
        self.timestamp = []
        self.timestamps = []
        self.received = False
        self.last_len = 0
        self.last_save_time = time.time()
        self.save_interval = 10  # seconds

        # Setup save directory
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)

    # source sample rate to 16k
    def resample_audio(self):
        starttime_ns = np.copy(self.timestamps[0])
        audios = np.copy(np.array(self.audios))
        num_samples = int(len(audios[0]) * self.whisper_rate / self.aria_rate)
        sampled_audios = resample(np.mean(np.array(audios), axis=0), num_samples)
        sampled_audios = sampled_audios / 1e8  # normalize sound intensity
        sampled_audios = sampled_audios.astype(np.float32)
        return sampled_audios, starttime_ns

    # source sample rate to 16k for saving audios as wav
    def resample_audio_wav(self):
        audios = np.copy(np.array(self.audios))
        current_len = len(audios[1])
        if current_len <= self.last_len:
            return None
        # only save new part
        new_audios = [ch[self.last_len :] for ch in audios]
        self.last_len = current_len
        mixed = np.mean(np.array(new_audios), axis=0)
        # Resample von 48k -> 16k
        num_samples = int(len(new_audios[0]) * self.whisper_rate / self.aria_rate)
        sampled_audios = resample(mixed, num_samples)
        # normalize to [-1,1]
        max_val = np.max(np.abs(sampled_audios))
        if max_val > 0:
            sampled_audios = sampled_audios / max_val
        return sampled_audios.astype(np.float32)

    def save_audio_chunk(self, audio_data, sample_rate=16000):
        """Save audio chunk to WAV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = self.save_dir / f"audio_chunk_{timestamp}.wav"

        # Convert to int16 for WAV format
        audio_int16 = (audio_data * 32767).astype(np.int16)

        with wave.open(str(filename), "wb") as wav_file:
            wav_file.setnchannels(1)  # mono
            wav_file.setsampwidth(2)  # 2 bytes for int16
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return filename

    def on_audio_received(self, audio_data: AudioData, record: AudioDataRecord):
        self.audio, self.timestamp = audio_data.data, record.capture_timestamps_ns
        self.timestamps += record.capture_timestamps_ns

        # Record Limitation: 100s;10 samples per second
        rec_limit = self.aria_rate * 10 * 100
        if len(self.timestamps) >= rec_limit:
            del self.timestamps[-rec_limit]

        # save data to audios
        for c in range(7):
            self.audios[c] += self.audio[c::7]
            if len(self.audios[c]) >= rec_limit:
                del self.audios[c][-rec_limit:]

        self.received = True

        # Check if 10 seconds have passed since last save
        current_time = time.time()
        if current_time - self.last_save_time >= self.save_interval:
            # Save audio chunk to file every 10 seconds
            resampled_audio = self.resample_audio_wav()
            if resampled_audio is not None:
                try:
                    # saved_file = self.save_audio_chunk(
                    #     resampled_audio, self.whisper_rate
                    # )
                    # print(f"Audio saved: {saved_file}")
                    self.last_save_time = current_time  # Update last save time
                except Exception as e:
                    print(f"Error saving audio: {e}")
