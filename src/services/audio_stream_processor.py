"""
Audio streaming and transcription pipeline with GPT inference integration.

This module handles real-time audio capture, speech-to-text transcription using Whisper,
and integration with a GPT-based inference system for intent recognition and tool calling.
"""

import logging
import os
import string
import time
from dataclasses import dataclass
from typing import List, Tuple

import aria.sdk as aria
import torch
import zmq
from faster_whisper import WhisperModel

from config import Settings, ZMQConfig
from services.aria import AriaStreamClient, AudioObserver
from services.prompt_extractor import LLMPromptExtractor

# Constants
WHISPER_MODEL = "small.en"
NANOSECONDS_PER_SECOND = int(1e9)
ITERATION_INTERVAL_SECONDS = 1


@dataclass
class TranscriptionWord:
    """Represents a single transcribed word with timing and confidence."""

    start_ns: int
    end_ns: int
    text: str
    confidence: float


class CUDNNPathConfigurator:
    """Configures CUDNN library path for PyTorch."""

    @staticmethod
    def configure():
        """Add CUDNN path to LD_LIBRARY_PATH environment variable."""
        cudnn_path = os.path.join(
            os.path.dirname(torch.__file__), "..", "nvidia", "cudnn", "lib"
        )
        cudnn_path = os.path.abspath(cudnn_path)
        current_ld_path = os.environ.get("LD_LIBRARY_PATH", "")
        os.environ["LD_LIBRARY_PATH"] = f"{cudnn_path}:{current_ld_path}"


class ZMQManager:
    """Manages ZeroMQ socket connections for command publishing."""

    def __init__(self, command_address: str = ZMQConfig.AUDIO_COMMAND_ADDRESS):
        """
        Initialize ZMQ manager.

        Args:
            command_address: ZMQ address to bind command socket to
        """
        self.context = zmq.Context()
        self.command_socket = None
        self.command_address = command_address

    def setup_sockets(self):
        """Initialize and configure all ZMQ sockets."""
        self.command_socket = self.context.socket(zmq.PUB)
        self.command_socket.bind(self.command_address)
        logging.info(f"Command socket bound to {self.command_address}")

    def send_command(self, command: str):
        """
        Send command via command socket.

        Args:
            command: Command string to send
        """
        if self.command_socket:
            self.command_socket.send_string(command)
            logging.debug(f"Sent command: {command}")
        else:
            logging.warning("Command socket not initialized")

    def close_all(self):
        """Close all sockets and cleanup context."""
        if self.command_socket:
            self.command_socket.close()
            logging.info("Command socket closed")
        self.context.term()


def normalize_phrase(phrase: str) -> str:
    """Remove punctuation and convert to lowercase."""
    return phrase.translate(str.maketrans("", "", string.punctuation)).strip().lower()


class AudioTranscriptionPipeline:
    """Main pipeline for audio streaming and transcription."""

    def __init__(
        self,
        whisper_model: str = WHISPER_MODEL,
        llm_model: str = "Qwen/Qwen2.5-0.5B-Instruct",
    ):
        """
        Initialize the audio transcription pipeline.

        Args:
            whisper_model: Whisper model identifier
            llm_model: LLM model identifier for prompt extraction
            output_dir: Directory for output files
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
        self.zmq_manager = ZMQManager()

        logging.info("Audio transcription pipeline initialized")

    def _process_segments(
        self, segments, starttime_ns: int
    ) -> Tuple[bool, List[TranscriptionWord]]:
        """
        Process transcription segments and detect trigger words.

        Args:
            segments: Iterable of transcription segments
            starttime_ns: Start time in nanoseconds

        Returns:
            Tuple of (should_quit, recorded_words)
        """
        should_quit = False
        recorded_words = []

        for segment in segments:
            if not hasattr(segment, "words") or not segment.words:
                continue

            logging.info(f"Segment: {segment.text}")

            # Process each word for trigger detection
            for word in segment.words:
                # Convert to nanoseconds
                start_ns = int(word.start * NANOSECONDS_PER_SECOND + starttime_ns)
                end_ns = int(word.end * NANOSECONDS_PER_SECOND + starttime_ns)

                recorded_words.append(
                    TranscriptionWord(
                        start_ns=start_ns,
                        end_ns=end_ns,
                        text=word.word,
                        confidence=word.probability,
                    )
                )

                logging.info(f"[{start_ns}ns -> {end_ns}ns] {word.word}")

            # Send segment to LLM for intent extraction
            if hasattr(segment, "text") and segment.text:
                command = self.llm_extractor.extract_object(segment.text)
                self.zmq_manager.send_command(command)

        return should_quit, recorded_words

    def run(self):
        """Execute the main audio streaming and transcription loop."""
        self.zmq_manager.setup_sockets()

        try:
            with AriaStreamClient() as audio_streamer:
                # Subscribe to audio data
                data_channels = [aria.StreamingDataType.Audio]
                message_size = 100
                observer: AudioObserver = audio_streamer.subscribe(
                    data_channels, AudioObserver(), message_size
                )

                logging.info("Started audio streaming")

                while True:
                    start_time = time.time()

                    if observer.received:
                        # Resample audio and transcribe
                        audios_16k, starttime_ns = observer.resample_audio()
                        segments, _ = self.whisper_model.transcribe(
                            audios_16k,
                            language="en",
                            word_timestamps=True,
                            vad_filter=True,
                            beam_size=5,
                            condition_on_previous_text=False,
                        )

                        if segments is None:
                            logging.debug("No segments detected, continuing...")
                            continue

                        # Convert to list to allow multiple iterations
                        segments_list = list(segments)

                        # Process segments for trigger words and recording
                        should_quit, recorded_words = self._process_segments(
                            segments_list, starttime_ns
                        )

                        if should_quit:
                            logging.info("Quit signal received, stopping pipeline")
                            break

                    # Maintain consistent iteration interval
                    elapsed = time.time() - start_time
                    if elapsed < ITERATION_INTERVAL_SECONDS:
                        time.sleep(ITERATION_INTERVAL_SECONDS - elapsed)

                audio_streamer.streaming_client.unsubscribe()
                logging.info("Unsubscribed from audio stream")

        except Exception as e:
            logging.error(f"Error in audio pipeline: {e}", exc_info=True)
        finally:
            self.zmq_manager.close_all()
            logging.info("Pipeline shutdown complete")


def stream_audio():
    """Entry point for the audio transcription pipeline."""
    # Configure CUDNN path
    CUDNNPathConfigurator.configure()

    # Create and run pipeline
    pipeline = AudioTranscriptionPipeline()
    pipeline.run()


if __name__ == "__main__":
    stream_audio()
