#!/usr/bin/env bash
# L0 -- every memory graph unit test, including the real image-feature model (T6.3f).
# The stage tests need numpy and scipy, and test_clip_encoder.py needs open_clip, torch
# and the ViT-B-32 weights, so this runs with the project's .venv, not the system python.
#
#   ./bench/memory_graph_tests.sh [PYTHON]    default PYTHON: .venv/bin/python (uv sync)
#
# Fetch the weights once with: .venv/bin/python -m memory_graph.clip_encoder
# No ROS, no robot, no network: nothing is downloaded here.
# Exit: 0 every test ran and passed, 1 a test failed, 3 SKIPPED -- never a pass.
# One skipped test makes the whole step SKIPPED, because that test did not check anything.
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${1:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || { echo "SKIP: no $PY -- run uv sync"; exit 3; }
cd "$REPO"
"$PY" - <<'PYEOF'
import sys
import unittest

suite = unittest.defaultTestLoader.discover("memory_graph/tests", top_level_dir=".")
result = unittest.TextTestRunner(verbosity=1).run(suite)
if not result.wasSuccessful():
    sys.exit(1)
for test, reason in result.skipped:
    print(f"SKIP: {test}: {reason}")
sys.exit(3 if result.skipped else 0)
PYEOF
