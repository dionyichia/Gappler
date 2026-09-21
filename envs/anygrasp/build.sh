#!/usr/bin/env bash
# Build the AnyGrasp Python env from nothing: envs/anygrasp/.venv (TESTBENCH_PLAN W5).
#
# The env sits on top of the project env (.venv) through a .pth file, so it shares .venv's torch
# (CUDA build) and numpy 2 and adds only what AnyGrasp needs: MinkowskiEngine and pointnet2,
# compiled here from the repo's own copies, plus the pinned packages in requirements.txt.
# Recipe first run by hand on 2026-09-11: docs/bench-runs/2026-09-11-labbox-w5-anygrasp-env.txt
#
#   ./envs/anygrasp/build.sh          reuse what is already built, fill in the rest
#   ./envs/anygrasp/build.sh --clean  delete the env and build everything (about 20 min on the lab box)
#
# Re-running is cheap: MinkowskiEngine and pointnet2 are compiled only if they do not already import
# in envs/anygrasp/.venv, which is where they live once built. The package install always runs and
# takes seconds when nothing changed. Use --clean after changing torch, CUDA or the GPU.
#
# Needs: .venv built (`uv sync`), uv, the CUDA toolkit (nvcc), libopenblas-dev, python3.10-dev.
# No sudo, nothing outside this repo is written except uv's download cache.
# Every machine-specific path can be overridden from the environment:
#   CUDA_HOME             default /usr/local/cuda-12.8
#   TORCH_CUDA_ARCH_LIST  default: this machine's GPU, read from torch (8.9 on the lab box)
#   BLAS_INC, BLAS_LIB    default: Ubuntu's openblas-pthread folders
#   MAX_JOBS              parallel compile jobs, default 8
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$REPO/envs/anygrasp"
ENV="$HERE/.venv"
PROJECT_PY="$REPO/.venv/bin/python"
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-12.8}"
BLAS_INC="${BLAS_INC:-/usr/include/x86_64-linux-gnu/openblas-pthread}"
BLAS_LIB="${BLAS_LIB:-/usr/lib/x86_64-linux-gnu/openblas-pthread}"
export MAX_JOBS="${MAX_JOBS:-8}"

die() { echo "build.sh: $*" >&2; exit 1; }
case "${1:-}" in
  --clean) clean=1 ;;
  "")      clean=0 ;;
  *)       die "usage: $0 [--clean]" ;;
esac
[ -x "$PROJECT_PY" ]                || die "no project env at .venv -- run 'uv sync' first"
[ -x "$UV" ]                        || die "uv not found (set UV=/path/to/uv)"
[ -x "$CUDA_HOME/bin/nvcc" ]        || die "no nvcc in $CUDA_HOME/bin (set CUDA_HOME)"
[ -f "$BLAS_INC/cblas.h" ]          || die "no cblas.h in $BLAS_INC (apt install libopenblas-dev, or set BLAS_INC)"
"$PROJECT_PY" -c "import torch; assert torch.cuda.is_available()" 2>/dev/null \
                                    || die ".venv's torch cannot see CUDA"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-$("$PROJECT_PY" -c \
  "import torch; print('%d.%d' % torch.cuda.get_device_capability())")}"

[ "$clean" = 1 ] && rm -rf "$ENV"
if [ -x "$ENV/bin/python" ]; then
  echo "== reusing ${ENV#$REPO/} (--clean to start over)"
else
  echo "== fresh env at ${ENV#$REPO/} (CUDA_HOME=$CUDA_HOME, arch $TORCH_CUDA_ARCH_LIST)"
  UV_PYTHON_DOWNLOADS=never "$UV" venv -q "$ENV" --python "$PROJECT_PY"
fi
site() { "$1" -c "import sysconfig; print(sysconfig.get_paths()['purelib'])"; }
site "$PROJECT_PY" > "$(site "$ENV/bin/python")/_project_venv.pth"   # see .venv's packages
export PATH="$CUDA_HOME/bin:$ENV/bin:$PATH"

# uv does not count packages seen through the .pth as installed, so it installs its own copies.
# Pinning them to .venv's versions keeps the two envs identical where they overlap.
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
"$UV" pip freeze --python "$PROJECT_PY" > "$tmp/constraints.txt"
"$UV" pip install -q --python "$ENV/bin/python" ninja==1.13.2

# The two CUDA builds, each skipped if it already imports. Built from copies so the repo's source
# trees stay clean. torch is imported first: both extensions link against its libraries.
built() { "$ENV/bin/python" -c "import torch, $1" 2>/dev/null; }

if built MinkowskiEngine; then
  echo "== MinkowskiEngine already built, skipping"
else
  echo "== MinkowskiEngine (the long step)"
  cp -r "$REPO/grasp_module/dependencies/MinkowskiEngine" "$tmp/"
  (cd "$tmp/MinkowskiEngine" && python setup.py -q install --force_cuda --blas=openblas \
    --blas_include_dirs="$BLAS_INC" --blas_library_dirs="$BLAS_LIB")
fi

if built pointnet2._ext; then
  echo "== pointnet2 already built, skipping"
else
  echo "== pointnet2"
  cp -r "$REPO/grasp_module/src/anygrasp_sdk/pointnet2" "$tmp/"
  rm -rf "$tmp/pointnet2/build"               # the repo tracks a stale build folder
  (cd "$tmp/pointnet2" && python setup.py -q install)
fi

echo "== pinned packages"
"$UV" pip install -q --python "$ENV/bin/python" -c "$tmp/constraints.txt" -r "$HERE/requirements.txt"
"$UV" pip install -q --python "$ENV/bin/python" --no-deps graspnetAPI==1.2.10

echo "== check: imports and the SDK demo"
python3 "$REPO/bench/nodes/probe_anygrasp_env.py" "$ENV/bin/python"
