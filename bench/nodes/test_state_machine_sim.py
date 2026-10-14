"""grasp_state_machine on MoveIt's SIMULATED arm, driven the way the real pipeline drives it.

Run by bench/state_machine_sim.sh, which has proven the arm is mock_components, the channel is
private, no rm_driver exists and the real arm is unreachable. This test plays every other actor:
  camera      /camera/camera/color/camera_info  (the real D435i intrinsics, docs/archive/output.log:200)
  camera TF   camera_link -> ... -> camera_color_optical_frame, only if the model lacks it (the
              RealSense driver publishes these on the robot)
  detector    /object_centroid_2d: an object straight ahead, far, lost for a while, far, then near
  operator    /manipulator/grasp_request: centroids only count after one (T1.25)
              /manipulator/release: lets go of the held object (T1.14)
  gripper     records /rm_driver/set_gripper_{position,pick_on}_cmd -- nothing acts on them
  AnyGrasp    in candidates mode only: /grasp_candidates, one fixed grasp at the gripper's pose
              1 cm up, sent in the camera frame as anygrasp_detection_node does. It is built in
              AnyGrasp's axes from where the gripper's links are, then turned into grasp_frame's
              by the node's own to_grasp_frame (T1.17)
and watches /pipeline_state, /joint_states, /manipulator/return_to_user, /manipulation/done and
the launch log.

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
    from geometry_msgs.msg import PointStamped, Pose, TransformStamped
    from sensor_msgs.msg import CameraInfo, JointState
    from std_msgs.msg import Bool, Empty, String
    from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener
    from tf2_geometry_msgs import do_transform_pose
    from grasp_interfaces.msg import GraspCandidate, GraspCandidateArray
    from rm_ros_interfaces.msg import Gripperpick, Gripperset
    import numpy as np
    from scipy.spatial.transform import Rotation
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble + the overlay first")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "grasp/anygrasp_node"))
from anygrasp_to_grasp_frame import to_grasp_frame  # noqa: E402
LOG = REPO / os.environ.get("BENCH_SM_LOG", "log/bench_state_machine.txt")
JOINTS = [f"joint{i}" for i in range(1, 7)]
HOME_MAIN = [0.0, 0.0, 0.7854, 0.0, 1.5708, 1.5708]      # mtc_planner.hpp HOME_JOINTS on main (CODE_AUDIT B4)
HOME_REALMAN = [-0.0175, -0.1745, 0.7854, -3.0718, -1.6930, -1.6057]
RETURN = HOME_MAIN  # mtc_planner.hpp RETURN_JOINTS is HOME_JOINTS since 2026-10-05 (T1.7)
FX, FY, CX, CY, W, H = 607.18, 606.92, 331.95, 250.13, 640, 480
OFFSET_X = 55.0        # CENTROID_TARGET_OFFSET_X: a centroid here means "no lateral error"
FAR, NEAR = 0.30, 0.15  # m; the code switches to EXECUTING below execute_depth_thresh_m, 0.21 since T1.11
CY_OFF = float(os.environ.get("SM_CY", "0"))    # lateral px added to the fake centroid
FAR = float(os.environ.get("SM_FAR", "0.30"))   # start depth (m); keep above 0.21
OPT = "camera_color_optical_frame"
CANDIDATES = os.environ.get("BENCH_SM_PATH") == "candidates"  # use_simple_execute false (T1.17)
TOL = 0.02  # rad


class Actors(Node):
    def __init__(self):
        super().__init__("bench_sm_actors")
        self.states, self.grip, self.returned, self.done, self.js = [], [], [], [], {}
        now = time.time
        self.create_subscription(String, "/pipeline_state", lambda m: self.states.append((now(), m.data)), 10)
        self.create_subscription(JointState, "/joint_states", lambda m: self.js.update(zip(m.name, m.position)), 10)
        self.create_subscription(Gripperset, "/rm_driver/set_gripper_position_cmd",
                                 lambda m: self.grip.append((now(), "set_position", f"position={m.position}")), 10)
        self.create_subscription(Gripperpick, "/rm_driver/set_gripper_pick_on_cmd", self._pick_on, 10)
        self.axes_at_close = None  # gripper approach and closing directions when told to close
        self.tip_at_close = None   # grasp_frame (the fingertips) in base_link when told to close
        self.create_subscription(Bool, "/manipulator/return_to_user", lambda m: self.returned.append((now(), m.data)), 10)
        self.create_subscription(Empty, "/manipulation/done", lambda m: self.done.append(now()), 10)
        self.cam_pub = self.create_publisher(CameraInfo, "/camera/camera/color/camera_info", 1)
        self.cen_pub = self.create_publisher(PointStamped, "/object_centroid_2d", 10)
        self.req_pub = self.create_publisher(Empty, "/manipulator/grasp_request", 10)
        self.rel_pub = self.create_publisher(Bool, "/manipulator/release", 10)
        self.cand_pub = self.create_publisher(GraspCandidateArray, "/grasp_candidates", 10)
        self.cand_base = None  # Pose in base_link; published in the camera frame while set
        self.depth = None
        self.create_timer(0.2, self._camera)
        self.create_timer(0.1, self._centroid)
        self.create_timer(0.2, self._candidate)
        self.tf = Buffer()
        self.tfl = TransformListener(self.tf, self)
        self.static = StaticTransformBroadcaster(self)

    def _pick_on(self, m):
        self.grip.append((time.time(), "pick_on", f"speed={m.speed} force={m.force}"))
        try:
            self.axes_at_close = self.gripper_axes()
            t = self.tf.lookup_transform("base_link", "grasp_frame", Time()).transform.translation
            self.tip_at_close = np.array([t.x, t.y, t.z])
        except Exception:
            pass

    def gripper_axes(self):
        """The gripper's approach and closing directions in base_link, from where its links are.
        Approach: Link6 towards grasp_frame. Closing: the line between the fingers."""
        def at(frame):
            t = self.tf.lookup_transform("base_link", frame, Time()).transform.translation
            return np.array([t.x, t.y, t.z])
        a = at("grasp_frame") - at("Link6")
        a /= np.linalg.norm(a)
        c = at("gripper_Link1") - at("gripper_Link3")
        c -= c.dot(a) * a
        return a, c / np.linalg.norm(c)

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
        m.point.x, m.point.y, m.point.z = CX + OFFSET_X + CY_OFF, CY, self.depth
        self.cen_pub.publish(m)

    def _candidate(self):
        if self.cand_base is None:
            return
        try:
            to_opt = self.tf.lookup_transform(OPT, "base_link", Time())
        except Exception:
            return
        m = GraspCandidateArray()
        m.header.frame_id, m.header.stamp = OPT, self.get_clock().now().to_msg()
        m.grasps = [GraspCandidate(score=0.9, width=0.05, depth=0.02, pose=do_transform_pose(self.cand_base, to_opt))]
        self.cand_pub.publish(m)

    def request(self):
        self.req_pub.publish(Empty())

    def release(self):
        self.rel_pub.publish(Bool(data=True))

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
        print(f"scenario: CY_OFF={CY_OFF:.0f}px FAR={FAR:.2f}m path={'candidates' if CANDIDATES else 'simple'}")
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
                  "main's (joint4 0.0) -- validated on the real arm 2026-09-23 (T1.7)" if ok else
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

        # ---- gate closed: centroids with no request start nothing (T1.25) -------
        t_gate = time.time()
        n.depth = FAR
        n.spin_until(lambda: n.seen("SELECTING", t_gate), 5)
        ignored = log_has(r"Centroid ignored: no grasp request open")
        check("centroids with no request are ignored, stays IDLE", ignored and not n.seen("SELECTING", t_gate),
              "5 s of centroids, no SELECTING, 'Centroid ignored' logged" if ignored and not n.seen("SELECTING", t_gate)
              else f"SELECTING {'seen' if n.seen('SELECTING', t_gate) else 'not seen'}, "
                   f"'Centroid ignored' {'logged' if ignored else 'not logged'}")
        if n.seen("SELECTING", t_gate):
            return
        n.release()
        rel_ignored = n.spin_until(lambda: log_has(r"Release ignored: not holding an object"), 5)
        check("a release with nothing held is ignored", rel_ignored,
              "'Release ignored' logged" if rel_ignored else "no 'Release ignored' line in 5 s")
        if not rel_ignored:
            return

        # ---- SELECTING: request, object far, straight ahead -------------------
        t1 = time.time()
        n.request()
        sel = n.spin_until(lambda: n.seen("SELECTING", t1), 120)
        check("request + centroid -> re-homes, then SELECTING", sel,
              "seen" if sel else "no SELECTING within 120 s of the request")
        if not sel:
            return
        n.request()
        busy = n.spin_until(lambda: log_has(r"Grasp request ignored: busy"), 5)
        check("a request during the approach is refused as busy", busy,
              "'busy' logged" if busy else "no 'busy' line in 5 s")
        before = n.joints()
        moved = n.spin_until(lambda: max(abs(a - b) for a, b in zip(n.joints(), before)) > 0.005
                             or log_has(r"SELECTING: (step failed|Cartesian step failed|EEF transform failed|goal transform failed)"), 90)
        step_fail = log_has(r"SELECTING: (step failed|Cartesian step failed|EEF transform failed|goal transform failed)")
        check("SELECTING: an approach step moves the arm", moved and not step_fail,
              "joints moved" if not step_fail else "step failed -- see the launch log for which")
        if step_fail:
            return

        # ---- object lost mid-approach: centroids stop, the age limit ends it ---
        t_lost = time.time()
        n.depth = None
        # Wait for both: IDLE on the topic can arrive before the log line reaches the file
        lost = n.spin_until(lambda: n.seen("IDLE", t_lost) and log_has(r"object lost"), 60)
        check("centroids stop -> approach ends, back to IDLE", lost,
              "'object lost' logged, IDLE seen" if lost else
              f"in 60 s: IDLE {'seen' if n.seen('IDLE', t_lost) else 'not seen'}, "
              f"'object lost' {'logged' if log_has(r'object lost') else 'not logged'}")
        if not lost:
            return
        # A request with no centroid lapses after grasp_request_timeout_s (10 s)
        t_lapse = time.time()
        n.request()
        lapsed = n.spin_until(lambda: log_has(r"Grasp request lapsed"), 20)
        check("a request with no centroid lapses, stays IDLE", lapsed and not n.seen("SELECTING", t_lapse),
              "'lapsed' logged, no SELECTING" if lapsed else "no 'lapsed' line in 20 s")
        if not lapsed:
            return
        # The failed approach closed the gate: the object coming back needs a new request
        t_back = time.time()
        n.depth = FAR
        n.spin_until(lambda: False, 2)
        if n.seen("SELECTING", t_back):
            return check("gate closed again after the failed approach", False,
                         "SELECTING with no new request")
        n.request()
        ignored_before = log_count(r"Centroid ignored")
        back = n.spin_until(lambda: n.seen("SELECTING", t_back), 120)
        check("object back + new request -> SELECTING again", back, "seen" if back else "no SELECTING within 120 s")
        if not back:
            return

        # ---- EXECUTING: object now within reach --------------------------------
        t2 = time.time()
        n.depth = NEAR
        ex = n.spin_until(lambda: n.seen("EXECUTING", t2), 90)
        check("object near -> EXECUTING", ex, "seen" if ex else "no EXECUTING in 90 s")
        if not ex:
            return
        # Centroids keep coming at NEAR. Once the snapshot is taken they must be dropped
        after_snap = n.spin_until(lambda: log_count(r"Centroid ignored") > ignored_before, 10)
        check("centroids after the EXECUTING snapshot are ignored", after_snap,
              "'Centroid ignored' logged after EXECUTING" if after_snap else "none logged in 10 s")
        opened = n.spin_until(lambda: any(k == "set_position" and t >= t2 for t, k, _ in n.grip), 15)
        check("gripper told to open", opened,
              next((d for t, k, d in n.grip if k == "set_position" and t >= t2), "no set_gripper_position_cmd"))
        if CANDIDATES:
            try:
                # moveToPose aims grasp_frame, not Link6, at the candidate (mtc_planner.cpp setIKFrame)
                eef = n.tf.lookup_transform("base_link", "grasp_frame", Time()).transform
            except Exception as e:
                return check("gripper pose for the fake candidate", False, f"no base_link -> grasp_frame: {e}")
            n.cand_base = Pose()
            n.cand_base.position.x, n.cand_base.position.y = eef.translation.x, eef.translation.y
            n.cand_base.position.z = eef.translation.z + 0.01
            # The grasp in AnyGrasp's axes (x approach, y closing), then the node's conversion
            a, c = n.gripper_axes()
            want = np.column_stack([a, c, np.cross(a, c)])
            q = n.cand_base.orientation
            q.x, q.y, q.z, q.w = (float(v) for v in Rotation.from_matrix(to_grasp_frame(want)).as_quat())
            angle = math.degrees(math.asin(min(1.0, abs(1 - 2 * (q.x * q.x + q.y * q.y)))))  # approachAngleDeg()
            locked = n.spin_until(lambda: log_has(r"EXECUTING: pose stable") or log_has(r"no candidate"), 30)
            check("candidates -> stability lock", locked and log_has(r"EXECUTING: pose stable"),
                  f"locked; candidate approach angle {angle:.1f} deg" if log_has(r"EXECUTING: pose stable") else
                  f"no lock in 30 s; approach angle {angle:.1f} deg (min_approach_angle_deg rejects below 20)")
            if not log_has(r"EXECUTING: pose stable"):
                return
        fail_re = (r"EXECUTING: (Cartesian move failed|no candidates received)" if CANDIDATES
                   else r"EXECUTING: final Cartesian step failed")
        closed = n.spin_until(lambda: any(k == "pick_on" for t, k, _ in n.grip) or log_has(fail_re), 90)
        if CANDIDATES:
            p = n.cand_base.position
            tip_target = np.array([p.x, p.y, p.z])  # the fingertip target the node publishes
        n.cand_base = None
        final_fail = log_has(fail_re)
        check("final approach, then gripper told to close", closed and not final_fail,
              "final move failed -- see the launch log" if final_fail
              else next((d for t, k, d in n.grip if k == "pick_on"), "no set_gripper_pick_on_cmd in 90 s"))
        if final_fail or not closed:
            return
        if CANDIDATES:
            # Did the gripper come in the way AnyGrasp asked? A wrong axis conversion is 90 deg off
            deg = lambda u, v: math.degrees(math.acos(min(1.0, abs(float(u.dot(v))))))
            if n.axes_at_close is None:
                return check("gripper points the way AnyGrasp asked", False, "no TF when told to close")
            app, clo = deg(n.axes_at_close[0], want[:, 0]), deg(n.axes_at_close[1], want[:, 1])
            if not check("gripper points the way AnyGrasp asked", app < 5 and clo < 5,
                         f"approach off by {app:.1f} deg, closing line off by {clo:.1f} deg (limit 5)"):
                return
            off = float(np.linalg.norm(n.tip_at_close - tip_target)) * 1000
            if not check("fingertips reach the published grasp point", off < 5,
                         f"grasp_frame {off:.1f} mm from it (limit 5)"):
                return
        n.depth = None
        ret = n.spin_until(lambda: any(v for _, v in n.returned), 120)
        ok, dev = n.near(RETURN)
        check("moves to the return pose and announces /manipulator/return_to_user", ret and ok,
              f"return_to_user {'published' if ret else 'not published'}; joints {dev:.4f} rad from RETURN_JOINTS")
        if not ret:
            return

        done = n.spin_until(lambda: len(n.done) > 0, 5)
        check("announces /manipulation/done at the return pose", done,
              "published" if done else "no /manipulation/done in 5 s")
        if not done:
            return

        # ---- hold: no release, so the gripper stays shut and new requests are refused (T1.14)
        t_hold = time.time()
        busy_before = log_count(r"Grasp request ignored: busy")
        n.request()
        n.spin_until(lambda: False, 5)
        opened_early = any(k == "set_position" and t >= t_hold for t, k, _ in n.grip)
        busy_hold = log_count(r"Grasp request ignored: busy") > busy_before
        idle_early = n.seen("IDLE", t_hold)
        check("holds with no release: gripper shut, requests refused", not opened_early and busy_hold and not idle_early,
              f"5 s: gripper {'opened' if opened_early else 'shut'}, request "
              f"{'refused' if busy_hold else 'not refused'}, IDLE {'seen' if idle_early else 'not seen'}")
        if opened_early or idle_early:
            return

        # ---- release: open, home, IDLE, ready for the next object (was CODE_AUDIT C7)
        t3 = time.time()
        n.release()
        let_go = n.spin_until(lambda: any(k == "set_position" and t >= t3 for t, k, _ in n.grip), 15)
        check("release opens the gripper", let_go,
              "set_gripper_position_cmd sent" if let_go else "no gripper open in 15 s")
        if not let_go:
            return
        back = n.spin_until(lambda: n.seen("IDLE", t3), 60)
        ok, dev = n.near(HOME_MAIN)
        check("after the release: re-homes and returns to IDLE", back and ok,
              f"IDLE {'seen' if back else 'not seen'}; joints {dev:.4f} rad from main's home")
        if not back:
            return

        # ---- second grasp in the same launch: a new request starts a new approach
        t4 = time.time()
        n.depth = FAR
        n.request()
        again = n.spin_until(lambda: n.seen("SELECTING", t4), 120)
        check("second request in the same launch -> SELECTING", again,
              "seen" if again else "no SELECTING within 120 s")

    try:
        run()
    finally:
        # ---- shutdown: does the node exit on SIGINT? (CODE_AUDIT C6: nothing is ever joined)
        pid = subprocess.run(["pgrep", "-f", "lib/grasp_state_machine/grasp_state_machine"], capture_output=True,
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
