#!/usr/bin/env python3
"""
Contract extractor for the Gappler robot stack.

Why this exists
---------------
Every seam in this system is a *string*. ROS binds publishers to subscribers by
literal topic name, TF by literal frame name, parameters by literal key. A
refactor that renames one of them in four places out of five compiles clean,
launches clean, and silently does nothing. That failure mode has already
happened twice in this repo (see docs/ORIENTATION.md 0b).

So the bench does not test behaviour -- there is no observed behaviour to
regress against for much of this system. It pins the *contracts*, and tells you
when one moves.

Keyed by contract, not by file
------------------------------
Locations are recorded but are NOT part of the pass/fail comparison, because
the planned refactor moves nearly every file. Moving `sam3_ros_node.py` into a
new package is fine. Moving the topic it publishes is not.

Usage
-----
    python3 bench/contracts.py extract          # print current contracts as JSON
    python3 bench/contracts.py snapshot         # write bench/golden/contracts.json
    python3 bench/contracts.py check            # diff current vs golden; exit 1 on regression
    python3 bench/contracts.py report           # human-readable inventory + orphan analysis

Stdlib only. Runs anywhere python3.8+ runs. No ROS, no deps, no hardware.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GOLDEN = REPO / "bench" / "golden" / "contracts.json"

# Vendored trees we neither own nor refactor. Excluded wholesale -- including
# them would bury our own contracts under upstream noise.
EXCLUDE_DIRS = {
    ".git", "install", "build", "log", "install_nav", "build_nav", "log_nav",
    "__pycache__", ".venv", "node_modules",
    "OpenVINS", "MinkowskiEngine", "moveit_task_constructor", "anygrasp_sdk",
    "archive",
}

# ROS message packages, used to recognise a type import as a message type.
MSG_PKG_RE = re.compile(r"^([a-z0-9_]+_(?:msgs|interfaces))(?:\.(msg|srv|action))?$")

# Code we own and will refactor, per docs/ORIENTATION.md 2. Everything else is
# vendor code that ships with the arm, the base or the LiDAR: its contracts still
# matter (we call into them) but they are not going to move because *we* moved a
# file, so the report separates them.
from _common import OWNED_PREFIXES   # noqa: E402 -- single source; edit there


def owned(loc: str) -> bool:
    """loc is a 'path:line' or 'path(tag)' string."""
    path = re.split(r"[:(]", loc)[0]
    return path.startswith(OWNED_PREFIXES)


def any_owned(locs) -> bool:
    return any(owned(l) for l in locs)


def is_excluded(path: Path) -> bool:
    return any(part in EXCLUDE_DIRS for part in path.parts)


def rel(path: Path) -> str:
    return str(path.relative_to(REPO))


def walk(*suffixes: str):
    for p in sorted(REPO.rglob("*")):
        r = p.relative_to(REPO)
        # bench/ is the instrument, not the robot: its test nodes subscribe to
        # /joint_states etc. and would otherwise read as contract changes.
        if r.parts[:1] == ("bench",):
            continue
        if p.is_file() and p.suffix in suffixes and not is_excluded(r):
            yield p


# --------------------------------------------------------------------------
# Python extraction (AST -- resolves constants, which regex cannot)
# --------------------------------------------------------------------------

class PyExtractor(ast.NodeVisitor):
    """Pulls topics/frames/params out of one Python file.

    Constant resolution is the whole point of using AST here: the repo writes
    `TOPIC_MASK = "/camera/sam/mask"` then `create_publisher(Image, TOPIC_MASK, 10)`.
    A regex over the create_publisher call sees only the identifier.
    """

    def __init__(self, path: Path, src: str, config: dict | None = None):
        self.path = path
        self.config = config or {}               # key -> {values} from our YAML files
        self.param_defaults: dict[str, str] = {}  # declare_parameter("x", "/default")
        self.loc = rel(path)
        self.consts: dict[str, str] = {}          # NAME -> literal str
        self.attr_consts: dict[str, str] = {}     # Class.NAME / Class.NAME.value -> literal str
        self.type_imports: dict[str, str] = {}    # Image -> sensor_msgs/Image
        self.out = new_bucket()
        self._collect_consts(ast.parse(src))

    # -- constant + import tables -----------------------------------------
    def _collect_consts(self, tree: ast.AST) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                m = MSG_PKG_RE.match(node.module)
                if m:
                    for a in node.names:
                        self.type_imports[a.asname or a.name] = f"{m.group(1)}/{a.name}"
            elif isinstance(node, ast.Assign):
                val = literal_str(node.value)
                if val is None:
                    continue
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.consts[t.id] = val
            elif isinstance(node, ast.ClassDef):
                # Enum / config classes: `class Topics: MASK = "/camera/sam/mask"`
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign):
                        val = literal_str(stmt.value)
                        if val is None:
                            continue
                        for t in stmt.targets:
                            if isinstance(t, ast.Name):
                                self.attr_consts[f"{node.name}.{t.id}"] = val
                                self.attr_consts[f"{node.name}.{t.id}.value"] = val
            elif isinstance(node, ast.Call) and _fn_name(node) == "declare_parameter" \
                    and len(node.args) >= 2:
                name, val = literal_str(node.args[0]), literal_str(node.args[1])
                if name and val is not None:
                    self.param_defaults[name] = val
        # Second pass: `topic = self.get_parameter("x").value`, `self.t = ROS2Topics.X.value`.
        # Needs the tables above, so it cannot run in the same walk.
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and literal_str(node.value) is None:
                val = self.resolve(node.value)
                if val is None:
                    continue
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.consts[t.id] = val
                    elif isinstance(t, ast.Attribute) and attr_path(t):
                        self.attr_consts[attr_path(t)] = val

    def from_config(self, key: str) -> str | None:
        """A value read from config: our YAML first, then the declare_parameter default.
        Ambiguous keys (two different values) resolve to nothing rather than a guess."""
        vals = self.config.get(key, set())
        if len(vals) == 1:
            return next(iter(vals))
        return self.param_defaults.get(key)

    def resolve(self, node: ast.AST | None) -> str | None:
        """Best-effort: literal -> constant -> class attribute -> give up."""
        if node is None:
            return None
        lit = literal_str(node)
        if lit is not None:
            return lit
        if isinstance(node, ast.Name):
            return self.consts.get(node.id)
        if isinstance(node, ast.Attribute):
            dotted = attr_path(node)
            if dotted:
                if dotted in self.attr_consts:
                    return self.attr_consts[dotted]
                # `ROS2Topics.AUDIO_PROMPT.value` -> try last two segments
                parts = dotted.split(".")
                for i in range(len(parts)):
                    cand = ".".join(parts[i:])
                    if cand in self.attr_consts:
                        return self.attr_consts[cand]
                # An enum built from config at import time (src/config/ros2.py):
                # `ROS2Topics.RGB_CAMERA_RAW.value` -> YAML key `rgb_camera_raw`
                if len(parts) >= 3 and parts[-1] == "value":
                    return self.from_config(parts[-2].lower())
        # `self.get_parameter("x").value`, `.get_parameter_value().string_value`, ...
        while isinstance(node, (ast.Attribute, ast.Call)):
            if isinstance(node, ast.Call) and _fn_name(node) in ("get_parameter", "declare_parameter") \
                    and node.args:
                name = literal_str(node.args[0])
                return self.from_config(name) if name else None
            node = node.func if isinstance(node, ast.Call) else node.value
        return None

    def resolve_type(self, node: ast.AST | None) -> str:
        if isinstance(node, ast.Name):
            return self.type_imports.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            dotted = attr_path(node) or "?"
            return self.type_imports.get(dotted.split(".")[-1], dotted)
        return "?"

    # -- the calls we care about ------------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func.attr if isinstance(node.func, ast.Attribute) else (
            node.func.id if isinstance(node.func, ast.Name) else None)

        if fn in ("create_publisher", "create_subscription") and len(node.args) >= 2:
            topic = self.resolve(node.args[1])
            mtype = self.resolve_type(node.args[0])
            if topic and topic.startswith("/"):
                direction = "publishers" if fn == "create_publisher" else "subscribers"
                self._topic(topic, mtype, direction, node.lineno)

        elif fn in ("declare_parameter", "get_parameter", "declare_parameter_or") and node.args:
            name = self.resolve(node.args[0])
            if name:
                self.out["params"][name].append(f"{self.loc}:{node.lineno}")

        elif fn in ("lookup_transform", "lookupTransform", "can_transform") and len(node.args) >= 2:
            for a in node.args[:2]:
                f = self.resolve(a)
                if f:
                    self.out["frames"][f].append(f"{self.loc}:{node.lineno}")

        # src/services/ros/ros_publisher.py: ROSPublisher(node_name, MsgType, topic, ...)
        elif fn == "ROSPublisher" and len(node.args) >= 3:
            topic = self.resolve(node.args[2])
            if topic and topic.startswith("/"):
                self._topic(topic, self.resolve_type(node.args[1]), "publishers", node.lineno)

        # message_filters.Subscriber(node, MsgType, "/topic")
        elif fn == "Subscriber" and len(node.args) >= 3:
            topic = self.resolve(node.args[2])
            if topic and topic.startswith("/"):
                self._topic(topic, self.resolve_type(node.args[1]), "subscribers", node.lineno)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # header.frame_id = "base_link"
        for t in node.targets:
            if isinstance(t, ast.Attribute) and t.attr == "frame_id":
                v = self.resolve(node.value)
                if v:
                    self.out["frames"][v].append(f"{self.loc}:{node.lineno}")
        self.generic_visit(node)

    def _topic(self, topic: str, mtype: str, direction: str, line: int) -> None:
        e = self.out["topics"][topic]
        e["types"].add(mtype)
        e[direction].append(f"{self.loc}:{line}")


def _fn_name(node: ast.Call) -> str | None:
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)


def literal_str(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    # simple "a" + "b" concatenation
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        l, r = literal_str(node.left), literal_str(node.right)
        if l is not None and r is not None:
            return l + r
    return None


def attr_path(node: ast.AST) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


# --------------------------------------------------------------------------
# C++ extraction (regex -- no compiler available, and this is enough)
# --------------------------------------------------------------------------

CPP_PUB = re.compile(r'create_publisher\s*<\s*([\w:]+)\s*>\s*\(\s*"([^"]+)"')
CPP_SUB = re.compile(r'create_subscription\s*<\s*([\w:]+)\s*>\s*\(\s*"([^"]+)"')
CPP_MF_SUB = re.compile(r'message_filters::Subscriber\s*<\s*([\w:]+)\s*>[^;]*?"([^"]+)"')
CPP_FRAME = re.compile(r'frame_id\s*=\s*"([^"]+)"')
CPP_TF = re.compile(r'(?:lookupTransform|canTransform)\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"')
CPP_TF_TARGET = re.compile(r'\.transform\s*\([^,]+,\s*"([^"]+)"')
CPP_PARAM = re.compile(r'declare_parameter\s*(?:<[^>]*>)?\s*\(\s*"([^"]+)"')


def cpp_type(t: str) -> str:
    # sensor_msgs::msg::Image -> sensor_msgs/Image
    parts = [p for p in t.split("::") if p not in ("msg", "srv", "action")]
    return "/".join(parts) if len(parts) > 1 else t


def extract_cpp(path: Path, src: str, out: dict) -> None:
    loc = rel(path)
    lines = src.splitlines()

    def line_of(pos: int) -> int:
        return src.count("\n", 0, pos) + 1

    for rx, direction in ((CPP_PUB, "publishers"), (CPP_SUB, "subscribers"), (CPP_MF_SUB, "subscribers")):
        for m in rx.finditer(src):
            topic = m.group(2)
            if not topic.startswith("/"):
                continue
            e = out["topics"][topic]
            e["types"].add(cpp_type(m.group(1)))
            e[direction].append(f"{loc}:{line_of(m.start())}")

    for m in CPP_FRAME.finditer(src):
        out["frames"][m.group(1)].append(f"{loc}:{line_of(m.start())}")
    for m in CPP_TF.finditer(src):
        for g in (1, 2):
            out["frames"][m.group(g)].append(f"{loc}:{line_of(m.start())}")
    for m in CPP_TF_TARGET.finditer(src):
        out["frames"][m.group(1)].append(f"{loc}:{line_of(m.start())}")
    for m in CPP_PARAM.finditer(src):
        out["params"][m.group(1)].append(f"{loc}:{line_of(m.start())}")


# --------------------------------------------------------------------------
# Launch files (they are Python, so AST works -- no ROS import needed)
# --------------------------------------------------------------------------

def extract_launch(path: Path, src: str, out: dict) -> None:
    loc = rel(path)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        out["parse_errors"].append(f"{loc}: {e}")
        return

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else None)
        kw = {k.arg: k.value for k in node.keywords if k.arg}

        if fname == "Node":
            pkg = literal_str(kw.get("package")) or "?"
            exe = literal_str(kw.get("executable")) or "?"
            name = literal_str(kw.get("name")) or ""
            entry = {"package": pkg, "executable": exe, "name": name, "remappings": [], "from": loc}

            remaps = kw.get("remappings")
            if isinstance(remaps, (ast.List, ast.Tuple)):
                for item in remaps.elts:
                    if isinstance(item, (ast.Tuple, ast.List)) and len(item.elts) == 2:
                        a, b = literal_str(item.elts[0]), literal_str(item.elts[1])
                        if a and b:
                            entry["remappings"].append([a, b])
            out["launch_nodes"].append(entry)

            # static_transform_publisher encodes the TF tree in its argv
            if exe == "static_transform_publisher":
                args = kw.get("arguments")
                if isinstance(args, (ast.List, ast.Tuple)):
                    vals = [v for v in (literal_str(e) for e in args.elts) if v is not None]
                    nums = [v for v in vals if re.fullmatch(r"-?[\d.]+", v)]
                    parent = child = None
                    if "--frame-id" in vals:
                        i = vals.index("--frame-id")
                        parent = vals[i + 1] if i + 1 < len(vals) else None
                    if "--child-frame-id" in vals:
                        i = vals.index("--child-frame-id")
                        child = vals[i + 1] if i + 1 < len(vals) else None
                    if parent is None or child is None:
                        named = [v for v in vals
                                 if not re.fullmatch(r"-?[\d.]+", v) and not v.startswith("-")]
                        if len(named) >= 2:
                            parent, child = named[-2], named[-1]
                    if parent and child and "${" not in parent and "${" not in child:
                        out["static_tf"].append({
                            "parent": parent, "child": child, "xyz_rpy": nums, "from": loc,
                        })
                        for f in (parent, child):
                            out["frames"][f].append(f"{loc}(static_tf)")

        elif fname in ("IncludeLaunchDescription", "PythonLaunchDescriptionSource"):
            for m in re.finditer(r"'([\w./]+\.launch\.py)'|\"([\w./]+\.launch\.py)\"", ast.unparse(node)):
                out["launch_includes"].append({"target": m.group(1) or m.group(2), "from": loc})

        elif fname == "FindPackageShare" and node.args:
            p = literal_str(node.args[0])
            if p:
                out["package_deps"].add(p)


# --------------------------------------------------------------------------
# URDF / xacro (link + joint names ARE the TF frame names)
# --------------------------------------------------------------------------

URDF_LINK = re.compile(r'<link\s+name\s*=\s*"([^"]+)"')
URDF_JOINT = re.compile(r'<joint\s+name\s*=\s*"([^"]+)"')
URDF_PARENT = re.compile(r'<parent\s+link\s*=\s*"([^"]+)"')
URDF_CHILD = re.compile(r'<child\s+link\s*=\s*"([^"]+)"')


def extract_urdf(path: Path, src: str, out: dict) -> None:
    loc = rel(path)
    for rx in (URDF_LINK, URDF_PARENT, URDF_CHILD):
        for m in rx.finditer(src):
            name = m.group(1)
            if "${" not in name:  # skip unexpanded xacro params
                out["frames"][name].append(f"{loc}(urdf)")


# --------------------------------------------------------------------------
# YAML (tiny indent-aware scalar reader -- pyyaml is not installed and this
# only needs to handle config/param files, not arbitrary YAML)
# --------------------------------------------------------------------------

YAML_KV = re.compile(r'^(\s*)([\w./~-]+)\s*:\s*(.*)$')


def extract_yaml(path: Path, src: str, out: dict) -> None:
    loc = rel(path)
    in_ros_params = False
    ros_params_indent = 0
    for i, line in enumerate(src.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = YAML_KV.match(line)
        if not m:
            continue
        indent, key, val = len(m.group(1)), m.group(2), m.group(3).strip()
        val = val.split("#")[0].strip().strip('"').strip("'")

        if key == "ros__parameters":
            in_ros_params, ros_params_indent = True, indent
            continue
        if in_ros_params and indent <= ros_params_indent and key != "ros__parameters":
            in_ros_params = False

        if in_ros_params and val:
            out["params"][key].append(f"{loc}:{i}")
        if val.startswith("/") and not val.startswith("//") and " " not in val:
            if re.fullmatch(r"/[\w/]+", val):
                out["topics"][val]["types"].add("?")
                out["topics"][val]["yaml_refs"].append(f"{loc}:{i}")
        if key in ("frame_id", "robot_base_frame", "global_frame", "odom_frame", "map_frame",
                   "base_frame", "odom_frame_id", "base_frame_id") and val:
            out["frames"][val].append(f"{loc}:{i}")


# --------------------------------------------------------------------------
# Absolute paths -- the 2.5 blocker, tracked so the fix is verifiable
# --------------------------------------------------------------------------

ABS_PATH = re.compile(r'(?<![\w/$])((?:~|/home|/Users|/opt|/mnt|/media|/srv)/[\w./+@~-]{2,})')
# vendor scripts already parameterise on $USERNAME -- not a portability bug
VENDOR_PATH_OK = re.compile(r'/home/\$\{?USERNAME|/home/\$\{?USER\b')


def extract_paths(path: Path, src: str, out: dict) -> None:
    # The bench's own source contains path patterns by definition; scanning it
    # would report the detector as a defect.
    if rel(path).startswith("bench/"):
        return
    loc = rel(path)
    for i, line in enumerate(src.splitlines(), 1):
        if VENDOR_PATH_OK.search(line):
            continue
        for m in ABS_PATH.finditer(line):
            p = m.group(1).rstrip(".,;:")
            if p.startswith("/opt/ros"):   # legitimate, every ROS install has it
                continue
            if len(p.split("/")) < 3:      # bare "/home/x" prefixes, not real paths
                continue
            out["abs_paths"][p].append(f"{loc}:{i}")


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def new_bucket() -> dict:
    return {
        "topics": defaultdict(lambda: {"types": set(), "publishers": [], "subscribers": [], "yaml_refs": []}),
        "frames": defaultdict(list),
        "params": defaultdict(list),
        "abs_paths": defaultdict(list),
        "launch_nodes": [],
        "launch_includes": [],
        "static_tf": [],
        "package_deps": set(),
        "parse_errors": [],
        "const_defs": defaultdict(lambda: defaultdict(list)),
    }


def merge(dst: dict, src: dict) -> None:
    for t, e in src["topics"].items():
        d = dst["topics"][t]
        d["types"] |= e["types"]
        for k in ("publishers", "subscribers", "yaml_refs"):
            d[k].extend(e[k])
    for k in ("frames", "params", "abs_paths"):
        for name, locs in src[k].items():
            dst[k][name].extend(locs)
    for k in ("launch_nodes", "launch_includes", "static_tf", "parse_errors"):
        dst[k].extend(src[k])
    dst["package_deps"] |= src["package_deps"]


def collect_const_defs(path: Path, src: str, out: dict) -> None:
    """Track SCREAMING_CASE string/number constants so duplicate definitions
    that have drifted apart (docs 8.10) show up mechanically."""
    loc = rel(path)
    for i, line in enumerate(src.splitlines(), 1):
        m = re.match(r'^\s*([A-Z][A-Z0-9_]{3,})\s*(?::\s*[\w\[\], .]+)?=\s*(.+?)\s*(?:#.*)?$', line)
        if m:
            name, val = m.group(1), m.group(2).rstrip(",")
            if len(val) < 120:
                out["const_defs"][name][val].append(f"{loc}:{i}")


def config_values() -> dict:
    """key -> {values} across our own YAML files, so code that reads a topic from
    config (NEXT_STEPS 2.15) stays visible. Vendor YAML is left out: its keys
    would make ours ambiguous."""
    cfg: dict[str, set] = defaultdict(set)
    for p in walk(".yaml", ".yml"):
        if not owned(rel(p)):
            continue
        for line in p.read_text(errors="replace").splitlines():
            m = YAML_KV.match(line)
            if m and not line.lstrip().startswith("#"):
                val = m.group(3).split("#")[0].strip().strip('"').strip("'")
                if val:
                    cfg[m.group(2)].add(val)
    return cfg


def extract_all() -> dict:
    out = new_bucket()
    cfg = config_values()

    for p in walk(".py"):
        src = p.read_text(errors="replace")
        collect_const_defs(p, src, out)
        extract_paths(p, src, out)
        if p.name.endswith(".launch.py"):
            extract_launch(p, src, out)
            continue
        try:
            ex = PyExtractor(p, src, cfg)
            ex.visit(ast.parse(src))
            merge(out, ex.out)
        except SyntaxError as e:
            out["parse_errors"].append(f"{rel(p)}: {e}")

    for p in walk(".cpp", ".hpp", ".h", ".cc"):
        src = p.read_text(errors="replace")
        extract_cpp(p, src, out)
        extract_paths(p, src, out)

    for p in walk(".urdf", ".xacro"):
        extract_urdf(p, p.read_text(errors="replace"), out)

    for p in walk(".yaml", ".yml"):
        src = p.read_text(errors="replace")
        extract_yaml(p, src, out)
        extract_paths(p, src, out)

    for p in walk(".sh", ".bash"):
        extract_paths(p, p.read_text(errors="replace"), out)

    return out


def to_json(out: dict) -> dict:
    topics = {}
    for t, e in sorted(out["topics"].items()):
        topics[t] = {
            "types": sorted(x for x in e["types"] if x != "?") or ["?"],
            "n_publishers": len(e["publishers"]),
            "n_subscribers": len(e["subscribers"]),
            "publishers": sorted(e["publishers"]),
            "subscribers": sorted(e["subscribers"]),
            "yaml_refs": sorted(e["yaml_refs"]),
            "owned": any_owned(e["publishers"] + e["subscribers"] + e["yaml_refs"]),
        }
    dup_consts = {
        n: {v: sorted(locs) for v, locs in vals.items()}
        for n, vals in sorted(out["const_defs"].items())
        if len(vals) > 1
    }
    return {
        "schema": 1,
        "git": git_describe(),
        "topics": topics,
        "frames": {k: sorted(v) for k, v in sorted(out["frames"].items())},
        "params": {k: sorted(v) for k, v in sorted(out["params"].items())},
        "abs_paths": {k: sorted(v) for k, v in sorted(out["abs_paths"].items())},
        "static_tf": sorted(out["static_tf"], key=lambda d: (d["parent"], d["child"], d["from"])),
        "launch_nodes": sorted(out["launch_nodes"], key=lambda d: (d["from"], d["package"], d["executable"])),
        "launch_includes": sorted(out["launch_includes"], key=lambda d: (d["from"], d["target"])),
        "package_deps": sorted(out["package_deps"]),
        "divergent_constants": dup_consts,
        "parse_errors": sorted(out["parse_errors"]),
    }


def git_describe() -> str:
    try:
        sha = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=5).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------
# check: contract-keyed diff. File moves are informational, not failures.
# --------------------------------------------------------------------------

def check(cur: dict, old: dict) -> int:
    errs: list[str] = []
    warns: list[str] = []
    info: list[str] = []

    ct, ot = cur["topics"], old["topics"]
    for t in sorted(set(ot) - set(ct)):
        errs.append(f"TOPIC REMOVED   {t}  (was: {', '.join(ot[t]['types'])})")
    # A brand-new topic with endpoints on only one side is the signature of a
    # rename applied to some call sites but not all -- the single most likely
    # way this refactor breaks the robot, and it is silent at build time.
    for t in sorted(set(ct) - set(ot)):
        c = ct[t]
        if c["n_publishers"] and not c["n_subscribers"]:
            errs.append(f"ORPHAN ADDED    {t}  publishers but no subscriber "
                        f"-- partial rename? ({', '.join(c['publishers'])})")
        elif c["n_subscribers"] and not c["n_publishers"]:
            errs.append(f"ORPHAN ADDED    {t}  subscribers but no publisher "
                        f"-- partial rename? ({', '.join(c['subscribers'])})")
        else:
            info.append(f"topic added     {t}  ({', '.join(c['types'])})")

    for t in sorted(set(ct) & set(ot)):
        c, o = ct[t], ot[t]
        if c["types"] != o["types"]:
            errs.append(f"TYPE CHANGED    {t}  {o['types']} -> {c['types']}")
        # Any *drop* in endpoints means a node stopped talking to this topic.
        # Deliberate removals are real, but they must be re-baselined explicitly
        # rather than passing silently.
        if c["n_publishers"] < o["n_publishers"]:
            lost = sorted(set(o["publishers"]) - set(c["publishers"]))
            errs.append(f"LOST PUBLISHER  {t}  {o['n_publishers']} -> {c['n_publishers']}"
                        + (f"  (was: {', '.join(lost)})" if lost else ""))
        if c["n_subscribers"] < o["n_subscribers"]:
            lost = sorted(set(o["subscribers"]) - set(c["subscribers"]))
            errs.append(f"LOST SUBSCRIBER {t}  {o['n_subscribers']} -> {c['n_subscribers']}"
                        + (f"  (was: {', '.join(lost)})" if lost else ""))
        if c["n_publishers"] > o["n_publishers"] or c["n_subscribers"] > o["n_subscribers"]:
            warns.append(f"endpoints added {t}  pub {o['n_publishers']}->{c['n_publishers']}"
                         f"  sub {o['n_subscribers']}->{c['n_subscribers']}")
        if sorted(c["publishers"] + c["subscribers"]) != sorted(o["publishers"] + o["subscribers"]):
            info.append(f"moved           {t}")

    for key, label in (("frames", "FRAME"), ("params", "PARAM")):
        c, o = cur[key], old[key]
        for n in sorted(set(o) - set(c)):
            errs.append(f"{label} REMOVED {'':<3}{n}")
        for n in sorted(set(c) - set(o)):
            info.append(f"{label.lower()} added   {n}")

    co = {(d["parent"], d["child"]) for d in cur["static_tf"]}
    oo = {(d["parent"], d["child"]) for d in old["static_tf"]}
    for p, ch in sorted(oo - co):
        errs.append(f"STATIC TF GONE  {p} -> {ch}")
    for p, ch in sorted(co - oo):
        info.append(f"static tf added {p} -> {ch}")

    n_old_paths, n_new_paths = len(old["abs_paths"]), len(cur["abs_paths"])
    if n_new_paths > n_old_paths:
        errs.append(f"ABS PATHS UP    {n_old_paths} -> {n_new_paths} hardcoded absolute paths")
    elif n_new_paths < n_old_paths:
        info.append(f"abs paths down  {n_old_paths} -> {n_new_paths}  (progress on NEXT_STEPS 2.5)")

    if cur["parse_errors"]:
        for e in cur["parse_errors"]:
            errs.append(f"PARSE ERROR     {e}")

    for label, items in (("REGRESSIONS", errs), ("warnings", warns), ("info", info)):
        if items:
            print(f"\n=== {label} ({len(items)}) ===")
            for x in items:
                print("  " + x)

    print(f"\nbaseline {old.get('git')}  ->  current {cur.get('git')}")
    if errs:
        print(f"\nFAIL: {len(errs)} contract regression(s).")
        print("If a change was deliberate, re-baseline with:  python3 bench/contracts.py snapshot")
        return 1
    print(f"\nPASS: no contract regressions. ({len(warns)} warnings, {len(info)} informational)")
    return 0


# --------------------------------------------------------------------------
# report: inventory + orphan analysis (finds bugs, not just regressions)
# --------------------------------------------------------------------------

def report(cur: dict, show_all: bool = False) -> int:
    t = cur["topics"]

    def keep(k: str) -> bool:
        return show_all or t[k].get("owned", True)

    dangling_pub = [k for k, v in t.items()
                    if v["n_publishers"] and not v["n_subscribers"] and not v["yaml_refs"] and keep(k)]
    dangling_sub = [k for k, v in t.items()
                    if v["n_subscribers"] and not v["n_publishers"] and not v["yaml_refs"] and keep(k)]
    owned_topics = [k for k in t if t[k].get("owned", True)]

    scope = "ALL CODE (incl. vendor)" if show_all else "CODE WE OWN (use --all for vendor too)"
    print("=" * 78)
    print(f"CONTRACT INVENTORY  @ {cur['git']}")
    print(f"scope: {scope}")
    print("=" * 78)
    print(f"  topics            {len(owned_topics):>4} ours / {len(t):>4} total")
    print(f"  TF frames         {len(cur['frames']):>4}")
    print(f"  ROS params        {len(cur['params']):>4}")
    print(f"  launch nodes      {len(cur['launch_nodes']):>4}")
    print(f"  static TF         {len(cur['static_tf']):>4}")
    print(f"  abs paths         {len(cur['abs_paths']):>4}   <- NEXT_STEPS 2.5 blocker")
    print(f"  divergent consts  {len(cur['divergent_constants']):>4}   <- ORIENTATION 8.10")

    def dump(title: str, keys, why: str) -> None:
        print(f"\n--- {title} ({len(keys)}) ---")
        print(f"    {why}")
        for k in sorted(keys):
            e = t[k]
            print(f"  {k:<44} {', '.join(e['types'])}")
            for loc in e["publishers"] + e["subscribers"]:
                tag = "pub" if loc in e["publishers"] else "sub"
                print(f"      {tag}: {loc}")

    dump("PUBLISHED, NOBODY LISTENS", dangling_pub,
         "dead output, a name that drifted, or an external consumer (RViz, a tool)")
    dump("SUBSCRIBED, NOBODY PUBLISHES", dangling_sub,
         "an external producer (vendor driver, OpenVINS) -- or a broken link")

    if cur["divergent_constants"]:
        print(f"\n--- CONSTANTS DEFINED MORE THAN ONCE WITH DIFFERENT VALUES ---")
        print("    the ORIENTATION 8.10 failure mode: edit one copy, miss the others")
        for name, vals in cur["divergent_constants"].items():
            print(f"  {name}")
            for v, locs in vals.items():
                extra = f"  (+{len(locs)-1} more)" if len(locs) > 1 else ""
                print(f"      = {v:<34} {locs[0]}{extra}")

    defined = {d["child"] for d in cur["static_tf"]} | {d["parent"] for d in cur["static_tf"]}
    for f, locs in cur["frames"].items():
        if any("(urdf)" in l for l in locs):
            defined.add(f)
    undefined = [f for f in sorted(set(cur["frames"]) - defined)
                 if f and not f.startswith("/") and "${" not in f
                 and (show_all or any_owned(cur["frames"][f]))]
    print(f"\n--- FRAMES REFERENCED BUT NEVER DEFINED IN A URDF OR STATIC TF ({len(undefined)}) ---")
    print("    every TF lookup against these fails at runtime, silently")
    for f in undefined:
        print(f"  {f:<40} {cur['frames'][f][0]}")

    print(f"\n--- HARDCODED ABSOLUTE PATHS ({len(cur['abs_paths'])}) ---")
    print("    NEXT_STEPS 2.5: nothing runs on a fresh clone until these are derived")
    for path, locs in sorted(cur["abs_paths"].items()):
        print(f"  {path}")
        for loc in locs:
            print(f"      {loc}")

    print(f"\n--- STATIC TF TREE ({len(cur['static_tf'])}) ---")
    for d in cur["static_tf"]:
        print(f"  {d['parent']:<20} -> {d['child']:<26} {d['from']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["extract", "snapshot", "check", "report"])
    ap.add_argument("--golden", default=str(GOLDEN))
    ap.add_argument("--all", action="store_true", help="include vendor code in report")
    a = ap.parse_args()

    cur = to_json(extract_all())
    gp = Path(a.golden)

    if a.cmd == "extract":
        json.dump(cur, sys.stdout, indent=2, sort_keys=True)
        print()
        return 0
    if a.cmd == "snapshot":
        gp.parent.mkdir(parents=True, exist_ok=True)
        gp.write_text(json.dumps(cur, indent=2, sort_keys=True) + "\n")
        print(f"wrote {rel(gp)}  @ {cur['git']}")
        print(f"  {len(cur['topics'])} topics, {len(cur['frames'])} frames, "
              f"{len(cur['params'])} params, {len(cur['abs_paths'])} abs paths")
        return 0
    if a.cmd == "report":
        return report(cur, show_all=a.all)
    if not gp.exists():
        print(f"no baseline at {rel(gp)} -- run: python3 bench/contracts.py snapshot", file=sys.stderr)
        return 2
    return check(cur, json.loads(gp.read_text()))


if __name__ == "__main__":
    sys.exit(main())
