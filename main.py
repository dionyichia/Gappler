#!/usr/bin/env python3
"""
Top-level entry point.
Launches orchestrator and AriaApplication in parallel.
"""

import subprocess
import sys
import signal
from pathlib import Path

ROOT = Path(__file__).parent
ORCHESTRATOR_PATH = ROOT / "ros2_robot_ws" / "src" / "orchestrator.py"
ARIA_APP_PATH = ROOT / "src" / "main.py"

processes = []


def shutdown(sig=None, frame=None):
    print("\n[root] Shutting down all processes...")
    for label, p in processes:
        if p.poll() is None:
            print(f"[root] Terminating {label}...")
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    sys.exit(0)


def launch(cmd, label):
    print(f"[root] Launching {label}...")
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    processes.append((label, p))
    return p


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    launch(["python3", str(ARIA_APP_PATH)], label="aria_app")
    launch(["python3", str(ORCHESTRATOR_PATH)], label="orchestrator")

    # Wait — if either process dies unexpectedly, shut everything down
    while True:
        for label, p in processes:
            if p.poll() is not None:
                print(f"[root] {label} exited unexpectedly (code {p.returncode})")
                shutdown()


if __name__ == "__main__":
    main()
