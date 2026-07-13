#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMFYUI_DIR="$REPO_DIR/ComfyUI"
CUSTOM_NODES_DIR="$COMFYUI_DIR/custom_nodes"

mkdir -p "$CUSTOM_NODES_DIR"
cd "$CUSTOM_NODES_DIR"

echo "[Custom Nodes] Cài đặt IPAdapter-Plus..."
NODE="ComfyUI_IPAdapter_plus"
if [ ! -d "$NODE" ]; then
    git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git "$NODE"
else
    cd "$NODE" && git pull && cd ..
fi

echo "[Custom Nodes] Cài đặt Efficiency Nodes..."
NODE="efficiency-nodes-comfyui"
if [ ! -d "$NODE" ]; then
    git clone https://github.com/jags111/efficiency-nodes-comfyui.git "$NODE"
else
    cd "$NODE" && git pull && cd ..
fi

# Install requirements cho từng node
echo "[Custom Nodes] Cài pip requirements cho custom nodes..."
for node_dir in "$CUSTOM_NODES_DIR"/*/; do
    req_file="${node_dir}requirements.txt"
    if [ -f "$req_file" ]; then
        echo "  → Cài requirements cho $(basename "$node_dir")"
        "$REPO_DIR/venv/bin/pip" install -r "$req_file"
    fi
done

echo "[Custom Nodes] OK!"