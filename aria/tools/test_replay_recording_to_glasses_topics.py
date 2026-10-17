"""Checks swap_sound, which puts a WAV in place of a recording's sound by capture time (T2.21).
No SDK or ROS needed:
    cd aria/tools && python -m unittest test_replay_recording_to_glasses_topics
"""

import unittest

import numpy as np

from replay_recording_to_glasses_topics import swap_sound

SAMPLE_NS = 1e9 / 48000


class SwapSoundTest(unittest.TestCase):
    def test_sample_n_of_the_wav_at_the_recording_sample_n(self):
        wav = np.arange(10, 20)
        # samples 3 to 5 of the recording, with the clock jitter seen on c2cbafe8 (up to 10 us)
        stamps = [1e9 + 3 * SAMPLE_NS + 8e3, 1e9 + 4 * SAMPLE_NS - 9e3, 1e9 + 5 * SAMPLE_NS]
        self.assertEqual(swap_sound(stamps, wav, 1e9, SAMPLE_NS, 1).tolist(), [13, 14, 15])

    def test_past_the_wav_is_silence(self):
        stamps = [1e9 + i * SAMPLE_NS for i in (9, 10, 11)]
        self.assertEqual(swap_sound(stamps, np.arange(1, 11), 1e9, SAMPLE_NS, 1).tolist(),
                         [10, 0, 0])

    def test_every_channel_gets_the_sound_interleaved(self):
        stamps = [1e9, 1e9 + SAMPLE_NS]
        self.assertEqual(swap_sound(stamps, np.array([5, 6]), 1e9, SAMPLE_NS, 3).tolist(),
                         [5, 5, 5, 6, 6, 6])


if __name__ == "__main__":
    unittest.main()
