"""Recorded wrist-camera frames through SAM 3 and AnyGrasp (PROJECT_PLAN T0.12).

Run by bench/anygrasp_replay.sh, which has already proven the ROS channel is private and
empty. Plays the bag on a loop, starts sam3_ros_node (.venv) and anygrasp_detection_node
(grasp/anygrasp_venv/.venv) as launchers/start_grasp_pipeline.py does, then publishes
/pipeline_state the way grasp_state_machine does: EXECUTING for a while, then IDLE.

  control  segmentation      SAM 3 publishes a mask on the recorded frames
  control  grasp detection   AnyGrasp publishes candidates in either state
  xfail    gate (A1)         candidates during EXECUTING and none during IDLE

The numbers printed (mask size, candidates per second, top score) are the baseline to
compare a perception change against. Exit 0 = no FAIL, 1 = a FAIL.
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import rclpy
    from grasp_interfaces.msg import GraspCandidateArray
    from sensor_msgs.msg import Image
    from std_msgs.msg import String
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble and install/setup.bash first")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / os.environ.get("BENCH_REPLAY_LOG", "log/bench_anygrasp_replay.txt")
BAG = os.environ.get("WRIST_CAMERA_BAG", str(REPO / "assets/recordings/wrist_camera"))
ANYGRASP_DIR = REPO / "grasp/anygrasp_node"
SAM3_WORK_DIR = REPO / "aria/aria_app/services/object_recognition"
PHASE_SEC = 30.0   # each /pipeline_state phase
LOAD_SEC = 180.0   # both models loading on one GPU


def main():
    rclpy.init()
    node = rclpy.create_node("bench_anygrasp_replay")
    masks, grasps = [], []   # (time, msg)
    node.create_subscription(Image, "/camera/sam/mask", lambda m: masks.append((time.time(), m)), 10)
    node.create_subscription(GraspCandidateArray, "/grasp_candidates",
                             lambda m: grasps.append((time.time(), m)), 10)
    state_pub = node.create_publisher(String, "/pipeline_state", 10)

    def spin(sec, until=None):
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(node, timeout_sec=0.05)
            if until and until():
                return True
        return bool(until and until())

    def hold(state, sec):
        """Publish state at 2 Hz for sec, like the state machine's repeated updates."""
        end = time.time() + sec
        while time.time() < end:
            state_pub.publish(String(data=state))
            spin(0.5)

    LOG.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG, "w")
    procs = []

    def start(cmd, cwd=None, env=None):
        log.write(f"\n===== {' '.join(map(str, cmd))} =====\n")
        log.flush()
        p = subprocess.Popen(list(map(str, cmd)), cwd=cwd, env=env, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)
        procs.append(p)
        return p

    results = []   # (tag, name, detail)
    try:
        sam_env = dict(os.environ, PYTHONPATH=f"{REPO / 'aria/aria_app'}{os.pathsep}{os.environ.get('PYTHONPATH', '')}")
        sam = start([REPO / ".venv/bin/python", REPO / "grasp/segmentation/sam3_ros_node.py"],
                    cwd=SAM3_WORK_DIR, env=sam_env)
        ag = start([REPO / "grasp/anygrasp_venv/.venv/bin/python", "anygrasp_detection_node.py",
                    "--checkpoint_path", "log/checkpoint_detection.tar"], cwd=ANYGRASP_DIR)
        # AnyGrasp creates its publisher only after the model has loaded
        ready = spin(LOAD_SEC, lambda: node.count_publishers("/grasp_candidates") > 0
                     and node.count_publishers("/camera/sam/mask") > 0
                     or sam.poll() is not None or ag.poll() is not None)
        if not ready or sam.poll() is not None or ag.poll() is not None:
            raise RuntimeError(f"models not loaded in {LOAD_SEC:.0f} s (sam exit {sam.poll()}, "
                               f"anygrasp exit {ag.poll()}) -- see {LOG.name}")
        start(["ros2", "bag", "play", "--loop", BAG])

        t0 = time.time()
        hold("EXECUTING", PHASE_SEC)
        t1 = time.time()
        hold("IDLE", PHASE_SEC)
        t2 = time.time()

        area = [sum(m.data) / len(m.data) for _, m in masks] if masks else []
        seg_ok = bool(masks)
        results.append(("PASS " if seg_ok else "FAIL ", "segmentation",
                        f"{len(masks)} masks in {t2 - t0:.0f} s, mean area {100 * sum(area) / len(area):.1f} % of the image"
                        if seg_ok else "no mask -- is the prompt object in the recording? (sam3_ros_node TEXT_PROMPT)"))

        def phase(a, b):
            ms = [m for ts, m in grasps if a <= ts < b]
            top = [m.grasps[0].score for m in ms if m.grasps]
            return len(ms), (max(top) if top else None)

        n_exec, top_exec = phase(t0, t1)
        n_idle, top_idle = phase(t1, t2)
        tops = [s for s in (top_exec, top_idle) if s is not None]
        det_ok = n_exec + n_idle > 0
        results.append(("PASS " if det_ok else "FAIL ", "grasp detection",
                        f"{n_exec + n_idle} candidate sets, {(n_exec + n_idle) / (t2 - t0):.2f}/s, top score {max(tops):.3f}"
                        if det_ok else "no candidates in either state -- see the log"))
        # the gate only means something if detection works at all
        if det_ok:
            gate_ok = n_exec > 0 and n_idle == 0
            results.append(("XPASS" if gate_ok else "XFAIL", "gate (A1)",
                            f"EXECUTING {n_exec} sets, IDLE {n_idle} sets (want EXECUTING > 0, IDLE 0)"))
    except RuntimeError as e:
        results.append(("FAIL ", "setup", str(e)))
    finally:
        for p in reversed(procs):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGINT)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
        log.close()
        node.destroy_node()
        rclpy.shutdown()

    print()
    for tag, name, detail in results:
        print(f"  [{tag}] {name:18s} {detail}")
    tags = [t for t, _, _ in results]
    if "XPASS" in tags:
        print("\n  XPASS: A1 did not reproduce -- retag it in CODE_AUDIT.")
    failed = "FAIL " in tags
    print("\nRESULT:", "FAIL (a control or the setup failed)" if failed
          else "PASS (controls pass; XFAIL = known finding reproduced)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
