"""T3.4 limiter and keyboard pipeline on domain 127, never hardware topics."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

try:
    import rclpy
    from geometry_msgs.msg import Twist
    from lifecycle_msgs.msg import Transition
    from lifecycle_msgs.srv import ChangeState
except ImportError as error:
    print(f"SKIP: {error}")
    sys.exit(3)

REPO = Path(__file__).resolve().parents[2]


def stop_process(process: subprocess.Popen) -> None:
    """Reap only this test's process group, including ros2 run children."""
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            continue
        # The launcher may exit before its child. Check the whole owned group.
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
    process.wait(timeout=3)


def main() -> None:
    if sys.flags.optimize:
        raise RuntimeError("REFUSED: Python optimization disables test assertions")
    if os.environ.get("ROS_DOMAIN_ID") != "127" or os.environ.get("ROS_LOCALHOST_ONLY") != "1":
        raise RuntimeError("REFUSED: wrong test domain or localhost setting")
    subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], check=True)
    prefix = subprocess.run(["ros2", "pkg", "prefix", "nav2_velocity_smoother"], capture_output=True, text=True)
    if prefix.returncode:
        print(f"SKIP: nav2_velocity_smoother unavailable: {prefix.stderr.strip()}")
        sys.exit(3)
    rclpy.init()
    node = rclpy.create_node("_t34_limiter_probe")
    process = None
    samples = []
    publisher = node.create_publisher(Twist, "/t34_probe/keyboard_input", 10)
    node.create_subscription(Twist, "/t34_probe/output",
                             lambda msg: samples.append((time.monotonic(), msg)), 10)

    def spin_for(seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.01)

    def check_stop(last_input: float, limit: float) -> float:
        assert samples, "no limiter output"
        for _, msg in samples:
            assert abs(msg.linear.x) <= 0.05001 and abs(msg.angular.z) <= 0.15001
            assert (msg.linear.y, msg.linear.z, msg.angular.x, msg.angular.y) == (0.0, 0.0, 0.0, 0.0)
        zeros = [t for t, msg in samples if t >= last_input and abs(msg.linear.x) < 1e-6 and abs(msg.angular.z) < 1e-6]
        assert zeros, "no zero output after input stops"
        delay = zeros[0] - last_input
        assert delay <= limit, f"zero output too late: {delay:.3f}s > {limit}s"
        assert all(abs(msg.linear.x) < 1e-6 and abs(msg.angular.z) < 1e-6
                   for t, msg in samples if t >= zeros[0]), "motion resumed after zero"
        return delay

    try:
        spin_for(1)
        occupied = subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], capture_output=True, text=True, timeout=35)
        assert occupied.returncode == 1 and node.get_name() in occupied.stderr, "guard missed a real hidden node"
        print("PASS: real hidden-node occupancy refused", flush=True)
        if set(node.get_node_names()) != {node.get_name()}:
            raise RuntimeError("REFUSED: domain became occupied")
        arguments = [
            "ros2", "run", "nav2_velocity_smoother", "velocity_smoother", "--ros-args",
            "-r", "__ns:=/t34_probe", "-r", "cmd_vel:=keyboard_input", "-r", "cmd_vel_smoothed:=output",
            "-p", "smoothing_frequency:=20.0", "-p", "feedback:=OPEN_LOOP",
            "-p", "max_velocity:=[0.05,0.0,0.15]", "-p", "min_velocity:=[-0.05,0.0,-0.15]",
            "-p", "max_accel:=[0.1,0.0,0.3]", "-p", "max_decel:=[-0.2,0.0,-0.6]",
            "-p", "velocity_timeout:=0.25", "-p", "use_sim_time:=false",
        ]
        with (REPO / "log/t34-smoother.log").open("w") as log:
            process = subprocess.Popen(arguments, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            client = node.create_client(ChangeState, "/t34_probe/velocity_smoother/change_state")
            assert client.wait_for_service(timeout_sec=8), "no lifecycle service"
            for transition in (Transition.TRANSITION_CONFIGURE, Transition.TRANSITION_ACTIVATE):
                request = ChangeState.Request()
                request.transition.id = transition
                future = client.call_async(request)
                rclpy.spin_until_future_complete(node, future, timeout_sec=5)
                assert future.done() and future.result().success, f"transition failed: {transition}"
            spin_for(0.5)
            assert publisher.get_subscription_count() == 1
            assert node.count_publishers("/t34_probe/output") == 1
            for x, z in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1)):
                for explicit in (False, True):
                    samples.clear()
                    command = Twist()
                    command.linear.x, command.angular.z = float(x), float(z)
                    for _ in range(8):
                        publisher.publish(command)
                        last_input = time.monotonic()
                        spin_for(0.1)
                    assert any((not x or x * msg.linear.x >= 0.049) and
                               (not z or z * msg.angular.z >= 0.149) for _, msg in samples), "no correctly signed capped motion"
                    if explicit:
                        publisher.publish(Twist())
                        last_input = time.monotonic()
                    spin_for(1)
                    delay = check_stop(last_input, 0.65)
                    print(f"PASS input=({x},{z}) explicit_zero={explicit}: zero after {delay:.3f}s", flush=True)
            if "--teleop" in sys.argv:
                from test_teleop import run_pipeline
                node.destroy_publisher(publisher)
                run_pipeline(node, samples, spin_for, check_stop)
            print("PASS: software velocity limits and timeout; physical braking NOT tested", flush=True)
    finally:
        if process is not None:
            stop_process(process)
        node.destroy_node()
        rclpy.shutdown()
    result = subprocess.run([sys.executable, str(REPO / "bench/t34_guard.py")], check=False)
    assert result.returncode == 0, "owned test nodes did not leave the domain empty"


if __name__ == "__main__":
    main()
