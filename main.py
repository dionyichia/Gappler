#!/usr/bin/env python3
"""
Top-level entry point.
Launches orchestrator and AriaApplication in parallel.
Ctrl+C shuts down the launchers. For the arm emergency stop,
run arm/estop/ in its own terminal.
"""

import os
import signal
import subprocess
import sys
import time

from gappler_common import ROOT

ORCHESTRATOR_PATH = ROOT / "launchers" / "grasp_orchestrator.py"
ARIA_APP_PATH = ROOT / "aria" / "aria_app" / "main.py"
# The uv venv lives at the repo root. "uv sync" creates it on a fresh clone.
ARIA_PYTHON = ROOT / ".venv" / "bin" / "python"

processes = []


def launch(
    cmd: list, label: str, delay: float = 0.0, cwd: str = None, env: dict = None
) -> subprocess.Popen:
    if delay > 0:
        print(f"[root] Waiting {delay}s before launching {label}...")
        time.sleep(delay)
    print(f"[root] Launching: {label}")
    p = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, cwd=cwd, env=env)
    processes.append((label, p))
    return p


def shutdown(signum=None, frame=None):
    print("\n[root] Shutting down all processes...")
    for label, p in reversed(processes):
        print(f"[root] Terminating: {label}")
        p.terminate()
    for label, p in reversed(processes):
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print(f"[root] Force killing: {label}")
            p.kill()
    print("[root] All processes stopped.")
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


if __name__ == "__main__":
    launch(["python3", str(ORCHESTRATOR_PATH)], label="orchestrator")
    launch(
        [str(ARIA_PYTHON), str(ARIA_APP_PATH)],
        label="aria_app",
        env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "aria" / "aria_app")
            + os.pathsep
            + os.environ.get("PYTHONPATH", ""),
        },
    )

    print("[root] Running — Ctrl+C shuts down launchers. Arm e-stop: arm/estop/ (separate terminal).")

    try:
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        pass
    finally:
        for label, p in processes:
            if p.poll() is not None:
                print(f"[root] '{label}' exited unexpectedly (code {p.returncode})")
                shutdown()
        print("[orchestrator] Terminated")
