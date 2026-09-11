#!/usr/bin/env python3
"""
Static soundness checks for the Gappler stack.

Companion to bench/contracts.py. Where that one asks "did a contract move?",
this one asks "is what's here internally consistent right now?" -- it needs no
baseline, so it is useful from the first run.

The checks are chosen for one specific refactor: moving files around into
one-folder-per-node, and pulling shared services out of nested packages. That
refactor breaks things in four ways, all of them silent until launch time:

  1. a launch file names a package that no longer exists
  2. a launch file names an executable that was renamed or moved
  3. a CMakeLists/setup.py install rule points at a script that moved
  4. an import breaks, or a name is used that was never imported
     (this is live in the tree today -- see the realman_manip src/main.py)

Usage:
    python3 bench/static.py            # run everything, exit 1 on any failure
    python3 bench/static.py --list     # show which checks exist
    python3 bench/static.py -v         # include passing detail

Stdlib only.
"""

from __future__ import annotations

import argparse
import ast
import builtins
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".git", "install", "build", "log", "__pycache__", ".venv", "node_modules",
    "OpenVINS", "MinkowskiEngine", "moveit_task_constructor", "anygrasp_sdk",
    "archive",
}

# Packages we get from an apt-installed ROS 2 Humble, not from this repo.
# A launch file naming one of these is fine; naming anything else that is not
# in the repo is a missing dependency.
KNOWN_EXTERNAL = {
    "nav2_bringup", "nav2_common", "nav2_map_server", "nav2_util", "nav2_bt_navigator",
    "slam_toolbox", "robot_state_publisher", "joint_state_publisher",
    "joint_state_publisher_gui", "rviz2", "tf2_ros", "xacro", "gazebo_ros",
    "controller_manager", "realsense2_camera", "realsense2_description",
    "pointcloud_to_laserscan", "moveit_ros_move_group", "moveit_configs_utils",
    "moveit_ros_visualization", "moveit_task_constructor_capabilities",
    "moveit_task_constructor_core", "moveit_task_constructor_demo",
    "moveit_task_constructor_visualization", "rviz_marker_tools",
    "launch", "launch_ros", "ros_gz_sim", "ros_gz_bridge", "rqt_gui",
    "image_transport", "cv_bridge", "depth_image_proc", "rmw_fastrtps_cpp",
    "twist_mux", "velocity_smoother", "nav2_lifecycle_manager", "nav2_amcl",
    "nav2_controller", "nav2_planner", "nav2_behaviors", "nav2_waypoint_follower",
    "nav2_velocity_smoother", "nav2_smoother", "nav2_collision_monitor",
}

# ROS 1 packages. The Echo Plus base packages under Navigation_Module/src/base
# and /drivers are dual-build (catkin + ament) vendor drops, so their package.xml
# legitimately declares ROS 1 deps. Not a defect.
ROS1_PKGS = {
    "roscpp", "rospy", "catkin", "message_generation", "message_runtime",
    "roslaunch", "tf", "std_msgs", "nodelet", "rosconsole",
}

KNOWN_EXTERNAL |= {
    "nav2_msgs", "warehouse_ros_mongo", "moveit_ros_warehouse", "livox_ros_driver2",
    "moveit_ros_planning_interface", "moveit_visual_tools", "rviz_visual_tools",
    "joint_trajectory_controller", "joint_state_broadcaster", "robot_localization",
}

# Code we own and will refactor (dion_docs/ORIENTATION.md 2). Vendor findings are
# still reported, but under a separate heading -- they are pre-existing
# conditions of the vendor drops, not things this refactor caused.
from _common import OWNED_PREFIXES   # noqa: E402 -- single source; edit there


# Vendor trees that nonetheless sit inside a workspace WE build, so a defect in
# them blocks our colcon run and is ours to solve even though we did not write it.
BLOCKING_VENDOR = ("Navigation_Module/src/livox_ros_driver2/",)


def owned(msg: str) -> bool:
    path = msg.split(":")[0].strip()
    return path.startswith(OWNED_PREFIXES) or path.startswith(BLOCKING_VENDOR)


# Roots that end up on PYTHONPATH at runtime (ros2_robot_ws/src/main.py:120
# puts src/ there explicitly; scripts dirs are added by ament install rules).
IMPORT_ROOTS = ["src", "."]


def is_excluded(p: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in p.parts)


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


def walk(*suffixes: str):
    for p in sorted(REPO.rglob("*")):
        if p.is_file() and p.suffix in suffixes and not is_excluded(p.relative_to(REPO)):
            yield p


class Result:
    def __init__(self, name: str, description: str):
        self.name, self.description = name, description
        self.failures: list[str] = []
        self.notes: list[str] = []
        self.n_checked = 0

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures


# ---------------------------------------------------------------------------

def check_python_syntax() -> Result:
    r = Result("python-syntax", "every Python file we own parses")
    for p in walk(".py"):
        r.n_checked += 1
        try:
            ast.parse(p.read_text(errors="replace"), filename=str(p))
        except SyntaxError as e:
            r.fail(f"{rel(p)}:{e.lineno}: {e.msg}")
    return r


def _bound_names(tree: ast.AST) -> set[str]:
    """Every name bound anywhere in the module, scopes flattened.

    Flattening is deliberate: we are only trying to catch names that are bound
    NOWHERE, which is the `Path` failure mode. A stricter per-scope analysis
    would find shadowing bugs too, at the cost of false positives that would
    make the check get ignored.
    """
    bound: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                a = n.args
                for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs, a.vararg, a.kwarg]:
                    if arg:
                        bound.add(arg.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            bound.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            bound.update(n.names)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
    return bound


def check_undefined_names() -> Result:
    r = Result("undefined-names", "no name is used that is never imported or assigned")
    bi = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__"}
    for p in walk(".py"):
        try:
            tree = ast.parse(p.read_text(errors="replace"))
        except SyntaxError:
            continue  # reported by check_python_syntax
        r.n_checked += 1
        bound = _bound_names(tree) | bi
        seen: set[str] = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                if n.id not in bound and n.id not in seen:
                    seen.add(n.id)
                    r.fail(f"{rel(p)}:{n.lineno}: '{n.id}' used but never bound in this module")
    return r


def check_internal_imports() -> Result:
    r = Result("internal-imports", "every intra-repo import resolves to a file that exists")
    roots = [REPO / x for x in IMPORT_ROOTS]
    top_level = set()
    for root in roots:
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir() and (child / "__init__.py").exists():
                    top_level.add(child.name)
                elif child.suffix == ".py":
                    top_level.add(child.stem)

    def resolves(module: str) -> bool:
        parts = module.split(".")
        for root in roots:
            base = root.joinpath(*parts)
            if base.with_suffix(".py").exists() or (base / "__init__.py").exists():
                return True
        return False

    for p in walk(".py"):
        try:
            tree = ast.parse(p.read_text(errors="replace"))
        except SyntaxError:
            continue
        r.n_checked += 1
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                mods = [n.module]
            elif isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            for m in mods:
                if m.split(".")[0] in top_level and not resolves(m):
                    r.fail(f"{rel(p)}:{n.lineno}: cannot resolve intra-repo import '{m}'")
    return r


def repo_packages() -> dict[str, Path]:
    pkgs: dict[str, Path] = {}
    # Some vendor drops generate package.xml at build time from a per-ROS-version
    # template (livox_ros_driver2/build.sh), and gitignore the result.
    for p in REPO.rglob("package_ROS*.xml"):
        if is_excluded(p.relative_to(REPO)):
            continue
        try:
            name = ET.parse(p).getroot().findtext("name")
        except ET.ParseError:
            continue
        if name:
            pkgs.setdefault(name.strip(), p.parent)
    for p in REPO.rglob("package.xml"):
        if is_excluded(p.relative_to(REPO)):
            continue
        try:
            name = ET.parse(p).getroot().findtext("name")
        except ET.ParseError:
            continue
        if name:
            pkgs[name.strip()] = p.parent
    return pkgs


def _launch_pkg_refs(tree: ast.AST) -> list[tuple[str, int]]:
    refs = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            fname = n.func.id if isinstance(n.func, ast.Name) else (
                n.func.attr if isinstance(n.func, ast.Attribute) else None)
            if fname in ("FindPackageShare", "get_package_share_directory") and n.args:
                if isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                    refs.append((n.args[0].value, n.lineno))
            for kw in n.keywords:
                if kw.arg == "package" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    refs.append((kw.value.value, n.lineno))
    return refs


def check_launch_packages() -> Result:
    r = Result("launch-packages",
               "every package a launch file names exists in the repo or in ROS Humble")
    pkgs = repo_packages()
    r.note(f"{len(pkgs)} packages found in repo")
    for p in walk(".py"):
        if not p.name.endswith(".launch.py"):
            continue
        try:
            tree = ast.parse(p.read_text(errors="replace"))
        except SyntaxError:
            continue
        r.n_checked += 1
        for name, line in _launch_pkg_refs(tree):
            if name not in pkgs and name not in KNOWN_EXTERNAL:
                r.fail(f"{rel(p)}:{line}: references package '{name}' "
                       f"-- not in repo, not a known ROS Humble package")
    return r


def check_package_xml_deps() -> Result:
    r = Result("package-xml-deps", "declared dependencies exist in repo or in ROS Humble")
    pkgs = repo_packages()
    dep_tags = ("depend", "exec_depend", "build_depend", "buildtool_depend",
                "build_export_depend", "test_depend")
    for name, d in sorted(pkgs.items()):
        # livox-style vendor drops gitignore package.xml and ship a template
        # only the ROS 2 manifest is relevant -- package_ROS1.xml legitimately
        # declares catkin/roscpp deps and is not what colcon reads
        px = next((c for c in (d / "package.xml", d / "package_ROS2.xml") if c.exists()), None)
        if px is None:
            continue
        try:
            root = ET.parse(px).getroot()
        except ET.ParseError as e:
            r.fail(f"{rel(px)}: malformed XML: {e}")
            continue
        r.n_checked += 1
        for tag in dep_tags:
            for el in root.findall(tag):
                dep = (el.text or "").strip()
                if not dep or dep in pkgs or dep in KNOWN_EXTERNAL or dep in ROS1_PKGS:
                    continue
                if dep.startswith(("ament_", "rclcpp", "rclpy", "std_", "sensor_", "geometry_",
                                   "nav_", "tf2", "visualization_", "builtin_", "rosidl_",
                                   "python3-", "libp", "eigen", "boost", "yaml", "pcl",
                                   "cv_bridge", "message_filters", "diagnostic_", "shape_",
                                   "trajectory_", "control_", "action_", "lifecycle_",
                                   "moveit", "rviz", "gazebo", "urdf", "kdl", "orocos",
                                   "backward_ros", "angles", "pluginlib", "class_loader")):
                    continue
                r.fail(f"{rel(px)}: package '{name}' declares <{tag}>{dep}</{tag}> "
                       f"-- not in repo, not recognised as a ROS Humble package")
    return r


def check_launch_executables() -> Result:
    r = Result("launch-executables",
               "every executable a launch file names is installed by its package")
    pkgs = repo_packages()

    def installed(pkg_dir: Path) -> set[str]:
        names: set[str] = set()
        cml = pkg_dir / "CMakeLists.txt"
        if cml.exists():
            txt = cml.read_text(errors="replace")
            for m in re.finditer(r"install\s*\(\s*(?:PROGRAMS|TARGETS)([^)]*)\)", txt, re.S):
                for tok in re.split(r"[\s\n]+", m.group(1)):
                    tok = tok.strip().strip('"')
                    if not tok or tok.upper() in ("DESTINATION", "RUNTIME", "LIBRARY", "ARCHIVE"):
                        continue
                    if tok.startswith("${") or "DESTINATION" in tok:
                        continue
                    names.add(Path(tok).name)
                    names.add(Path(tok).stem)
            for m in re.finditer(r"add_executable\s*\(\s*([\w.-]+)", txt):
                names.add(m.group(1))
            for m in re.finditer(r"rclcpp_components_register_node\s*\([^)]*EXECUTABLE\s+([\w.-]+)",
                                 txt, re.S):
                names.add(m.group(1))
        sp = pkg_dir / "setup.py"
        if sp.exists():
            for m in re.finditer(r"['\"]([\w.-]+)\s*=\s*[\w.]+:[\w]+['\"]", sp.read_text(errors="replace")):
                names.add(m.group(1))
        return names

    cache: dict[str, set[str]] = {}
    for p in walk(".py"):
        if not p.name.endswith(".launch.py"):
            continue
        try:
            tree = ast.parse(p.read_text(errors="replace"))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Node"):
                continue
            kw = {k.arg: k.value for k in n.keywords if k.arg}
            pkg = kw.get("package")
            exe = kw.get("executable")
            if not (isinstance(pkg, ast.Constant) and isinstance(exe, ast.Constant)):
                continue
            pkg, exe = pkg.value, exe.value
            if pkg not in pkgs:
                continue  # covered by check_launch_packages
            r.n_checked += 1
            if pkg not in cache:
                cache[pkg] = installed(pkgs[pkg])
            if exe not in cache[pkg] and Path(exe).stem not in cache[pkg]:
                r.fail(f"{rel(p)}:{n.lineno}: Node(package='{pkg}', executable='{exe}') "
                       f"-- '{exe}' is not installed by {pkg}")
    return r


def check_install_targets_exist() -> Result:
    r = Result("install-targets", "scripts named in CMakeLists install(PROGRAMS) exist on disk")
    for cml in REPO.rglob("CMakeLists.txt"):
        if is_excluded(cml.relative_to(REPO)):
            continue
        txt = cml.read_text(errors="replace")
        for m in re.finditer(r"install\s*\(\s*PROGRAMS([^)]*?)DESTINATION", txt, re.S):
            for tok in re.split(r"[\s\n]+", m.group(1)):
                tok = tok.strip().strip('"')
                if not tok or tok.startswith("${"):
                    continue
                r.n_checked += 1
                if not (cml.parent / tok).exists():
                    r.fail(f"{rel(cml)}: install(PROGRAMS {tok}) -- file does not exist")
    return r


def check_xml_wellformed() -> Result:
    r = Result("xml-wellformed", "package.xml / urdf / xacro parse as XML")
    for p in list(walk(".urdf", ".xacro")) + [x for x in REPO.rglob("package.xml")
                                              if not is_excluded(x.relative_to(REPO))]:
        r.n_checked += 1
        try:
            ET.parse(p)
        except ET.ParseError as e:
            r.fail(f"{rel(p)}: {e}")
    return r


def check_launch_file_includes() -> Result:
    r = Result("launch-includes", "launch files included by other launch files exist")
    all_launch = {p.name for p in walk(".py") if p.name.endswith(".launch.py")}
    all_launch |= {p.name for p in REPO.rglob("*.launch") if not is_excluded(p.relative_to(REPO))}
    pkgs = repo_packages()
    for p in walk(".py"):
        if not p.name.endswith(".launch.py"):
            continue
        txt = p.read_text(errors="replace")
        for m in re.finditer(r"['\"]([\w-]+\.launch(?:\.py|\.xml)?)['\"]", txt):
            target = m.group(1)
            r.n_checked += 1
            if target in all_launch:
                continue
            # may live in an external package -- only flag when the enclosing
            # launch file resolves it against an in-repo package
            if any(f"'{k}'" in txt or f'"{k}"' in txt for k in pkgs):
                found = any((d / "launch" / target).exists() for d in pkgs.values())
                if not found:
                    line = txt.count("\n", 0, m.start()) + 1
                    r.fail(f"{rel(p)}:{line}: includes '{target}' -- not found in any repo package")
    return r


def check_generated_manifests() -> Result:
    """Vendor drops that build package.xml from a per-ROS-version template must
    ship the ROS 2 template, or colcon cannot see the package at all."""
    r = Result("generated-manifests",
               "vendor packages that generate package.xml ship the ROS 2 template")
    seen: set[Path] = set()
    for tpl in REPO.rglob("package_ROS*.xml"):
        if is_excluded(tpl.relative_to(REPO)) or tpl.parent in seen:
            continue
        seen.add(tpl.parent)
        d = tpl.parent
        r.n_checked += 1
        if (d / "package.xml").exists():
            continue  # already generated in this working tree
        if not (d / "package_ROS2.xml").exists():
            have = sorted(x.name for x in d.glob("package_ROS*.xml"))
            r.fail(f"{rel(d)}/: build.sh generates package.xml from package_ROS2.xml, "
                   f"but only {have} is present and package.xml is gitignored "
                   f"-- colcon will not find this package on a fresh clone")
    return r


CHECKS = [
    check_python_syntax,
    check_undefined_names,
    check_internal_imports,
    check_xml_wellformed,
    check_launch_packages,
    check_package_xml_deps,
    check_launch_executables,
    check_launch_file_includes,
    check_install_targets_exist,
    check_generated_manifests,
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("-k", metavar="NAME", help="run only checks whose name contains NAME")
    a = ap.parse_args()

    if a.list:
        for c in CHECKS:
            r = c.__doc__ or ""
            print(f"  {c.__name__.replace('check_', ''):<22}")
        return 0

    checks = [c for c in CHECKS if not a.k or a.k in c.__name__]
    results = [c() for c in checks]
    failed = 0

    print("=" * 78)
    print(f"STATIC CHECKS  ({len(results)} checks)")
    print("=" * 78)
    n_ours = n_vendor = 0
    for r in results:
        ours = [f for f in r.failures if owned(f)]
        vendor = [f for f in r.failures if not owned(f)]
        n_ours += len(ours)
        n_vendor += len(vendor)
        mark = "FAIL" if ours else ("warn" if vendor else "PASS")
        print(f"\n[{mark}] {r.name}  ({r.n_checked} checked)")
        print(f"       {r.description}")
        for n in r.notes:
            print(f"       note: {n}")
        for f in ours:
            print(f"   !   {f}")
        if vendor:
            if a.verbose:
                print(f"       -- vendor code ({len(vendor)}), pre-existing:")
                for f in vendor:
                    print(f"       .   {f}")
            else:
                print(f"       -- plus {len(vendor)} finding(s) in vendor code (-v to show)")
        if ours:
            failed += 1

    print("\n" + "=" * 78)
    print(f"findings: {n_ours} in code we own, {n_vendor} in vendor code")
    if failed:
        print(f"FAIL: {failed}/{len(results)} checks have findings in code we own.")
        return 1
    print(f"PASS: all {len(results)} checks clean for code we own.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
