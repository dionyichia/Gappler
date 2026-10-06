"""Fail-closed discovery checks, without requiring ROS or hardware."""
import subprocess
import json
import unittest
from unittest.mock import patch

from t34_guard import check_domain


class GuardTests(unittest.TestCase):
    def test_only_private_local_domain_allowed(self):
        for domain, local in (("0", "1"), ("91", "1"), ("127", "0"), ("bad", "1")):
            with self.subTest(domain=domain, local=local):
                with patch("t34_guard.subprocess.run") as run:
                    with self.assertRaises(RuntimeError):
                        check_domain(domain, local)
                    run.assert_not_called()

    def test_empty_graph_passes(self):
        result = subprocess.CompletedProcess([], 0, json.dumps({"nodes": [], "topics": ["/rosout", "/parameter_events"]}), "")
        with patch("t34_guard.subprocess.run", return_value=result) as run:
            check_domain("127", "1")
            self.assertEqual(run.call_count, 1)
            self.assertIn("--discover", run.call_args.args[0])

    def test_nodes_or_hidden_topics_refused(self):
        graphs = [(["/_hidden_node"], []), ([], ["/action/_action/status"])]
        for nodes, topics in graphs:
            result = subprocess.CompletedProcess([], 0, json.dumps({"nodes": nodes, "topics": topics}), "")
            with patch("t34_guard.subprocess.run", return_value=result):
                with self.assertRaises(RuntimeError):
                    check_domain("127", "1")

    def test_discovery_failure_is_not_empty(self):
        with patch("t34_guard.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "DDS failure")):
            with self.assertRaisesRegex(RuntimeError, "discovery"):
                check_domain("127", "1")
        with patch("t34_guard.subprocess.run", side_effect=subprocess.TimeoutExpired("ros2", 15)):
            with self.assertRaisesRegex(RuntimeError, "discovery"):
                check_domain("127", "1")
        with patch("t34_guard.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "warning")):
            with self.assertRaisesRegex(RuntimeError, "discovery"):
                check_domain("127", "1")
        for snapshot in ("", "{}", '{"nodes": "bad", "topics": []}'):
            with patch("t34_guard.subprocess.run", return_value=subprocess.CompletedProcess([], 0, snapshot, "")):
                with self.assertRaisesRegex(RuntimeError, "discovery"):
                    check_domain("127", "1")


if __name__ == "__main__":
    unittest.main()
