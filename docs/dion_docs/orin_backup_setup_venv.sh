#!/usr/bin/env bash
# Builds the repo's .venv on a Jetson Orin, for the segmentation service (T2.1).
# The Orin is the backup machine for when the lab box is down.
#
#   ./docs/dion_docs/orin_backup_setup_venv.sh
#
# Why not `uv sync`: on the Orin's ARM processor several locked packages have no build
# (projectaria-client-sdk, decord), and PyPI's torch is not built for Jetson. So this installs
# only what the segmentation service needs, with NVIDIA's Jetson torch. Running `uv sync` here
# would replace this .venv with one that cannot use the GPU.
#
# Needs first, once, with sudo: JetPack (CUDA, cuDNN) and ROS 2 Humble.
# The venv sees the system packages, so ROS's Python (rclpy, message types) works inside it.
# Exit: 0 ready and the GPU works, 1 a step failed.
set -euo pipefail
REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
# NVIDIA's Jetson wheels for JetPack 6 with CUDA 12.6. Override if JetPack changes.
JETSON_INDEX="${JETSON_INDEX:-https://pypi.jetson-ai-lab.io/jp6/cu126}"
SAM3_GIT="git+https://github.com/Axemortal/rcp-sam3.git@main"   # same fork as pyproject.toml

[ -f /etc/nv_tegra_release ] || { echo "FAIL: not a Jetson. Use 'uv sync' on other machines."; exit 1; }
[ -f /opt/ros/humble/setup.bash ] || { echo "FAIL: no ROS 2 Humble. Install it first."; exit 1; }

[ -x "$REPO/.venv/bin/python" ] || python3 -m venv --system-site-packages "$REPO/.venv"
PIP=("$REPO/.venv/bin/python" -m pip install --extra-index-url "$JETSON_INDEX")

"${PIP[@]}" --upgrade pip
# torch first, from the Jetson index, so nothing below pulls PyPI's build in its place
# Same torch and triton versions as uv.lock on the box. torchvision 0.25 is paired with torch 2.10.
# SAM 3 imports triton (sam3/model/edt.py) even for still images.
"${PIP[@]}" --index-url "$JETSON_INDEX" torch==2.10.0 torchvision==0.25.0 triton==3.6.0
# The Jetson torch build links libcudss (NVIDIA's sparse solver), which JetPack does not ship.
# Put NVIDIA's Jetson build of it in torch's own lib/ folder, which torch searches first.
CUDSS_URL="https://developer.download.nvidia.com/compute/cudss/redist/libcudss/linux-aarch64/libcudss-linux-aarch64-0.6.0.5_cuda12-archive.tar.xz"
CUDSS_SHA256="e6f5d5122d735f9dbfd42c9eaba067a557a5613ee4a6001806935de11aff4b09"
TORCH_LIB="$("$REPO/.venv/bin/python" -c 'import importlib.util,os;print(os.path.join(os.path.dirname(importlib.util.find_spec("torch").origin),"lib"))')"
if [ ! -e "$TORCH_LIB/libcudss.so.0" ]; then
  tmp="$(mktemp -d)"
  curl -fsSL --retry 10 --retry-all-errors -C - "$CUDSS_URL" -o "$tmp/cudss.tar.xz"
  echo "$CUDSS_SHA256  $tmp/cudss.tar.xz" | sha256sum -c -
  tar -xJf "$tmp/cudss.tar.xz" -C "$tmp"
  cp -P "$tmp"/libcudss-*/lib/libcudss.so* "$TORCH_LIB/"
  rm -rf "$tmp"
fi
# SAM 3 without its decord dependency, which has no ARM build. SAM 3 still imports decord when it
# loads (sam3/train/data/sam3_image_dataset.py), so install decord2, a fork that provides the same
# `import decord` and has an ARM build. Only SAM 3's video code calls it.
"${PIP[@]}" --no-deps "$SAM3_GIT"
"${PIP[@]}" decord2==3.4.0
# Versions copied from uv.lock, so the Orin runs what the box runs. Update both together.
"${PIP[@]}" einops==0.8.2 ftfy==6.1.1 huggingface-hub==1.4.1 iopath==0.1.10 psutil==7.2.2 \
  pycocotools==2.0.11 regex==2026.1.15 timm==1.0.24 tqdm==4.67.3 typing-extensions==4.15.0 \
  numpy==2.2.6 opencv-python==4.13.0.92 scipy==1.15.3

"$REPO/.venv/bin/python" - <<'EOF'
import torch
assert torch.cuda.is_available(), "torch installed but cannot see the GPU"
print(f"torch {torch.__version__}, GPU: {torch.cuda.get_device_name(0)}")
from sam3 import build_sam3_image_model  # noqa: F401
print("sam3 imports")
EOF
echo "PASS: $REPO/.venv is ready for the segmentation service"
