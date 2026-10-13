"""Keep both navigation and shared-service checks when updating the bench runner."""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]


class BenchCoverageTests(unittest.TestCase):
    def test_l4_keeps_both_suite_lists_without_duplicates(self) -> None:
        runner = (REPO / "bench/run.sh").read_text()
        loops = re.findall(r"for t in ([\w ]+); do", runner)
        self.assertEqual(len(loops), 1, "expected one resolved L4 suite loop")
        suites = loops[0].split()
        required = {"sim_moveit", "estop_delivery", "state_machine_sim", "nav_nodes",
                    "velocity_smoother", "cloud_scan", "slam_persistence",
                    "anygrasp_env", "anygrasp_replay", "segmentation_service"}
        self.assertTrue(required.issubset(suites), required - set(suites))
        self.assertEqual(len(suites), len(set(suites)), "duplicate L4 suite")
        for suite in suites:
            self.assertTrue((REPO / "bench" / f"{suite}.sh").is_file(), suite)

    def test_l0_keeps_navigation_and_shared_service_checks(self) -> None:
        runner = (REPO / "bench/run.sh").read_text()
        for script in ("memory_graph_tests.sh", "test_segmentation_logic.py",
                       "test_command_ownership.py", "test_cloud_scan.py",
                       "test_slam_maps.py", "test_map_saver.py"):
            self.assertEqual(runner.count(script), 1, script)


if __name__ == "__main__":
    unittest.main()
