#!/usr/bin/env python3
"""Play a glasses recording (.vrs) into the live glasses topics, for testing without the glasses (T2.9).

Everything after the glasses runs as it does live: the recording's RGB and eye camera frames go
to the app's own rgb_worker and et_worker (image_streaming_pipeline.py), which publish the
undistorted image and the gaze. Only the frame source changes, as replay_audio_file_to_prompt.py
does for the microphone. Frames go out at the speed they were recorded.

With --audio, the recording's microphone goes through the app's own AudioObserver into
audio_worker (Whisper, the LLM), which publishes the spoken word stamped with the recording's
capture time, on the same clock as the images and gaze (T2.21). --audio-wav plays a WAV in place
of the recorded sound, sample N of the file at the time of the recording's sample N. Make one with
the recording's length, for example silence with a command placed where you look at the object.

On the lab box, on a private ROS channel (CLAUDE.md), with the segmentation service and the aria
segmentation client running:
    source aria/aria_env.sh
    python aria/tools/replay_recording_to_glasses_topics.py <id>.vrs --from-s 14 --to-s 29 --audio
"""

import argparse
import multiprocessing
import tempfile
import time
from types import SimpleNamespace

import numpy as np

from replay_audio_file_to_prompt import read_wav


def swap_sound(stamps, wav: np.ndarray, first_ns: int, sample_ns: float, channels: int):
    """The interleaved audio data for samples taken at `stamps`, from the WAV in place of the
    recording: the sample at time t is the WAV's sample round((t - first_ns) / sample_ns), or
    silence past its end. Every channel gets the same sound."""
    i = np.rint((np.asarray(stamps, dtype=np.int64) - first_ns) / sample_ns).astype(np.int64)
    inside = (i >= 0) & (i < len(wav))
    mono = np.where(inside, wav[np.clip(i, 0, len(wav) - 1)], 0)
    return np.repeat(mono, channels)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("vrs")
    parser.add_argument("--from-s", type=float, default=0.0, help="start this far into the recording")
    parser.add_argument("--to-s", type=float, default=float("inf"), help="stop this far into it")
    parser.add_argument("--audio", action="store_true",
                        help="also play the microphone into the voice pipeline (T2.21)")
    parser.add_argument("--audio-wav", help="play this WAV in place of the recorded sound "
                        "(implies --audio)")
    args = parser.parse_args()
    args.audio = args.audio or args.audio_wav is not None

    # Imported here so --help works without the glasses SDK
    from projectaria_tools.core.data_provider import create_vrs_data_provider
    from projectaria_tools.core.sensor_data import TimeDomain
    from projectaria_tools.core.stream_id import StreamId

    from config import AriaConfig
    from config import AudioStreamingPipelineConfig as audio_cfg
    from services.aria_device.stream.audio_streaming_client_observer import SAMPLE_NS, AudioObserver
    from services.aria_device.stream.audio_streaming_pipeline import audio_worker
    from services.aria_device.stream.image_streaming_pipeline import _put_latest, et_worker, rgb_worker

    provider = create_vrs_data_provider(args.vrs)
    rgb, eye = StreamId(AriaConfig.RGB_STREAM_ID), StreamId(AriaConfig.EYE_STREAM_ID)
    mic = provider.get_stream_id_from_label("mic")
    calib_json = provider.get_file_tags()["calib_json"]   # what the live stream hands the workers
    if args.audio:
        mic_first_ns = provider.get_audio_data_by_index(mic, 0)[1].capture_timestamps_ns[0]
        wav = (read_wav(args.audio_wav, AriaConfig.AUDIO_SAMPLE_RATE).mean(axis=0).astype(np.int32)
               if args.audio_wav else None)
        # no WAV chunks saved, as the live observer does every 10 s
        observer = AudioObserver(save_dir=tempfile.mkdtemp(), save_interval=10**9)

    # spawn, as aria_app/main.py does: a forked worker cannot use CUDA once this process has
    ctx = multiprocessing.get_context("spawn")
    quit_event = ctx.Event()
    rgb_queue, eye_queue = ctx.Queue(maxsize=1), ctx.Queue(maxsize=1)
    workers = [ctx.Process(target=fn, args=(q, quit_event, calib_json), daemon=True)
               for fn, q in ((rgb_worker, rgb_queue), (et_worker, eye_queue))]
    if args.audio:
        audio_queue = ctx.Queue(maxsize=1)
        workers.append(ctx.Process(target=audio_worker, args=(audio_queue, quit_event), daemon=True))
    for w in workers:
        w.start()

    options = provider.get_default_deliver_queued_options()
    options.deactivate_stream_all()
    for s in (rgb, eye) + ((mic,) if args.audio else ()):
        options.activate_stream(s)
    try:
        # Each worker reads its queue only once set up (eye model, undistortion maps: 20 s or more
        # on the box), so hand each one frame and wait until both are taken. full(), not empty():
        # put() returns before its feeder thread writes the frame to the pipe, so empty() is True
        # at once. full() stays True until the worker's get() (only this process puts here).
        # The audio worker skips empty audio, so once it takes one chunk Whisper and the LLM are
        # loaded.
        print("Waiting for the workers: the eye model and rgb_worker's undistortion maps"
              + (", Whisper and the LLM..." if args.audio else "..."))
        waited = time.monotonic()
        for q, s in ((rgb_queue, rgb), (eye_queue, eye)):
            image, record = provider.get_image_data_by_index(s, 0)
            q.put((image.to_numpy_array(), record.capture_timestamp_ns))
        starting = [rgb_queue, eye_queue]
        if args.audio:
            audio_queue.put((np.zeros((1, 0), np.int32), 0))
            starting.append(audio_queue)
        while any(q.full() for q in starting):
            if not all(w.is_alive() for w in workers):
                raise SystemExit("A worker stopped while starting")
            time.sleep(0.5)
        print(f"The workers took their first input after {time.monotonic() - waited:.0f} s")
        t0 = start = None
        audio_sent = -np.inf   # playback time the audio was last handed over
        for data in provider.deliver_queued_sensor_data(options):
            t = data.get_time_ns(TimeDomain.DEVICE_TIME) / 1e9
            t0 = t if t0 is None else t0
            if t - t0 < args.from_s:
                continue
            if t - t0 > args.to_s or not all(w.is_alive() for w in workers):
                break
            if start is None:
                start = time.monotonic() - (t - t0)
                print(f"Playing from {args.from_s:g} s")
            time.sleep(max(0.0, (t - t0) - (time.monotonic() - start)))
            if data.stream_id() == mic:
                audio, record = data.audio_data_and_record()
                if wav is not None:
                    audio = SimpleNamespace(data=swap_sound(
                        record.capture_timestamps_ns, wav, mic_first_ns, SAMPLE_NS,
                        AriaConfig.NUM_AUDIO_CHANNELS))
                observer.on_audio_received(audio, record)
                # as AudioStreamingPipeline.run does: the buffer, every iteration_interval_s
                if t - audio_sent >= audio_cfg.ITERATION_INTERVAL_SECONDS:
                    _put_latest(audio_queue, observer.snapshot())
                    audio_sent = t
                continue
            queue = rgb_queue if data.stream_id() == rgb else eye_queue
            image, record = data.image_data_and_record()
            # The recorded glasses capture time, as the live stream sends it (T2.19)
            _put_latest(queue, (image.to_numpy_array(), record.capture_timestamp_ns))
        print(f"Done at {t - t0:.0f} s" if t0 is not None else "No frames")
    except KeyboardInterrupt:   # Ctrl-C
        pass
    finally:
        quit_event.set()
        for q in (rgb_queue, eye_queue) + ((audio_queue,) if args.audio else ()):
            q.cancel_join_thread()
        for w in workers:
            w.join(timeout=10)


if __name__ == "__main__":
    main()
