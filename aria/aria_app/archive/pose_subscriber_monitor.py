#!/usr/bin/env python3
"""
OpenVINS Rate Monitor
Tracks the actual received rate of IMU and camera topics feeding into OpenVINS.
Prints a live table every second showing published vs received rates.
"""

import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image, Imu

RESET = "\033[0m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
BOLD = "\033[1m"
CLEAR = "\033[2J\033[H"


class TopicStats:
    def __init__(self, name: str):
        self.name = name
        self.count = 0
        self.total = 0
        self.last_stamp = None
        self.last_wall = None
        self.stamp_gaps = []
        self.wall_gaps = []

    def record_both(self, wall: float, stamp: float):
        self.count += 1
        self.total += 1

        if self.last_wall is not None:
            self.wall_gaps.append(wall - self.last_wall)
            self.stamp_gaps.append(stamp - self.last_stamp)
            if len(self.wall_gaps) > 1000:
                self.wall_gaps.pop(0)
                self.stamp_gaps.pop(0)

        self.last_wall = wall
        self.last_stamp = stamp

    def flush(self) -> dict:
        count = self.count
        self.count = 0

        if not self.wall_gaps:
            return {
                "name": self.name,
                "wall_rate": 0,
                "stamp_rate": 0,
                "min_gap_ms": 0,
                "max_gap_ms": 0,
                "total": self.total,
                "count_this_sec": count,
            }

        recent_wall = self.wall_gaps[-min(len(self.wall_gaps), 100) :]
        recent_stamp = self.stamp_gaps[-min(len(self.stamp_gaps), 100) :]

        avg_wall_gap = sum(recent_wall) / len(recent_wall)
        avg_stamp_gap = sum(recent_stamp) / len(recent_stamp)

        wall_rate = 1.0 / avg_wall_gap if avg_wall_gap > 0 else 0
        stamp_rate = 1.0 / avg_stamp_gap if avg_stamp_gap > 0 else 0

        return {
            "name": self.name,
            "wall_rate": wall_rate,
            "stamp_rate": stamp_rate,
            "min_gap_ms": min(recent_wall) * 1000,
            "max_gap_ms": max(recent_wall) * 1000,
            "total": self.total,
            "count_this_sec": count,
        }


class RateMonitor(Node):
    def __init__(self):
        super().__init__("openvins_rate_monitor")

        self._stats = {
            "imu": TopicStats("/aria/imu"),
            "slam_left": TopicStats("/aria/slam_left/raw"),
            "slam_right": TopicStats("/aria/slam_right/raw"),
        }

        self.create_subscription(
            Imu, "/aria/imu", self._imu_cb, qos_profile_sensor_data
        )
        self.create_subscription(
            Image, "/aria/slam_left/raw", self._left_cb, qos_profile_sensor_data
        )
        self.create_subscription(
            Image, "/aria/slam_right/raw", self._right_cb, qos_profile_sensor_data
        )

        self._start = time.time()
        self.create_timer(1.0, self._print_stats)

    def _imu_cb(self, msg: Imu):
        wall = time.time()
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self._stats["imu"].record_both(wall, stamp)

    def _left_cb(self, msg: Image):
        wall = time.time()
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self._stats["slam_left"].record_both(wall, stamp)

    def _right_cb(self, msg: Image):
        wall = time.time()
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self._stats["slam_right"].record_both(wall, stamp)

    def _print_stats(self):
        uptime = time.time() - self._start
        results = {k: v.flush() for k, v in self._stats.items()}

        print(CLEAR, end="")
        print(
            f"{BOLD}=== OpenVINS Topic Rate Monitor (uptime: {uptime:.0f}s) ==={RESET}\n"
        )

        header = (
            f"{'Topic':<30} {'Wall Hz':>10} {'Stamp Hz':>10}"
            f" {'Min gap':>10} {'Max gap':>10} {'Total':>8} {'Last sec':>10}"
        )
        print(BOLD + header + RESET)
        print("-" * len(header))

        for key, r in results.items():
            wall_rate = r.get("wall_rate", 0)
            stamp_rate = r.get("stamp_rate", 0)
            min_gap = r.get("min_gap_ms", 0)
            max_gap = r.get("max_gap_ms", 0)
            total = r.get("total", 0)
            last_sec = r.get("count_this_sec", 0)

            if wall_rate < 10:
                color = RED
            elif wall_rate < 100 and key == "imu":
                color = YELLOW
            else:
                color = GREEN

            print(
                f"{color}{r['name']:<30}{RESET}"
                f" {wall_rate:>10.1f}"
                f" {stamp_rate:>10.1f}"
                f" {min_gap:>9.2f}ms"
                f" {max_gap:>9.2f}ms"
                f" {total:>8}"
                f" {last_sec:>10}"
            )

        print()
        print(
            f"{BOLD}Wall Hz{RESET}  = messages received per second (what OpenVINS actually gets)"
        )
        print(
            f"{BOLD}Stamp Hz{RESET} = rate implied by message timestamps (what the sensor produces)"
        )
        print(
            f"{BOLD}Gap{RESET}      = wall time between consecutive received messages"
        )
        print()
        print("If Wall Hz << Stamp Hz → DDS is dropping or batching messages")
        print("If Stamp Hz is unexpected → timestamp issue in publisher")


def main():
    rclpy.init()
    node = RateMonitor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
