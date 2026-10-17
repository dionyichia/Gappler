"""Checks that AudioObserver keeps the newest sample's glasses time and fills audio gaps with
silence, so counting back from the newest sample stays right (T2.21).

Needs the glasses SDK (projectaria_tools), no ROS. On the lab box, or on the Mac with the
~/aria-test venv:
    source aria/aria_env.sh
    python -m unittest discover -s aria/aria_app/services/aria_device/stream -p "test_*.py"
"""

import tempfile
import unittest
from types import SimpleNamespace

import numpy as np

from config import AriaConfig
from services.aria_device.stream.audio_streaming_client_observer import (
    MAX_BUFFER_SAMPLES,
    SAMPLE_NS,
    AudioObserver,
)

CHANNELS = AriaConfig.NUM_AUDIO_CHANNELS


def chunk(first_ns: float, n: int, value: int):
    """n samples of `value` on every channel, the first taken at first_ns, as the SDK hands them."""
    data = np.full(n * CHANNELS, value, dtype=np.int32)
    stamps = [int(first_ns + i * SAMPLE_NS) for i in range(n)]
    return SimpleNamespace(data=data), SimpleNamespace(capture_timestamps_ns=stamps)


class AudioObserverTest(unittest.TestCase):
    def setUp(self):
        self.observer = AudioObserver(save_dir=tempfile.mkdtemp(), save_interval=10**9)

    def test_newest_time_comes_with_the_audio(self):
        self.observer.on_audio_received(*chunk(1e9, 100, 1))
        audio, end_ns = self.observer.snapshot()
        self.assertEqual(audio.shape, (CHANNELS, 100))
        self.assertEqual(end_ns, int(1e9 + 99 * SAMPLE_NS))

    def test_back_to_back_chunks_add_no_silence(self):
        self.observer.on_audio_received(*chunk(1e9, 100, 1))
        self.observer.on_audio_received(*chunk(1e9 + 100 * SAMPLE_NS, 100, 2))
        audio, _ = self.observer.snapshot()
        self.assertEqual(audio.shape[1], 200)
        self.assertTrue((audio != 0).all())

    def test_a_gap_is_filled_with_silence(self):
        self.observer.on_audio_received(*chunk(1e9, 100, 1))
        # 1000 samples (about 21 ms) go missing
        self.observer.on_audio_received(*chunk(1e9 + 1100 * SAMPLE_NS, 100, 2))
        audio, end_ns = self.observer.snapshot()
        self.assertEqual(audio.shape[1], 1200)
        self.assertTrue((audio[:, 100:1100] == 0).all())
        self.assertTrue((audio[:, 1100:] == 2).all())
        # counting back from the newest sample lands on the second chunk's first sample
        self.assertAlmostEqual(end_ns - 99 * SAMPLE_NS, 1e9 + 1100 * SAMPLE_NS, delta=1)

    def test_a_gap_longer_than_the_buffer_clears_it(self):
        self.observer.on_audio_received(*chunk(1e9, 100, 1))
        self.observer.on_audio_received(*chunk(1e9 + 2 * MAX_BUFFER_SAMPLES * SAMPLE_NS, 100, 2))
        audio, _ = self.observer.snapshot()
        self.assertEqual(audio.shape[1], 100)
        self.assertTrue((audio == 2).all())


if __name__ == "__main__":
    unittest.main()
