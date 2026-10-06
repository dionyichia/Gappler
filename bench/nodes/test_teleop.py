"""Pseudo-terminal tests of the real keyboard loop and downstream smoother."""
import os
from pathlib import Path
import pty
import signal
import subprocess
import sys
import termios
import time

from geometry_msgs.msg import Twist
from test_velocity_smoother import stop_process

REPO = Path(__file__).resolve().parents[2]


def run_pipeline(node, samples, spin_for, check_stop) -> None:
    """Exercise terminal input, silence and exits without a chassis subscriber."""
    raw = []
    subscription = node.create_subscription(
        Twist, "/t34_probe/keyboard_input",
        lambda msg: raw.append((time.monotonic(), msg)), 10,
    )
    try:
        for exit_mode in ("q", "ctrl_c", "sigint", "crash"):
            master, slave = pty.openpty()
            original = termios.tcgetattr(slave)
            process = None
            try:
                with (REPO / f"log/t34-teleop-{exit_mode}.log").open("w") as log:
                    process = subprocess.Popen([
                        sys.executable, str(REPO / "nav/simple_teleop/simple_teleop/teleop_node.py"),
                        "--ros-args", "-r", "__ns:=/t34_probe", "-r", "cmd_vel:=keyboard_input",
                        "-p", "speed:=0.05", "-p", "turn:=0.15", "-p", "key_timeout:=0.25",
                    ], stdin=slave, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    spin_for(1.5)
                    assert process.poll() is None, "teleop exited during startup"
                    raw.clear()
                    spin_for(1.1)
                    assert len(raw) >= 9, "keyboard read blocks 10 Hz publication during silence"
                    periods = [raw[i][0] - raw[i - 1][0] for i in range(1, len(raw))]
                    rate = (len(raw) - 1) / (raw[-1][0] - raw[0][0])
                    assert 8 <= rate <= 12 and max(periods) <= 0.2, f"publication not near 10 Hz: {rate:.2f} Hz"
                    print(f"PASS teleop {exit_mode}: idle publication {rate:.2f} Hz", flush=True)
                    assert all(msg.linear.x == 0 and msg.angular.z == 0 for _, msg in raw), "idle startup not zero"
                    assert node.count_publishers("/t34_probe/keyboard_input") == 1, "unexpected command publisher"
                    for key, x, z in (("w", 1, 0), ("s", -1, 0), ("a", 0, 1), ("d", 0, -1)):
                        samples.clear()
                        raw.clear()
                        for _ in range(8):
                            os.write(master, key.encode())
                            last_key = time.monotonic()
                            spin_for(0.1)
                        assert any((not x or x * msg.linear.x >= 0.049) and
                                   (not z or z * msg.angular.z >= 0.149) for _, msg in samples), "wrong movement direction or absent output"
                        spin_for(1.1)
                        delay = check_stop(last_key, 1.0)
                        zeros = [t for t, msg in raw if t >= last_key and msg.linear.x == 0 and msg.angular.z == 0]
                        assert zeros and zeros[0] - last_key <= 0.4, "keyboard inactivity did not zero requested velocity"
                        assert all(abs(msg.linear.x) <= 0.05001 and abs(msg.angular.z) <= 0.15001 for _, msg in raw)
                        print(f"PASS teleop {exit_mode}/{key}: silence → zero after {delay:.3f}s", flush=True)
                    for action in ("x", exit_mode):
                        samples.clear()
                        raw.clear()
                        for _ in range(8):
                            os.write(master, b"w")
                            spin_for(0.1)
                        assert any(msg.linear.x >= 0.049 for _, msg in samples), "stop test never moved"
                        stopped = time.monotonic()
                        if action == "sigint":
                            os.killpg(process.pid, signal.SIGINT)
                        elif action == "crash":
                            os.killpg(process.pid, signal.SIGKILL)
                        else:
                            os.write(master, {"x": b"x", "q": b"q", "ctrl_c": b"\x03"}[action])
                        spin_for(1)
                        delay = check_stop(stopped, 0.65)
                        if action != "crash":
                            assert any(stopped <= t <= stopped + 0.2 and
                                       msg.linear.x == 0 and msg.angular.z == 0 for t, msg in raw), \
                                f"no prompt raw zero for {action}; smoother timeout could hide a missing final publish"
                        print(f"PASS teleop {action}: zero after {delay:.3f}s", flush=True)
                    expected = -signal.SIGKILL if exit_mode == "crash" else 0
                    assert process.wait(timeout=3) == expected, f"unexpected exit: {process.returncode}"
                    if exit_mode != "crash":
                        assert termios.tcgetattr(slave) == original, "terminal settings not restored"
            finally:
                if process is not None:
                    stop_process(process)
                os.close(master)
                os.close(slave)
                spin_for(0.5)
        for parameter in ("speed:=-0.1", "turn:=-0.1", "key_timeout:=0.0"):
            master, slave = pty.openpty()
            original = termios.tcgetattr(slave)
            process = None
            try:
                with (REPO / "log/t34-teleop-invalid.log").open("w") as log:
                    process = subprocess.Popen([
                        sys.executable, str(REPO / "nav/simple_teleop/simple_teleop/teleop_node.py"),
                        "--ros-args", "-r", "__ns:=/t34_probe", "-r", "cmd_vel:=keyboard_input",
                        "-p", parameter,
                    ], stdin=slave, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                    assert process.wait(timeout=5) != 0, f"invalid parameter accepted: {parameter}"
                    assert termios.tcgetattr(slave) == original
                print(f"PASS rejected invalid teleop parameter {parameter}", flush=True)
            finally:
                if process is not None:
                    stop_process(process)
                os.close(master)
                os.close(slave)
    finally:
        node.destroy_subscription(subscription)


if __name__ == "__main__":
    from test_velocity_smoother import main
    sys.argv.append("--teleop")
    main()
