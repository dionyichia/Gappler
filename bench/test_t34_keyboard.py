"""Test real keyboard input and bench startup readiness without importing ROS."""
import ast
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import termios
import tty
from types import SimpleNamespace
from typing import Callable
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "nav/simple_teleop/simple_teleop/teleop_node.py"
BENCH = Path(__file__).resolve().parent / "nodes/test_teleop.py"


class KeyboardTests(unittest.TestCase):
    def test_burst_does_not_hide_stop_quit_or_interrupt(self):
        tree = ast.parse(SOURCE.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_get_key")
        namespace = {"select": select, "sys": sys, "os": os}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), namespace)
        get_key = namespace["_get_key"]
        master, slave = pty.openpty()
        original = termios.tcgetattr(slave)
        terminal = os.fdopen(os.dup(slave), "r")
        try:
            tty.setraw(slave)
            with patch("sys.stdin", terminal):
                self.assertEqual(get_key(), "")
                os.write(master, b"wxq\x03")
                self.assertEqual(get_key(), "w")
                self.assertEqual(get_key(), "x")
                self.assertEqual(get_key(), "q")
                with self.assertRaises(KeyboardInterrupt):
                    get_key()
        finally:
            termios.tcsetattr(slave, termios.TCSADRAIN, original)
            terminal.close()
            os.close(master)
            os.close(slave)


class KeyboardStartupTests(unittest.TestCase):
    def readiness(self, clock: list[float]) -> Callable:
        """Load the real wait function, with a deterministic clock and no ROS import."""
        tree = ast.parse(BENCH.read_text())
        function = next((node for node in tree.body if isinstance(node, ast.FunctionDef)
                         and node.name == "_wait_for_keyboard_startup"), None)
        self.assertIsNotNone(function, "bounded keyboard-readiness gate missing")
        namespace = {"subprocess": subprocess, "Callable": Callable,
                     "time": SimpleNamespace(monotonic=lambda: clock[0])}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(BENCH), "exec"), namespace)
        return namespace["_wait_for_keyboard_startup"]

    def test_delayed_first_message_starts_measurement_after_readiness(self) -> None:
        clock, raw = [0.0], []

        def spin_for(seconds: float) -> None:
            clock[0] += seconds
            if clock[0] >= 1.944:
                raw.append((clock[0], None))

        self.readiness(clock)(SimpleNamespace(poll=lambda: None), raw, spin_for)
        self.assertGreaterEqual(clock[0], 1.944)
        self.assertLess(clock[0], 2.0)
        self.assertTrue(raw)

    def test_silent_startup_times_out(self) -> None:
        clock = [0.0]

        def spin_for(seconds: float) -> None:
            clock[0] += seconds

        with self.assertRaisesRegex(TimeoutError, "keyboard.*publish"):
            self.readiness(clock)(SimpleNamespace(poll=lambda: None), [], spin_for, timeout=0.2)
        self.assertAlmostEqual(clock[0], 0.2)

    def test_startup_exit_is_reported(self) -> None:
        clock, waits = [0.0], []
        with self.assertRaisesRegex(RuntimeError, "keyboard.*exited.*3"):
            self.readiness(clock)(SimpleNamespace(poll=lambda: 3), [], waits.append)
        self.assertEqual(waits, [])

    def test_pipeline_uses_readiness_instead_of_fixed_startup_sleep(self) -> None:
        tree = ast.parse(BENCH.read_text())
        pipeline = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                        and node.name == "run_pipeline")
        calls = [node for node in ast.walk(pipeline) if isinstance(node, ast.Call)]
        self.assertTrue(any(isinstance(node.func, ast.Name)
                            and node.func.id == "_wait_for_keyboard_startup" for node in calls))
        self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id == "spin_for"
                             and node.args and isinstance(node.args[0], ast.Constant)
                             and node.args[0].value == 1.5 for node in calls))


if __name__ == "__main__":
    unittest.main()
