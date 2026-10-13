"""Keep T3.4 checks and existing dev suites when resolving runner merges."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]


class BenchCoverageTests(unittest.TestCase):
    def test_l4_keeps_t34_and_dev_suites_once(self) -> None:
        runner = (REPO / "bench/run.sh").read_text()
        loops = re.findall(r"for t in ([\w ]+); do", runner)
        self.assertEqual(len(loops), 1)
        suites = loops[0].split()
        required = {"sim_moveit", "estop_delivery", "state_machine_sim", "nav_nodes",
                    "velocity_smoother", "anygrasp_env", "anygrasp_replay",
                    "segmentation_service"}
        self.assertTrue(required.issubset(suites), required - set(suites))
        self.assertEqual(len(suites), len(set(suites)))
        for suite in suites:
            self.assertTrue((REPO / "bench" / f"{suite}.sh").is_file(), suite)

    def test_l0_keeps_t34_and_dev_checks_once(self) -> None:
        runner = (REPO / "bench/run.sh").read_text()
        for script in ("memory_graph_tests.sh", "test_segmentation_logic.py",
                       "test_t34_guard.py", "test_t34_keyboard.py", "test_t34_launch.py",
                       "test_command_ownership.py", "test_t34_bench_coverage.py"):
            self.assertEqual(runner.count(script), 1, script)


if __name__ == "__main__":
    unittest.main()
