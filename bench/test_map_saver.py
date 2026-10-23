"""Snapshot publication and image validation must not overwrite existing maps."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import sys
import os
import signal
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("save_slam_map", REPO / "nav/robot_slam/scripts/save_slam_map.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MapSaverTests(unittest.TestCase):
    def test_repeated_signals_cannot_interrupt_child_cleanup(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True)

        def interrupt(signum, frame):
            raise KeyboardInterrupt

        handlers = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}

        class RepeatedSignals:
            pid = child.pid

            def wait(self, timeout):
                signal.raise_signal(signal.SIGINT)
                signal.raise_signal(signal.SIGTERM)
                return child.wait(timeout=timeout)

        try:
            module.stop_image_saver(RepeatedSignals())
            self.assertIsNotNone(child.poll())
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=3)

    def test_requires_stationary_ack_before_ros_or_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "not-created"
            result = subprocess.run([sys.executable, str(REPO / "nav/robot_slam/scripts/save_slam_map.py"),
                                     "--output-root", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("--stationary", result.stderr)
            self.assertFalse(output.exists())

    def fixture(self, folder):
        (folder / "completed_map.posegraph").write_bytes(b"test graph")
        (folder / "completed_map.data").write_bytes(b"test data")
        (folder / "current_map.pgm").write_bytes(b"P5\n# fixture\n2 1\n255\n\x00\xfe")
        (folder / "current_map.yaml").write_text("image: current_map.pgm\nresolution: 0.05\norigin: [0, 0, 0]\n")

    def test_publish_new_directory(self):
        with tempfile.TemporaryDirectory(prefix="maps with spaces ") as directory:
            root = Path(directory)
            partial = root / ".partial-test"
            partial.mkdir()
            self.fixture(partial)
            final = root / "session-test"
            module.publish_snapshot(partial, final)
            self.assertFalse(partial.exists())
            self.assertTrue((final / "completed_map.data").is_file())

    def test_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            final = root / "session-test"
            final.mkdir()
            (final / "keep").write_bytes(b"original")
            partial = root / ".partial-test"
            partial.mkdir()
            with self.assertRaises(FileExistsError):
                module.publish_snapshot(partial, final)
            self.assertEqual((final / "keep").read_bytes(), b"original")
            self.assertTrue(partial.exists())

    @unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML unavailable; validation runs on box")
    def test_rejects_invalid_image_reference_and_raster(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.fixture(folder)
            module.validate_snapshot(folder, 2, 1, 0.05)
            for image in ("../outside.pgm", "/outside.pgm", "missing.pgm"):
                (folder / "current_map.yaml").write_text(f"image: {image}\nresolution: 0.05\norigin: [0, 0, 0]\n")
                with self.assertRaises(ValueError):
                    module.validate_snapshot(folder, 2, 1, 0.05)
            self.fixture(folder)
            (folder / "current_map.pgm").write_bytes(b"P5\n2 1\n255\n\x00")
            with self.assertRaisesRegex(ValueError, "raster"):
                module.validate_snapshot(folder, 2, 1, 0.05)


if __name__ == "__main__":
    unittest.main()
