#!/usr/bin/env python3
"""Characterise point-order monotonicity of t35b_proof3 scans (read-only).

The pinned fork's IMU deskew path (UndistortPcl) assumes points arrive sorted by
time (its sort is commented out; IMU_Processing.cpp:289). Recorded scans are
flagged unsorted (740/740 in the strict audit), so this quantifies the
inversions: any-decrease steps, the largest backward step, and the largest
excursion below the running maximum (a bound on deskew interval misassignment).
"""
import sqlite3
from pathlib import Path

BAG = (
    Path.home()
    / "rcp-Gappler/log/t59-fastlivo/log/t35b-capture.R0fVks/t35b_proof3/t35b_proof3_0.db3"
)

from rclpy.serialization import deserialize_message  # noqa: E402
from livox_ros_driver2.msg import CustomMsg  # noqa: E402

con = sqlite3.connect(f"file:{BAG}?mode=ro", uri=True)
tid = con.execute("SELECT id FROM topics WHERE name='/livox/lidar'").fetchone()[0]
rows = con.execute(
    "SELECT data FROM messages WHERE topic_id=? ORDER BY timestamp LIMIT 20", (tid,)
).fetchall()

total = 0
decreases = 0
scans_with_decreases = 0
max_decrease_us = 0.0
max_excursion_us = 0.0
for (data,) in rows:
    msg = deserialize_message(bytes(data), CustomMsg)
    prev = None
    run_max = None
    scan_decreases = 0
    for p in msg.points:
        curv_ms = p.offset_time / 1e6  # ms
        total += 1
        if prev is None:
            run_max = curv_ms
        else:
            if curv_ms < prev:
                decreases += 1
                scan_decreases += 1
                decrease_us = (prev - curv_ms) * 1000.0
                max_decrease_us = max(max_decrease_us, decrease_us)
            run_max = max(run_max, curv_ms)
            excursion_us = (run_max - curv_ms) * 1000.0
            max_excursion_us = max(max_excursion_us, excursion_us)
        prev = curv_ms
    if scan_decreases:
        scans_with_decreases += 1

print(
    f"ORDER scans=20 total_points={total} decrease_steps={decreases} "
    f"scans_with_decreases={scans_with_decreases}"
)
print(
    f"ORDER max_decrease_us={max_decrease_us:.3f} "
    f"max_excursion_below_running_max_us={max_excursion_us:.3f}"
)
