"""Test the real input function under a PTY without importing ROS."""
import ast
import os
from pathlib import Path
import pty
import select
import sys
import termios
import tty
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "nav/simple_teleop/simple_teleop/teleop_node.py"


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


if __name__ == "__main__":
    unittest.main()
