"""Plan and execute on MoveIt's SIMULATED arm; check the fake joints got there.

Run by bench/sim_moveit.sh, which has already proven the arm is mock_components
and the ROS channel is private. The two home poses are CODE_AUDIT B4's: this
shows whether each is reachable and collision-free *in the model* -- it says
nothing about whether it is safe for the real arm or its surroundings.
"""
import sys
import time

try:
    import rclpy
    from rclpy.action import ActionClient
    from rclpy.node import Node
    from moveit_msgs.action import MoveGroup
    from moveit_msgs.msg import Constraints, JointConstraint
    from sensor_msgs.msg import JointState
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble + the overlay first")
    sys.exit(3)

JOINTS = [f"joint{i}" for i in range(1, 7)]
POSES = [  # name, target -- values from mtc_planner.hpp HOME_JOINTS on each branch
    ("home (main)",          [0.0, 0.0, 0.7854, 0.0, 1.5708, 1.5708]),
    ("home (realman_manip)", [-0.0175, -0.1745, 0.7854, -3.0718, -1.6930, -1.6057]),
    ("zero",                 [0.0] * 6),
]
TOL = 0.01  # rad
ERR = {1: "SUCCESS", 99999: "FAILURE", -1: "PLANNING_FAILED", -2: "INVALID_MOTION_PLAN",
       -4: "CONTROL_FAILED", -6: "TIMED_OUT", -10: "START_STATE_IN_COLLISION",
       -12: "GOAL_IN_COLLISION", -13: "GOAL_VIOLATES_PATH_CONSTRAINTS",
       -14: "GOAL_CONSTRAINTS_VIOLATED", -31: "NO_IK_SOLUTION"}


class Bench(Node):
    def __init__(self):
        super().__init__("bench_sim_moveit")
        self.client = ActionClient(self, MoveGroup, "/move_action")
        self.js = {}
        self.create_subscription(JointState, "/joint_states", self._js, 10)

    def _js(self, m):
        self.js.update(zip(m.name, m.position))

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
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {name:<22} {status:<24} max joint error {dev:.4f} rad")
    n.destroy_node()
    rclpy.shutdown()
    print("PASS: MoveIt plans and executes on the simulated arm" if not fails
          else f"FAIL: {fails} of {len(POSES)} motions")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
