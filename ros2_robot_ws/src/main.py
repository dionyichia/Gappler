"""
Main orchestrator for the robot grasping pipeline.
Run from ros2_robot_ws/ with:
    python main.py

Launches in order:
  1. ROS2 bringup (rm_driver, robot_state_publisher, move_group, rm_control)
  2. [TEMPORARY] Dummy mask publisher — replace with SAM node when ready
  3. AnyGrasp node (conda env)
  4. Grasp visualizer
  5. Grasp state machine

Note: When the full perception pipeline is ready, items 2 and 3 will be
removed from here and launched separately as part of that pipeline.
"""

import os
import signal
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Placeholders — fill in before running
# ---------------------------------------------------------------------------
ANYGRASP_CONDA_ENV = "anygrasp"
ANYGRASP_DIR = "/home/iot22/GitHub/Renaissance-Capstone-Project/ros2_robot_ws/src/rm_mtc/src/perception"
ANYGRASP_CHECKPOINT = "log/checkpoint_tracking.tar"


ANYGRASP_NODE_PATH = os.path.join(
    os.path.dirname(__file__), "rm_mtc/src/perception/anygrasp_node.py"
)
DUMMY_MASK_NODE_PATH = os.path.join(
    os.path.dirname(__file__), "rm_mtc/src/perception/dummy_mask_publisher.py"
)
GRASP_VIZ_NODE_PATH = os.path.join(
    os.path.dirname(__file__), "rm_mtc/src/perception/grasp_viz.py"
)

# ---------------------------------------------------------------------------
# Process registry
# ---------------------------------------------------------------------------
processes = []


def launch(
    cmd: list, label: str, delay: float = 0.0, cwd: str = None
) -> subprocess.Popen:
    if delay > 0:
        print(f"[main] Waiting {delay}s before launching {label}...")
        time.sleep(delay)
    print(f"[main] Launching: {label}")
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd)
    processes.append((label, p))
    return p


def shutdown(signum=None, frame=None):
    print("\n[main] Shutting down all processes...")
    for label, p in reversed(processes):
        print(f"[main] Terminating: {label}")
        p.terminate()
    for label, p in reversed(processes):
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[main] Force killing: {label}")
            p.kill()
    print("[main] All processes stopped.")
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


# ---------------------------------------------------------------------------
# Launch sequence
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 0. RealSense camera driver
    launch(
        [
            "ros2",
            "launch",
            "realsense2_camera",
            "rs_launch.py",
            "align_depth.enable:=true",
            "pointcloud.enable:=true",
        ],
        label="realsense_camera",
        delay=0.0,
    )

    # 1. ROS2 bringup — allow time for move_group to fully initialise
    launch(
        ["ros2", "launch", "rm_mtc", "background.launch.py"],
        label="rm_bringup",
        delay=0.0,
    )

    # 2. [TEMPORARY] Dummy mask publisher — replace with SAM node when ready
    launch(
        ["python3", DUMMY_MASK_NODE_PATH],
        label="dummy_mask_publisher [TEMPORARY]",
        delay=0.0,  # Edit delay back to 10s later on
    )

    # 3. AnyGrasp node — runs in conda env
    # PLACEHOLDER: replace ANYGRASP_CONDA_ENV and ANYGRASP_CHECKPOINT
    launch(
        [
            "conda",
            "run",
            "-n",
            ANYGRASP_CONDA_ENV,
            "python",
            ANYGRASP_NODE_PATH,
            "--checkpoint_path",
            ANYGRASP_CHECKPOINT,
        ],
        label="anygrasp_node",
        delay=2.0,
        cwd=ANYGRASP_DIR,
    )

    # 4. Grasp visualizer — runs in normal ROS2 env
    launch(["python3", GRASP_VIZ_NODE_PATH], label="grasp_viz", delay=2.0)

    # 5. Grasp state machine — launched last, after all sources are ready
    launch(
        ["ros2", "launch", "rm_mtc", "grasp_state_machine.launch.py"],
        label="grasp_state_machine",
        delay=5.0,
    )

    print("[main] All processes launched. Press Ctrl+C to shut down.")

    # Monitor for unexpected exits
    while True:
        for label, p in processes:
            if p.poll() is not None:
                print(f"[main] WARNING: '{label}' exited with code {p.returncode}")
        time.sleep(2.0)
