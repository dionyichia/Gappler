#!/usr/bin/env python3
"""
Top-level entry point.
Launches orchestrator and AriaApplication in parallel.
Press 'q' or Ctrl+C for emergency stop.
"""

import subprocess
import sys
import signal
import time
from pathlib import Path

ROOT = Path(__file__).parent
ORCHESTRATOR_PATH = ROOT / "ros2_robot_ws" / "src" / "orchestrator.py"
ARIA_APP_PATH = ROOT / "src" / "main.py"

processes = []


def shutdown(sig=None, frame=None):
    print("\n[root] EMERGENCY STOP — killing all processes...")
    for label, p in processes:
        if p.poll() is None:
            print(f"[root] Terminating {label}...")
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"[root] Force killing {label}...")
                p.kill()
    print("[root] All processes stopped.")
    sys.exit(0)


def launch(cmd, label):
    print(f"[root] Launching {label}...")
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    processes.append((label, p))
    return p


def main():
    # Register OS-level signals
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    launch(["python3", str(ARIA_APP_PATH)], label="aria_app")
    launch(["python3", str(ORCHESTRATOR_PATH)], label="orchestrator")

    print("[root] Running — press 'q' for emergency stop.")

    from src.utils import TerminalRawMode, exit_keypress

    with TerminalRawMode():
        while True:
            # Emergency stop on 'q'
            if exit_keypress():
                print("\n[root] 'q' pressed — emergency stop triggered.")
                shutdown()

            # Watchdog — if either child dies unexpectedly, stop everything
            for label, p in processes:
                if p.poll() is not None:
                    print(f"[root] '{label}' exited unexpectedly (code {p.returncode})")
                    shutdown()

            time.sleep(0.1)


if __name__ == "__main__":
    main()
