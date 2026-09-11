"""grasp_state_machine on MoveIt's SIMULATED arm, driven the way the real pipeline drives it.

Run by bench/state_machine_sim.sh, which has proven the arm is mock_components, the channel is
private, no rm_driver exists and the real arm is unreachable. This test plays every other actor:
  camera      /camera/camera/color/camera_info  (the real D435i intrinsics, output.log:200)
  camera TF   camera_link -> ... -> camera_color_optical_frame, only if the model lacks it (the
              RealSense driver publishes these on the robot)
  detector    /object_centroid_2d: an object straight ahead, far, then near
  gripper     records /rm_driver/set_gripper_{position,pick_on}_cmd -- nothing acts on them
and watches /pipeline_state, /joint_states, /manipulator/return_to_user and the launch log.

Checks follow the code's own intent (grasp_state_machine.cpp workerLoop). Ones that encode an
audit finding are expected-fail. A failure stops the run and names itself; later checks are
reported as not reached. Exit 0 = every control passed or was an expected-fail, 1 = a control
failed, 3 = skipped.
"""
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.time import Time
    from geometry_msgs.msg import PointStamped, TransformStamped
    from sensor_msgs.msg import CameraInfo, JointState
    from std_msgs.msg import Bool, String
    from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener
    from rm_ros_interfaces.msg import Gripperpick, Gripperset
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble + the overlay first")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]
LOG = REPO / os.environ.get("BENCH_SM_LOG", "log/bench_state_machine.txt")
JOINTS = [f"joint{i}" for i in range(1, 7)]
HOME_MAIN = [0.0, 0.0, 0.7854, 0.0, 1.5708, 1.5708]      # mtc_planner.hpp HOME_JOINTS on main (CODE_AUDIT B4)
HOME_REALMAN = [-0.0175, -0.1745, 0.7854, -3.0718, -1.6930, -1.6057]
RETURN = [0.0, -0.2443, 2.3562, 0.0, -0.5585, 1.5708]    # mtc_planner.hpp RETURN_JOINTS
FX, FY, CX, CY, W, H = 607.18, 606.92, 331.95, 250.13, 640, 480
OFFSET_X = 55.0        # CENTROID_TARGET_OFFSET_X: a centroid here means "no lateral error"
FAR, NEAR = 0.30, 0.15  # m; the code switches to EXECUTING below EXECUTE_DEPTH_THRESH_M = 0.18
OPT = "camera_color_optical_frame"
TOL = 0.02  # rad


class Actors(Node):
    def __init__(self):
        super().__init__("bench_sm_actors")
        self.states, self.grip, self.returned, self.js = [], [], [], {}
        now = time.time
        self.create_subscription(String, "/pipeline_state", lambda m: self.states.append((now(), m.data)), 10)
        self.create_subscription(JointState, "/joint_states", lambda m: self.js.update(zip(m.name, m.position)), 10)
        self.create_subscription(Gripperset, "/rm_driver/set_gripper_position_cmd",
                                 lambda m: self.grip.append((now(), "set_position", f"position={m.position}")), 10)
        self.create_subscription(Gripperpick, "/rm_driver/set_gripper_pick_on_cmd",
                                 lambda m: self.grip.append((now(), "pick_on", f"speed={m.speed} force={m.force}")), 10)
        self.create_subscription(Bool, "/manipulator/return_to_user", lambda m: self.returned.append((now(), m.data)), 10)
        self.cam_pub = self.create_publisher(CameraInfo, "/camera/camera/color/camera_info", 1)
        self.cen_pub = self.create_publisher(PointStamped, "/object_centroid_2d", 10)
        self.depth = None
        self.create_timer(0.2, self._camera)
        self.create_timer(0.1, self._centroid)
        self.tf = Buffer()
        self.tfl = TransformListener(self.tf, self)
        self.static = StaticTransformBroadcaster(self)

    def _camera(self):
        m = CameraInfo()
        m.header.frame_id, m.header.stamp = OPT, self.get_clock().now().to_msg()
        m.width, m.height = W, H
        m.k = [FX, 0.0, CX, 0.0, FY, CY, 0.0, 0.0, 1.0]
        self.cam_pub.publish(m)

    def _centroid(self):
        if self.depth is None:
            return
        m = PointStamped()
        m.header.frame_id, m.header.stamp = OPT, self.get_clock().now().to_msg()
        m.point.x, m.point.y, m.point.z = CX + OFFSET_X, CY, self.depth
        self.cen_pub.publish(m)

    def spin_until(self, pred, sec):
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if pred():
                return True
        return pred()

    def joints(self):
        return [self.js.get(j, float("nan")) for j in JOINTS]

    def near(self, target):
        dev = max(abs(a - b) for a, b in zip(self.joints(), target))
        return dev <= TOL, dev

    def seen(self, state, since):
        return any(s == state and t >= since for t, s in self.states)

    def has_tf(self, target, source):
        return self.tf.can_transform(target, source, Time())


def log_has(pattern):
    try:
        return re.search(pattern, LOG.read_text(errors="replace")) is not None
    except OSError:
        return False


def log_count(pattern):
    try:
        return len(re.findall(pattern, LOG.read_text(errors="replace")))
    except OSError:
        return 0


def supply_optical_frames(n):
    """What the RealSense driver publishes on the robot (D435 nominal colour offset)."""
    t1 = TransformStamped()
    t1.header.frame_id, t1.child_frame_id = "camera_link", "camera_color_frame"
    t1.transform.translation.y = 0.015
    t1.transform.rotation.w = 1.0
    t2 = TransformStamped()
    t2.header.frame_id, t2.child_frame_id = "camera_color_frame", OPT
    t2.transform.rotation.x, t2.transform.rotation.y = -0.5, 0.5
    t2.transform.rotation.z, t2.transform.rotation.w = -0.5, 0.5
    now = n.get_clock().now().to_msg()
    t1.header.stamp = t2.header.stamp = now
    n.static.sendTransform([t1, t2])


def main():
    rclpy.init()
    n = Actors()
    R = []  # (name, kind, status, detail); status PASS/FAIL/XFAIL/XPASS/INFO/NOT REACHED

    def check(name, ok, detail, kind="control"):
        status = ("PASS" if ok else "FAIL") if kind == "control" else ("XPASS" if ok else "XFAIL")
        R.append((name, kind, status, detail))
        return ok

    def run():
        # ---- startup: safety walls, home, IDLE ---------------------------------
        t0 = time.time()
        if not n.spin_until(lambda: len(n.js) >= 6, 30):
            return check("simulated joint states", False, "no /joint_states in 30 s")
        walls = n.spin_until(lambda: log_has(r"Safety walls added"), 60)
        check("safety walls accepted by the planning scene", walls,
              "logged" if walls else "not logged in 60 s (addSafetyWalls loops until they are)")
        if not walls:
            return
        idle = n.spin_until(lambda: n.seen("IDLE", t0), 120)
        fails = log_count(r"Homing failed")
        ok, dev = n.near(HOME_MAIN)
        check("startup: homes, then publishes IDLE", idle and ok,
              f"IDLE {'seen' if idle else 'not seen'}; joints {dev:.4f} rad from main's home; "
              f"{fails} 'Homing failed' retries")
        if not idle:
            return
        realman = n.near(HOME_REALMAN)[0]
        R.append(("home pose actually used", "info", "INFO",
                  "main's (joint4 0.0) -- unvalidated on the real arm, CODE_AUDIT B4" if ok else
                  "realman_manip's" if realman else f"neither table row: {[round(x, 3) for x in n.joints()]}"))

        # ---- camera frames -----------------------------------------------------
        if not n.spin_until(lambda: n.has_tf("base_link", OPT), 5):
            if n.has_tf("base_link", "camera_link"):
                supply_optical_frames(n)
                n.spin_until(lambda: n.has_tf("base_link", OPT), 5)
                R.append(("camera optical frame", "info", "INFO",
                          "model stops at camera_link; test published camera_link -> camera_color_optical_frame "
                          "(D435 nominal), as the RealSense driver does on the robot"))
            if not n.has_tf("base_link", OPT):
                return check("camera frame reachable from base_link", False,
                             "no camera_link or camera_color_optical_frame in the TF tree")

        # ---- SELECTING: object far, straight ahead -----------------------------
        t1 = time.time()
        n.depth = FAR
        sel = n.spin_until(lambda: n.seen("SELECTING", t1), 120)
        check("object seen -> re-homes, then SELECTING", sel,
              "seen" if sel else "no SELECTING within 120 s of the first centroid")
        if not sel:
            return
        before = n.joints()
        moved = n.spin_until(lambda: max(abs(a - b) for a, b in zip(n.joints(), before)) > 0.005
                             or log_has(r"SELECTING: (step failed|Cartesian step failed|EEF transform failed|goal transform failed)"), 90)
        step_fail = log_has(r"SELECTING: (step failed|Cartesian step failed|EEF transform failed|goal transform failed)")
        check("SELECTING: an approach step moves the arm", moved and not step_fail,
              "joints moved" if not step_fail else "step failed -- see the launch log for which")
        if step_fail:
            return

        # ---- EXECUTING: object now within reach --------------------------------
        t2 = time.time()
        n.depth = NEAR
        ex = n.spin_until(lambda: n.seen("EXECUTING", t2), 90)
        check("object near -> EXECUTING", ex, "seen" if ex else "no EXECUTING in 90 s")
        if not ex:
            return
        opened = n.spin_until(lambda: any(k == "set_position" and t >= t2 for t, k, _ in n.grip), 15)
        check("gripper told to open", opened,
              next((d for t, k, d in n.grip if k == "set_position" and t >= t2), "no set_gripper_position_cmd"))
        closed = n.spin_until(lambda: any(k == "pick_on" for t, k, _ in n.grip)
                              or log_has(r"EXECUTING: final Cartesian step failed"), 90)
        final_fail = log_has(r"EXECUTING: final Cartesian step failed")
        check("final approach, then gripper told to close", closed and not final_fail,
              "final Cartesian step failed -- worker thread exits, node stays up doing nothing" if final_fail
              else next((d for t, k, d in n.grip if k == "pick_on"), "no set_gripper_pick_on_cmd in 90 s"))
        if final_fail or not closed:
            return
        n.depth = None
        ret = n.spin_until(lambda: any(v for _, v in n.returned), 120)
        ok, dev = n.near(RETURN)
        check("moves to the return pose and announces /manipulator/return_to_user", ret and ok,
              f"return_to_user {'published' if ret else 'not published'}; joints {dev:.4f} rad from RETURN_JOINTS")
        if not ret:
            return

        # ---- after the cycle: the loop's intent is home + IDLE, ready for the next object
        t3 = time.time()
        back = n.spin_until(lambda: n.seen("IDLE", t3), 60)
        check("after a grasp: re-homes and returns to IDLE for the next object", back,
              "IDLE seen" if back else "stays EXECUTING: workerLoop returns after success (CODE_AUDIT C7)",
              kind="xfail")

    try:
        run()
    finally:
        # ---- shutdown: does the node exit on SIGINT? (CODE_AUDIT C6: nothing is ever joined)
        pid = subprocess.run(["pgrep", "-f", "lib/rm_mtc/grasp_state_machine"], capture_output=True,
                             text=True).stdout.split()
        if pid:
            os.kill(int(pid[0]), 2)
            t = time.time()
            while time.time() - t < 15 and subprocess.run(["kill", "-0", pid[0]], capture_output=True).returncode == 0:
                time.sleep(0.5)
            gone = subprocess.run(["kill", "-0", pid[0]], capture_output=True).returncode != 0
            R.append(("node exits within 15 s of SIGINT", "info", "INFO",
                      "exited" if gone else "still running after 15 s (see CODE_AUDIT C6)"))
        n.destroy_node()
        rclpy.shutdown()

    print("\n  pipeline_state sequence: " + " -> ".join(s for _, s in n.states))
    print("  gripper commands: " + ("; ".join(f"{k} {d}" for _, k, d in n.grip) or "none"))
    for name, kind, status, detail in R:
        print(f"  [{status:5s}] {name:62s} {detail}")
    failed = [r for r in R if r[2] == "FAIL"]
    if failed:
        print(f"\n  Stopped at: {failed[0][0]}. Later checks not reached.")
    print("\nRESULT:", "FAIL" if failed else "PASS (XFAIL = known finding reproduced)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
