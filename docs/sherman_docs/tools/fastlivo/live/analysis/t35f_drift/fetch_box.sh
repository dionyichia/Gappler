#!/bin/bash
# usage: fetch_box.sh [files in out/ ...]  -- copy results from the box (default: everything small)
D=$(cd "$(dirname "$0")" && pwd)
rsync -a -e "ssh -o HostKeyAlias=10.91.242.76 -o ConnectTimeout=15" --exclude 'map_*.npz' rcp2026@100.87.133.60:rcp-Gappler/log/t59-fastlivo/log/t35f-drift/out/ "$D/out/"
