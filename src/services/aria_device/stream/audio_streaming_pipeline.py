"""
Audio streaming and transcription pipeline with LLM inference integration.

Handles real-time audio capture from an Aria device, speech-to-text transcription
via Whisper, and intent extraction via an LLM, publishing results over ROS2.
"""

import logging
import multiprocessing
import queue
import time
from multiprocessing import Queue
from multiprocessing.synchronize import Event

import aria.sdk as aria
import numpy as np
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from scipy.signal import resample
from std_msgs.msg import String

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


def audio_worker(
    raw_audio_queue: Queue,
    quit_event: Event,
) -> None:
    prompt_publisher = ROSPublisher(
        "Aria_audio_prompt_publisher",
        String,
        ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value,
    )
    whisper_model = WhisperModel(
        AudioStreamingPipelineConfig.TRANSCRIPTION_MODEL,
        device=Settings.DEVICE,
        compute_type="int8",
    )
    llm_extractor = LLMPromptExtractor(AudioStreamingPipelineConfig.LLM_MODEL)
    previous_transcription = ""
    previous_prompt = ""

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
        Join all segment texts, log the full transcription, extract intent via
        the LLM, and publish the resulting prompt over ROS2.
        """
        nonlocal previous_transcription, previous_prompt

        if not segments:
            return

        transcription = "\n".join(seg.text for seg in segments)

        if transcription == previous_transcription:
            prompt = previous_prompt
        else:
            previous_transcription = transcription
            logger.info(
                f"Transcription: {transcription}",
            )

            prompt = llm_extractor.extract_object(transcription)
            previous_prompt = prompt

        msg = String()
        msg.data = prompt
        prompt_publisher.publish(msg)

    while not quit_event.is_set():
        try:
            channel_buffers = raw_audio_queue.get(timeout=0.1)
            audio_16k = _get_resampled_audio(channel_buffers)
            if len(audio_16k) == 0:
                continue

            segments = _transcribe(audio_16k)
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
