"""Can this interpreter run AnyGrasp? (TESTBENCH_PLAN W5)

Stdlib only; drives the target interpreter in subprocesses so one broken import cannot hide
the others. Stage 1 imports every dependency separately. Stage 2 runs the SDK's own
grasp_detection/demo.py on its example frame, in a scratch folder (log/anygrasp_probe/) that
links in exactly what the robot's node uses: the perception folder's gsnet / lib_cxx builds,
its license/ folder and log/checkpoint_detection.tar. Headless (no --debug), GPU only.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PERCEPTION = REPO / "ros2_robot_ws/src/rm_mtc/src/perception"
SDK_DET = REPO / "grasp_module/src/anygrasp_sdk/grasp_detection"
SCRATCH = REPO / "log/anygrasp_probe"
CANDIDATES = [REPO / "envs/anygrasp/.venv/bin/python", REPO / "log/w5/venv/bin/python",
              REPO / ".venv/bin/python"]

# module, what it is, code printed on success
IMPORTS = [
    ("torch", "PyTorch", "import torch;print(torch.__version__,'cuda',torch.version.cuda,'gpu',torch.cuda.is_available())"),
    ("numpy", "numpy (AnyGrasp pins 1.21.2; the project env has 2.x)", "import numpy;print(numpy.__version__)"),
    ("MinkowskiEngine", "sparse-conv CUDA extension, built by hand", "import MinkowskiEngine as ME;print(ME.__version__)"),
    ("pointnet2", "AnyGrasp's CUDA op (grasp_module/src/anygrasp_sdk/pointnet2)", "import pointnet2._ext;print('ok')"),
    ("open3d", "point clouds (pinned 0.18.0)", "import open3d;print(open3d.__version__)"),
    ("graspnetAPI", "GraspGroup data structure", "import graspnetAPI;print('ok')"),
    ("sklearn", "scikit-learn (pinned 1.3.2)", "import sklearn;print(sklearn.__version__)"),
    ("scipy", "scipy (pinned 1.10.1)", "import scipy;print(scipy.__version__)"),
    ("PIL", "Pillow", "import PIL;print(PIL.__version__)"),
    ("lib_cxx", "vendor licence binary (links libcrypto.so.1.1)", "import lib_cxx;print('ok')"),
    ("gsnet", "vendor AnyGrasp binary", "import gsnet;print('ok')"),
]


def pick_python(argv):
    if len(argv) > 1:
        return Path(argv[1])
    for c in CANDIDATES:
        if c.exists():
            return c
    return None


def last_line(text):
    lines = [l for l in text.strip().splitlines() if l.strip()]
    return lines[-1][:150] if lines else ""


def prepare_scratch():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    (SCRATCH / "log").mkdir(parents=True)
    shutil.copy(SDK_DET / "demo.py", SCRATCH / "demo.py")
    for so in PERCEPTION.glob("*.so"):
        (SCRATCH / so.name).symlink_to(so)
    (SCRATCH / "license").symlink_to(PERCEPTION / "license")
    (SCRATCH / "example_data").symlink_to(SDK_DET / "example_data")
    (SCRATCH / "log/checkpoint_detection.tar").symlink_to(PERCEPTION / "log/checkpoint_detection.tar")


def main(argv):
    py = pick_python(argv)
    if py is None or not py.exists():
        print("SKIP: no interpreter found -- pass one, or build an env (W5)")
        return 3
    ckpt = PERCEPTION / "log/checkpoint_detection.tar"
    if not ckpt.exists():
        print(f"SKIP: {ckpt.relative_to(REPO)} missing (gitignored; see dion_docs/ASSETS.md)")
        return 3
    prepare_scratch()
    env = dict(os.environ, PYTHONNOUSERSITE="")   # never set it (ORIENTATION 8.5); empty = unset
    env.pop("PYTHONNOUSERSITE")
    print(f"interpreter: {py}\nscratch:     {SCRATCH.relative_to(REPO)}\n\nStage 1 -- imports, each in its own process")
    failed = []
    for mod, what, code in IMPORTS:
        r = subprocess.run([str(py), "-c", code], cwd=SCRATCH, env=env,
                           capture_output=True, text=True, timeout=180)
        ok = r.returncode == 0
        if not ok:
            failed.append(mod)
        detail = last_line(r.stdout) if ok else last_line(r.stderr or r.stdout)
        print(f"  [{'PASS' if ok else 'FAIL'}] {mod:16s} {detail}")
        if not ok:
            print(f"         ({what})")

    print("\nStage 2 -- SDK detection demo on its example frame")
    if {"torch", "numpy", "gsnet"} & set(failed):
        print("  [SKIP] demo: torch, numpy or gsnet does not import -- nothing to run")
        verdict = 1
    else:
        try:
            r = subprocess.run([str(py), "demo.py", "--checkpoint_path", "log/checkpoint_detection.tar",
                                "--top_down_grasp"], cwd=SCRATCH, env=env,
                               capture_output=True, text=True, timeout=900)
            out = r.stdout + r.stderr
            rc = r.returncode
        except subprocess.TimeoutExpired as e:
            out, rc = (e.stdout or "") + (e.stderr or "") if isinstance(e.stdout, str) else "", 124
        (SCRATCH / "demo_output.txt").write_text(out)
        lic = [l.strip() for l in out.splitlines() if re.search(r"licen[cs]e", l, re.I)]
        score = next((l.strip() for l in out.splitlines() if l.startswith("grasp score:")), None)
        for l in lic[:4]:
            print(f"  licence line: {l[:140]}")
        ok = rc == 0 and score is not None
        print(f"  [{'PASS' if ok else 'FAIL'}] demo exit {rc}: " + (score if score else last_line(out)))
        print(f"  full output: {(SCRATCH / 'demo_output.txt').relative_to(REPO)}")
        verdict = 0 if ok else 1

    print("\nRESULT:", "PASS -- this interpreter runs AnyGrasp" if verdict == 0
          else f"FAIL -- missing or broken: {', '.join(failed) or 'demo run'}")
    return verdict


if __name__ == "__main__":
    sys.exit(main(sys.argv))
