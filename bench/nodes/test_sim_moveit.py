"""Plan and execute on MoveIt's SIMULATED arm; check the fake joints got there.

Run by bench/sim_moveit.sh, which has already proven the arm is mock_components
and the ROS channel is private. The home poses are T1.3 candidates: this
shows whether each is reachable and collision-free *in the model* and records
where every link ends up (robot-base frame) plus the camera viewing direction.
It says nothing about whether a pose is safe for the real arm or its
surroundings: link origins are not collision meshes, and the table position in
the robot frame is unknown (T1.4), so no clearance or containment verdict is
printed here.
"""
import math
import os
import sys
import time

try:
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from rclpy.time import Time
    from geometry_msgs.msg import TransformStamped
    from moveit_msgs.action import MoveGroup
    from moveit_msgs.msg import Constraints, JointConstraint
    from sensor_msgs.msg import JointState
    from tf2_ros import Buffer, StaticTransformBroadcaster, TransformListener
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble + the overlay first")
    sys.exit(3)

JOINTS = [f"joint{i}" for i in range(1, 7)]
POSES = [  # name, target -- values from mtc_planner.hpp HOME_JOINTS on each branch
    ("home (main)",          [0.0, 0.0, 0.7854, 0.0, 1.5708, 1.5708]),
    ("home (realman_manip)", [-0.0175, -0.1745, 0.7854, -3.0718, -1.6930, -1.6057]),
    ("home (C2 tucked)",     [0.0, -0.20, 0.7854, 0.0, 1.35, 1.5708]),  # T1.3 probe, reverts if C2 loses
    ("zero",                 [0.0] * 6),
]
TOL = 0.01  # rad
ERR = {1: "SUCCESS", 99999: "FAILURE", -1: "PLANNING_FAILED", -2: "INVALID_MOTION_PLAN",
       -4: "CONTROL_FAILED", -6: "TIMED_OUT", -10: "START_STATE_IN_COLLISION",
       -12: "GOAL_IN_COLLISION", -13: "GOAL_VIOLATES_PATH_CONSTRAINTS",
       -14: "GOAL_CONSTRAINTS_VIOLATED", -31: "NO_IK_SOLUTION"}
LINK_FRAMES = [f"Link{i}" for i in range(1, 7)] + ["grasp_frame", "camera_link"]
# camera_color_optical_frame does not exist in the sim model (verified live on
# the box 2026-09-23: static tree holds camera_link + camera_bottom_screw_frame
# only). Camera POSITION comes from camera_link TF; VIEW uses the Link6 flange
# normal as proxy (camera is fixed-mounted ~5 cm off Link6, tilt per vendor
# xacro), flagged wherever the view vector is printed.
# T1.4 mount truth (model): arm base 0.18 m fwd, 0.48 m up, yaw pi, robot-base-relative only.
MOUNT_XYZ = (0.18, 0.0, 0.48)
HOLD = int(os.environ.get("BENCH_POSE_HOLD", "0"))  # seconds to hold each settled pose for RViz viewing


class Bench(Node):
    def __init__(self):
        super().__init__("bench_sim_moveit")
        self.client = ActionClient(self, MoveGroup, "/move_action")
        self.js = {}
        self.create_subscription(JointState, "/joint_states", self._js, 10)
        self.tf = Buffer()
        self.tfl = TransformListener(self.tf, self)
        self.static = StaticTransformBroadcaster(self)
        self._pub_mount()

    def _js(self, m):
        self.js.update(zip(m.name, m.position))

    def _pub_mount(self):
        """robot_base_link -> base_link, T1.4 mount truth. The sim model roots at
        base_link; without this edge the link frames cannot be read in robot coordinates."""
        t = TransformStamped()
        t.header.frame_id, t.child_frame_id = "robot_base_link", "base_link"
        t.transform.translation.x, t.transform.translation.y, t.transform.translation.z = MOUNT_XYZ
        t.transform.rotation.x, t.transform.rotation.y = 0.0, 0.0
        t.transform.rotation.z, t.transform.rotation.w = 1.0, 0.0  # yaw pi
        self.static.sendTransform(t)

    def place(self, name):
        """Print robot-frame link origins, grasp/camera pose and camera view direction
        at the settled pose. Origins are not collision meshes: this records placement,
        it never verdicts containment or clearance. Returns False on any TF miss."""
        tr = {}
        for f in LINK_FRAMES:
            try:
                tr[f] = self.tf.lookup_transform("robot_base_link", f, Time())
            except Exception as e:
                print(f"  [PLACE] {name}: tf-missing for {f} ({e})")
                return False
        p = {f: t.transform.translation for f, t in tr.items()}
        q = tr["Link6"].transform.rotation
        qx, qy, qz, qw = q.x, q.y, q.z, q.w
        view = (2 * (qx * qz + qw * qy), 2 * (qy * qz - qw * qx), 1 - 2 * (qx * qx + qy * qy))
        maxr = max(math.hypot(v.x, v.y) for f, v in p.items() if f.startswith("Link"))
        links = " ".join(f"{f}=(%+.3f,%+.3f,%+.3f)" % (p[f].x, p[f].y, p[f].z)
                         for f in LINK_FRAMES if f.startswith("Link"))
        print(f"  [PLACE] {name}: {links}")
        g, c = p["grasp_frame"], p["camera_link"]
        print(f"  [PLACE] {name}: grasp=(%+.3f,%+.3f,%+.3f) camera=(%+.3f,%+.3f,%+.3f) "
              f"view[Link6-normal-proxy]=(%+.3f,%+.3f,%+.3f) max_origin_radius=%.3f m"
              % (g.x, g.y, g.z, c.x, c.y, c.z, *view, maxr))
        return True

    def spin_until(self, fut, timeout):
        end = time.time() + timeout
        while rclpy.ok() and not fut.done() and time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.1)
        return fut.done()

    def go(self, target):
        g = MoveGroup.Goal()
        r = g.request
        r.group_name = "rm_group"
        r.num_planning_attempts = 5
        r.allowed_planning_time = 5.0
        r.max_velocity_scaling_factor = 0.3
        r.max_acceleration_scaling_factor = 0.3
        r.goal_constraints = [Constraints(joint_constraints=[
            JointConstraint(joint_name=j, position=p, tolerance_above=TOL / 2,
                            tolerance_below=TOL / 2, weight=1.0) for j, p in zip(JOINTS, target)])]
        g.planning_options.plan_only = False   # execute -- on the simulated controller
        sent = self.client.send_goal_async(g)
        if not self.spin_until(sent, 15) or not sent.result().accepted:
            return "goal rejected", None
        res = sent.result().get_result_async()
        if not self.spin_until(res, 60):
            return "no result in 60 s", None
        code = res.result().result.error_code.val
        return ERR.get(code, str(code)), code


def main():
    rclpy.init()
    n = Bench()
    if not n.client.wait_for_server(timeout_sec=30):
        print("FAIL: /move_action not available")
        return 1
    t0 = time.time()
    while len(n.js) < 6 and time.time() - t0 < 10:
        rclpy.spin_once(n, timeout_sec=0.1)
    if not all(j in n.js for j in JOINTS):
        print("FAIL: no /joint_states from the simulated arm")
        return 1

    fails = 0
    for name, target in POSES:
        status, code = n.go(target)
        t1 = time.time()
        while time.time() - t1 < 1.5:          # let the final joint_states arrive
            rclpy.spin_once(n, timeout_sec=0.05)
        got = [n.js.get(j, float("nan")) for j in JOINTS]
        dev = max(abs(a - b) for a, b in zip(got, target))
        ok = code == 1 and dev <= 2 * TOL
        rec = n.place(name)  # placement record; a TF miss fails the pose, reachability logic unchanged
        ok = ok and rec
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<22} {status:<24} max joint error {dev:.4f} rad")
        if HOLD > 0:  # hold the settled pose for RViz viewing; TF stays alive via spins
            t2 = time.time()
            while time.time() - t2 < HOLD:
                rclpy.spin_once(n, timeout_sec=0.1)
    n.destroy_node()
    rclpy.shutdown()
    print("PASS: MoveIt plans and executes on the simulated arm" if not fails
          else f"FAIL: {fails} of {len(POSES)} motions")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
