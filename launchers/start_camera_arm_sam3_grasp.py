"""
Starts the robot grasping pipeline. launchers/grasp_orchestrator.py runs it when the
start-grasp message arrives. By hand, after `source global_env.sh`:
    python3 launchers/start_camera_arm_sam3_grasp.py

Launches in order:
  1. ROS2 bringup (rm_driver, robot_state_publisher, move_group, rm_control)
  2. [TEMPORARY] Dummy mask publisher — replace with SAM node when ready
  3. AnyGrasp node — commented out for bring-up, see the note at its call site (T1.17)
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

from gappler_common import ROOT, camera_serial

# ---------------------------------------------------------------------------
# Paths, from the repo root that gappler_common finds (NEXT_STEPS 2.15)
# ---------------------------------------------------------------------------
REPO_ROOT = str(ROOT)
GRASP = os.path.join(REPO_ROOT, "grasp")

ANYGRASP_CONDA_ENV = "anygrasp"
ANYGRASP_DIR = os.path.join(GRASP, "anygrasp_node")
ANYGRASP_CHECKPOINT = "log/checkpoint_detection.tar"  # relative to ANYGRASP_DIR


ANYGRASP_NODE_PATH = os.path.join(
    ANYGRASP_DIR, "anygrasp_detection_node.py"
)
SAM3_PROJECT_ROOT = REPO_ROOT
SAM3_NODE_PATH = os.path.join(GRASP, "segmentation", "sam3_ros_node.py")
SAM3_WORK_DIR = os.path.join(REPO_ROOT, "aria/aria_app/services/object_recognition")
GRASP_VIZ_NODE_PATH = os.path.join(GRASP, "grasp_viz", "grasp_viz.py")
RVIZ_CONFIG_PATH = os.path.join(GRASP, "grasp_viz", "rviz_config.rviz")

# ---------------------------------------------------------------------------
# Process registry
# ---------------------------------------------------------------------------
processes = []


def launch(
    cmd: list, label: str, delay: float = 0.0, cwd: str = None, env: dict = None
) -> subprocess.Popen:
    if delay > 0:
        print(f"[main] Waiting {delay}s before launching {label}...")
        time.sleep(delay)
    print(f"[main] Launching: {label}")
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd, env=env)
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
            # The leading _ makes the launch file read the serial as text, not a number.
            f"serial_no:='_{camera_serial('wrist_camera')}'",
            "align_depth.enable:=true",
            "pointcloud.enable:=true",
        ],
        label="realsense_camera",
        delay=0.0,
    )

    # 1. ROS2 bringup — allow time for move_group to fully initialise
    launch(
        ["ros2", "launch", "arm_bringup", "arm_bringup.launch.py"],
        label="rm_bringup",
        delay=0.0,
    )

    # 2. Local SAM3 Node publisher
    launch(
        ["uv", "run", "--project", SAM3_PROJECT_ROOT, "python", SAM3_NODE_PATH],
        label="sam3_ros_node",
        delay=0.0,
        cwd=SAM3_WORK_DIR,
        env={
            **os.environ,
            "PYTHONPATH": os.path.join(REPO_ROOT, "aria/aria_app")
            + os.pathsep
            + os.environ.get("PYTHONPATH", ""),
        },
    )

    # 3. AnyGrasp node — OFF for bring-up (T1.17), commented out 2026-09-23.
    #
    # Nothing reads what it publishes while USE_SIMPLE_EXECUTE is true
    # (grasp_state_machine.cpp:41, CHANNEL_CONTRACT B-1): the state machine grasps from
    # /object_centroid_2d and ignores /grasp_candidates. Starting it anyway loads the model,
    # takes the GPU and adds a startup failure mode for output nobody uses.
    #
    # Put it back in T1.17, when the flag is flipped, together with the T1.8 gate fixes.
    # launch(
    #     [
    #         "conda",
    #         "run",
    #         "-n",
    #         ANYGRASP_CONDA_ENV,
    #         "python",
    #         ANYGRASP_NODE_PATH,
    #         "--checkpoint_path",
    #         ANYGRASP_CHECKPOINT,
    #     ],
    #     label="anygrasp_detection_node",
    #     delay=2.0,
    #     cwd=ANYGRASP_DIR,
    # )

    # 4. Grasp visualizer — runs in normal ROS2 env
    launch(["python3", GRASP_VIZ_NODE_PATH], label="grasp_viz", delay=2.0)

    # 4b. Manipulation RViz — owned by main.py so it survives grasp_viz crashes
    #     and closes cleanly when grasping is done (main.py shutdown kills it).
    launch(["rviz2", "-d", RVIZ_CONFIG_PATH], label="manipulation_rviz", delay=3.0)

    # 5. Grasp state machine — launched last, after all sources are ready
    launch(
        ["ros2", "launch", "grasp_state_machine", "grasp_state_machine.launch.py"],
        label="grasp_state_machine",
        delay=5.0,
    )

    print("[main] All processes launched. Press Ctrl+C to shut down.")

    # Monitor for unexpected exits (warn once per process)
    warned = set()
    while True:
        for label, p in processes:
            if p.poll() is not None and label not in warned:
                print(f"[main] WARNING: '{label}' exited with code {p.returncode}")
                warned.add(label)
        time.sleep(2.0)
