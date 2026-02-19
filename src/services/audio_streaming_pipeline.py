"""
Audio streaming and transcription pipeline with LLM inference integration.

Handles real-time audio capture from an Aria device, speech-to-text transcription
via Whisper, and intent extraction via an LLM, publishing results over ROS2.
"""

import logging
import os
import time
from multiprocessing.synchronize import Event

import aria.sdk as aria
import numpy as np
import torch
from faster_whisper import WhisperModel
from faster_whisper.transcribe import Segment
from std_msgs.msg import String

from config import AudioStreamingPipelineConfig, ROS2Topics, Settings
from services.aria_device import AriaStreamClient, AudioObserver
from services.prompt_extractor import LLMPromptExtractor
from services.ros.ros_publisher import ROSPublisher

logger = logging.getLogger(__name__)


def _configure_cudnn_path() -> None:
    """Prepend the PyTorch-bundled CUDNN library directory to LD_LIBRARY_PATH."""
    cudnn_path = os.path.abspath(
        os.path.join(os.path.dirname(torch.__file__), "..", "nvidia", "cudnn", "lib")
    )
    current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    os.environ["LD_LIBRARY_PATH"] = f"{cudnn_path}:{current_ld_path}"


class AudioStreamingPipeline:
    """Real-time pipeline: Aria audio → Whisper transcription → LLM intent → ROS2."""

    def __init__(
        self,
        quit_event: Event,
        whisper_model: str = AudioStreamingPipelineConfig.TRANSCRIPTION_MODEL,
        llm_model: str = AudioStreamingPipelineConfig.LLM_MODEL,
    ):
        """
        Initialize the audio streaming pipeline.

        Args:
            whisper_model: Whisper model identifier
            llm_model: LLM model identifier for prompt extraction
        """
        # Configure logging
        logging.getLogger("faster_whisper").setLevel(logging.WARNING)

        # Initialize components
        self.whisper_model = WhisperModel(
            whisper_model,
            device=Settings.DEVICE,
            compute_type="int8",
        )
        self.llm_extractor = LLMPromptExtractor(llm_model)
        self.prompt_publisher = ROSPublisher(
            "Aria_audio_prompt_publisher",
            String,
            ROS2Topics.AUDIO_TRANSCRIPTION_PROMPT.value,
        )
        self._previous_transcription = ""
        self._previous_prompt = ""
        self._quit_event = quit_event

        logging.info("Audio streaming pipeline initialised")

    def _transcribe(self, audio: np.ndarray) -> list:
        """Return Whisper segments for the given 16 kHz mono audio array."""
        segments, _ = self.whisper_model.transcribe(
            audio,
            language="en",
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )
        # Materialise the generator so segments can be reused.
        return list(segments)

    def _process_segments(self, segments: list[Segment]) -> None:
        """
        Join all segment texts, log the full transcription, extract intent via
        the LLM, and publish the resulting prompt over ROS2.
        """
        if not segments:
            return

        transcription = "\n".join(seg.text for seg in segments)

        if transcription == self._previous_transcription:
            prompt = self._previous_prompt
        else:
            self._previous_transcription == transcription
            logging.info(f"Transcription: {transcription}")
            prompt = self.llm_extractor.extract_object(transcription)

        msg = String()
        msg.data = prompt
        self._previous_prompt = prompt
        self.prompt_publisher.publish(msg)

    def run(self) -> None:
        """Stream audio from the Aria device and run the transcription loop."""
        try:
            with AriaStreamClient() as aria_stream_client:
                # Subscribe to audio data
                data_channels = [aria.StreamingDataType.Audio]
                message_size = 100
                observer: AudioObserver = aria_stream_client.subscribe(
                    data_channels, AudioObserver(), message_size
                )

                logging.info("Started audio streaming")

                while not self._quit_event.is_set():
                    iteration_start = time.time()

                    if observer.received:
                        audio_16k = observer.get_resampled_audio()
                        segments = self._transcribe(audio_16k)
                        self._process_segments(segments)

                    # Pace the loop to a consistent iteration interval.
                    elapsed = time.time() - iteration_start
                    remaining = (
                        AudioStreamingPipelineConfig.ITERATION_INTERVAL_SECONDS
                        - elapsed
                    )
                    if remaining > 0:
                        time.sleep(remaining)

        except Exception as e:
            logging.error(f"Error in audio pipeline: {e}", exc_info=True)
        finally:
            logging.info("Pipeline shutdown complete")


def stream_audio(quit_event: Event) -> None:
    _configure_cudnn_path()
    AudioStreamingPipeline(quit_event).run()


if __name__ == "__main__":
    stream_audio()
