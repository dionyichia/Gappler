"""Checks how the voice pipeline picks the finished sentence to transcribe (T2.10).

Pure logic, no audio, but the module imports the glasses SDK, Whisper and ROS, so it runs on the
lab box:
    source aria/aria_env.sh
    python -m unittest discover -s aria/aria_app/services/aria_device/stream -p "test_*.py"
Times are seconds from the start of the audio window.
"""

import math
import unittest

from services.aria_device.stream.audio_streaming_pipeline import finished_sentence

WINDOW, SILENCE, NOTHING_HANDLED = 15.0, 0.7, -math.inf


class FinishedSentenceTest(unittest.TestCase):
    def test_no_speech(self):
        self.assertIsNone(finished_sentence([], WINDOW, SILENCE, NOTHING_HANDLED))

    def test_still_speaking_waits(self):
        # speech ends 0.3 s before now: not yet followed by enough silence
        self.assertIsNone(finished_sentence([(10.0, 14.7)], WINDOW, SILENCE, NOTHING_HANDLED))

    def test_finished_sentence_is_returned(self):
        self.assertEqual(finished_sentence([(10.0, 14.0)], WINDOW, SILENCE, NOTHING_HANDLED),
                         (10.0, 14.0))

    def test_a_handled_sentence_is_not_returned_again(self):
        # handled when it ended at 14.0, one tick later the window has moved 0.25 s
        self.assertIsNone(finished_sentence([(9.75, 13.75)], WINDOW, SILENCE, 13.75))

    def test_pauses_inside_one_sentence_wait_for_its_end(self):
        # "pick up ... the light", the second part still going
        self.assertIsNone(finished_sentence([(8.0, 9.0), (10.0, 14.8)], WINDOW, SILENCE,
                                            NOTHING_HANDLED))

    def test_all_new_speech_is_one_sentence(self):
        self.assertEqual(finished_sentence([(8.0, 9.0), (10.0, 13.0)], WINDOW, SILENCE,
                                           NOTHING_HANDLED), (8.0, 13.0))

    def test_only_speech_after_the_handled_sentence_counts(self):
        # "pick up the light" handled (ended at 6.0), then "release" finished
        self.assertEqual(finished_sentence([(3.0, 6.0), (11.0, 12.5)], WINDOW, SILENCE, 6.0),
                         (11.0, 12.5))


if __name__ == "__main__":
    unittest.main()
