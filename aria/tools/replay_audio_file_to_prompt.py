#!/usr/bin/env python3
"""Feed a recorded WAV file into the glasses voice pipeline, for testing without the glasses (T2.8).

Everything after the microphone runs as it does live: audio_worker transcribes with Whisper, the
LLM picks the object word, and the word goes out on /aria/audio/prompt. Only the audio source
changes. Like AudioObserver, it hands over the last max_buffer_s seconds once every
iteration_interval_s. The file is followed by max_buffer_s of silence, so the last words roll
out of the window as they would live.

Whisper and the LLM load once, about a minute on the box. After each file the script asks for the
next one, so later replays start at once (T2.16): Enter plays the same file again, a short name
plays assets/recordings/voice_commands/<name>_command.wav (release, pick_up_box), a path plays
that file, q quits.

Record on the Mac (QuickTime, File, New Audio Recording), then convert:
    afconvert -f WAVE -d LEI16@48000 -c 1 voice.m4a voice.wav
On the lab box:
    source aria/aria_env.sh
    python aria/tools/replay_audio_file_to_prompt.py voice.wav    # or: ... pick_up_box
"""

import argparse
import multiprocessing
import os
import time

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

VOICE_COMMANDS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                              "assets", "recordings", "voice_commands")


def read_wav(path: str, rate: int) -> np.ndarray:
    """16-bit WAV as (channels, samples) int32 at `rate`, the shape AudioObserver.snapshot() gives."""
    # scipy, not the wave module: afconvert writes the extensible header wave cannot read
    file_rate, audio = wavfile.read(path)
    if audio.dtype != np.int16:
        raise ValueError(f"{path}: 16-bit WAV only (afconvert -d LEI16@48000)")
    audio = audio.reshape(len(audio), -1).T
    if file_rate != rate:
        audio = resample_poly(audio, rate, file_rate, axis=1)
    return audio.astype(np.int32)


def windows(n_samples: int, rate: int, step_s: float, window_s: float):
    """(start, end) of the trailing window at each step, as the live buffer would hold it."""
    step, window = int(rate * step_s), int(rate * window_s)
    for end in range(step, n_samples + step, step):
        end = min(end, n_samples)
        yield max(0, end - window), end


def next_wav(answer: str, last: str, commands_dir: str = VOICE_COMMANDS):
    """The WAV to play for what was typed at the prompt, or None if there is no such file."""
    answer = answer.strip()
    if not answer:
        return last
    if os.path.isfile(answer):
        return answer
    named = os.path.join(commands_dir, f"{answer}_command.wav")
    return named if os.path.isfile(named) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("wav", help="a WAV path, or a name such as release or pick_up_box")
    args = parser.parse_args()
    wav = next_wav(args.wav, None)
    if wav is None:
        raise SystemExit(f"No such file or {args.wav}_command.wav in {VOICE_COMMANDS}")

    # Imported here so the helpers above load without the glasses SDK (tests, the Mac)
    from config import AriaConfig, AudioStreamingPipelineConfig as cfg
    from services.aria_device.stream.audio_streaming_pipeline import _put_latest, audio_worker

    rate = AriaConfig.AUDIO_SAMPLE_RATE
    read_wav(wav, rate)   # a bad file fails now, not after the minute of loading

    # spawn, as aria_app/main.py does: a forked worker cannot use CUDA once this process has
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue(maxsize=1)
    quit_event = ctx.Event()
    worker = ctx.Process(target=audio_worker, args=(queue, quit_event), daemon=True)
    worker.start()
    try:
        # The worker skips an empty chunk, so once it takes one Whisper and the LLM are loaded.
        # put() lands in the background: wait for the chunk to show, then for it to go.
        print("Loading Whisper and the LLM...")
        queue.put(np.zeros((1, 0), np.int32))
        for want_empty in (False, True):
            while queue.empty() != want_empty:
                if not worker.is_alive():
                    raise SystemExit("The audio worker stopped, see the error above")
                time.sleep(0.2)
        while True:
            audio = read_wav(wav, rate)
            audio = np.pad(audio, ((0, 0), (0, rate * cfg.MAX_BUFFER_SECONDS)))
            print(f"Playing {wav}, {audio.shape[1] / rate:.0f} s including the trailing silence")
            for start, end in windows(audio.shape[1], rate, cfg.ITERATION_INTERVAL_SECONDS,
                                      cfg.MAX_BUFFER_SECONDS):
                if not worker.is_alive():
                    raise SystemExit("The audio worker stopped, see the error above")
                _put_latest(queue, audio[:, start:end])
                time.sleep(cfg.ITERATION_INTERVAL_SECONDS)
            answer = input("Next: Enter = same file, a name (release, pick_up_box), a path, q = quit: ")
            while answer.strip() != "q" and next_wav(answer, wav) is None:
                answer = input(f"No such file or {answer.strip()}_command.wav. Try again: ")
            if answer.strip() == "q":
                break
            wav = next_wav(answer, wav)
    except (KeyboardInterrupt, EOFError):   # Ctrl-C, Ctrl-D
        pass
    finally:
        quit_event.set()
        queue.cancel_join_thread()   # else exit waits on a chunk nobody will read
        worker.join(timeout=10)


if __name__ == "__main__":
    main()
