#!/usr/bin/env python3
"""One-topic rclpy receive-cost probe: rate, total CPU, callback CPU.

Diagnostic for preview load (2026-10-18): it showed that rclpy's conversion of
one 20k-point livox_ros_driver2 CustomMsg costs ~127 ms, so a normal Python
subscription to /livox/lidar saturates a core at 10 Hz (4.4 Hz intake, 99% CPU)
and starves every other topic in the same node; images (30 Hz, 15%) and IMU
(200 Hz, 16%) are cheap. live_preview.py therefore subscribes the scan raw and
deserializes once per render.

Run on the lab box with the nav overlay sourced, while a publisher (driver or
bag play) is live on the same ROS domain:

    python3 probe_topic.py /livox/lidar lidar 12
    python3 probe_topic.py /camera/camera/color/image_raw image 12
    python3 probe_topic.py /livox/imu imu 12

It subscribes best-effort with the sensor-data QoS, prints one line per run
and exits 0. It publishes nothing and writes nothing.
"""
from __future__ import annotations

import sys
import time

import rclpy
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message

TYPES = {
    "lidar": "livox_ros_driver2/msg/CustomMsg",
    "image": "sensor_msgs/msg/Image",
    "imu": "sensor_msgs/msg/Imu",
    "info": "sensor_msgs/msg/CameraInfo",
}


def main() -> int:
    if len(sys.argv) != 4 or sys.argv[2] not in TYPES:
        print(f"usage: {sys.argv[0]} <topic> <{'|'.join(TYPES)}> <seconds>")
        return 2
    topic, kind, duration = sys.argv[1], sys.argv[2], float(sys.argv[3])
    msg_type = get_message(TYPES[kind])
    rclpy.init()
    node = rclpy.create_node(f"probe_{kind}")
    samples = []
    count = 0

    def cb(msg) -> None:
        nonlocal count
        started = time.process_time()
        count += 1
        samples.append(time.process_time() - started)

    node.create_subscription(msg_type, topic, cb, qos_profile_sensor_data)
    cpu0, t0 = time.process_time(), time.monotonic()
    while time.monotonic() - t0 < duration:
        rclpy.spin_once(node, timeout_sec=0.05)
    elapsed = time.monotonic() - t0
    cpu = time.process_time() - cpu0
    median_ms = sorted(samples)[len(samples) // 2] * 1000 if samples else 0.0
    print(f"{kind:5s} received={count:6d} rate={count / elapsed:8.2f} Hz  "
          f"process_cpu={cpu / elapsed * 100:5.0f}%  callback_median={median_ms:6.2f} ms")
    node.destroy_node()
    rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
