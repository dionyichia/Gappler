"""
Audio streaming and transcription pipeline with LLM inference integration.

Handles real-time audio capture from an Aria device, speech-to-text transcription
via Whisper, and intent extraction via an LLM, publishing results over ROS2.
"""

import logging
import math
import multiprocessing
import queue
import re
import time
from multiprocessing import Queue
from multiprocessing.synchronize import Event

import aria.sdk as aria
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from faster_whisper.vad import VadOptions, get_speech_timestamps
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from scipy.signal import resample
from std_msgs.msg import Bool, String

from config import AriaConfig, AudioStreamingPipelineConfig, ROS2Topics, Settings
from services.aria_device import AriaStreamClient, AudioObserver
from services.prompt_extractor import LLMPromptExtractor
from services.ros import ROSPublisher

# Configure logging
logger = logging.getLogger(__name__)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)


def _put_latest(q: Queue, item) -> None:
    """Discard stale item and put the latest one."""
    try:
        q.get_nowait()
    except Exception:
        pass
    try:
        q.put_nowait(item)
    except Exception:
        pass


def finished_sentence(speech, window_s, silence_s, handled_until):
    """The sentence to transcribe now, as (start, end), or None (T2.10, CHANNEL_CONTRACT A-5).

    speech: the voice detector's (start, end) spans. All times are seconds from the window start.
    handled_until: where the last transcribed sentence ended, negative once it has left the window.
    Every span starting after it is one new sentence, finished once silence_s has passed since
    its last span ended.
    """
    new = [(start, end) for start, end in speech if start > handled_until]
    if not new or window_s - new[-1][1] < silence_s:
        return None
    return new[0][0], new[-1][1]


def is_release(transcription: str) -> bool:
    """True if the sentence has a release phrase as whole words, so "released" and "let's go" do
    not count (T2.6, CHANNEL_CONTRACT A-1)."""
    words = " " + " ".join(re.findall(r"[a-z']+", transcription.lower())) + " "
    return any(f" {phrase} " in words for phrase in AudioStreamingPipelineConfig.RELEASE_PHRASES)


def audio_worker(
    raw_audio_queue: Queue,
    quit_event: Event,
) -> None:
    prompt_publisher = ROSPublisher(
        "Aria_audio_prompt_publisher",
        String,
        ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value,
        QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        ),
    )
    release_publisher = ROSPublisher(
        "Aria_release_publisher",
        Bool,
        ROS2Topics.MANIPULATOR_RELEASE.value,
        QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        ),
    )
    whisper_model = WhisperModel(
        AudioStreamingPipelineConfig.TRANSCRIPTION_MODEL,
        device=Settings.DEVICE,
        compute_type="int8",
    )
    llm_extractor = LLMPromptExtractor(AudioStreamingPipelineConfig.LLM_MODEL)
    sample_rate = AudioStreamingPipelineConfig.WHISPER_SAMPLE_RATE
    silence_s = AudioStreamingPipelineConfig.END_OF_SPEECH_SILENCE_SECONDS
    # Splits speech at pauses of silence_s, so a pause inside a sentence shorter than that is kept.
    # Other settings are faster-whisper's defaults: speech threshold 0.5, and each span padded by
    # 0.4 s so Whisper gets whole words. The padding adds to the wait: a sentence counts as
    # finished about silence_s + 0.4 s after its last word.
    vad_options = VadOptions(min_silence_duration_ms=int(silence_s * 1000))
    handled_until = -math.inf   # monotonic time the last transcribed sentence ended

    def _get_resampled_audio(channel_buffers: np.ndarray) -> np.ndarray:
        """Mix, downsample and normalise raw channel buffers into a 16 kHz mono array."""
        if channel_buffers is None or channel_buffers.size == 0:
            return np.array([], dtype=np.float32)

        # Mix to mono
        mono = np.mean(channel_buffers.astype(np.float32), axis=0)

        # Downsample
        target_length = int(
            len(mono)
            * AudioStreamingPipelineConfig.WHISPER_SAMPLE_RATE
            / AriaConfig.AUDIO_SAMPLE_RATE
        )
        resampled = resample(mono, target_length)

        # Normalise
        peak = np.max(np.abs(resampled))
        if peak > 0:
            resampled /= peak
        return resampled.astype(np.float32)

    def _transcribe(audio: np.ndarray) -> list:
        """Return Whisper segments for the given 16 kHz mono audio array."""
        segments, _ = whisper_model.transcribe(
            audio,
            language="en",
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
        # Materialise the generator so segments can be reused.
        return list(segments)

    def _process_segments(segments: list[Segment]) -> None:
        """
        Join the sentence's segment texts, extract the object via the LLM, and publish it once.
        Nothing is published when the LLM finds no object (T2.10). The stop word wins over
        release, and release goes to /manipulator/release, never out as a word (T2.6).
        """
        if not segments:
            return

        transcription = "\n".join(seg.text for seg in segments)
        prompt = llm_extractor.extract_object(transcription)
        if prompt != AudioStreamingPipelineConfig.STOP_KEYWORD and is_release(transcription):
            logger.info(f"Transcription: {transcription!r} -> release")
            release_publisher.publish(Bool(data=True))
            return
        logger.info(f"Transcription: {transcription!r} -> {prompt!r}")
        if not prompt:
            return

        msg = String()
        msg.data = prompt
        prompt_publisher.publish(msg)

    while not quit_event.is_set():
        try:
            channel_buffers = raw_audio_queue.get(timeout=0.1)
            audio_16k = _get_resampled_audio(channel_buffers)
            if len(audio_16k) == 0:
                continue

            # The buffer ends now: act only on a sentence followed by silence_s of quiet
            window_s = len(audio_16k) / sample_rate
            window_start = time.monotonic() - window_s
            speech = [(span["start"] / sample_rate, span["end"] / sample_rate)
                      for span in get_speech_timestamps(audio_16k, vad_options)]
            sentence = finished_sentence(speech, window_s, silence_s,
                                         handled_until - window_start)
            if sentence is None:
                continue
            handled_until = window_start + sentence[1]

            start, end = (int(t * sample_rate) for t in sentence)
            segments = _transcribe(audio_16k[start:end])
            _process_segments(segments)

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Audio worker error: {e}", exc_info=True)


class AudioStreamingPipeline:
    """Real-time pipeline: Aria audio → Whisper transcription → LLM intent → ROS2."""

    def __init__(self, quit_event: Event):
        self.quit_event = quit_event

        self.raw_audio_queue = multiprocessing.Queue(maxsize=1)
        self.audio_process = multiprocessing.Process(
            target=audio_worker,
            args=(self.raw_audio_queue, self.quit_event),
            daemon=True,
        )
        self.audio_process.start()

        logger.info("Audio streaming pipeline initialised")

    def run(self) -> None:
        """Stream audio from the Aria device and run the transcription loop."""
        try:
            with AriaStreamClient() as aria_stream_client:
                # Subscribe to audio data
                data_channels = [(aria.StreamingDataType.Audio, 100)]
                observer = AudioObserver()
                aria_stream_client.subscribe(data_channels, observer)

                logger.info("Started audio streaming")

                while not self.quit_event.is_set():
                    iteration_start = time.time()

                    if observer.received:
                        observer.received = False
                        _put_latest(self.raw_audio_queue, observer.snapshot())

                    # Pace the loop to a consistent iteration interval.
                    elapsed = time.time() - iteration_start
                    remaining = (
                        AudioStreamingPipelineConfig.ITERATION_INTERVAL_SECONDS
                        - elapsed
                    )
                    if remaining > 0:
                        time.sleep(remaining)

        except KeyboardInterrupt:
            logger.warning("Audio streaming pipeline interrupted by user")
        except Exception as e:
            logger.error(f"Error in audio pipeline: {e}", exc_info=True)
        finally:
            self.audio_process.join(timeout=5)
            logger.info("Pipeline shutdown complete")


def stream_audio(aria_streaming_started: Event, quit_event: Event) -> None:
    pipeline = AudioStreamingPipeline(quit_event)
    aria_streaming_started.wait()
    pipeline.run()
