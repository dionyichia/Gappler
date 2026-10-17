#!/usr/bin/env python3
"""Quantify the avia_handler curvature clamp on unsorted t35b_proof3 scans.

Simulates preprocess.cpp:180-190 exactly on the first 20 scans, in recorded
message order, with the clamp chain using the already-rewritten previous point
(as the C++ does). Read-only.
"""
import sqlite3
from pathlib import Path

BAG = (
    Path.home()
    / "rcp-Gappler/log/t59-fastlivo/log/t35b-capture.R0fVks/t35b_proof3/t35b_proof3_0.db3"
)

from rclpy.serialization import deserialize_message  # noqa: E402
from livox_ros_driver2.msg import CustomMsg  # noqa: E402

CLAMP_STEP_MS = 0.004166667  # float(100/24000), milliseconds

con = sqlite3.connect(f"file:{BAG}?mode=ro", uri=True)
tid = con.execute("SELECT id FROM topics WHERE name='/livox/lidar'").fetchone()[0]
rows = con.execute(
    "SELECT data FROM messages WHERE topic_id=? ORDER BY timestamp LIMIT 20", (tid,)
).fetchall()

total = 0
clamped = 0
first_rewrites = 0
backward = 0
for (data,) in rows:
    msg = deserialize_message(bytes(data), CustomMsg)
    prev = None
    for i, p in enumerate(msg.points):
        total += 1
        curv = p.offset_time / 1e6
        if i == 0:
            if abs(curv) >= 1.0:
                curv = 0.0
                first_rewrites += 1
        else:
            if abs(curv - prev) >= 1.0:
                curv = prev + CLAMP_STEP_MS
                clamped += 1
            if p.offset_time * 1e-6 < (prev if prev is not None else 0.0) - 1.0:
                backward += 1
        prev = curv

print(f"CLAMP scans=20 total_points={total} rewritten={clamped} first_point_rewrites={first_rewrites}")
print(f"CLAMP rewritten_fraction={clamped / total:.6f}")
print(f"CLAMP backward_jumps_over_1ms={backward}")
