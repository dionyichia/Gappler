#!/usr/bin/env python3
"""Play a glasses recording (.vrs) into the live glasses topics, for testing without the glasses (T2.9).

Everything after the glasses runs as it does live: the recording's RGB and eye camera frames go
to the app's own rgb_worker and et_worker (image_streaming_pipeline.py), which publish the
undistorted image and the gaze. Only the frame source changes, as replay_audio_file_to_prompt.py
does for the microphone. Frames go out at the speed they were recorded.

On the lab box, on a private ROS channel (CLAUDE.md), with the segmentation service and the aria
segmentation client running, then say a word with replay_audio_file_to_prompt.py or
`ros2 topic pub --once /aria/audio/prompt std_msgs/String "data: box"`:
    source aria/aria_env.sh
    python aria/tools/replay_recording_to_glasses_topics.py <id>.vrs --from-s 14 --to-s 29
"""

import argparse
import multiprocessing
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("vrs")
    parser.add_argument("--from-s", type=float, default=0.0, help="start this far into the recording")
    parser.add_argument("--to-s", type=float, default=float("inf"), help="stop this far into it")
    args = parser.parse_args()

    # Imported here so --help works without the glasses SDK
    from projectaria_tools.core.data_provider import create_vrs_data_provider
    from projectaria_tools.core.sensor_data import TimeDomain
    from projectaria_tools.core.stream_id import StreamId

    from config import AriaConfig
    from services.aria_device.stream.image_streaming_pipeline import _put_latest, et_worker, rgb_worker

    provider = create_vrs_data_provider(args.vrs)
    rgb, eye = StreamId(AriaConfig.RGB_STREAM_ID), StreamId(AriaConfig.EYE_STREAM_ID)
    calib_json = provider.get_file_tags()["calib_json"]   # what the live stream hands the workers

    # spawn, as aria_app/main.py does: a forked worker cannot use CUDA once this process has
    ctx = multiprocessing.get_context("spawn")
    quit_event = ctx.Event()
    rgb_queue, eye_queue = ctx.Queue(maxsize=1), ctx.Queue(maxsize=1)
    workers = [ctx.Process(target=fn, args=(q, quit_event, calib_json), daemon=True)
               for fn, q in ((rgb_worker, rgb_queue), (et_worker, eye_queue))]
    for w in workers:
        w.start()

    options = provider.get_default_deliver_queued_options()
    options.deactivate_stream_all()
    for s in (rgb, eye):
        options.activate_stream(s)
    try:
        print("Waiting for the workers: the eye model and rgb_worker's undistortion maps...")
        # ponytail: fixed wait. rgb_worker's maps took about 20 s on the box. Frames before the
        # workers are up are dropped. Wait on their first published message if this ever fails
        time.sleep(30)
        t0 = start = None
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
            queue = rgb_queue if data.stream_id() == rgb else eye_queue
            _put_latest(queue, data.image_data_and_record()[0].to_numpy_array())
        print(f"Done at {t - t0:.0f} s" if t0 is not None else "No frames")
    except KeyboardInterrupt:   # Ctrl-C
        pass
    finally:
        quit_event.set()
        for q in (rgb_queue, eye_queue):
            q.cancel_join_thread()
        for w in workers:
            w.join(timeout=10)


if __name__ == "__main__":
    main()
