"""
Audio streaming and transcription pipeline with GPT inference integration.

This module handles real-time audio capture, speech-to-text transcription using Whisper,
and integration with a GPT-based inference system for intent recognition and tool calling.
"""

import json
import os
from pathlib import Path
import re
import string
import sys

import aria.sdk as aria
import pandas as pd
from faster_whisper import WhisperModel

from aria_device import AriaStreamClient, AudioObserver
from config import AudioStreamProcessorConfig
from utils import CSVWriter
from services.zmq_manager import ZMQManager

# Constants
WHISPER_MODEL = "small.en"
NANOSECONDS_PER_SECOND = int(1e9)
TRIGGER_WORD_START = "start"
TRIGGER_WORD_FINISH = "finish"


def normalize_word(word: str) -> str:
    """Remove punctuation and convert to lowercase."""
    return word.translate(str.maketrans("", "", string.punctuation)).strip().lower()


def find_timestamps(csv_file, question, gpt_output):
    """
    Match GPT output words with timestamps from CSV transcription.

    Args:
        csv_file: Path to CSV containing transcribed words with timestamps
        question: Original question text
        gpt_output: GPT response containing words to match

    Returns:
        Updated GPT output with timestamp information
    """
    gpt_words = gpt_output.get("word", [])
    timestamp_result = {"startTime_ns": [], "endTime_ns": []}

    df = pd.read_csv(csv_file)

    for gpt_word in gpt_words:
        gpt_word_cleaned = normalize_word(gpt_word)

        for index, row in df.iterrows():
            csv_word_cleaned = normalize_word(row["written"])

            if gpt_word_cleaned == csv_word_cleaned:
                timestamp_result["startTime_ns"].append(row["startTime_ns"])
                timestamp_result["endTime_ns"].append(row["endTime_ns"])
                df = df.drop(index)
                break

    gpt_output.update(timestamp_result)
    gpt_output["question"] = [question]
    return gpt_output


# loads question from transcribed speech saved in CSV
def combine_written_to_string(csv_file):
    """
    Combine all transcribed words into a single cleaned string.

    Args:
        csv_file: Path to CSV containing transcribed words

    Returns:
        Combined and cleaned transcription text
    """
    df = pd.read_csv(csv_file)
    words = []
    for _, row in df.iterrows():
        cleaned = normalize_word(row["written"])
        words.append(cleaned)
    return " ".join(words).strip()


def stream_audio(project_root: Path) -> None:
    csv_filepath = os.path.join(project_root, AudioStreamProcessorConfig.CSV_FILEPATH)
    csv_writer = CSVWriter(csv_filepath)

    model = WhisperModel(WHISPER_MODEL, device="auto", compute_type="int8")

    zmq_manager = ZMQManager()
    zmq_manager.setup_sockets()

    with AriaStreamClient() as audio_streamer:
        data_channels = [aria.StreamingDataType.Audio]
        message_size = 100
        observer = audio_streamer.subscribe(
            data_channels, AudioObserver(), message_size
        )

        quit_flag = False
        save_flag = False
        start_time = 0
        command = "WAIT"
        # Speak "START" to start the recording, speak "FINISH" to save the command and start LLM Inference
        while not quit_flag:
            data = [["startTime_ns", "endTime_ns", "written", "confidence"]]
            if observer.received:
                audios_16k, starttime_ns = observer.resample_audio()
                segments, _ = model.transcribe(
                    audios_16k,
                    language="en",
                    word_timestamps=True,
                    vad_filter=True,
                    beam_size=5,
                    condition_on_previous_text=False,
                )

                if segments is None:
                    print("No segments detected, continue listening...")
                    continue

                for segment in segments:
                    for word in segment.words:
                        normalized_word = re.sub(r"[^\w]", "", word.word.lower())
                        if normalized_word == "start":  # start detected
                            print("START DETECTED!\n")
                            start_time = word.start
                            save_flag = True
                            command = "START"
                        elif normalized_word == "finish" and save_flag:  # end detected
                            print("FINISH DETECTED!\n")
                            quit_flag = True
                            save_flag = False
                            command = "END"

                        # save spoken words
                        if save_flag:
                            if word.start >= start_time:
                                begin = int(
                                    word.start * NANOSECONDS_PER_SECOND + starttime_ns
                                )
                                end = int(
                                    word.end * NANOSECONDS_PER_SECOND + starttime_ns
                                )
                                print(f"[{begin}ns, -> {end}ns] {word.word}")
                                data.append([begin, end, word.word, word.probability])

            # Send command with a topic prefix "command" via ZMQ
            zmq_manager.send_command(command)

        # 5. Unsubscribe to clean up resources
        print("Stop listening to audio data")
        audio_streamer.streaming_client.unsubscribe()

        # 6. save data/word list
        print("Saving word list to CSV file...")
        del data[1]  # delete first row "start"
        csv_writer.write_rows(data)

        # 7. initialize GPT inference (LLama) via ZMQ
        # question = combine_written_to_string(csv_filepath)
        # response = zmq_manager.request_gpt_inference(question)

        # process tool call
        # tool_response = json.loads(response.get("tool"))
        # if tool_response is not None:
        #     print(f"Tool response received: <{tool_response}\n")
        #     tool_call = tool_response["function_name"][0]
        #     print(f"Tool call: {tool_call}")
        #     if tool_call == "grab_brick":
        #         pass
        #     else:
        #         # publish directly, grab_brick not called, no intention alignment needed
        #         zmq_manager.publish_tool_call(tool_response)
        #         sys.exit()
        # else:
        #     print("No tool response received from Avalon server, check if it is running")

        # # process intention alignment
        # intent_response = json.loads(response.get("intent"))
        # if intent_response is not None:
        #     print(f"Intent response received: {intent_response}\n")
        #     intent_json = find_timestamps(csv_filepath, question, intent_response)
        #     tool_response["arguments"] = [intent_json]
        #     zmq_manager.publish_tool_call(tool_response)
        #     print(f"tool_call {tool_response} published to ZMQ, ending GPT inference...")
        # else:
        #     print("No intent response received from Avalon server, check if it is running")

        # close ZMQ sockets
        zmq_manager.close_all()
