#!/usr/bin/env python3
"""
Preflight: is this machine capable of running the stack, and is the hardware there?

Two separate questions, run separately:

  * default      L2: can this machine run L3-L4 (build + simulation)? No robot needed.
  * --hardware   L5: is the robot there? Arm, LiDAR, wrist camera, glasses and the live
                 ROS graph. Gates L6, the arm test a person runs at the robot.

Exit: 0 all pass, 1 any fail. With --hardware, 3 (skipped) when the arm does not answer,
because with no arm there is nothing for L6 to test.

Runs everything that can be checked WITHOUT commanding the arm. The boundary is
absolute and is enforced in code (see SAFETY below): this script never publishes
to a /rm_driver/*_cmd topic and never launches grasp_state_machine or
ros2_robot_ws/src/main.py, because both home the arm within seconds of start
(ORIENTATION.md 8.1). Everything up to that line is fair game -- network,
drivers, TF tree, topic rates, model weights, licences, GPU.

Designed to run in two very different places and say clearly which one it is in:

  * a laptop (macOS / no ROS)  -> nearly everything SKIPs, with a reason each
  * the lab box (Ubuntu 22.04) -> the real bring-up check

Nothing here is destructive and nothing needs sudo. Read-only throughout.

    python3 bench/preflight.py              # L2: the machine
    python3 bench/preflight.py --hardware   # L5: the robot
    python3 bench/preflight.py -g net       # only one group
    python3 bench/preflight.py --json    # machine-readable

Stdlib only.
"""

from __future__ import annotations

import argparse
import getpass
import glob
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
from pathlib import Path

from _common import OWNED_PREFIXES

REPO = Path(__file__).resolve().parent.parent

# --- Facts read out of the repo, not out of the docs -----------------------
# rm_driver.cpp:4094,4097
ARM_IP, ARM_PORT = "192.168.1.18", 8080
ARM_UDP_HOST, ARM_UDP_PORT = "192.168.1.10", 8089
# livox_ros_driver2/config/MID360_config.json
LIDAR_IP = "192.168.1.3"
LIDAR_HOST_IP = "192.168.1.5"
# docs/archive/RCP_NEW_USER_STARTUP_GUIDE.md 1
ARM_NIC = "enp2s0"
ARIA_SERIAL = "1WM10350101291"
# docs/archive/RCP_NEW_USER_STARTUP_GUIDE.md 4, T5 -- the expected arm->camera transform
TF_EXPECT = {("base_link", "camera_color_optical_frame"): (-0.100, -0.049, 0.728)}
TF_TOL = 0.05
CAMERA_HZ_RANGE = (8.0, 20.0)          # guide says 13-14 Hz

# The D435i's own USB product id. Matching "Intel" or "8086" alone is wrong: the
# box's AX201 Bluetooth adapter is also "8087:0026 Intel Corp." and would pass.
RS_USB_IDS = ("8086:0b3a",)            # D435i. Other RealSense models would be added here
RS_USB_NAME = "realsense"              # the description, lower-cased
# V4L2 pixel formats, by what the D435i exposes them for
RS_V4L2_COLOUR = ("YUYV", "MJPG")
RS_V4L2_DEPTH = ("Z16 ",)              # trailing space: 'Z16 ' is the fourcc, 'Z16' matches nothing else

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"


class Check:
    def __init__(self, group: str, name: str, why: str):
        self.group, self.name, self.why = group, name, why
        self.status = SKIP
        self.detail = ""
        self.reason = ""      # only for SKIP: why it could not run
        self.fix = ""         # what to do about a FAIL

    def ok(self, detail=""):     self.status, self.detail = PASS, detail; return self
    def bad(self, d="", fix=""): self.status, self.detail, self.fix = FAIL, d, fix; return self
    def warn(self, d="", fix=""):self.status, self.detail, self.fix = WARN, d, fix; return self
    def skip(self, reason):      self.status, self.reason = SKIP, reason; return self


def sh(cmd: list[str] | str, timeout=10) -> tuple[int, str]:
    """Run a command, return (rc, combined output). Never raises.

    On timeout the whole process group gets SIGINT, then SIGKILL, and whatever
    it printed so far comes back with rc 124. `ros2 topic hz` and `tf2_echo`
    never exit on their own, so their output only ever arrives this way; and
    `ros2 run` puts the real process one level down, where a plain kill would
    leave it running. PYTHONUNBUFFERED stops a piped ros2 CLI holding its
    output in a buffer that dies with it.
    """
    try:
        p = subprocess.Popen(cmd, shell=isinstance(cmd, str), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, start_new_session=True,
                             env=dict(os.environ, PYTHONUNBUFFERED="1"))
    except FileNotFoundError:
        return 127, "not found"
    except Exception as e:                                     # noqa: BLE001
        return 1, str(e)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, (out or "").strip()
    except subprocess.TimeoutExpired:
        pass
    out = ""
    for sig in (signal.SIGINT, signal.SIGKILL):
        try:
            os.killpg(p.pid, sig)
        except ProcessLookupError:
            pass
        try:
            out, _ = p.communicate(timeout=3)   # retrying communicate loses no output
            break
        except subprocess.TimeoutExpired:
            continue
    return 124, (out or "").strip()


def _exists(p) -> bool:
    """Path.exists() RAISES PermissionError under a locked parent on Python < 3.12
    -- e.g. /home/iot22/... read as rcp2026. Here, unreachable counts as absent."""
    try:
        return Path(p).exists()
    except OSError:
        return False


def _exists_or_prefix(p) -> bool:
    """True if p exists, or p is a file-name prefix with siblings (slam_toolbox's
    map_file_name `completed_map` is stored as completed_map.posegraph + .data)."""
    if _exists(p):
        return True
    q = Path(p)
    try:
        return q.parent.is_dir() and any(x.name.startswith(q.name + ".") for x in q.parent.iterdir())
    except OSError:
        return False


def is_linux() -> bool:
    return platform.system() == "Linux"


LAB_OVERRIDE: bool | None = None     # --lab / --no-lab


def on_lab_machine() -> bool:
    """Is this plausibly the robot's workstation, rather than someone's laptop?

    This matters for honesty in the output: on a laptop, "sam3.pt is missing" and
    "the arm does not answer" are not failures, they are questions that cannot be
    asked here. Reporting them as FAIL would train people to ignore red.
    """
    if LAB_OVERRIDE is not None:
        return LAB_OVERRIDE
    return is_linux() and (Path("/opt/ros/humble").exists() or bool(shutil.which("nvidia-smi")))


def on_arm_subnet() -> bool:
    if not (is_linux() and shutil.which("ip")):
        return False
    rc, out = sh(["ip", "-4", "addr"], timeout=8)
    return rc == 0 and bool(re.search(r"inet 192\.168\.1\.\d+", out))


NOT_LAB = ("not the lab workstation (no ROS, no NVIDIA GPU) -- "
           "this can only be judged on the robot's machine")
NOT_SUBNET = ("this host has no address on 192.168.1.0/24, so the arm and LiDAR "
              "cannot be reached from here by definition")


def ros_env() -> bool:
    return Path("/opt/ros/humble").exists() or bool(os.environ.get("ROS_DISTRO"))


def ros_graph_up() -> bool:
    """Is there a live ROS graph to interrogate? Cheap and read-only."""
    if not shutil.which("ros2"):
        return False
    rc, out = sh(["ros2", "node", "list"], timeout=12)
    return rc == 0 and bool(out.strip())


# ===========================================================================
# GROUP: host
# ===========================================================================

def g_host() -> list[Check]:
    cs = []

    c = Check("host", "platform", "which machine this is deciding everything below")
    cs.append(c.ok(f"{platform.system()} {platform.release()} {platform.machine()}"))

    c = Check("host", "ram", "SAM 3 (3.4 GB) + AnyGrasp + Nav2 need headroom; 16 GB is the floor")
    total = avail = None
    if is_linux() and Path("/proc/meminfo").exists():
        mi = dict(re.findall(r"^(\w+):\s+(\d+) kB", Path("/proc/meminfo").read_text(), re.M))
        total = int(mi.get("MemTotal", 0)) / 1024**2
        avail = int(mi.get("MemAvailable", 0)) / 1024**2
    elif platform.system() == "Darwin":
        rc, out = sh(["sysctl", "-n", "hw.memsize"])
        if rc == 0 and out.isdigit():
            total = int(out) / 1024**3
    if total is None:
        cs.append(c.skip("cannot read memory size on this platform"))
    else:
        d = f"{total:.1f} GB total" + (f", {avail:.1f} GB available" if avail else "")
        cs.append(c.ok(d) if total >= 15 else c.warn(d, "16 GB+ recommended"))

    c = Check("host", "disk", "model weights and four colcon build trees are large")
    try:
        st = os.statvfs(REPO)
        free = st.f_bavail * st.f_frsize / 1024**3
        d = f"{free:.1f} GB free at {REPO}"
        cs.append(c.ok(d) if free >= 20 else c.warn(d, "builds + weights need ~20 GB"))
    except Exception as e:                                     # noqa: BLE001
        cs.append(c.skip(str(e)))

    c = Check("host", "cpu", "colcon build of MoveIt + MTC is CPU bound")
    cs.append(c.ok(f"{os.cpu_count()} cores"))
    return cs


# ===========================================================================
# GROUP: gpu
# ===========================================================================

def g_gpu() -> list[Check]:
    cs = []

    c = Check("gpu", "nvidia-driver", "SAM 3 and AnyGrasp are CUDA-only in this stack")
    if not shutil.which("nvidia-smi"):
        cs.append(c.skip("nvidia-smi not present (no NVIDIA GPU, or not a Linux host)"))
        cs.append(Check("gpu", "vram", "SAM 3 + AnyGrasp + a VLM contend for VRAM")
                  .skip("no NVIDIA GPU detected"))
    else:
        rc, out = sh(["nvidia-smi",
                      "--query-gpu=name,driver_version,memory.total,memory.used",
                      "--format=csv,noheader"])
        if rc != 0:
            cs.append(c.bad(out, "driver installed but not responding; check `nvidia-smi`"))
            cs.append(Check("gpu", "vram", "VRAM headroom").skip("nvidia-smi failed"))
        else:
            first = out.splitlines()[0]
            cs.append(c.ok(first))
            m = re.search(r"(\d+)\s*MiB,\s*(\d+)\s*MiB", first)
            c2 = Check("gpu", "vram", "SAM 3 + AnyGrasp + a VLM contend for VRAM")
            if m:
                tot, used = int(m.group(1)), int(m.group(2))
                d = f"{(tot-used)/1024:.1f} GB free of {tot/1024:.1f} GB"
                cs.append(c2.ok(d) if tot - used > 6000 else
                          c2.warn(d, "SAM 3 alone wants several GB"))
            else:
                cs.append(c2.skip("could not parse nvidia-smi memory output"))

    # ORIENTATION 8.5 / startup guide rule 3: ~/.local's torch is the CUDA build,
    # conda's is CPU-only. PYTHONNOUSERSITE=1 flips which one wins and breaks it.
    c = Check("gpu", "pythonnousersite",
              "PYTHONNOUSERSITE=1 forces conda's CPU-only torch -> libc10_cuda.so ImportError")
    v = os.environ.get("PYTHONNOUSERSITE")
    cs.append(c.bad(f"PYTHONNOUSERSITE={v}",
                    "unset it -- see docs/archive/RCP_NEW_USER_STARTUP_GUIDE.md 5.2") if v
              else c.ok("not set (correct)"))

    c = Check("gpu", "torch-cuda", "the interpreter that runs SAM 3 must see CUDA")
    venv_py = REPO / ".venv" / "bin" / "python"     # SAM 3 runs from the project venv
    py = str(venv_py) if venv_py.exists() else shutil.which("python3")
    if not py:
        cs.append(c.skip("no .venv and no python3 on PATH"))
    else:
        rc, out = sh([py, "-c",
                      "import torch;print(torch.__version__, torch.cuda.is_available())"],
                     timeout=90)
        if rc != 0:
            cs.append(c.skip(f"torch not importable by {py} ({out.splitlines()[-1][:70] if out else ''})"))
        else:
            ver, cuda = (out.split() + ["?"])[:2]
            cs.append(c.ok(f"torch {ver}, cuda={cuda}") if cuda == "True"
                      else c.warn(f"torch {ver}, cuda={cuda}", "CUDA build expected"))
    return cs


# ===========================================================================
# GROUP: ros
# ===========================================================================

def g_ros() -> list[Check]:
    cs = []

    c = Check("ros", "humble", "everything in ros2_robot_ws and Navigation_Module needs it")
    if Path("/opt/ros/humble").exists():
        cs.append(c.ok(f"/opt/ros/humble present, ROS_DISTRO={os.environ.get('ROS_DISTRO','<unsourced>')}"))
    else:
        cs.append(c.skip("no /opt/ros/humble -- not a ROS machine"))

    c = Check("ros", "colcon", "needed to build the three workspaces")
    cs.append(c.ok(shutil.which("colcon")) if shutil.which("colcon")
              else c.skip("colcon not on PATH"))

    # The four-install-spaces trap: env.sh and the startup guide are emphatic
    # that only the repo-root overlay is complete.
    c = Check("ros", "overlay", "only the repo-root install/ has rm_* AND MoveIt Task Constructor")
    spaces = [p for p in (REPO / "install", REPO / "ros2_robot_ws" / "install",
                          REPO / "deps_ws" / "install",
                          REPO / "ros2_robot_ws" / "src" / "install")
              if (p / "setup.bash").exists()]
    if not spaces:
        cs.append(c.skip("no install/ anywhere -- nothing has been built in this clone"))
    else:
        names = ", ".join(str(p.relative_to(REPO)) for p in spaces)
        root_ok = (REPO / "install" / "setup.bash").exists()
        has_mtc = (REPO / "install" / "moveit_task_constructor_core").exists()
        if root_ok and has_mtc:
            cs.append(c.ok(f"repo-root overlay present with MTC (also found: {names})"))
        elif root_ok:
            cs.append(c.warn(f"repo-root overlay present but no MTC in it ({names})",
                             "rebuild with `colcon build` FROM THE REPO ROOT"))
        else:
            cs.append(c.warn(f"only partial overlays: {names}",
                             "build from the repo root so both workspaces are discovered"))

    c = Check("ros", "no-double-source",
              "sourcing deps_ws/install on top of the root overlay duplicates every MTC .so")
    ament = os.environ.get("AMENT_PREFIX_PATH", "")
    if not ament:
        cs.append(c.skip("AMENT_PREFIX_PATH unset -- no overlay sourced in this shell"))
    else:
        dupes = [p for p in ament.split(":") if p.endswith("deps_ws/install") or "/deps_ws/" in p]
        both = dupes and str(REPO / "install") in ament
        cs.append(c.bad("both repo-root and deps_ws overlays are sourced",
                        "source only env.sh / the repo-root install") if both
                  else c.ok(f"{len(ament.split(':'))} prefixes, no duplicate MTC overlay"))

    c = Check("ros", "domain-id", "a mismatched ROS_DOMAIN_ID silently hides every topic")
    d = os.environ.get("ROS_DOMAIN_ID")
    cs.append(c.ok(f"ROS_DOMAIN_ID={d}") if d else c.ok("ROS_DOMAIN_ID unset (default 0)"))
    return cs


# ===========================================================================
# GROUP: env  (python environments)
# ===========================================================================

def g_env() -> list[Check]:
    cs = []

    c = Check("env", "venv", "the Aria SDK and SAM 3 live in the project venv")
    v = REPO / ".venv"
    if (v / "bin" / "python").exists():
        rc, out = sh([str(v / "bin" / "python"), "--version"])
        cs.append(c.ok(f"{v.relative_to(REPO)} -> {out}"))
    else:
        cs.append(c.skip("no .venv in this clone -- run `uv sync`"))

    # AnyGrasp's env is envs/anygrasp/.venv, built on top of .venv by envs/anygrasp/build.sh (W5).
    c = Check("env", "anygrasp-env",
              "AnyGrasp needs MinkowskiEngine (CUDA extension) next to torch")
    candidates = [REPO / "envs" / "anygrasp" / ".venv" / "bin" / "python", v / "bin" / "python"]
    found = [py for py in candidates if py.exists()]
    if not found:
        cs.append(c.skip("no project venv yet -- run `uv sync`, then ./envs/anygrasp/build.sh"))
    else:
        py = found[0]
        rc, out = sh([str(py), "-c", "import MinkowskiEngine as ME;print(ME.__version__)"],
                     timeout=60)
        where = py.parent.parent.relative_to(REPO)
        if rc == 0:
            cs.append(c.ok(f"MinkowskiEngine {out.strip()} in {where}"))
        else:
            cs.append(c.bad(f"MinkowskiEngine not importable from {where}",
                            "build it: ./envs/anygrasp/build.sh (about 20 min)"))

    return cs


# ===========================================================================
# GROUP: assets  (things not in git that the stack needs at runtime)
# ===========================================================================

def g_assets() -> list[Check]:
    cs = []
    lab = on_lab_machine()
    perception = REPO / "ros2_robot_ws/src/rm_mtc/src/perception"

    c = Check("assets", "sam3-weights", "3.4 GB checkpoint, gitignored")
    p = REPO / "src/models/sam3/sam3.pt"
    if p.exists():
        cs.append(c.ok(f"{p.stat().st_size/1024**3:.2f} GB"))
    elif not lab:
        cs.append(c.skip(NOT_LAB))
    else:
        cs.append(c.bad(f"missing: {p.relative_to(REPO)}", "copy it from the lab machine"))

    # The two AnyGrasp nodes want DIFFERENT checkpoints. The hardware-verified
    # run used the tracking one; ros2_robot_ws/src/main.py:30 launches the
    # detection one. Both are checked so the discrepancy is visible.
    for fn, who in (("checkpoint_detection.tar", "anygrasp_detection_node.py (what main.py launches)"),
                    ("checkpoint_tracking.tar", "anygrasp_node.py (what the 2026-08-25 session verified)")):
        c = Check("assets", f"anygrasp-{fn.split('_')[1].split('.')[0]}", f"needed by {who}")
        p = perception / "log" / fn
        if p.exists():
            cs.append(c.ok(f"{p.stat().st_size/1024**2:.0f} MB"))
        elif not lab:
            cs.append(c.skip(NOT_LAB))
        else:
            cs.append(c.bad(f"missing: log/{fn}", "gitignored; copy from the lab machine"))

    c = Check("assets", "anygrasp-licence", "machine-locked; a new machine needs re-registration")
    lic = perception / "license"
    files = sorted(x.name for x in lic.glob("*")) if lic.exists() else []
    if files:
        cs.append(c.ok(f"{len(files)} file(s): {', '.join(files)} "
                       f"(lock can only be verified by running the node)"))
    else:
        cs.append(c.bad("no licence files", "re-register with the vendor -- ~2 working days"))

    c = Check("assets", "anygrasp-so", "compiled binaries built against a pinned torch")
    sos = sorted(p.name for p in perception.glob("*.so"))
    cs.append(c.ok(", ".join(sos)) if sos else c.bad("no .so files in perception/"))

    c = Check("assets", "slam-map", "slam_localization reads a prebuilt map")
    ref = REPO / "Navigation_Module/src/robot_slam/config/slam_toolbox_localization.yaml"
    want = None
    if ref.exists():
        m = re.search(r"map_file_name:\s*(\S+)", ref.read_text())
        want = m.group(1) if m else None
    if not want:
        cs.append(c.skip("no map_file_name in slam_toolbox_localization.yaml"))
    else:
        exp = Path(os.path.expanduser(want))
        if _exists_or_prefix(exp):
            owner = exp.parts[2] if len(exp.parts) > 2 and exp.parts[1] == "home" else None
            note = (f" -- but in /home/{owner}, not this user's home"
                    if owner and not str(exp).startswith(f"{Path.home()}/") else "")
            cs.append(c.ok(f"{want} present{note}"))
        elif not lab:
            cs.append(c.skip(NOT_LAB))
        else:
            cs.append(c.warn(f"{want} not present on this machine",
                             "build one with slam_mapping.launch.py, or fix the path"))
    return cs


# ===========================================================================
# GROUP: net  (hardware reachability -- still no commands sent)
# ===========================================================================

def _has_ip(addr: str) -> bool:
    """Exact: 192.168.1.10 must not match 192.168.1.100, nor .5 match .50-.59."""
    rc, out = sh(["ip", "-4", "addr"], timeout=8)
    return rc == 0 and re.search(rf"inet {re.escape(addr)}/", out) is not None


def _tcp(host: str, port: int, timeout=3.0) -> str:
    """'open' | 'refused' | 'unreachable'. Refused is meaningful: host is up."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return "open"
    except ConnectionRefusedError:
        return "refused"
    except Exception:                                          # noqa: BLE001
        return "unreachable"
    finally:
        s.close()


def g_net() -> list[Check]:
    cs = []
    linux = is_linux()
    # Gate on the lab box, not on Linux: a teammate's laptop or a CI runner is
    # Linux too, and "no enp2s0" there is not a failure (on_lab_machine docstring).
    lab = on_lab_machine()
    subnet = on_arm_subnet()

    c = Check("net", "arm-nic", f"{ARM_NIC} carries both the arm and (per config) the LiDAR")
    if not lab:
        cs.append(c.skip(NOT_LAB))
    elif not shutil.which("ip"):
        cs.append(c.skip("`ip` not available"))
    else:
        rc, out = sh(["ip", "addr", "show", ARM_NIC], timeout=8)
        if rc != 0:
            cs.append(c.bad(f"interface {ARM_NIC} does not exist", "check the NIC name"))
        elif "NO-CARRIER" in out:
            cs.append(c.bad(f"{ARM_NIC} NO-CARRIER -- nothing electrically connected",
                            "plug the cable in; no software fixes this"))
        else:
            ips = re.findall(r"inet (\d+\.\d+\.\d+\.\d+/\d+)", out)
            cs.append(c.ok(f"{ARM_NIC} up, addresses: {', '.join(ips) or 'none'}"))

    # The finding: the arm's driver demands the host be .10, the LiDAR's config
    # demands the host be .5, both on 192.168.1.0/24, on one physical port.
    c = Check("net", "arm-lidar-coexist",
              f"arm needs host {ARM_UDP_HOST}, LiDAR needs host {LIDAR_HOST_IP} -- same /24, one NIC")
    if not lab:
        cs.append(c.skip(NOT_LAB))
    elif not shutil.which("ip"):
        cs.append(c.skip("`ip` not available"))
    else:
        has_arm, has_lidar = _has_ip(ARM_UDP_HOST), _has_ip(LIDAR_HOST_IP)
        if has_arm and has_lidar:
            cs.append(c.ok(f"both {ARM_UDP_HOST} and {LIDAR_HOST_IP} are configured"))
        elif has_arm:
            cs.append(c.warn(f"{ARM_UDP_HOST} configured, {LIDAR_HOST_IP} is NOT",
                             f"LiDAR data streams will not arrive; add an alias: "
                             f"`sudo ip addr add {LIDAR_HOST_IP}/24 dev {ARM_NIC}`"))
        elif has_lidar:
            cs.append(c.warn(f"{LIDAR_HOST_IP} configured, {ARM_UDP_HOST} is NOT",
                             f"arm connects but sends zero feedback (presents as a hang); "
                             f"`sudo nmcli con up {ARM_NIC}`"))
        else:
            cs.append(c.bad("neither host address is configured",
                            f"`sudo nmcli con up {ARM_NIC}` for the arm; add "
                            f"{LIDAR_HOST_IP}/24 as an alias for the LiDAR"))

    c = Check("net", "arm-ping", f"RM65 control box at {ARM_IP}")
    if not subnet:
        cs.append(c.skip(NOT_SUBNET))
    elif not shutil.which("ping"):
        cs.append(c.skip("no ping binary"))
    else:
        flag = "-W1" if linux else "-W1000"
        rc, _ = sh(["ping", "-c", "2", flag, ARM_IP], timeout=12)
        cs.append(c.ok(f"{ARM_IP} responds") if rc == 0
                  else c.bad(f"{ARM_IP} unreachable",
                             "check cable, and that the host has 192.168.1.10/24"))

    c = Check("net", "arm-port", f"control server on {ARM_IP}:{ARM_PORT} "
                                 f"(opens ~60 s after power-on)")
    st = _tcp(ARM_IP, ARM_PORT) if subnet else None
    if st is None:
        cs.append(c.skip(NOT_SUBNET))
    elif st == "open":
        cs.append(c.ok(f"{ARM_IP}:{ARM_PORT} accepting connections"))
    elif st == "refused":
        cs.append(c.warn(f"{ARM_IP}:{ARM_PORT} refused -- host is up, server not listening yet",
                         "normal within ~60 s of power-on; wait and retry"))
    else:
        cs.append(c.bad(f"{ARM_IP}:{ARM_PORT} unreachable", "arm powered off, or wrong subnet"))

    c = Check("net", "lidar-ping", f"Livox MID-360 at {LIDAR_IP}")
    if not subnet:
        cs.append(c.skip(NOT_SUBNET))
    elif not shutil.which("ping"):
        cs.append(c.skip("no ping binary"))
    else:
        flag = "-W1" if linux else "-W1000"
        rc, _ = sh(["ping", "-c", "2", flag, LIDAR_IP], timeout=12)
        cs.append(c.ok(f"{LIDAR_IP} responds") if rc == 0
                  else c.warn(f"{LIDAR_IP} unreachable",
                              f"LiDAR powered off, or host lacks {LIDAR_HOST_IP}"))

    cs.extend(realsense_checks(lab))

    c = Check("net", "aria-glasses", "glasses auth is a prerequisite for any Aria stream")
    aria = shutil.which("aria") or str(REPO / ".venv" / "bin" / "aria")
    if not Path(aria).exists():
        cs.append(c.skip("aria CLI not found (venv not built, or not the lab machine)"))
    else:
        rc, out = sh([aria, "auth", "check"], timeout=30)
        last = out.strip().splitlines()[-1][:120] if out.strip() else f"rc={rc}"
        if "Traceback" in out:      # the CLI itself is broken, not the pairing
            cs.append(c.bad(f"aria CLI crashed: {last}", "fix the venv (see TESTBENCH_PLAN W1)"))
        elif "no devices connected" in out.lower():
            # The CLI works but finds no glasses. It can still exit 0 here, which used to
            # pass as "authenticated" with the glasses unplugged (2026-09-11 box run).
            cs.append(c.bad("aria CLI works, but no glasses are connected over USB",
                            "plug in the glasses, then re-run"))
        elif rc != 0:
            cs.append(c.warn(last, "run `aria auth pair`"))
        else:
            cs.append(c.ok(f"authenticated"
                           + (f", device {ARIA_SERIAL} seen" if ARIA_SERIAL in out else "")))
    return cs


def rs_v4l2_nodes() -> dict[str, list[str]]:
    """Sort the RealSense's own /dev/video* nodes by what they can capture.

    The D435i exposes one node per stream plus a metadata node for each. Which
    number lands on which stream is not fixed, so ask each node what pixel
    formats it offers instead of assuming an order.

    Only nodes the kernel attributes to a RealSense are considered: this box is
    shared, and any USB webcam someone plugs in also offers YUYV, which would
    otherwise let this check pass on the wrong camera. Returns
    {"colour": [...], "depth": [...]}; anything else is left out.
    """
    found: dict[str, list[str]] = {"colour": [], "depth": []}
    for node in sorted(glob.glob("/dev/video*")):
        try:
            name = Path(f"/sys/class/video4linux/{Path(node).name}/name").read_text()
        except OSError:
            continue                      # no sysfs entry: cannot attribute it, so skip it
        if RS_USB_NAME not in name.lower():
            continue
        rc, out = sh(["v4l2-ctl", "-d", node, "--list-formats"], timeout=6)
        if rc != 0:
            continue
        if any(f in out for f in RS_V4L2_COLOUR):
            found["colour"].append(node)
        elif any(f in out for f in RS_V4L2_DEPTH):
            found["depth"].append(node)
    return found


def rs_grab(node: str) -> tuple[str, str]:
    """Try to capture one frame from a V4L2 node. Returns (verdict, detail).

    verdict is "ok", "busy" (someone else holds the camera -- not our answer to
    give) or "fail". This is the only part of preflight that opens a device
    rather than just reading about it, so "busy" is deliberately not a failure.
    """
    rc, out = sh(["v4l2-ctl", "-d", node, "--stream-mmap", "--stream-count=1",
                  "--stream-to=/dev/null"], timeout=15)
    low = out.lower()
    if rc == 0:
        return "ok", ""
    if "busy" in low or "resource temporarily unavailable" in low:
        return "busy", out.strip().splitlines()[-1] if out.strip() else "device busy"
    if rc == 124:
        return "fail", "no frame within 15 s (the camera answers but never delivers)"
    return "fail", out.strip().splitlines()[-1] if out.strip() else f"v4l2-ctl exit {rc}"


def realsense_checks(lab: bool) -> list[Check]:
    """Two questions, because they fail separately and for different reasons:
    is the camera on the USB bus, and can it actually deliver a frame.

    Both were one check until 2026-09-14, which passed on nothing more than the
    USB id. That morning it PASSED on a camera whose colour stream could not be
    opened at all (xioctl(VIDIOC_S_FMT) errno=5), and it would also have passed
    on the Bluetooth adapter alone -- see RS_USB_IDS.
    """
    why_usb = "D435i, eye-in-hand on Link6 -- the only camera on the robot"
    why_str = "a camera on the bus is not a camera that streams -- every grasp transform needs its frames"
    usb = Check("net", "realsense-usb", why_usb)
    stream = Check("net", "realsense-stream", why_str)

    if not lab:
        return [usb.skip(NOT_LAB), stream.skip(NOT_LAB)]
    if not shutil.which("lsusb"):
        return [usb.skip("lsusb not available"), stream.skip("lsusb not available")]

    rc, out = sh(["lsusb"], timeout=8)
    hits = [l.strip() for l in out.splitlines()
            if any(i in l for i in RS_USB_IDS) or RS_USB_NAME in l.lower()]
    if not hits:
        usb.bad("no RealSense on USB",
                "check the camera's USB cable. A wedged camera can drop off the bus entirely: "
                "seen 2026-09-14 after a librealsense hardware reset, and only a replug brought it back")
        return [usb, stream.skip("no camera on the bus to stream from")]
    usb.ok(hits[0])

    # On the bus, but does it work? Needs the V4L2 nodes and v4l2-ctl.
    if not shutil.which("v4l2-ctl"):
        return [usb, stream.skip("v4l2-ctl not installed (apt install v4l-utils)")]
    if not glob.glob("/dev/video*"):
        stream.bad("on the USB bus, but there are no /dev/video* nodes at all",
                   "the camera is enumerated but its UVC interfaces did not come up -- replug it")
        return [usb, stream]

    nodes = rs_v4l2_nodes()
    if not nodes["colour"] and not nodes["depth"]:
        stream.bad("/dev/video* nodes exist, but the kernel attributes none of them to a RealSense",
                   "the camera is half up, or those nodes belong to another camera -- replug it")
        return [usb, stream]
    if not nodes["colour"]:
        stream.bad(f"no RealSense node offers a colour format ({'/'.join(RS_V4L2_COLOUR)}); "
                   f"depth nodes found: {', '.join(nodes['depth'])}",
                   "the camera is half up. Replug it, then re-run")
        return [usb, stream]

    verdict, detail = rs_grab(nodes["colour"][0])
    node = nodes["colour"][0]
    if verdict == "busy":
        return [usb, stream.skip(f"{node} is held by another process -- "
                                 f"stop the camera driver, or leave it: {detail}")]
    if verdict == "fail":
        stream.bad(f"{node} is a colour node but delivered no frame: {detail}",
                   "this is the 2026-09-14 state: enumerated, colour stream dead. A replug fixed it")
        return [usb, stream]

    # Colour works. Depth is reported alongside, but its failure is the same finding.
    extra = ""
    if nodes["depth"]:
        d_verdict, d_detail = rs_grab(nodes["depth"][0])
        extra = (f"; depth {nodes['depth'][0]} ok" if d_verdict == "ok"
                 else f"; depth {nodes['depth'][0]} {d_verdict}: {d_detail}")
        if d_verdict == "fail":
            stream.bad(f"colour {node} delivers frames, but depth failed{extra[1:]}",
                       "grasping needs depth. Replug the camera, then re-run")
            return [usb, stream]
    stream.ok(f"one frame from colour {node}{extra}")
    return [usb, stream]


# ===========================================================================
# GROUP: graph  (live ROS -- read-only interrogation, no commands)
# ===========================================================================

def g_graph() -> list[Check]:
    cs = []
    if not shutil.which("ros2"):
        why = "ros2 CLI not on PATH -- source /opt/ros/humble/setup.bash and the repo overlay"
        return [Check("graph", n, d).skip(why) for n, d in (
            ("nodes", "what is actually running"),
            ("camera-hz-color", "RGB stream"),
            ("camera-hz-depth", "aligned depth stream"),
            ("tf-arm-camera", "base_link -> camera_color_optical_frame gates every grasp"),
            ("tf-base-bridge", "robot_base_link -> base_link joins the nav and arm TF trees"),
            ("joint-states", "proof the arm is sending feedback"),
        )]
    if not ros_graph_up():
        why = "no ROS graph is running (start the driver / camera first; see startup guide 4)"
        return [Check("graph", n, d).skip(why) for n, d in (
            ("nodes", "what is actually running"),
            ("camera-hz-color", "RGB stream"),
            ("camera-hz-depth", "aligned depth stream"),
            ("tf-arm-camera", "base_link -> camera_color_optical_frame gates every grasp"),
            ("tf-base-bridge", "robot_base_link -> base_link joins the nav and arm TF trees"),
            ("joint-states", "proof the arm is sending feedback"),
        )]

    rc, nodes = sh(["ros2", "node", "list"], timeout=15)
    cs.append(Check("graph", "nodes", "what is actually running")
              .ok(f"{len(nodes.splitlines())} nodes: "
                  f"{', '.join(nodes.split()[:6])}{' ...' if len(nodes.split()) > 6 else ''}"))

    rc, topics = sh(["ros2", "topic", "list"], timeout=15)
    topics_set = set(topics.split())

    for label, topic in (("color", "/camera/camera/color/image_raw"),
                         ("depth", "/camera/camera/aligned_depth_to_color/image_raw")):
        c = Check("graph", f"camera-hz-{label}", f"{topic} should run 13-14 Hz")
        if topic not in topics_set:
            cs.append(c.skip(f"{topic} not advertised -- RealSense driver not launched"))
            continue
        rc, out = sh(["ros2", "topic", "hz", "-w", "20", topic], timeout=20)
        m = re.search(r"average rate:\s*([\d.]+)", out)
        if not m:
            cs.append(c.bad(f"{topic} advertised but no messages",
                            "driver up but not publishing"))
        else:
            hz = float(m.group(1))
            d = f"{hz:.1f} Hz"
            cs.append(c.ok(d) if CAMERA_HZ_RANGE[0] <= hz <= CAMERA_HZ_RANGE[1]
                      else c.warn(d, f"expected {CAMERA_HZ_RANGE[0]}-{CAMERA_HZ_RANGE[1]} Hz"))

    for (parent, child), expect in TF_EXPECT.items():
        c = Check("graph", "tf-arm-camera",
                  f"{parent} -> {child}; a missing link silently skips every grasp candidate")
        rc, out = sh(["ros2", "run", "tf2_ros", "tf2_echo", parent, child], timeout=12)
        m = re.search(r"[Tt]ranslation:\s*\[?\s*(-?[\d.]+),\s*(-?[\d.]+),\s*(-?[\d.]+)", out)
        if not m:
            cs.append(c.bad(f"no transform {parent} -> {child}",
                            "needs BOTH the arm's robot_state_publisher and the RealSense driver"))
        else:
            got = tuple(float(m.group(i)) for i in (1, 2, 3))
            dev = max(abs(a - b) for a, b in zip(got, expect))
            d = (f"[{got[0]:.3f}, {got[1]:.3f}, {got[2]:.3f}] "
                 f"(expected [{expect[0]:.3f}, {expect[1]:.3f}, {expect[2]:.3f}])")
            cs.append(c.ok(d) if dev <= TF_TOL
                      else c.warn(d + f", max deviation {dev:.3f} m",
                                  "camera mount or URDF may have changed"))

    c = Check("graph", "tf-base-bridge",
              "robot_base_link -> base_link exists only in slam_localization.launch.py, "
              "not in slam_mapping -- during mapping the arm is off the TF tree entirely")
    rc, out = sh(["ros2", "run", "tf2_ros", "tf2_echo", "robot_base_link", "base_link"], timeout=12)
    cs.append(c.ok("present") if "ranslation" in out
              else c.warn("absent", "expected during a mapping run; required for localization"))

    c = Check("graph", "joint-states", "proof the arm is sending UDP feedback, not just connected")
    if "/joint_states" not in topics_set:
        cs.append(c.skip("/joint_states not advertised -- arm driver not launched"))
    else:
        rc, out = sh(["ros2", "topic", "hz", "-w", "10", "/joint_states"], timeout=20)
        m = re.search(r"average rate:\s*([\d.]+)", out)
        cs.append(c.ok(f"{float(m.group(1)):.1f} Hz") if m
                  else c.bad("/joint_states advertised but silent",
                             f"classic symptom of the host not being {ARM_UDP_HOST} "
                             f"-- arm connects, sends nothing"))
    return cs


# ===========================================================================
# SAFETY: the line this bench does not cross
# ===========================================================================

FORBIDDEN = [
    "/rm_driver/movej_cmd", "/rm_driver/movel_cmd", "/rm_driver/movec_cmd",
    "/rm_driver/movej_p_cmd", "/rm_driver/movej_canfd_cmd",
    "/rm_driver/set_gripper_position_cmd", "/rm_driver/set_gripper_pick_on_cmd",
]

NOT_TESTABLE_HERE = [
    ("arm motion", "grasp_state_machine homes the arm within seconds of launch, unprompted "
                   "(ORIENTATION 8.1). Nothing in this bench launches it."),
    ("grasp execution", "AnyGrasp -> MoveIt -> arm has never been run end to end; there is no "
                        "known-good result to compare against (startup guide 7)."),
    ("gripper", "opening or closing the gripper is a physical command; out of scope by design."),
    ("Nav2 driving", "publishing /goal_pose moves the base. Not exercised."),
    ("the full pipeline", "voice -> SAM 3 -> gaze -> grasp is severed at "
                          "object_recognition_pipeline.py:384 (ORIENTATION 6.2), so there is "
                          "no end-to-end path to test yet."),
]

# ===========================================================================
# GROUP: home  (whose account is this? -- per-user state and hardcoded homes)
# ===========================================================================

HOME_PATH_RE = re.compile(r"/home/[A-Za-z0-9_.-]+/[^\s\"'`:,;(){}\[\]]*")
HOME_SCAN_SKIP = {".git", "install", "build", "log", "bench", "docs", ".venv", "venv",
                  "node_modules", "__pycache__"}   # plus any <name>_docs/ folder, below
HOME_SCAN_EXT = (".py", ".sh", ".yaml", ".yml", ".xml", ".json", ".launch", ".cfg")


def _hardcoded_home_paths() -> dict[str, list[str]]:
    """{absolute /home/... path: [file:line, ...]} over owned code (_common.OWNED_PREFIXES)."""
    hits: dict[str, list[str]] = {}
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in HOME_SCAN_SKIP and not d.endswith("_docs")]
        for fn in files:
            if not fn.endswith(HOME_SCAN_EXT):
                continue
            f = Path(root) / fn
            if not str(f.relative_to(REPO)).startswith(OWNED_PREFIXES):
                continue    # vendored code's example paths (/home/patrick/...) are not ours
            try:
                lines = f.read_text(errors="replace").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines, 1):
                for m in HOME_PATH_RE.finditer(line):
                    hits.setdefault(m.group(0).rstrip("."), []).append(
                        f"{f.relative_to(REPO)}:{i}")
    return hits


def g_home() -> list[Check]:
    cs = []
    user, home = getpass.getuser(), Path.home()
    # The lab box moved from user iot22 to rcp2026 by copying folders. ~/.local
    # (CUDA torch), ~/.aria (certs), conda envs and ~/maps are per-user: every
    # check that looks at them is answering for the user named here.
    c = Check("home", "running-user", "per-user state (~/.local, ~/.aria, conda, ~/maps) "
                                      "is judged for this user only")
    cs.append(c.ok(f"{user} ({home})"))

    c = Check("home", "hardcoded-homes",
              "absolute /home/<user>/ paths in the code must resolve for whoever runs it")
    hits = _hardcoded_home_paths()
    foreign = {p: w for p, w in hits.items() if not p.startswith(f"{home}/")}
    if not foreign:
        cs.append(c.ok(f"none outside {home}" if hits else "none"))
        return cs
    owners = sorted({p.split("/")[2] for p in foreign})
    where = lambda p: f"{p} ({foreign[p][0]}{f' +{len(foreign[p])-1}' if len(foreign[p]) > 1 else ''})"
    if not on_lab_machine():
        cs.append(c.skip(f"{len(foreign)} path(s) hardcode /home/{','.join(owners)}/ -- "
                         f"whether they resolve can only be judged on the lab machine"))
        return cs
    def why(p: str) -> str:
        """'' if genuinely absent; ' [no access: /home/x]' if a locked ancestor hides it."""
        a = Path(p).parent
        while not _exists(a) and a != a.parent:
            a = a.parent
        return "" if os.access(a, os.R_OK | os.X_OK) else f" [no access: {a}]"
    missing = sorted(p for p in foreign if not _exists_or_prefix(p))
    resolving = sorted(p for p in foreign if p not in missing)
    borrowed = (f"; {len(resolving)} more resolve into /home/{','.join(owners)}/ -- "
                f"{user} would silently run another user's copy" if resolving else "")
    if missing:
        cs.append(c.bad(f"{len(missing)} of {len(foreign)} hardcoded path(s) unreachable, "
                        f"e.g. {where(missing[0])}{why(missing[0])}{borrowed}",
                        f"running as {user}: parametrise these, or run as their owner "
                        f"(full list: python3 bench/preflight.py -g home --json)"))
        c.detail += "\n" + "\n".join(f"           missing: {where(p)}{why(p)}" for p in missing[1:])
    else:
        cs.append(c.warn(f"all {len(foreign)} resolve -- but into /home/{','.join(owners)}/, "
                         f"so {user} silently runs another user's copy, not {home}",
                         "parametrise these before trusting any run as this user"))
    return cs


GROUPS = {"host": g_host, "home": g_home, "gpu": g_gpu, "ros": g_ros, "env": g_env,
          "assets": g_assets, "net": g_net, "graph": g_graph}
# L2 asks only "can L3-L4 run here". An unplugged robot does not stop a build or a simulation,
# so the robot's own checks are their own level, L5 (--hardware).
HARDWARE_GROUPS = ["net", "graph"]
L2_GROUPS = [g for g in GROUPS if g not in HARDWARE_GROUPS]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-g", "--group", action="append", choices=list(GROUPS),
                    help="run only these groups (repeatable)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hardware", action="store_true",
                    help="L5: check the robot before an L6 arm test: " + ", ".join(HARDWARE_GROUPS))
    lab = ap.add_mutually_exclusive_group()
    lab.add_argument("--lab", dest="lab", action="store_const", const=True,
                     help="treat this as the lab machine (overrides the Linux+ROS/GPU guess)")
    lab.add_argument("--no-lab", dest="lab", action="store_const", const=False,
                     help="treat this as NOT the lab machine: lab-only checks SKIP")
    a = ap.parse_args()
    global LAB_OVERRIDE
    LAB_OVERRIDE = a.lab

    names = a.group or (HARDWARE_GROUPS if a.hardware else L2_GROUPS)
    checks: list[Check] = []
    for n in names:
        checks.extend(GROUPS[n]())

    if a.json:
        json.dump([{k: getattr(c, k) for k in
                    ("group", "name", "why", "status", "detail", "reason", "fix")}
                   for c in checks], sys.stdout, indent=2)
        print()
        return 1 if any(c.status == FAIL for c in checks) else 0

    mark = {PASS: "PASS", FAIL: "FAIL", WARN: "warn", SKIP: "skip"}
    print("=" * 78)
    print("PREFLIGHT -- " + ("L5: is the robot there? No arm motion" if a.hardware and not a.group
                             else "can this machine run L3-L4 (the robot is checked by --hardware)"))
    print(f"host: {platform.system()} {platform.machine()}   repo: {REPO}")
    print(f"user: {getpass.getuser()}   lab machine: {on_lab_machine()} "
          f"({'forced' if LAB_OVERRIDE is not None else 'guessed: Linux + ROS or NVIDIA'})")
    print("=" * 78)

    for g in names:
        gcs = [c for c in checks if c.group == g]
        if not gcs:
            continue
        print(f"\n### {g}")
        for c in gcs:
            print(f"  [{mark[c.status]}] {c.name:<22} {c.detail or c.reason}")
            if c.status in (FAIL, WARN) and c.fix:
                print(f"         -> {c.fix}")

    n = {s: sum(1 for c in checks if c.status == s) for s in (PASS, FAIL, WARN, SKIP)}
    skipped = [c for c in checks if c.status == SKIP]

    print("\n" + "=" * 78)
    print(f"RESULT   {n[PASS]} pass   {n[FAIL]} fail   {n[WARN]} warn   {n[SKIP]} skipped")
    print("=" * 78)

    if skipped:
        print(f"\nCOULD NOT BE RUN HERE ({len(skipped)}) -- these are unverified, not passing:")
        by_reason: dict[str, list[str]] = {}
        for c in skipped:
            by_reason.setdefault(c.reason, []).append(f"{c.group}/{c.name}")
        for reason, items in sorted(by_reason.items(), key=lambda kv: -len(kv[1])):
            print(f"\n  {reason}")
            for i in items:
                print(f"      - {i}")

    print(f"\nNOT TESTABLE BY THIS BENCH AT ALL, BY DESIGN:")
    for what, why in NOT_TESTABLE_HERE:
        print(f"  - {what}: {why}")
    print(f"\n  This script never publishes to any of: {', '.join(FORBIDDEN[:3])}, ...")
    print("  Everything past that line needs a human at the robot with the e-stop in hand.")

    if a.hardware and not a.group:
        arm = next(c for c in checks if c.name == "arm-ping")
        if arm.status != PASS:
            print(f"\nSKIPPED: the arm does not answer ({arm.status.lower()}), so L6 has nothing to test.")
            return 3
    return 1 if n[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
