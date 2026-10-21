"""Checks the WAV replay helpers (T2.8). Numpy and scipy only, no ROS or glasses SDK:
    python -m unittest discover -s aria/tools -p "test_*.py"
"""

import os
import tempfile
import unittest
import wave

import numpy as np

from replay_audio_file_to_prompt import next_wav, read_wav, windows


class WindowsTest(unittest.TestCase):
    def test_trailing_window_like_the_live_buffer(self):
        # 25 s at 10 Hz, a step of 1 s, a 10 s window
        got = list(windows(250, 10, 1, 10))
        self.assertEqual(got[0], (0, 10))        # grows from the start
        self.assertEqual(got[9], (0, 100))       # full at 10 s
        self.assertEqual(got[10], (10, 110))     # then slides
        self.assertEqual(got[-1], (150, 250))    # ends on the last sample
        self.assertEqual(len(got), 25)

    def test_a_short_last_step_still_reaches_the_end(self):
        self.assertEqual(list(windows(25, 10, 1, 10))[-1], (0, 25))


class ReadWavTest(unittest.TestCase):
    def test_mono_44k1_becomes_one_channel_at_48k(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "voice.wav")
            with wave.open(path, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(44100)
                w.writeframes(np.full(44100, 1000, np.int16).tobytes())
            audio = read_wav(path, 48000)
        self.assertEqual(audio.shape, (1, 48000))
        self.assertEqual(audio.dtype, np.int32)


class NextWavTest(unittest.TestCase):
    def test_enter_a_name_a_path_or_nothing_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            release = os.path.join(tmp, "release_command.wav")
            other = os.path.join(tmp, "voice.wav")
            for path in (release, other):
                open(path, "w").close()
            self.assertEqual(next_wav("", other, tmp), other)            # Enter: same file
            self.assertEqual(next_wav(" release ", other, tmp), release)  # short name
            self.assertEqual(next_wav(other, release, tmp), other)        # a path
            self.assertIsNone(next_wav("pick", other, tmp))               # neither


if __name__ == "__main__":
    unittest.main()
