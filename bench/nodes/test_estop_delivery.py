"""Does estop.py deliver its stop message? Driven the way an operator would drive it.

Run by bench/estop_delivery.sh, which has already proven the ROS channel is private
and no rm_driver is running -- nothing on this channel acts on a stop message.
estop.py needs a terminal (getch() puts the tty in raw mode), so it runs under a
pseudo-terminal and gets real keystrokes.

  control  key 'e'         -> Stop(state=True)  on /rm_driver/emergency_stop_cmd
  control  key 'r'         -> Stop(state=False) on the same topic
  control  key 's'         -> Empty on /rm_driver/move_stop_cmd
  xfail    Ctrl+C key      -> Stop(state=True). Expected to fail [inferred]: raw mode
                              turns Ctrl+C into a plain character, so no SIGINT is raised
  xfail    kill -INT (xN)  -> Stop(state=True). Expected to fail: CODE_AUDIT B2 (publish,
                              then destroy_node/shutdown at once). A race, so repeated

Controls must pass. An xfail that passes is reported as XPASS: the finding did not
reproduce, retag it. Exit 0 = controls pass, 1 = a control failed, 3 = skipped.
"""
import os
import pty
import signal
import subprocess
import sys
import time
from pathlib import Path

try:
    import rclpy
    from rclpy.node import Node
    from rm_ros_interfaces.msg import Stop
    from std_msgs.msg import Empty
except ImportError as e:
    print(f"SKIP: {e} -- source ROS 2 Humble + the overlay first")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]
ESTOP = REPO / "ros2_robot_ws/src/estop.py"
ESTOP_TOPIC = "/rm_driver/emergency_stop_cmd"
SOFT_TOPIC = "/rm_driver/move_stop_cmd"
TRIALS = int(os.environ.get("BENCH_ESTOP_TRIALS", "5"))
LOG = REPO / os.environ.get("BENCH_ESTOP_LOG", "log/bench_estop.txt")
WAIT = 3.0  # s allowed for a message to arrive


class Listener(Node):
    def __init__(self):
        super().__init__("bench_estop_listener")
        self.got = []  # (topic, state or None, time)
        self.create_subscription(Stop, ESTOP_TOPIC,
                                 lambda m: self.got.append((ESTOP_TOPIC, m.state, time.time())), 10)
        self.create_subscription(Empty, SOFT_TOPIC,
                                 lambda m: self.got.append((SOFT_TOPIC, None, time.time())), 10)

    def spin_for(self, sec, until=None):
        end = time.time() + sec
        while time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.05)
            if until and until():
                return True
        return bool(until and until())

    def arrived(self, topic, state, since, sec=WAIT):
        hit = lambda: any(t == topic and (state is None or s == state) and ts >= since
                          for t, s, ts in self.got)
        return self.spin_for(sec, hit)


class EStopProc:
    """estop.py under a pseudo-terminal, in its own session (our signals don't reach it)."""

    def __init__(self, log):
        self.master, slave = pty.openpty()
        self.p = subprocess.Popen([sys.executable, str(ESTOP)], stdin=slave, stdout=log,
                                  stderr=subprocess.STDOUT, start_new_session=True)
        os.close(slave)

    def key(self, b):
        os.write(self.master, b)

    def wait_exit(self, sec):
        try:
            return self.p.wait(sec)
        except subprocess.TimeoutExpired:
            return None

    def kill(self):
        if self.p.poll() is None:
            os.killpg(self.p.pid, signal.SIGKILL)
            self.p.wait(5)
        os.close(self.master)


def ready(node, proc, sec=20.0):
    """estop.py's publishers are discovered by us, and given a moment to match."""
    ok = node.spin_for(sec, lambda: node.count_publishers(ESTOP_TOPIC) >= 1
                       and node.count_publishers(SOFT_TOPIC) >= 1)
    node.spin_for(1.0)
    return ok and proc.p.poll() is None


def main():
    rclpy.init()
    node = Listener()
    results = []  # (name, kind, ok, detail)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "w") as log:
        # ---- controls + Ctrl+C, one process -----------------------------------
        e = EStopProc(log)
        try:
            if not ready(node, e):
                print(f"FAIL: estop.py did not come up (exit {e.p.poll()}) -- see {LOG}")
                return 1
            for name, key, topic, state in (("key 'e' -> emergency stop", b"e", ESTOP_TOPIC, True),
                                            ("key 'r' -> resume", b"r", ESTOP_TOPIC, False),
                                            ("key 's' -> soft stop", b"s", SOFT_TOPIC, None)):
                t = time.time()
                e.key(key)
                ok = node.arrived(topic, state, t)
                results.append((name, "control", ok, "arrived" if ok else f"nothing in {WAIT:.0f} s"))

            t = time.time()
            e.key(b"\x03")
            ok = node.arrived(ESTOP_TOPIC, True, t)
            rc = e.wait_exit(2.0)
            results.append(("Ctrl+C key -> emergency stop", "xfail", ok,
                            ("stop arrived" if ok else "no stop")
                            + ("; estop.py still running" if rc is None else f"; estop.py exited {rc}")))
        finally:
            e.kill()

        # ---- SIGINT, repeated: B2 is a race ------------------------------------
        delivered, details = 0, []
        for i in range(TRIALS):
            log.write(f"\n===== SIGINT trial {i + 1}/{TRIALS} =====\n")
            log.flush()
            e = EStopProc(log)
            try:
                if not ready(node, e):
                    details.append(f"#{i + 1}: did not come up")
                    continue
                t = time.time()
                os.kill(e.p.pid, signal.SIGINT)
                ok = node.arrived(ESTOP_TOPIC, True, t)
                rc = e.wait_exit(5.0)
                delivered += ok
                details.append(f"#{i + 1}: {'stop' if ok else 'none'}, exit {rc}")
            finally:
                e.kill()
        results.append((f"kill -INT -> emergency stop ({TRIALS} trials)", "xfail",
                        delivered == TRIALS, f"{delivered}/{TRIALS} delivered  [" + "; ".join(details) + "]"))

    node.destroy_node()
    rclpy.shutdown()

    print()
    failed = False
    for name, kind, ok, detail in results:
        if kind == "control":
            tag = "PASS " if ok else "FAIL "
            failed |= not ok
        else:
            tag = "XPASS" if ok else "XFAIL"
        print(f"  [{tag}] {name:42s} {detail}")
    if any(k == "xfail" and ok for _, k, ok, _ in results):
        print("\n  XPASS: an expected failure did not reproduce -- retag the finding (CODE_AUDIT B2 / TESTBENCH_PLAN W3).")
    print("\nRESULT:", "FAIL (a control case failed)" if failed else "PASS (controls pass; XFAIL = known finding reproduced)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
